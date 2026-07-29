"""Shared repository path constants and ingest helpers."""

from __future__ import annotations

from pathlib import Path

from lib.nps_filename import CATEGORY_MAP

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

HIGHLIGHTS_AUDIO = PROJECT_ROOT / "highlights" / "audio"
HIGHLIGHTS_SPECTROGRAMS = PROJECT_ROOT / "highlights" / "spectrograms"
HIGHLIGHTS_SITE_PHOTOS = PROJECT_ROOT / "highlights" / "site_photos"

CATALOG_HIGHLIGHTS = PROJECT_ROOT / "data" / "catalog" / "highlights.json"
CATALOG_AUDIO_CLIPS = PROJECT_ROOT / "data" / "catalog" / "audio_clips.csv"
CATALOG_SITE_NAMES = PROJECT_ROOT / "data" / "catalog" / "site_names.csv"
CATALOG_SCHEMA = PROJECT_ROOT / "data" / "catalog" / "highlights.schema.json"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"

INGEST_ROOT = PROJECT_ROOT / "ingest"
INGEST_AUDIO = INGEST_ROOT / "audio"
INGEST_SITE_PHOTOS = INGEST_ROOT / "site_photos"
INGEST_OVERRIDES = INGEST_ROOT / "overrides.json"

INGEST_CATEGORY_ALIASES: dict[str, str] = {
    "birds": "BIRDS",
    "bird": "BIRDS",
    "bird id": "BIRDS",
    "mammals": "MAMMALS",
    "mammal": "MAMMALS",
    "mammal reference": "MAMMALS",
    "geophony": "GEOPHONY",
    "insects": "INSECTS",
    "insect": "INSECTS",
    "general": "GENERAL",
}


def resolve_ingest_category(audio_path: Path) -> tuple[str, str]:
    """Return (display category, folder name) from a path under ingest/audio/."""
    try:
        rel = audio_path.resolve().relative_to(INGEST_AUDIO.resolve())
    except ValueError:
        return "General", "GENERAL"

    for part in rel.parts[:-1]:
        alias = INGEST_CATEGORY_ALIASES.get(part.lower())
        if alias is not None:
            return CATEGORY_MAP[alias], alias
        folder = part.upper()
        if folder in CATEGORY_MAP:
            return CATEGORY_MAP[folder], folder
    return "General", "GENERAL"
