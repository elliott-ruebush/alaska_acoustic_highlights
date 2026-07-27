#!/usr/bin/env python3
"""Build a JSON catalog of highlight audio clips for the NPS Soundscapes site."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import librosa
import pandas as pd
import soundfile as sf
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "highlights" / "audio"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "highlights_catalog.json"
DEFAULT_SPECTROGRAMS = PROJECT_ROOT / "highlights" / "spectrograms"
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "audio_clips_catalog.csv"
DEFAULT_ARTIST = "National Park Service"

AUDIO_EXTENSIONS = {".wav", ".mp3"}

FILENAME_RE = re.compile(
    r"^([A-Z]{4})([A-Z0-9]+)_(\d{8})_(\d{6})[\s_]+(.*)$",
    re.IGNORECASE,
)
PREFIX_RE = re.compile(
    r"^([A-Z]{4}[A-Z0-9]+_\d{8}_\d{6})",
    re.IGNORECASE,
)
PROCESSING_START_RE = re.compile(
    r"\s+(?:TRIM|BANDPASS|AMPLIFY|FADE(?:\s+OUT)?|COMPRESS|CROP|BESSEL(?:\s+FILTER|\s+BANDPASS)?|"
    r"NOISE\s+REDUCTION|HIGH\s+PASS|LOW\s+PASS|NOTCH|EQ|NORMALIZE|LIMIT)\b",
    re.IGNORECASE,
)

CATEGORY_MAP = {
    "BIRDS": "Birds",
    "MAMMALS": "Mammals",
    "GEOPHONY": "Geophony",
    "INSECTS": "Insects",
    "GENERAL": "General",
}


def parse_args() -> argparse.Namespace:
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
    return parser.parse_args()


def format_date(raw: str) -> str:
    if len(raw) != 8 or not raw.isdigit():
        return ""
    yyyy, mm, dd = raw[:4], raw[4:6], raw[6:8]
    if mm == "00" or dd == "00":
        return ""
    return f"{yyyy}-{mm}-{dd}"


def format_time(raw: str) -> str:
    if len(raw) != 6 or not raw.isdigit():
        return ""
    return f"{raw[:2]}:{raw[2:4]}:{raw[4:6]}"


def file_prefix(filename: str) -> str:
    match = PREFIX_RE.match(Path(filename).stem)
    return match.group(1).upper() if match else ""


def parse_filename(filename: str) -> dict[str, str]:
    stem = Path(filename).stem
    match = FILENAME_RE.match(stem)
    if not match:
        return {
            "park_code": "",
            "site_code": "",
            "recorded_date": "",
            "recorded_time": "",
            "description": stem,
            "prefix": file_prefix(filename),
        }
    park, site, date_raw, time_raw, description = match.groups()
    return {
        "park_code": park.upper(),
        "site_code": site.upper(),
        "recorded_date": format_date(date_raw),
        "recorded_time": format_time(time_raw),
        "description": description.strip(),
        "prefix": f"{park.upper()}{site.upper()}_{date_raw}_{time_raw}".upper(),
    }


def split_processing(description: str) -> tuple[str, str]:
    match = PROCESSING_START_RE.search(description)
    if not match:
        return description.strip(), ""
    display = description[: match.start()].strip(" ,._-")
    processing = description[match.start() :].strip()
    return display or description.strip(), processing


def category_from_path(path: Path, input_root: Path) -> tuple[str, str]:
    try:
        rel = path.relative_to(input_root)
    except ValueError:
        rel = path
    for part in rel.parts[:-1]:
        folder = part.upper()
        if folder in CATEGORY_MAP:
            return CATEGORY_MAP[folder], folder
    return "General", "GENERAL"


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


def spectrogram_paths(
    audio_path: Path,
    input_root: Path,
    spectrograms_root: Path,
    category_folder: str,
) -> tuple[str, str | None]:
    rel_audio = audio_path.relative_to(input_root)
    png_rel = rel_audio.with_suffix(".png")
    spectrogram_path = spectrograms_root / png_rel
    spectrogram_repo = repo_relative(spectrogram_path)

    lowfreq_path: str | None = None
    if category_folder == "GEOPHONY":
        lowfreq_file = spectrogram_path.with_name(f"{spectrogram_path.stem}_lowfreq.png")
        lowfreq_path = repo_relative(lowfreq_file)

    return spectrogram_repo, lowfreq_path


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


def iter_audio_files(input_root: Path) -> list[Path]:
    if not input_root.is_dir():
        return []
    files = [
        path
        for path in input_root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return sorted(files)


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
    spectrogram_path, spectrogram_lowfreq_path = spectrogram_paths(
        path, input_root, spectrograms_root, category_folder
    )

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
        "spectrogram_path": spectrogram_path,
        "spectrogram_lowfreq_path": spectrogram_lowfreq_path,
        "duration_sec": round(duration_sec, 1),
        "sample_rate": sample_rate,
        "format": path.suffix.lower().lstrip("."),
        "file_size_bytes": path.stat().st_size,
        "artist": resolve_artist(path, catalog_row),
        "species_common": species_common(catalog_row),
        "species_scientific": species_scientific(catalog_row),
        "xc_quality": xc_quality_value(catalog_row),
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

        lowfreq = clip.get("spectrogram_lowfreq_path")
        if lowfreq:
            expected += 1
            lowfreq_path = PROJECT_ROOT / lowfreq
            if lowfreq_path.is_file():
                present += 1
            else:
                missing.append(lowfreq)

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
    if missing_specs:
        print(f"Missing spectrogram files ({len(missing_specs)}):")
        for path in missing_specs[:20]:
            print(f"  - {path}")
        if len(missing_specs) > 20:
            print(f"  ... and {len(missing_specs) - 20} more")


def main() -> int:
    args = parse_args()
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
    audio_files = iter_audio_files(input_root)
    if not audio_files:
        print(f"No audio files found under {input_root}", file=sys.stderr)
        return 1

    used_ids: set[str] = set()
    clips = [
        build_clip(path, input_root, spectrograms_root, catalog_index, used_ids)
        for path in audio_files
    ]

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
