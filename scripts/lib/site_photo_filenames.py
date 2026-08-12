"""Parse cardinal site photo filenames for site key, date, and photo id."""

from __future__ import annotations

import re

PHOTO_PREFIX = "CardinalPhotoComposite_"
DATE_RE = re.compile(r"(20\d{6})")
YEAR_AFTER_LETTER_RE = re.compile(r"(?<=[A-Z])\d{4}(?=[_.])", re.IGNORECASE)
PHOTO_ID_RE = re.compile(r"^([a-z]{4}[a-z0-9]+)_(20\d{6})$")


def photo_stem(name: str) -> str:
    """Filename stem with optional CardinalPhotoComposite_ prefix removed."""
    stem = name
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    if stem.startswith(PHOTO_PREFIX):
        stem = stem[len(PHOTO_PREFIX) :]
    return stem


def parse_site_key_from_filename(name: str) -> str | None:
    """Extract park+site key from cardinal or short site photo names."""
    stem = photo_stem(name)
    match = re.match(r"^([A-Z]{4})(.+)$", stem, re.IGNORECASE)
    if not match:
        return None
    park, rest = match.group(1), match.group(2)
    site_part = re.split(r"[_]", rest)[0]
    site_part = re.sub(r"\d{4}$", "", site_part)
    if not site_part:
        return None
    return f"{park.upper()}{site_part.upper()}"


YEAR_AFTER_UNDERSCORE_RE = re.compile(r"_(20\d{2})(?:\D|$)")


def years_in_filename(name: str) -> set[str]:
    """Years from YYYYMMDD segments or PARKSITE_YYYY-style suffixes."""
    years = {match.group(0)[:4] for match in DATE_RE.finditer(name)}
    for match in YEAR_AFTER_LETTER_RE.finditer(name):
        years.add(match.group(0))
    for match in YEAR_AFTER_UNDERSCORE_RE.finditer(name):
        years.add(match.group(1))
    return years


def dates_in_filename(name: str) -> list[str]:
    """YYYYMMDD segments found in a filename, in order."""
    return DATE_RE.findall(name)


def taken_date_from_filename(name: str) -> str | None:
    """Best-effort ISO date (YYYY-MM-DD) from a site photo filename."""
    file_dates = dates_in_filename(name)
    if file_dates:
        ymd = file_dates[0]
        return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"

    years = years_in_filename(name)
    if not years:
        return None
    year = max(years)
    return f"{year}-01-01"


def photo_id_from_site_and_date(site_key: str, taken_date: str) -> str:
    """Canonical photo id: ``{site_key.lower()}_{YYYYMMDD}``."""
    ymd = taken_date.replace("-", "")
    return f"{site_key.lower()}_{ymd}"


def parse_photo_id(photo_id: str) -> dict[str, str] | None:
    """Parse a canonical photo id into site_key and taken_date."""
    match = PHOTO_ID_RE.match(photo_id)
    if not match:
        return None
    site_slug, ymd = match.groups()
    park_code = site_slug[:4].upper()
    site_code = site_slug[4:].upper()
    site_key = f"{park_code}{site_code}"
    taken_date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
    return {
        "site_key": site_key,
        "park_code": park_code,
        "site_code": site_code,
        "taken_date": taken_date,
    }
