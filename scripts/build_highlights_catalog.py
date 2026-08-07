#!/usr/bin/env python3
"""Build a JSON catalog of highlight audio clips for the NPS Soundscapes site."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import librosa
import pandas as pd
import soundfile as sf
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.catalog_validate import validate_clips
from lib.nps_filename import (
    category_from_path,
    file_prefix,
    parse_filename,
    PROCESSING_START_RE,
    split_processing,
)
from lib.overrides import apply_overrides_to_clips, load_overrides
from lib.paths import (
    CATALOG_AUDIO_CLIPS,
    CATALOG_HIGHLIGHTS,
    CATALOG_SITE_NAMES,
    HIGHLIGHTS_AUDIO,
    HIGHLIGHTS_SPECTROGRAMS,
    INGEST_OVERRIDES,
    PROJECT_ROOT,
)
from lib.site_names import apply_site_names_to_clips, load_site_names

DEFAULT_INPUT = HIGHLIGHTS_AUDIO
DEFAULT_OUTPUT = CATALOG_HIGHLIGHTS
DEFAULT_SPECTROGRAMS = HIGHLIGHTS_SPECTROGRAMS
DEFAULT_CATALOG = CATALOG_AUDIO_CLIPS
DEFAULT_ARTIST = "National Park Service"

AUDIO_EXTENSIONS = {".wav", ".mp3"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build JSON catalog for NPS Soundscapes highlight clips.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Highlights audio root (default: {DEFAULT_INPUT.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--spectrograms-dir",
        type=Path,
        default=DEFAULT_SPECTROGRAMS,
        help=(
            f"Spectrogram root mirroring audio layout "
            f"(default: {DEFAULT_SPECTROGRAMS.relative_to(PROJECT_ROOT)})"
        ),
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help=f"Audio clips catalog CSV for enrichment (default: {DEFAULT_CATALOG.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--site-names",
        type=Path,
        default=CATALOG_SITE_NAMES,
        help=(
            f"Site name lookup CSV (default: "
            f"{CATALOG_SITE_NAMES.relative_to(PROJECT_ROOT)})"
        ),
    )
    parser.add_argument(
        "--overrides",
        type=Path,
        default=INGEST_OVERRIDES,
        help=f"Optional per-clip metadata overrides JSON (default: {INGEST_OVERRIDES.relative_to(PROJECT_ROOT)})",
    )
    return parser.parse_args(argv)


def repo_relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def load_catalog_index(catalog_path: Path) -> dict[str, pd.Series]:
    df = pd.read_csv(catalog_path, dtype=str)
    index: dict[str, pd.Series] = {}
    for _, row in df.iterrows():
        prefix = file_prefix(str(row["filename"]))
        if prefix and prefix not in index:
            index[prefix] = row
    return index


def read_mp3_tags(path: Path) -> tuple[str, str]:
    try:
        audio = MP3(path, ID3=ID3)
    except ID3NoHeaderError:
        return "", ""
    if audio.tags is None:
        return "", ""
    title = str(audio.tags["TIT2"]) if "TIT2" in audio.tags else ""
    artist = str(audio.tags["TPE1"]) if "TPE1" in audio.tags else ""
    return title.strip(), artist.strip()


def read_wav_tags(path: Path) -> tuple[str, str]:
    try:
        from mutagen.wave import WAVE
    except ImportError:
        return "", ""

    audio = WAVE(path)
    if audio.tags is None:
        return "", ""
    title = ""
    artist = ""
    if audio.get("title"):
        title = str(audio.get("title")[0]).strip()
    if audio.get("artist"):
        artist = str(audio.get("artist")[0]).strip()
    return title, artist


def sensible_title(tag_title: str, cleaned_description: str, raw_description: str) -> str:
    if tag_title and tag_title != raw_description:
        return tag_title
    if tag_title and not PROCESSING_START_RE.search(tag_title):
        return tag_title
    return cleaned_description


def resolve_title(path: Path, parsed: dict[str, str]) -> str:
    cleaned, _ = split_processing(parsed["description"])
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        tag_title, _ = read_mp3_tags(path)
        return sensible_title(tag_title, cleaned, parsed["description"])
    if suffix == ".wav":
        tag_title, _ = read_wav_tags(path)
        return sensible_title(tag_title, cleaned, parsed["description"])
    return cleaned


def resolve_artist(path: Path, catalog_row: pd.Series | None) -> str:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        _, tag_artist = read_mp3_tags(path)
        if tag_artist:
            return tag_artist
    elif suffix == ".wav":
        _, tag_artist = read_wav_tags(path)
        if tag_artist:
            return tag_artist

    if catalog_row is not None:
        recordist = catalog_row.get("xc_recordist")
        if isinstance(recordist, str) and recordist.strip():
            return recordist.strip()
    return DEFAULT_ARTIST


def null_if_empty(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def species_common(catalog_row: pd.Series | None) -> str | None:
    if catalog_row is None:
        return None
    common = null_if_empty(catalog_row.get("xc_common_name"))
    if common and common.lower() != "soundscape":
        return common
    return None


def species_scientific(catalog_row: pd.Series | None) -> str | None:
    if catalog_row is None:
        return None
    genus = null_if_empty(catalog_row.get("xc_genus"))
    species = null_if_empty(catalog_row.get("xc_species"))
    if genus and species:
        return f"{genus} {species}"
    return None


def xc_quality_value(catalog_row: pd.Series | None) -> float | None:
    if catalog_row is None:
        return None
    raw = null_if_empty(catalog_row.get("xc_quality"))
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_audio_info(path: Path) -> tuple[float, int]:
    if path.suffix.lower() == ".wav":
        info = sf.info(path)
        return float(info.duration), int(info.samplerate)
    duration = float(librosa.get_duration(path=path))
    sample_rate = int(librosa.get_samplerate(path))
    return duration, sample_rate


def spectrogram_path(
    audio_path: Path,
    input_root: Path,
    spectrograms_root: Path,
) -> str:
    rel_audio = audio_path.relative_to(input_root)
    png_rel = rel_audio.with_suffix(".png")
    spectrogram_file = spectrograms_root / png_rel
    return repo_relative(spectrogram_file)


def load_existing_site_photos(
    output_path: Path,
) -> dict[str, dict[str, str | None]]:
    if not output_path.is_file():
        return {}
    with output_path.open(encoding="utf-8") as handle:
        catalog = json.load(handle)
    return {
        clip["id"]: {
            "site_photo_path": clip.get("site_photo_path"),
            "site_photo_year": clip.get("site_photo_year"),
        }
        for clip in catalog
        if "id" in clip
    }


def merge_site_photos(
    clips: list[dict[str, Any]],
    existing_photos: dict[str, dict[str, str | None]],
) -> None:
    for clip in clips:
        existing = existing_photos.get(clip["id"])
        if not existing:
            continue
        if existing.get("site_photo_path") is not None:
            clip["site_photo_path"] = existing["site_photo_path"]
        if existing.get("site_photo_year") is not None:
            clip["site_photo_year"] = existing["site_photo_year"]


def unique_id(prefix: str, path: Path, used_ids: set[str]) -> str:
    base = prefix.lower()
    if base not in used_ids:
        used_ids.add(base)
        return base

    ext = path.suffix.lower().lstrip(".")
    candidate = f"{base}-{ext}"
    counter = 2
    while candidate in used_ids:
        candidate = f"{base}-{ext}-{counter}"
        counter += 1
    used_ids.add(candidate)
    return candidate


def dedupe_audio_files(files: list[Path]) -> list[Path]:
    """When same prefix has both .wav and .mp3, keep .mp3 only."""
    kept: dict[str, Path] = {}
    no_prefix: list[Path] = []
    for path in files:
        prefix = file_prefix(path.name)
        if not prefix:
            no_prefix.append(path)
            continue
        current = kept.get(prefix)
        if current is None:
            kept[prefix] = path
        elif path.suffix.lower() == ".mp3":
            kept[prefix] = path
    return sorted(list(kept.values()) + no_prefix)


def iter_audio_files(input_root: Path) -> list[Path]:
    if not input_root.is_dir():
        return []
    files = [
        path
        for path in input_root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return dedupe_audio_files(sorted(files))


def build_clip(
    path: Path,
    input_root: Path,
    spectrograms_root: Path,
    catalog_index: dict[str, pd.Series],
    used_ids: set[str],
) -> dict[str, Any]:
    parsed = parse_filename(path.name)
    catalog_row = catalog_index.get(parsed["prefix"])
    category, category_folder = category_from_path(path, input_root)
    cleaned_description, _ = split_processing(parsed["description"])
    duration_sec, sample_rate = get_audio_info(path)
    spectrogram_repo_path = spectrogram_path(path, input_root, spectrograms_root)

    return {
        "id": unique_id(parsed["prefix"] or path.stem, path, used_ids),
        "title": resolve_title(path, parsed),
        "category": category,
        "category_folder": category_folder,
        "park_code": parsed["park_code"] or None,
        "site_code": parsed["site_code"] or None,
        "recorded_date": parsed["recorded_date"] or None,
        "recorded_time": parsed["recorded_time"] or None,
        "description": cleaned_description,
        "audio_path": repo_relative(path),
        "spectrogram_path": spectrogram_repo_path,
        "duration_sec": round(duration_sec, 1),
        "sample_rate": sample_rate,
        "format": path.suffix.lower().lstrip("."),
        "file_size_bytes": path.stat().st_size,
        "artist": resolve_artist(path, catalog_row),
        "species_common": species_common(catalog_row),
        "species_scientific": species_scientific(catalog_row),
        "xc_quality": xc_quality_value(catalog_row),
        "site_photo_path": None,
        "site_photo_year": None,
        "site_name": None,
    }


def summarize_spectrograms(clips: list[dict[str, Any]]) -> tuple[int, int, list[str]]:
    present = 0
    expected = 0
    missing: list[str] = []

    for clip in clips:
        spec_path = PROJECT_ROOT / clip["spectrogram_path"]
        expected += 1
        if spec_path.is_file():
            present += 1
        else:
            missing.append(clip["spectrogram_path"])

    return present, expected, missing


def print_summary(clips: list[dict[str, Any]], missing_specs: list[str]) -> None:
    print(f"\nWrote {len(clips)} clip(s)")

    by_category: dict[str, int] = {}
    for clip in clips:
        by_category[clip["category"]] = by_category.get(clip["category"], 0) + 1
    print("\nBy category:")
    for category in sorted(by_category):
        print(f"  {category}: {by_category[category]}")

    present, expected, _ = summarize_spectrograms(clips)
    print(f"\nSpectrograms present: {present}/{expected}")

    site_photo_count = sum(1 for clip in clips if clip.get("site_photo_path"))
    print(f"Clips with site photos: {site_photo_count}/{len(clips)}")
    print(
        "When adding NEW site photos, run: "
        "python scripts/build_site_photos.py --sync-catalog"
    )

    if missing_specs:
        print(f"Missing spectrogram files ({len(missing_specs)}):")
        for path in missing_specs[:20]:
            print(f"  - {path}")
        if len(missing_specs) > 20:
            print(f"  ... and {len(missing_specs) - 20} more")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_root = args.input.resolve()
    output_path = args.output.resolve()
    spectrograms_root = args.spectrograms_dir.resolve()
    catalog_path = args.catalog.resolve()

    if not input_root.is_dir():
        print(f"Input directory not found: {input_root}", file=sys.stderr)
        return 1
    if not catalog_path.is_file():
        print(f"Catalog not found: {catalog_path}", file=sys.stderr)
        return 1

    catalog_index = load_catalog_index(catalog_path)
    existing_site_photos = load_existing_site_photos(output_path)
    audio_files = iter_audio_files(input_root)
    if not audio_files:
        print(f"No audio files found under {input_root}", file=sys.stderr)
        return 1

    used_ids: set[str] = set()
    clips = [
        build_clip(path, input_root, spectrograms_root, catalog_index, used_ids)
        for path in audio_files
    ]
    merge_site_photos(clips, existing_site_photos)

    try:
        overrides = load_overrides(args.overrides.resolve())
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    override_count = apply_overrides_to_clips(clips, overrides)
    if override_count:
        print(f"Applied metadata overrides to {override_count} clip(s)")

    site_names = load_site_names(args.site_names.resolve())
    site_name_count = apply_site_names_to_clips(clips, site_names)
    if site_name_count:
        print(f"Resolved site names for {site_name_count} clip(s)")

    try:
        validate_clips(clips)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(clips, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    _, _, missing_specs = summarize_spectrograms(clips)
    print_summary(clips, missing_specs)
    print(f"\nCatalog written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
