#!/usr/bin/env python3
"""Validate highlights catalog JSON and referenced media files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.catalog_validate import validate_clips

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "catalog" / "highlights.json"

REQUIRED_FIELDS = (
    "id",
    "title",
    "category",
    "audio_path",
    "spectrogram_path",
    "duration_sec",
)


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def validate_clip(clip: dict[str, Any], index: int, errors: list[str]) -> None:
    clip_id = clip.get("id") or f"<index {index}>"

    for field in REQUIRED_FIELDS:
        if _is_missing(clip.get(field)):
            errors.append(f"{clip_id}: missing required field '{field}'")

    for path_field in ("audio_path", "spectrogram_path"):
        rel = clip.get(path_field)
        if _is_missing(rel):
            continue
        file_path = PROJECT_ROOT / rel
        if not file_path.is_file():
            errors.append(f"{clip_id}: {path_field} file not found: {rel}")

    for optional_field in ("site_photo_path",):
        rel = clip.get(optional_field)
        if _is_missing(rel):
            continue
        file_path = PROJECT_ROOT / rel
        if not file_path.is_file():
            errors.append(f"{clip_id}: {optional_field} file not found: {rel}")


def validate_catalog(catalog_path: Path) -> list[str]:
    errors: list[str] = []

    if not catalog_path.is_file():
        return [f"Catalog file not found: {catalog_path}"]

    try:
        with catalog_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON in {catalog_path}: {exc}"]

    try:
        validate_clips(data)
    except ValueError as exc:
        return [str(exc)]

    for index, clip in enumerate(data):
        if not isinstance(clip, dict):
            errors.append(f"Entry {index}: expected object, got {type(clip).__name__}")
            continue
        validate_clip(clip, index, errors)

    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate highlights catalog JSON and referenced media files."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help="Path to highlights catalog JSON (default: data/catalog/highlights.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    catalog_path = args.catalog.resolve()
    errors = validate_catalog(catalog_path)

    if errors:
        print(f"Catalog validation failed ({len(errors)} error(s)):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Catalog valid: {catalog_path} ({catalog_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
