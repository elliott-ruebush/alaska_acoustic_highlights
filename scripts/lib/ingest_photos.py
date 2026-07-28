"""Match ingest site photos to clip IDs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from lib.nps_filename import file_prefix, parse_filename
from lib.paths import CATALOG_HIGHLIGHTS

SITE_KEY_RE = re.compile(r"^([A-Z]{4})([A-Z0-9]+)", re.IGNORECASE)
DATE_RE = re.compile(r"(20\d{6})")


@dataclass(frozen=True)
class ClipRef:
    clip_id: str
    site_key: str | None
    recorded_date: str | None


def site_key_from_codes(park_code: str | None, site_code: str | None) -> str | None:
    if park_code and site_code:
        return f"{park_code}{site_code}".upper()
    return None


def site_key_from_name(name: str) -> str | None:
    parsed = parse_filename(name)
    if parsed["park_code"] and parsed["site_code"]:
        return f"{parsed['park_code']}{parsed['site_code']}".upper()
    stem = Path(name).stem
    match = SITE_KEY_RE.match(stem.upper())
    if not match:
        return None
    return f"{match.group(1).upper()}{match.group(2).upper()}"


def years_in_name(name: str) -> set[str]:
    return {match.group(1)[:4] for match in DATE_RE.finditer(name)}


def load_catalog_clip_refs() -> list[ClipRef]:
    if not CATALOG_HIGHLIGHTS.is_file():
        return []
    catalog = json.loads(CATALOG_HIGHLIGHTS.read_text(encoding="utf-8"))
    refs: list[ClipRef] = []
    for clip in catalog:
        refs.append(
            ClipRef(
                clip_id=clip["id"],
                site_key=site_key_from_codes(clip.get("park_code"), clip.get("site_code")),
                recorded_date=clip.get("recorded_date"),
            )
        )
    return refs


def clip_refs_from_audio_plans(audio_plans) -> list[ClipRef]:
    refs: list[ClipRef] = []
    for plan in audio_plans:
        parsed = parse_filename(plan.source.name)
        refs.append(
            ClipRef(
                clip_id=plan.clip_id,
                site_key=site_key_from_codes(parsed["park_code"], parsed["site_code"]),
                recorded_date=parsed["recorded_date"] or None,
            )
        )
    return refs


def pick_clip_for_site(
    candidates: list[ClipRef],
    photo_name: str,
) -> str | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0].clip_id

    photo_years = years_in_name(photo_name)
    if not photo_years:
        return candidates[0].clip_id

    dated: list[tuple[ClipRef, int]] = []
    for clip in candidates:
        if clip.recorded_date:
            dated.append((clip, int(clip.recorded_date[:4])))
    if not dated:
        return candidates[0].clip_id

    def score(item: tuple[ClipRef, int]) -> tuple[int, int]:
        clip, year = item
        if str(year) in photo_years:
            return (0, year)
        return (1, abs(year - int(next(iter(photo_years)))))

    return min(dated, key=score)[0].clip_id


def resolve_photo_clip_id(
    photo_path: Path,
    *,
    batch_clip_ids: set[str],
    clip_refs: list[ClipRef],
) -> tuple[str | None, str]:
    """Return (clip_id, match_method) or (None, 'unmatched')."""
    stem = photo_path.stem.lower()

    if stem in batch_clip_ids:
        return stem, "clip_id"

    prefix = file_prefix(photo_path.name)
    if prefix and prefix.lower() in batch_clip_ids:
        return prefix.lower(), "file_prefix"

    by_site: dict[str, list[ClipRef]] = {}
    for ref in clip_refs:
        if ref.site_key:
            by_site.setdefault(ref.site_key, []).append(ref)

    site_key = site_key_from_name(photo_path.name)
    if site_key and site_key in by_site:
        clip_id = pick_clip_for_site(by_site[site_key], photo_path.name)
        if clip_id:
            return clip_id, "site_key"

    return None, "unmatched"
