#!/usr/bin/env python3
"""
Match cardinal-direction site photos to highlight clips and copy WebP assets
into highlights/site_photos/.

Photos are optional per clip. Catalog fields:
- ``site_photo_path`` → ``highlights/site_photos/{clip_id}.webp``
- ``site_photo_year`` → year the site photo was taken (when known)

Matching (from NPS cardinal photo composites on the ADSB volume):
- Site key = park_code + site_code (e.g. DENATOKO).
- Prefer a source photo from the same calendar year as ``recorded_date``.
- If none from that year, use any photo for the site (closest date to the recording).

You can also drop ``{clip_id}.webp`` (or .jpg/.png) into highlights/site_photos/
manually; re-run with ``--sync-catalog`` to refresh paths without re-copying.

Source default:
  /Volumes/NPS_ADSB_Data/E_Ruebush_2026_Files/cardinal_photos/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "catalog" / "highlights.json"
DEFAULT_SOURCE = Path(
    "/Volumes/NPS_ADSB_Data/E_Ruebush_2026_Files/cardinal_photos"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "highlights" / "site_photos"
PHOTO_PREFIX = "CardinalPhotoComposite_"
MAX_WIDTH = 1200
WEBP_QUALITY = 82
SUPPORTED_EXT = {".webp", ".jpg", ".jpeg", ".png"}


@dataclass
class PhotoMatch:
    clip_id: str
    site_key: str
    recorded_year: str | None
    photo_year: str | None
    source: str | None
    output: str | None
    status: str  # ok, skipped, no_source, missing_site, failed, dry_run
    notes: str | None = None


def load_catalog(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def site_key(clip: dict) -> str | None:
    park = clip.get("park_code")
    site = clip.get("site_code")
    if park and site:
        return f"{park}{site}"
    return None


def parse_site_key_from_filename(name: str) -> str | None:
    stem = name
    if stem.startswith(PHOTO_PREFIX):
        stem = stem[len(PHOTO_PREFIX) :]
    if stem.lower().endswith(".jpg"):
        stem = stem[:-4]
    match = re.match(r"^([A-Z]{4})(.+)$", stem)
    if not match:
        return None
    park, rest = match.group(1), match.group(2)
    site_part = re.split(r"[_]", rest)[0]
    site_part = re.sub(r"\d{4}$", "", site_part)
    return park + site_part


def dates_in_filename(name: str) -> list[str]:
    return re.findall(r"(20\d{6})", name)


def years_in_filename(name: str) -> set[str]:
    years = {date[:4] for date in dates_in_filename(name)}
    for match in re.finditer(r"(?<=[A-Z])\d{4}(?=[_.])", name):
        years.add(match.group(0))
    return years


def index_source_photos(source_dir: Path) -> dict[str, list[Path]]:
    by_site: dict[str, list[Path]] = {}
    if not source_dir.is_dir():
        return by_site
    for path in sorted(source_dir.glob("CardinalPhotoComposite_*.jpg")):
        key = parse_site_key_from_filename(path.name)
        if key:
            by_site.setdefault(key, []).append(path)
    return by_site


def best_date_in_file(path: Path, record_ymd: str | None) -> str | None:
    file_dates = dates_in_filename(path.name)
    if not file_dates:
        return None
    if record_ymd:
        return min(file_dates, key=lambda d: abs(int(d) - int(record_ymd)))
    return max(file_dates)


def photo_year_from_source(path: Path, record_ymd: str | None = None) -> str | None:
    best = best_date_in_file(path, record_ymd)
    if best:
        return best[:4]
    years = years_in_filename(path.name)
    return max(years) if years else None


def pick_source_for_year(candidates: list[Path], recorded_date: str | None) -> Path | None:
    if not candidates or not recorded_date:
        return None

    record_year = recorded_date[:4]
    record_ymd = recorded_date.replace("-", "")
    in_year = [path for path in candidates if record_year in years_in_filename(path.name)]
    if not in_year:
        return None

    dated: list[tuple[Path, str]] = []
    for path in in_year:
        best = best_date_in_file(path, record_ymd) or f"{record_year}0101"
        dated.append((path, best))

    return min(dated, key=lambda item: abs(int(item[1]) - int(record_ymd)))[0]


def pick_source_for_site(candidates: list[Path], recorded_date: str | None) -> Path | None:
    if not candidates:
        return None
    if not recorded_date:
        return max(candidates, key=lambda path: path.stat().st_mtime)

    record_ymd = recorded_date.replace("-", "")
    dated: list[tuple[Path, str]] = []
    for path in candidates:
        best = best_date_in_file(path, record_ymd)
        if best:
            dated.append((path, best))

    if dated:
        return min(dated, key=lambda item: abs(int(item[1]) - int(record_ymd)))[0]
    return max(candidates, key=lambda path: path.stat().st_size)


def pick_source(candidates: list[Path], recorded_date: str | None) -> tuple[Path | None, str | None]:
    if not candidates:
        return None, None

    record_ymd = recorded_date.replace("-", "") if recorded_date else None
    source = pick_source_for_year(candidates, recorded_date)
    if source is None:
        source = pick_source_for_site(candidates, recorded_date)
    if source is None:
        return None, None
    return source, photo_year_from_source(source, record_ymd)


def output_path_for_clip(output_root: Path, clip_id: str) -> Path:
    return output_root / f"{clip_id}.webp"


def existing_site_photo(output_root: Path, clip_id: str) -> Path | None:
    for ext in SUPPORTED_EXT:
        candidate = output_root / f"{clip_id}{ext}"
        if candidate.is_file():
            return candidate
    return None


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
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def sync_catalog_paths(
    catalog: list[dict],
    output_root: Path,
    photo_years: dict[str, str | None] | None = None,
) -> tuple[list[dict], int]:
    matched = 0
    for clip in catalog:
        clip_id = clip["id"]
        existing = existing_site_photo(output_root, clip_id)
        if existing:
            clip["site_photo_path"] = repo_relative(existing)
            if photo_years is not None:
                clip["site_photo_year"] = photo_years.get(clip_id)
            matched += 1
        else:
            clip["site_photo_path"] = None
            if photo_years is not None:
                clip["site_photo_year"] = None
    return catalog, matched


def process_clip(
    clip: dict,
    *,
    source_by_site: dict[str, list[Path]],
    output_root: Path,
    execute: bool,
    force: bool,
) -> PhotoMatch:
    clip_id = clip["id"]
    key = site_key(clip)
    recorded_date = clip.get("recorded_date")
    dest = output_path_for_clip(output_root, clip_id)

    if not key:
        return PhotoMatch(
            clip_id=clip_id,
            site_key="",
            recorded_year=recorded_date[:4] if recorded_date else None,
            photo_year=None,
            source=None,
            output=None,
            status="missing_site",
        )

    record_year = recorded_date[:4] if recorded_date else None
    candidates = source_by_site.get(key, [])
    source, photo_year = pick_source(candidates, recorded_date)

    if not source:
        existing = existing_site_photo(output_root, clip_id)
        if existing:
            return PhotoMatch(
                clip_id=clip_id,
                site_key=key,
                recorded_year=record_year,
                photo_year=clip.get("site_photo_year"),
                source=None,
                output=repo_relative(existing),
                status="skipped",
                notes="manual file already present",
            )
        return PhotoMatch(
            clip_id=clip_id,
            site_key=key,
            recorded_year=record_year,
            photo_year=None,
            source=None,
            output=None,
            status="no_source",
        )

    if dest.exists() and not force:
        return PhotoMatch(
            clip_id=clip_id,
            site_key=key,
            recorded_year=record_year,
            photo_year=photo_year,
            source=str(source),
            output=repo_relative(dest),
            status="skipped",
            notes="output exists (use --force)",
        )

    if not execute:
        return PhotoMatch(
            clip_id=clip_id,
            site_key=key,
            recorded_year=record_year,
            photo_year=photo_year,
            source=str(source),
            output=repo_relative(dest),
            status="dry_run",
        )

    try:
        encode_webp(source, dest)
    except OSError as exc:
        return PhotoMatch(
            clip_id=clip_id,
            site_key=key,
            recorded_year=record_year,
            photo_year=photo_year,
            source=str(source),
            output=None,
            status="failed",
            notes=str(exc),
        )

    return PhotoMatch(
        clip_id=clip_id,
        site_key=key,
        recorded_year=record_year,
        photo_year=photo_year,
        source=str(source),
        output=repo_relative(dest),
        status="ok",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build site photo WebPs for highlight clips.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute", action="store_true", help="Write WebP files and update catalog")
    parser.add_argument("--force", action="store_true", help="Overwrite existing WebP outputs")
    parser.add_argument(
        "--sync-catalog",
        action="store_true",
        help="Only refresh site_photo_path from files in highlights/site_photos/",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "site_photos_report.json",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    catalog_path = args.catalog.resolve()
    output_root = args.output.resolve()
    catalog = load_catalog(catalog_path)

    if args.sync_catalog and not args.execute:
        catalog, matched = sync_catalog_paths(catalog, output_root)
        catalog_path.write_text(
            json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Synced catalog: {matched}/{len(catalog)} clips have site_photo_path")
        return 0

    source_by_site = index_source_photos(args.source.resolve())
    if not source_by_site and not args.sync_catalog:
        print(f"Warning: no source photos found at {args.source}", file=sys.stderr)

    results: list[PhotoMatch] = []
    for clip in catalog:
        results.append(
            process_clip(
                clip,
                source_by_site=source_by_site,
                output_root=output_root,
                execute=args.execute,
                force=args.force,
            )
        )

    if args.execute:
        photo_years = {
            result.clip_id: result.photo_year
            for result in results
            if result.output
        }
        catalog, matched = sync_catalog_paths(catalog, output_root, photo_years)
        catalog_path.write_text(
            json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Updated catalog: {matched}/{len(catalog)} clips with site_photo_path")

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    print("\n=== Site photos summary ===")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    failures = [r for r in results if r.status == "failed"]
    if failures:
        print("\nFailures:")
        for result in failures:
            print(f"  {result.clip_id}: {result.notes}")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps([asdict(r) for r in results], indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nReport: {args.report}")

    if not args.execute:
        print("\nDry-run only. Re-run with --execute to write WebPs and update the catalog.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
