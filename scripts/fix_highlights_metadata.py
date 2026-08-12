#!/usr/bin/env python3
"""Rewrite ID3 metadata on NPS acoustic highlight MP3 copies."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import pandas as pd
from mutagen.id3 import COMM, ID3, ID3NoHeaderError, TALB, TCON, TCOP, TDRC, TIT2, TPE1, TXXX
from mutagen.mp3 import MP3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.nps_filename import file_prefix, parse_filename, split_processing

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "highlights" / "audio"
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "catalog" / "audio_clips.csv"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "reports" / "metadata_fix_report.csv"

ALBUM = "Soundscapes of Alaska"
DEFAULT_ARTIST = "National Park Service"
COPYRIGHT = (
    "This work was created by the United States Government and is in the public domain."
)

GENRE_MAP = {
    "BIRDS": "Birds",
    "BIRD ID": "Birds",
    "MAMMALS": "Mammals",
    "MAMMAL REFERENCE": "Mammals",
    "GEOPHONY": "Geophony",
    "INSECTS": "Insects",
    "GENERAL": "General",
    "ALASKA SOUND SHOWCASE PT. 2": "General",
}

LATITUDE_RE = re.compile(r"^-?\d{1,3}(?:\.\d+)?$")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fix ID3 metadata on highlight MP3 copies (no re-encode).",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Directory to walk for audio (default: {DEFAULT_INPUT.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help=f"Highlights catalog CSV (default: {DEFAULT_CATALOG.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned tag changes without modifying files",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help=f"Write audit CSV (default: {DEFAULT_REPORT.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT,
        help="Override report CSV path",
    )
    parser.add_argument(
        "--include-wav",
        action="store_true",
        help="Also process WAV files (limited tag support via RIFF INFO)",
    )
    return parser.parse_args(argv)


def genre_from_path(path: Path, input_root: Path) -> str:
    try:
        rel = path.relative_to(input_root)
    except ValueError:
        rel = path
    for part in rel.parts[:-1]:
        mapped = GENRE_MAP.get(part.upper())
        if mapped:
            return mapped
    return "General"


def sensible_recordist(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if LATITUDE_RE.match(text):
        return ""
    if text.replace(".", "", 1).replace("-", "", 1).isdigit():
        return ""
    return text


def species_label(row: pd.Series | None) -> str:
    if row is None:
        return ""
    common = row.get("xc_common_name")
    if isinstance(common, str) and common.strip() and common.strip().lower() != "soundscape":
        return common.strip()
    genus = row.get("xc_genus")
    species = row.get("xc_species")
    if isinstance(genus, str) and genus.strip() and isinstance(species, str) and species.strip():
        return f"{genus.strip()} {species.strip()}"
    return ""


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
    title = ""
    artist = ""
    if "TIT2" in audio.tags:
        title = str(audio.tags["TIT2"])
    if "TPE1" in audio.tags:
        artist = str(audio.tags["TPE1"])
    return title, artist


def build_tags(
    path: Path,
    input_root: Path,
    parsed: dict[str, str],
    catalog_row: pd.Series | None,
) -> dict[str, str]:
    display_title, processing = split_processing(parsed["description"])
    genre = genre_from_path(path, input_root)
    recordist = sensible_recordist(
        catalog_row.get("xc_recordist") if catalog_row is not None else ""
    )
    artist = recordist or DEFAULT_ARTIST
    species = species_label(catalog_row)

    comment_parts = [
        f"Park: {parsed['park_code']}" if parsed["park_code"] else "",
        f"Site: {parsed['site_code']}" if parsed["site_code"] else "",
        f"Species: {species}" if species else "",
        f"Original filename: {path.name}",
    ]
    comment = " | ".join(part for part in comment_parts if part)

    return {
        "title": display_title,
        "artist": artist,
        "album": ALBUM,
        "genre": genre,
        "date": parsed["recorded_date"],
        "comment": comment,
        "copyright": COPYRIGHT,
        "processing": processing,
    }


def write_mp3_tags(path: Path, tags: dict[str, str]) -> None:
    try:
        audio = MP3(path, ID3=ID3)
    except ID3NoHeaderError:
        audio = MP3(path)
        audio.add_tags()

    audio.tags = ID3()
    audio.tags.add(TIT2(encoding=3, text=tags["title"]))
    audio.tags.add(TPE1(encoding=3, text=tags["artist"]))
    audio.tags.add(TALB(encoding=3, text=tags["album"]))
    audio.tags.add(TCON(encoding=3, text=tags["genre"]))
    if tags["date"]:
        audio.tags.add(TDRC(encoding=3, text=tags["date"]))
    audio.tags.add(
        COMM(encoding=3, lang="eng", desc="", text=tags["comment"]),
    )
    audio.tags.add(TCOP(encoding=3, text=tags["copyright"]))
    if tags["processing"]:
        audio.tags.add(
            TXXX(encoding=3, desc="processing", text=tags["processing"]),
        )
    audio.save()


def write_wav_tags(path: Path, tags: dict[str, str]) -> None:
    from mutagen.wave import WAVE

    audio = WAVE(path)
    if audio.tags is None:
        audio.add_tags()
    audio["title"] = tags["title"]
    audio["artist"] = tags["artist"]
    audio["album"] = tags["album"]
    audio["genre"] = tags["genre"]
    if tags["date"]:
        audio["date"] = tags["date"]
    audio["comment"] = tags["comment"]
    if tags["processing"]:
        audio["comment"] = f"{tags['comment']} | Processing: {tags['processing']}"
    audio.save()


def iter_audio_files(input_root: Path, include_wav: bool) -> list[Path]:
    if not input_root.is_dir():
        return []
    extensions = {".mp3"}
    if include_wav:
        extensions.add(".wav")
    files: list[Path] = []
    for path in input_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            files.append(path)
    return sorted(files)


def process_file(
    path: Path,
    input_root: Path,
    catalog_index: dict[str, pd.Series],
    dry_run: bool,
    include_wav: bool,
) -> dict[str, object]:
    parsed = parse_filename(path.name)
    catalog_row = catalog_index.get(parsed["prefix"])
    new_tags = build_tags(path, input_root, parsed, catalog_row)

    old_title, old_artist = "", ""
    if path.suffix.lower() == ".mp3":
        old_title, old_artist = read_mp3_tags(path)
    elif include_wav:
        from mutagen.wave import WAVE

        audio = WAVE(path)
        if audio.tags:
            old_title = str(audio.get("title", [""])[0]) if audio.get("title") else ""
            old_artist = str(audio.get("artist", [""])[0]) if audio.get("artist") else ""

    changed = old_title != new_tags["title"] or old_artist != new_tags["artist"]

    if dry_run:
        print(f"\n{path}")
        print(f"  title:   {old_title!r} -> {new_tags['title']!r}")
        print(f"  artist:  {old_artist!r} -> {new_tags['artist']!r}")
        print(f"  album:   {new_tags['album']!r}")
        print(f"  genre:   {new_tags['genre']!r}")
        print(f"  date:    {new_tags['date']!r}")
        if new_tags["processing"]:
            print(f"  processing: {new_tags['processing']!r}")
        print(f"  comment: {new_tags['comment']!r}")
    else:
        if path.suffix.lower() == ".mp3":
            write_mp3_tags(path, new_tags)
        elif include_wav:
            write_wav_tags(path, new_tags)

    return {
        "filepath": str(path.relative_to(input_root)),
        "old_title": old_title,
        "new_title": new_tags["title"],
        "old_artist": old_artist,
        "new_artist": new_tags["artist"],
        "changed": changed,
    }


def write_report(report_path: Path, rows: list[dict[str, object]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "filepath",
        "old_title",
        "new_title",
        "old_artist",
        "new_artist",
        "changed",
    ]
    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_root = args.input.resolve()
    catalog_path = args.catalog.resolve()

    if not catalog_path.is_file():
        print(f"Catalog not found: {catalog_path}", file=sys.stderr)
        return 1

    if not input_root.is_dir():
        print(f"Input directory not found: {input_root}", file=sys.stderr)
        print("Create it and copy highlight audio before running.", file=sys.stderr)
        return 1

    catalog_index = load_catalog_index(catalog_path)
    audio_files = iter_audio_files(input_root, args.include_wav)
    if not audio_files:
        print(f"No MP3 files found under {input_root}")
        if not args.include_wav:
            print("Use --include-wav to process WAV copies (limited tag support).")
        return 0

    mode = "DRY RUN" if args.dry_run else "WRITE"
    print(f"{mode}: {len(audio_files)} file(s) in {input_root}")

    rows: list[dict[str, object]] = []
    for path in audio_files:
        rows.append(
            process_file(
                path,
                input_root,
                catalog_index,
                dry_run=args.dry_run,
                include_wav=args.include_wav,
            )
        )

    changed_count = sum(1 for row in rows if row["changed"])
    print(f"\nDone: {changed_count}/{len(rows)} file(s) would change tags.")

    if args.report:
        write_report(args.report_path.resolve(), rows)
        print(f"Report written to {args.report_path.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
