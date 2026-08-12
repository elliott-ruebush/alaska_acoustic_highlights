"""Load and apply per-clip metadata overrides from ingest/overrides.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.nps_filename import CATEGORY_MAP, file_prefix

OVERRIDABLE_FIELDS = frozenset(
    {
        "title",
        "description",
        "category",
        "artist",
        "species_common",
        "species_scientific",
        "xc_quality",
        "site_photo_id",
        "recorded_date",
        "recorded_time",
        "park_code",
        "site_code",
        "site_name",
    }
)

CATEGORY_TO_FOLDER = {display: folder for folder, display in CATEGORY_MAP.items()}


def load_overrides(path: Path) -> dict[str, dict[str, Any]]:
    """Return override entries keyed by lowercase clip id or file prefix."""
    if not path.is_file():
        return {}

    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)

    if not isinstance(raw, dict):
        raise ValueError(f"overrides file must be a JSON object: {path}")

    index: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        if not isinstance(value, dict):
            raise ValueError(f"override for {key!r} must be an object")
        unknown = set(value) - OVERRIDABLE_FIELDS
        if unknown:
            raise ValueError(
                f"override for {key!r} has unknown fields: {', '.join(sorted(unknown))}"
            )
        index[key.lower()] = value
    return index


def lookup_override(
    overrides: dict[str, dict[str, Any]],
    *,
    clip_id: str,
    audio_filename: str,
) -> dict[str, Any] | None:
    if clip_id.lower() in overrides:
        return overrides[clip_id.lower()]
    prefix = file_prefix(audio_filename)
    if prefix and prefix.lower() in overrides:
        return overrides[prefix.lower()]
    return None


def apply_override(clip: dict[str, Any], override: dict[str, Any]) -> None:
    for field, value in override.items():
        if field == "category":
            if value not in CATEGORY_TO_FOLDER:
                raise ValueError(
                    f"invalid category override {value!r} for clip {clip.get('id')}"
                )
            clip["category"] = value
            clip["category_folder"] = CATEGORY_TO_FOLDER[value]
            continue
        clip[field] = value


def apply_overrides_to_clips(
    clips: list[dict[str, Any]],
    overrides: dict[str, dict[str, Any]],
) -> int:
    """Apply overrides; return count of clips updated."""
    if not overrides:
        return 0

    updated = 0
    for clip in clips:
        audio_name = Path(clip["audio_path"]).name
        override = lookup_override(overrides, clip_id=clip["id"], audio_filename=audio_name)
        if override is None:
            continue
        apply_override(clip, override)
        updated += 1
    return updated
