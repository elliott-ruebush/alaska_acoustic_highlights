"""Validate highlight catalog clips against highlights.schema.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import jsonschema

    _HAS_JSONSCHEMA = True
except ImportError:
    jsonschema = None  # type: ignore[assignment,misc]
    _HAS_JSONSCHEMA = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "data" / "catalog" / "highlights.schema.json"

CATEGORIES = frozenset({"Birds", "Mammals", "Geophony", "Insects", "General"})

REQUIRED_FIELDS = (
    "id",
    "title",
    "category",
    "category_folder",
    "park_code",
    "site_code",
    "recorded_date",
    "recorded_time",
    "description",
    "audio_path",
    "spectrogram_path",
    "duration_sec",
    "sample_rate",
    "format",
    "file_size_bytes",
    "artist",
    "species_common",
    "species_scientific",
    "xc_quality",
    "site_photo_path",
    "site_photo_year",
    "site_name",
)

_NULLABLE_STRING_FIELDS = frozenset(
    {
        "park_code",
        "site_code",
        "recorded_date",
        "recorded_time",
        "species_common",
        "species_scientific",
        "site_photo_path",
        "site_photo_year",
        "site_name",
    }
)

_clip_schema: dict[str, Any] | None = None


def _load_clip_schema() -> dict[str, Any]:
    global _clip_schema
    if _clip_schema is None:
        with SCHEMA_PATH.open(encoding="utf-8") as handle:
            _clip_schema = json.load(handle)
    return _clip_schema


def _clip_label(clip: Any, index: int) -> str:
    if isinstance(clip, dict) and clip.get("id"):
        return str(clip["id"])
    return f"<index {index}>"


def _validate_with_jsonschema(clips: list[Any]) -> None:
    schema = _load_clip_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []

    for index, clip in enumerate(clips):
        label = _clip_label(clip, index)
        for error in sorted(validator.iter_errors(clip), key=lambda exc: list(exc.path)):
            path = ".".join(str(part) for part in error.absolute_path)
            location = f"{label}.{path}" if path else label
            errors.append(f"{location}: {error.message}")

    if errors:
        raise ValueError(
            f"Catalog schema validation failed ({len(errors)} error(s)):\n"
            + "\n".join(f"  - {error}" for error in errors)
        )


def _is_string_or_null(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _validate_clip_stdlib(clip: Any, index: int, errors: list[str]) -> None:
    label = _clip_label(clip, index)

    if not isinstance(clip, dict):
        errors.append(f"{label}: expected object, got {type(clip).__name__}")
        return

    for field in REQUIRED_FIELDS:
        if field not in clip:
            errors.append(f"{label}: missing required field '{field}'")

    extra_fields = set(clip) - set(REQUIRED_FIELDS)
    if extra_fields:
        extras = ", ".join(sorted(extra_fields))
        errors.append(f"{label}: unexpected field(s): {extras}")

    category = clip.get("category")
    if category is not None and category not in CATEGORIES:
        errors.append(
            f"{label}: invalid category '{category}' "
            f"(expected one of: {', '.join(sorted(CATEGORIES))})"
        )

    for field in ("id", "category_folder", "audio_path", "spectrogram_path", "format"):
        value = clip.get(field)
        if isinstance(value, str) and not value:
            errors.append(f"{label}: '{field}' must be a non-empty string")

    for field in _NULLABLE_STRING_FIELDS:
        value = clip.get(field)
        if field in clip and not _is_string_or_null(value):
            errors.append(f"{label}: '{field}' must be a string or null")

    for field in ("title", "description", "artist"):
        value = clip.get(field)
        if field in clip and not isinstance(value, str):
            errors.append(f"{label}: '{field}' must be a string")

    duration = clip.get("duration_sec")
    if "duration_sec" in clip and not isinstance(duration, (int, float)):
        errors.append(f"{label}: 'duration_sec' must be a number")

    sample_rate = clip.get("sample_rate")
    if "sample_rate" in clip and not isinstance(sample_rate, int):
        errors.append(f"{label}: 'sample_rate' must be an integer")

    file_size = clip.get("file_size_bytes")
    if "file_size_bytes" in clip:
        if not isinstance(file_size, int):
            errors.append(f"{label}: 'file_size_bytes' must be an integer")
        elif file_size < 0:
            errors.append(f"{label}: 'file_size_bytes' must be >= 0")

    xc_quality = clip.get("xc_quality")
    if "xc_quality" in clip and xc_quality is not None and not isinstance(
        xc_quality, (int, float)
    ):
        errors.append(f"{label}: 'xc_quality' must be a number or null")


def _validate_with_stdlib(clips: list[Any]) -> None:
    errors: list[str] = []
    for index, clip in enumerate(clips):
        _validate_clip_stdlib(clip, index, errors)

    if errors:
        raise ValueError(
            f"Catalog schema validation failed ({len(errors)} error(s)):\n"
            + "\n".join(f"  - {error}" for error in errors)
        )


def validate_clips(clips: list[Any]) -> None:
    """Validate a list of highlight clips against the catalog JSON schema.

    Raises:
        ValueError: If clips is not a list or any clip fails validation.
    """
    if not isinstance(clips, list):
        raise ValueError(
            f"Catalog must be a JSON array, got {type(clips).__name__}"
        )

    if not SCHEMA_PATH.is_file():
        raise ValueError(f"Catalog schema not found: {SCHEMA_PATH}")

    if _HAS_JSONSCHEMA:
        _validate_with_jsonschema(clips)
    else:
        _validate_with_stdlib(clips)
