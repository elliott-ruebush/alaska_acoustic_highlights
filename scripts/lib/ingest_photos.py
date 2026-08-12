"""Resolve ingest site photos to canonical photo ids."""

from __future__ import annotations

from pathlib import Path

from lib.site_photos import photo_record_from_filename


def resolve_photo_id(photo_path: Path) -> tuple[str | None, str]:
    """Return (photo_id, match_method) or (None, 'unmatched')."""
    meta = photo_record_from_filename(photo_path.name)
    if meta:
        return meta["id"], "filename"

    stem_meta = photo_record_from_filename(f"{photo_path.stem}.jpg")
    if stem_meta:
        return stem_meta["id"], "stem"

    return None, "unmatched"
