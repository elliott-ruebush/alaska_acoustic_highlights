#!/usr/bin/env python3
"""Build a filesystem catalog of NPS acoustic highlight recordings."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import pandas as pd

DEFAULT_ROOT = Path("/Volumes/NPS_ADSB_Data/NPS_Type_1_Acoustic_Audio_Highlights")
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "catalog" / "audio_clips.csv"

AUDIO_EXTENSIONS = {".wav", ".mp3", ".aiff"}

# Dominant pattern: PARKSITE_YYYYMMDD_HHMMSS[ _/description]
HIGH_CONFIDENCE_RE = re.compile(
    r"^([A-Z]{4})([A-Z0-9]+)[_-](\d{8})[_-]((?:\d{6})|HHMMSS)(?:[_ ](.*))?$",
    re.IGNORECASE,
)

# Embedded park/site/date/time (e.g. Bettles_GAARRangerStation_20220627_072800 ...)
EMBEDDED_PARKSITE_RE = re.compile(
    r"([A-Z]{4}[A-Z0-9]+)[_-](\d{8})[_-]((?:\d{6})|HHMMSS)",
    re.IGNORECASE,
)

DATE_TIME_RE = re.compile(r"(\d{8})[_-]((?:\d{6})|HHMMSS)")

XC_PATHS = [
    DEFAULT_ROOT / "BIRD ID/for xeno-canto/FINAL2020/XC_batch_upload_NPSAKR_20200314.xlsx",
    DEFAULT_ROOT / "BIRD ID/for xeno-canto/XC_batch_upload_NPSAKR_20200314.xlsx",
    DEFAULT_ROOT / "BIRD ID/for xeno-canto/XC_batch_upload_NPSAKR_20191029.xlsx",
]

XC_COLUMN_MAP = {
    "genus": "xc_genus",
    "species": "xc_species",
    "subspecies": "xc_subspecies",
    "soundtype": "xc_soundtype",
    "quality": "xc_quality",
    "recordist": "xc_recordist",
    "date (YYYY-MM-DD)": "xc_date",
    "time (24h)": "xc_time",
    "latitude": "xc_latitude",
    "longitude": "xc_longitude",
    "location": "xc_location",
    "country": "xc_country",
    "elevation": "xc_elevation",
    "remarks": "xc_remarks",
    "seen? (Y/N)": "xc_seen",
    "playback-used? (Y/N)": "xc_playback_used",
    "background": "xc_background",
    "license": "xc_license",
}


def normalize_stem(filename: str) -> str:
    return Path(filename).stem.lower()


def format_date(raw: str) -> str:
    if len(raw) != 8 or not raw.isdigit():
        return ""
    yyyy, mm, dd = raw[:4], raw[4:6], raw[6:8]
    if mm == "00" or dd == "00":
        return ""
    return f"{yyyy}-{mm}-{dd}"


def format_time(raw: str) -> str:
    if raw.upper() == "HHMMSS":
        return ""
    if len(raw) != 6 or not raw.isdigit():
        return ""
    return f"{raw[:2]}:{raw[2:4]}:{raw[4:6]}"


def split_parksite(parksite: str) -> tuple[str, str]:
    if len(parksite) >= 4 and parksite[:4].isalpha():
        return parksite[:4].upper(), parksite[4:].upper()
    return "", parksite.upper()


def strip_description_suffix(stem: str, match_end: int) -> str:
    remainder = stem[match_end:].lstrip("_ ").strip("._ ")
    return remainder


def parse_filename(filename: str) -> dict:
    stem = Path(filename).stem
    result = {
        "parsed_park_code": "",
        "parsed_site_code": "",
        "parsed_date": "",
        "parsed_time": "",
        "free_text_description": stem,
        "parse_confidence": "unparsed",
    }

    high = HIGH_CONFIDENCE_RE.match(stem)
    if high:
        park, site, date_raw, time_raw, desc = high.groups()
        result.update(
            {
                "parsed_park_code": park.upper(),
                "parsed_site_code": site.upper(),
                "parsed_date": format_date(date_raw),
                "parsed_time": format_time(time_raw),
                "free_text_description": (desc or "").strip("._ "),
                "parse_confidence": "high",
            }
        )
        return result

    embedded = EMBEDDED_PARKSITE_RE.search(stem)
    if embedded:
        parksite, date_raw, time_raw = embedded.groups()
        park, site = split_parksite(parksite)
        desc = strip_description_suffix(stem, embedded.end())
        if not desc:
            desc = strip_description_suffix(stem, 0)
            prefix = stem[: embedded.start()].strip("._- ")
            desc = prefix if prefix else stem
        result.update(
            {
                "parsed_park_code": park,
                "parsed_site_code": site,
                "parsed_date": format_date(date_raw),
                "parsed_time": format_time(time_raw),
                "free_text_description": desc,
                "parse_confidence": "low",
            }
        )
        return result

    date_time = DATE_TIME_RE.search(stem)
    if date_time:
        date_raw, time_raw = date_time.groups()
        desc = strip_description_suffix(stem, date_time.end())
        if not desc:
            desc = stem[: date_time.start()].strip("._- ") or stem
        result.update(
            {
                "parsed_date": format_date(date_raw),
                "parsed_time": format_time(time_raw),
                "free_text_description": desc,
                "parse_confidence": "low",
            }
        )
        return result

    return result


def is_sensitive(relative_path: str) -> bool:
    parts = Path(relative_path).parts
    return bool(parts) and parts[0] == "HUMANS OH HUMANS"


def load_xc_catalog() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in XC_PATHS:
        if not path.exists():
            print(f"Warning: XC catalog not found: {path}", file=sys.stderr)
            continue
        df = pd.read_excel(path)
        if "filename" not in df.columns:
            print(f"Warning: no filename column in {path}", file=sys.stderr)
            continue
        df = df.copy()
        df["_match_key"] = df["filename"].astype(str).map(normalize_stem)
        df["_xc_source"] = path.name
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["_match_key"])

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset="_match_key", keep="first")
    return combined


def build_xc_lookup(xc_df: pd.DataFrame) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    if xc_df.empty:
        return lookup

    for _, row in xc_df.iterrows():
        key = row["_match_key"]
        if not key or key in lookup:
            continue
        genus = row.get("genus", "")
        species = row.get("species", "")
        common_name = ""
        if pd.notna(genus) and pd.notna(species):
            common_name = f"{genus} {species}".strip()
        lookup[key] = {
            "xc_matched": True,
            "xc_common_name": common_name,
            "xc_source": row.get("_xc_source", ""),
            **{
                out_col: row.get(src_col, "")
                for src_col, out_col in XC_COLUMN_MAP.items()
                if src_col in row.index
            },
        }
    return lookup


def walk_audio_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.startswith("._"):
                continue
            ext = Path(name).suffix.lower()
            if ext not in AUDIO_EXTENSIONS:
                continue
            files.append(Path(dirpath) / name)
    return files


def classify_path(root: Path, full_path: Path) -> tuple[str, str]:
    rel = full_path.relative_to(root)
    parts = rel.parts
    if len(parts) == 1:
        return "root", ""
    category = parts[0]
    subfolder = str(Path(*parts[1:-1])) if len(parts) > 2 else ""
    return category, subfolder


def build_catalog_row(root: Path, full_path: Path, xc_lookup: dict[str, dict]) -> dict:
    rel_path = str(full_path.relative_to(root))
    filename = full_path.name
    category_folder, subfolder_path = classify_path(root, full_path)
    parsed = parse_filename(filename)

    row = {
        "filepath": rel_path,
        "filename": filename,
        "category_folder": category_folder,
        "subfolder_path": subfolder_path,
        "extension": full_path.suffix.lower().lstrip("."),
        "file_size_bytes": full_path.stat().st_size,
        **parsed,
        "sensitive_flag": is_sensitive(rel_path),
        "xc_matched": False,
    }

    xc_data = xc_lookup.get(normalize_stem(filename))
    if xc_data:
        row.update(xc_data)
    else:
        row.update(
            {
                "xc_matched": False,
                "xc_common_name": "",
                "xc_source": "",
                **{col: "" for col in XC_COLUMN_MAP.values()},
            }
        )

    return row


def print_summary(df: pd.DataFrame) -> None:
    print(f"\n=== Catalog Summary ===")
    print(f"Total rows: {len(df)}")

    print("\nRows per category_folder:")
    for category, count in df["category_folder"].value_counts().sort_index().items():
        print(f"  {category}: {count}")

    print("\nCount by parse_confidence:")
    for confidence, count in df["parse_confidence"].value_counts().sort_index().items():
        print(f"  {confidence}: {count}")

    print(f"\nsensitive_flag=True: {int(df['sensitive_flag'].sum())}")
    print(f"xc_matched=True: {int(df['xc_matched'].sum())}")

    messy = df.loc[df["parse_confidence"] != "high", "filename"].head(10).tolist()
    print("\nExample filenames with parse_confidence != 'high':")
    for name in messy:
        print(f"  - {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"Error: highlights root not found: {root}", file=sys.stderr)
        return 1

    print(f"Loading Xeno-Canto catalogs from {root} ...")
    xc_df = load_xc_catalog()
    xc_lookup = build_xc_lookup(xc_df)
    print(f"Loaded {len(xc_lookup)} unique XC filename entries")

    print(f"Walking audio files under {root} ...")
    audio_files = walk_audio_files(root)
    print(f"Found {len(audio_files)} audio files")

    rows = [build_catalog_row(root, path, xc_lookup) for path in sorted(audio_files)]
    df = pd.DataFrame(rows)

    column_order = [
        "filepath",
        "filename",
        "category_folder",
        "subfolder_path",
        "extension",
        "file_size_bytes",
        "parsed_park_code",
        "parsed_site_code",
        "parsed_date",
        "parsed_time",
        "free_text_description",
        "parse_confidence",
        "sensitive_flag",
        "xc_matched",
        "xc_common_name",
        "xc_genus",
        "xc_species",
        "xc_subspecies",
        "xc_soundtype",
        "xc_quality",
        "xc_recordist",
        "xc_date",
        "xc_time",
        "xc_latitude",
        "xc_longitude",
        "xc_location",
        "xc_country",
        "xc_elevation",
        "xc_remarks",
        "xc_seen",
        "xc_playback_used",
        "xc_background",
        "xc_license",
        "xc_source",
    ]
    df = df.reindex(columns=column_order)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote catalog to {args.output}")

    print_summary(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
