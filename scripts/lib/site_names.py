"""Load park/site code → display name mapping from data/catalog/site_names.csv."""

from __future__ import annotations

import csv
from pathlib import Path

from lib.paths import CATALOG_SITE_NAMES


def load_site_names(path: Path = CATALOG_SITE_NAMES) -> dict[tuple[str, str], str]:
    """Return {(park_code, site_code): site_name} from the site names CSV."""
    if not path.is_file():
        return {}

    index: dict[tuple[str, str], str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            park = (row.get("park_code") or "").strip().upper()
            site = (row.get("site_code") or "").strip().upper()
            name = (row.get("site_name") or "").strip()
            if not park or not site or not name:
                continue
            index[(park, site)] = name
    return index


def lookup_site_name(
    index: dict[tuple[str, str], str],
    park_code: str | None,
    site_code: str | None,
) -> str | None:
    if not park_code or not site_code:
        return None
    return index.get((park_code.upper(), site_code.upper()))


def apply_site_names_to_clips(
    clips: list[dict],
    index: dict[tuple[str, str], str],
) -> int:
    """Set site_name on clips when a mapping exists; return count updated."""
    if not index:
        return 0

    updated = 0
    for clip in clips:
        name = lookup_site_name(index, clip.get("park_code"), clip.get("site_code"))
        if name is None:
            clip["site_name"] = None
            continue
        clip["site_name"] = name
        updated += 1
    return updated
