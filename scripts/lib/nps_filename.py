"""Shared NPS acoustic highlight filename parsing and path helpers."""

from __future__ import annotations

import re
from pathlib import Path

FILENAME_RE = re.compile(
    r"^([A-Z]{4})([A-Z0-9]+)_(\d{8})_(\d{6})[\s._-]+(.*)$",
    re.IGNORECASE,
)
PREFIX_RE = re.compile(
    r"^([A-Z]{4}[A-Z0-9]+_\d{8}_\d{6})",
    re.IGNORECASE,
)
PROCESSING_START_RE = re.compile(
    r"\s+(?:TRIMMED(?:\s+MORE)?|TRIM|BANDPASS|AMPLIFY|FADE(?:\s+OUT)?|COMPRESS|CROP|"
    r"BESSEL(?:\s+FILTER|\s+BANDPASS)?|NOISE\s+REDUCTION|HIGH\s+PASS|LOW\s+PASS|NOTCH|EQ|NORMALIZE|LIMIT)\b",
    re.IGNORECASE,
)

CATEGORY_MAP = {
    "BIRDS": "Birds",
    "MAMMALS": "Mammals",
    "GEOPHONY": "Geophony",
    "INSECTS": "Insects",
    "GENERAL": "General",
}


def format_date(raw: str) -> str:
    if len(raw) != 8 or not raw.isdigit():
        return ""
    yyyy, mm, dd = raw[:4], raw[4:6], raw[6:8]
    if mm == "00" or dd == "00":
        return ""
    return f"{yyyy}-{mm}-{dd}"


def format_time(raw: str) -> str:
    if len(raw) != 6 or not raw.isdigit():
        return ""
    return f"{raw[:2]}:{raw[2:4]}:{raw[4:6]}"


def file_prefix(filename: str) -> str:
    match = PREFIX_RE.match(Path(filename).stem)
    return match.group(1).upper() if match else ""


def parse_filename(filename: str) -> dict[str, str]:
    stem = Path(filename).stem
    match = FILENAME_RE.match(stem)
    if not match:
        return {
            "park_code": "",
            "site_code": "",
            "recorded_date": "",
            "recorded_time": "",
            "description": stem,
            "prefix": file_prefix(filename),
        }
    park, site, date_raw, time_raw, description = match.groups()
    return {
        "park_code": park.upper(),
        "site_code": site.upper(),
        "recorded_date": format_date(date_raw),
        "recorded_time": format_time(time_raw),
        "description": description.strip(),
        "prefix": f"{park.upper()}{site.upper()}_{date_raw}_{time_raw}".upper(),
    }


def split_processing(description: str) -> tuple[str, str]:
    match = PROCESSING_START_RE.search(description)
    if not match:
        return description.strip(), ""
    display = description[: match.start()].strip(" ,._-")
    processing = description[match.start() :].strip()
    return display or description.strip(), processing


def category_from_path(path: Path, input_root: Path) -> tuple[str, str]:
    try:
        rel = path.relative_to(input_root)
    except ValueError:
        rel = path
    for part in rel.parts[:-1]:
        folder = part.upper()
        if folder in CATEGORY_MAP:
            return CATEGORY_MAP[folder], folder
    return "General", "GENERAL"
