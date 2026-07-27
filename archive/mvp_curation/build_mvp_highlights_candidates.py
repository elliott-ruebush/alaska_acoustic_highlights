"""
Build ranked highlights candidates for the MVP curated launch set.

Filters the full catalog down to non-sensitive, non-restricted, cleanly-parsed
clips, deduplicates wav/mp3 pairs (prefers wav), scores rows by keyword hits
against a "greatest hits" wishlist plus a quality-modifier lexicon, then caps
each category to a manageable top-N so the resulting candidate set is in the low
hundreds -- reviewable by a human in one sitting -- rather than the full
~2,400-row clean-candidate pool. Pare the output further down to ~50-100
final picks by hand.

This is a starting point for manual curation, not a final list -- every row
should still be listened to and legally/scientifically vetted before publish.
"""
import argparse
import re
import sys
from typing import Any

import pandas as pd

CATALOG = "data/audio_clips_catalog.csv"
OUT = "archive/mvp_curation/mvp_highlights_candidates.csv"

# Per-category cap on the *ranked* pool, applied after scoring. Sized so the
# total candidate set lands in the low hundreds (~150 here) instead of thousands,
# while still giving a real choice of ~2-4x the eventual pick count per
# category. BIRD ID and MAMMAL REFERENCE get the most headroom since they're
# both large pools with genuine variety (many species / wolves+whales+bears);
# INSECTS/GENERAL are already small so the cap barely trims them.
DEFAULT_CATEGORY_CAPS = {
    "BIRD ID": 40,
    "MAMMAL REFERENCE": 40,
    "GEOPHONY": 30,
    "INSECTS": 20,
    "GENERAL": 15,
    "root": 4,
    "Alaska Sound Showcase pt. 2": 3,
}
DEFAULT_CAP = 20  # fallback for any category not listed above

MAMMAL_TYPE_CAPS = {
    "wolf": 12,
    "whale": 6,
    "bear": 6,
    "ungulate": 4,
    "squirrel/marmot": 4,
    "canid other": 2,
    "other": 3,
}

MAMMAL_REFERENCE_CATEGORY = "MAMMAL REFERENCE"

EXCLUDE_PATH_SUBSTRINGS = [
    "UNIDENTIFIED",
    "issues",
    "duff stuff",
    "censored",
    "FRONTCOUNTRY TAKEOFF CLIPS",
    "Ground Squirrel Alarms",  # rights-restricted to NPS interp use only
    "need editing",
    "further issues",
]

# Non-capturing groups to avoid pandas str.contains warning about match groups.
HEDGE_PATTERN = re.compile(
    r"\b(?:unknown|possibly|probable|unidentified|is this really|maybe|unsure|"
    r"perhaps|unk\d)\b",
    re.IGNORECASE,
)

WISHLIST_KEYWORDS = {
    "wolf": 10, "wolves": 10, "howl": 8,
    "whale": 10, "breach": 8,
    "surge": 9, "glacier": 7, "rumbl": 6,
    "rock slide": 8, "rockslide": 8, "avalanche": 8, "thunder": 6,
    "chorus": 6, "song": 3,
    "marmot": 6, "squirrel": 4, "grouse": 4,
    "bear": 7, "guttural": 5,
    "caribou": 6, "moose": 6, "dall": 5, "sheep": 4, "sesamoid": 4,
    "bleat": 4, "ungulate": 5,
    "pika": 4, "beaver": 4,
    "coyote": 5,
    "grasshopper": 4, "stridulat": 4, "wingbeat": 3,
    "waves": 4, "surf": 4, "creaking": 4, "ice bubbles": 5,
    "foghorn": 7, "reverberat": 4, "echo": 4,
}

# The ranger who labeled these clips applied a semi-systematic quality
# vocabulary while annotating (confirmed empirically via word-frequency
# analysis of free_text_description, not guessed). Word-boundary regex
# checks are ordered so specific phrases ("very clear", "no clipping")
# don't also double-trigger their weaker/opposite generic counterpart
# ("clear", "clipping"). "great"/"greater" are deliberately excluded --
# they're almost entirely species names (Great Grey Owl, Greater Yellowlegs),
# not quality remarks.
QUALITY_PATTERNS = [
    (re.compile(r"\bexcellent\b", re.I), 5, "excellent"),
    (re.compile(r"\b(very|relatively) clear\b", re.I), 3, "very_clear"),
    (re.compile(r"\b(good|high) quality\b", re.I), 3, "good_quality"),
    (re.compile(r"\bno clipping\b", re.I), 1, "no_clipping"),
    (re.compile(r"\bclipping\b", re.I), -3, "clipping"),
    (re.compile(r"\bclear\b", re.I), 1, "clear"),
    (re.compile(r"\bfaint\b", re.I), -3, "faint"),
    (re.compile(r"\bdistant\b", re.I), -1, "distant"),
    (re.compile(r"\bdistorted\b", re.I), -4, "distorted"),
    (re.compile(r"\bpoor\b", re.I), -4, "poor"),
]

MAMMAL_TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("wolf", re.compile(r"\b(?:wolf|wolves|howl)\b", re.I)),
    ("whale", re.compile(r"\b(?:whale|humpback|breach)\b", re.I)),
    ("bear", re.compile(r"\bbear\b", re.I)),
    ("squirrel/marmot", re.compile(r"\b(?:squirrel|marmot|ags|ground squirrel)\b", re.I)),
    ("ungulate", re.compile(r"\b(?:caribou|moose|sheep|dall|elk|ungulate)\b", re.I)),
    ("canid other", re.compile(r"\b(?:coyote|fox)\b", re.I)),
]


def parse_key_value_pairs(pairs: list[str], label: str) -> dict[str, int]:
    """Parse repeatable KEY=VALUE CLI arguments."""
    result: dict[str, int] = {}
    for pair in pairs:
        if "=" not in pair:
            print(f"Invalid {label} (expected KEY=VALUE): {pair!r}", file=sys.stderr)
            sys.exit(1)
        key, value = pair.split("=", 1)
        key = key.strip()
        try:
            result[key] = int(value.strip())
        except ValueError:
            print(f"Invalid {label} value (expected int): {pair!r}", file=sys.stderr)
            sys.exit(1)
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build scored MVP highlights candidates from the audio clips catalog.",
    )
    parser.add_argument(
        "--catalog",
        default=CATALOG,
        help=f"Input catalog CSV (default: {CATALOG})",
    )
    parser.add_argument(
        "--output",
        default=OUT,
        help=f"Output highlights candidates CSV (default: {OUT})",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=0,
        help="Only include clips with composite score >= this value (default: 0)",
    )
    parser.add_argument(
        "--max-per-category",
        type=int,
        default=None,
        help="If set, use this cap for every category (overrides --category-cap defaults)",
    )
    parser.add_argument(
        "--category-cap",
        action="append",
        default=[],
        metavar="CATEGORY=N",
        help="Per-category upper bound (repeatable; merges with defaults)",
    )
    parser.add_argument(
        "--mammal-type-cap",
        action="append",
        default=[],
        metavar="TYPE=N",
        help="Per mammal sub-type cap within MAMMAL REFERENCE (repeatable)",
    )
    return parser


def resolve_config(args: argparse.Namespace) -> dict[str, Any]:
    category_caps = dict(DEFAULT_CATEGORY_CAPS)
    category_caps.update(parse_key_value_pairs(args.category_cap, "--category-cap"))
    if args.max_per_category is not None:
        category_caps = {cat: args.max_per_category for cat in category_caps}
        category_caps["__default__"] = args.max_per_category

    mammal_type_caps = dict(MAMMAL_TYPE_CAPS)
    mammal_type_caps.update(parse_key_value_pairs(args.mammal_type_cap, "--mammal-type-cap"))

    return {
        "catalog": args.catalog,
        "output": args.output,
        "min_score": args.min_score,
        "max_per_category": args.max_per_category,
        "category_caps": category_caps,
        "mammal_type_caps": mammal_type_caps,
    }


def print_config(config: dict[str, Any]) -> None:
    print("Active highlights candidates config:")
    print(f"  catalog: {config['catalog']}")
    print(f"  output: {config['output']}")
    print(f"  min_score: {config['min_score']}")
    if config["max_per_category"] is not None:
        print(f"  max_per_category: {config['max_per_category']} (all categories)")
    print("  category_caps:")
    for cat, cap in sorted(config["category_caps"].items()):
        if cat == "__default__":
            continue
        print(f"    {cat}: {cap}")
    if "__default__" in config["category_caps"]:
        print(f"    <default>: {config['category_caps']['__default__']}")
    print("  mammal_type_caps:")
    for mtype, cap in config["mammal_type_caps"].items():
        print(f"    {mtype}: {cap}")
    print()


def classify_mammal(desc: str) -> str:
    """Classify a MAMMAL REFERENCE description into a sub-type bucket."""
    for mtype, pattern in MAMMAL_TYPE_PATTERNS:
        if pattern.search(desc):
            return mtype
    return "other"


def score_row(desc: str) -> int:
    d = desc.lower()
    return sum(w for kw, w in WISHLIST_KEYWORDS.items() if kw in d)


def quality_signal(desc: str) -> tuple[int, str]:
    """Extract the ranger's informal quality vocabulary from a description.

    Returns (score_delta, comma-joined tag list). "no clipping" and
    "clipping" are mutually exclusive per description (no clipping wins);
    "very clear"/"relatively clear" preempt the weaker generic "clear" tag
    so a clip isn't credited for both.
    """
    score = 0
    tags: list[str] = []
    has_strong_clear = bool(re.search(r"\b(very|relatively) clear\b", desc, re.I))
    has_no_clipping = bool(re.search(r"\bno clipping\b", desc, re.I))
    for pattern, weight, tag in QUALITY_PATTERNS:
        if tag == "clear" and has_strong_clear:
            continue
        if tag == "clipping" and has_no_clipping:
            continue
        if pattern.search(desc):
            score += weight
            tags.append(tag)
    return score, ",".join(tags)


def category_cap(category_caps: dict[str, int], category: str) -> int:
    return category_caps.get(category, category_caps.get("__default__", DEFAULT_CAP))


def select_candidates(candidates: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Apply min-score filter and per-category / per-mammal-type caps."""
    filtered = candidates[candidates["score"] >= config["min_score"]].copy()
    category_caps = config["category_caps"]
    mammal_type_caps = config["mammal_type_caps"]

    selected_groups: list[pd.DataFrame] = []
    for cat, group in filtered.groupby("category_folder", sort=True):
        ranked = group.sort_values("score", ascending=False)
        if cat == MAMMAL_REFERENCE_CATEGORY:
            mammals = ranked.copy()
            mammals["mammal_type"] = mammals["free_text_description"].fillna("").apply(classify_mammal)
            type_groups: list[pd.DataFrame] = []
            for mtype, mgroup in mammals.groupby("mammal_type", sort=True):
                cap = mammal_type_caps.get(mtype, mammal_type_caps.get("other", 0))
                type_groups.append(mgroup.head(cap))
            selected_groups.append(pd.concat(type_groups))
        else:
            chunk = ranked.head(category_cap(category_caps, cat)).copy()
            chunk["mammal_type"] = ""
            selected_groups.append(chunk)

    if not selected_groups:
        return filtered.iloc[0:0].copy()

    return pd.concat(selected_groups).sort_values(
        ["category_folder", "score"], ascending=[True, False]
    )


def print_results(candidates: pd.DataFrame, selected: pd.DataFrame) -> None:
    pre_cap_counts = candidates["category_folder"].value_counts()
    print(f"Pre-cap clean-candidate pool: {pre_cap_counts.sum()}")
    print(pre_cap_counts)
    print(f"\nAfter filters + caps -> selected candidates: {len(selected)}")
    print(selected["category_folder"].value_counts())

    mammals = selected[selected["category_folder"] == MAMMAL_REFERENCE_CATEGORY]
    if len(mammals):
        print(f"\nMAMMAL REFERENCE by mammal_type ({len(mammals)} total):")
        for mtype, grp in mammals.groupby("mammal_type", sort=True):
            ranked = grp.sort_values("score", ascending=False)
            print(f"  {mtype}: {len(ranked)}")
            for _, r in ranked.head(3).iterrows():
                print(f"    [{r['score']:>2}] {r['free_text_description']}")

    print("\nTop-scored per category (up to 8 shown):")
    for cat, grp in selected.groupby("category_folder"):
        top = grp.sort_values("score", ascending=False).head(8)
        print(f"\n== {cat} ==")
        for _, r in top.iterrows():
            print(f"  [{r['score']:>2}] {r['free_text_description']}")


def main() -> None:
    args = build_arg_parser().parse_args()
    config = resolve_config(args)
    print_config(config)

    df = pd.read_csv(config["catalog"])

    keep = ~df["sensitive_flag"]
    for sub in EXCLUDE_PATH_SUBSTRINGS:
        keep &= ~df["subfolder_path"].fillna("").str.contains(sub, case=False, regex=False)
        keep &= ~df["filepath"].fillna("").str.contains(sub, case=False, regex=False)

    keep &= df["parse_confidence"].isin(["high", "low"])
    keep &= ~df["free_text_description"].fillna("").str.contains(
        HEDGE_PATTERN.pattern, regex=True, case=False
    )
    keep &= df["file_size_bytes"] > 100_000  # drop empty/corrupt-looking files

    candidates = df[keep].copy()

    candidates["stem"] = candidates["filename"].str.rsplit(".", n=1).str[0].str.lower()
    candidates["is_wav"] = candidates["extension"].str.lower() == "wav"
    candidates = candidates.sort_values("is_wav", ascending=False).drop_duplicates("stem", keep="first")

    descriptions = candidates["free_text_description"].fillna("")
    candidates["keyword_score"] = descriptions.apply(score_row)
    quality = descriptions.apply(quality_signal)
    candidates["quality_score"] = quality.apply(lambda t: t[0])
    candidates["quality_tags"] = quality.apply(lambda t: t[1])

    candidates["score"] = candidates["keyword_score"] + candidates["quality_score"]
    candidates.loc[candidates["xc_matched"] & (candidates["xc_quality"].isin(["A", "B"])), "score"] += 3

    candidates = candidates.sort_values(["category_folder", "score"], ascending=[True, False])

    selected = select_candidates(candidates, config)

    selected[[
        "filepath", "filename", "category_folder", "parsed_park_code", "parsed_site_code",
        "parsed_date", "free_text_description", "score", "keyword_score", "quality_score",
        "quality_tags", "mammal_type", "xc_common_name", "xc_quality", "file_size_bytes",
    ]].to_csv(config["output"], index=False)

    print_results(candidates, selected)


if __name__ == "__main__":
    main()
