"""Site photo entities, assignment rules, and WebP encoding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from lib.paths import CATALOG_SITE_PHOTOS, PROJECT_ROOT
from lib.site_photo_filenames import (
    parse_photo_id,
    parse_site_key_from_filename,
    photo_id_from_site_and_date,
    taken_date_from_filename,
)

MAX_WIDTH = 1200
WEBP_QUALITY = 82


def clip_site_key(clip: dict[str, Any]) -> str | None:
    park = clip.get("park_code")
    site = clip.get("site_code")
    if park and site:
        return f"{park}{site}".upper()
    return None


def photo_record_from_filename(name: str) -> dict[str, str] | None:
    """Parse photo metadata (id, site_key, park_code, site_code, taken_date) from a filename."""
    site_key = parse_site_key_from_filename(name)
    if not site_key:
        return None

    taken_date = taken_date_from_filename(name)
    if not taken_date:
        return None

    park_code = site_key[:4]
    site_code = site_key[4:]
    photo_id = photo_id_from_site_and_date(site_key, taken_date)
    return {
        "id": photo_id,
        "site_key": site_key,
        "park_code": park_code,
        "site_code": site_code,
        "taken_date": taken_date,
    }


def photo_path_for_id(photo_id: str) -> str:
    return f"highlights/site_photos/{photo_id}.webp"


def build_photo_record(
    meta: dict[str, str],
    *,
    source_filename: str | None = None,
) -> dict[str, Any]:
    return {
        "id": meta["id"],
        "path": photo_path_for_id(meta["id"]),
        "site_key": meta["site_key"],
        "park_code": meta["park_code"],
        "site_code": meta["site_code"],
        "taken_date": meta["taken_date"],
        "source_filename": source_filename,
    }


def photo_record_from_id(photo_id: str) -> dict[str, str] | None:
    parsed = parse_photo_id(photo_id)
    if not parsed:
        return None
    return {
        "id": photo_id,
        **parsed,
    }


def pick_closest_photo(
    photos: list[dict[str, Any]],
    site_key: str,
    recorded_date: str | None,
) -> str | None:
    """Return photo id with taken_date closest to recorded_date at the same site."""
    site_photos = [photo for photo in photos if photo.get("site_key") == site_key]
    if not site_photos:
        return None
    if not recorded_date:
        return max(site_photos, key=lambda photo: photo["taken_date"])["id"]

    record_ymd = int(recorded_date.replace("-", ""))

    def distance(photo: dict[str, Any]) -> int:
        taken_ymd = int(str(photo["taken_date"]).replace("-", ""))
        return abs(taken_ymd - record_ymd)

    return min(site_photos, key=distance)["id"]


def assign_site_photo_ids(
    clips: list[dict[str, Any]],
    photos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Set ``site_photo_id`` on each clip from the shared photo catalog."""
    for clip in clips:
        key = clip_site_key(clip)
        if key:
            clip["site_photo_id"] = pick_closest_photo(
                photos,
                key,
                clip.get("recorded_date"),
            )
        else:
            clip["site_photo_id"] = None
    return clips


def encode_webp(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGB")
        width, height = image.size
        if width > MAX_WIDTH:
            new_height = round(height * (MAX_WIDTH / width))
            image = image.resize((MAX_WIDTH, new_height), Image.Resampling.LANCZOS)
        image.save(dest, format="WEBP", quality=WEBP_QUALITY, method=6)


def repo_relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def load_site_photos_catalog(path: Path = CATALOG_SITE_PHOTOS) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_site_photos_catalog(
    photos: list[dict[str, Any]],
    path: Path = CATALOG_SITE_PHOTOS,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_photos = sorted(photos, key=lambda photo: photo["id"])
    path.write_text(
        json.dumps(sorted_photos, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def merge_photo_records(
    existing: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {photo["id"]: photo for photo in existing}
    for record in new_records:
        current = by_id.get(record["id"])
        if current is None:
            by_id[record["id"]] = record
            continue
        merged = dict(current)
        for field in ("path", "site_key", "park_code", "site_code", "taken_date"):
            if record.get(field):
                merged[field] = record[field]
        if record.get("source_filename"):
            merged["source_filename"] = record["source_filename"]
        by_id[record["id"]] = merged
    return sorted(by_id.values(), key=lambda photo: photo["id"])


def scan_photo_files(output_root: Path) -> list[dict[str, Any]]:
    """Build photo records from canonical ``{photo_id}.webp`` files on disk."""
    records: list[dict[str, Any]] = []
    if not output_root.is_dir():
        return records

    for path in sorted(output_root.glob("*.webp")):
        meta = photo_record_from_id(path.stem)
        if meta is None:
            continue
        records.append(build_photo_record(meta, source_filename=path.name))
    return records


def output_path_for_photo(output_root: Path, photo_id: str) -> Path:
    return output_root / f"{photo_id}.webp"


def index_source_photos(source_dir: Path) -> dict[str, list[Path]]:
    by_site: dict[str, list[Path]] = {}
    if not source_dir.is_dir():
        return by_site
    for path in sorted(source_dir.glob("CardinalPhotoComposite_*.jpg")):
        key = parse_site_key_from_filename(path.name)
        if key:
            by_site.setdefault(key, []).append(path)
    return by_site


def build_catalog_from_sources(
    source_by_site: dict[str, list[Path]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for paths in source_by_site.values():
        for path in paths:
            meta = photo_record_from_filename(path.name)
            if not meta or meta["id"] in seen:
                continue
            seen.add(meta["id"])
            records.append(build_photo_record(meta, source_filename=path.name))
    return records
