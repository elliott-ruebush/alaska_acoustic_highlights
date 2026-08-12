#!/usr/bin/env python3
"""
Build site photo WebP assets and maintain the site photo catalog.

Photos are first-class entities in ``data/catalog/site_photos.json``. Clips
reference a photo via ``site_photo_id`` (closest ``taken_date`` to
``recorded_date`` at the same site).

Workflow:
1. Copy cardinal sources (or ingest drops) → ``highlights/site_photos/{photo_id}.webp``
2. Build/update ``data/catalog/site_photos.json`` from disk + sources
3. Assign ``site_photo_id`` on each clip in ``data/catalog/highlights.json``

Use ``--sync-catalog`` to rescan ``highlights/site_photos/`` and reassign clip
ids without re-copying from external sources.

Source default:
  /Volumes/NPS_ADSB_Data/E_Ruebush_2026_Files/cardinal_photos/
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.paths import CATALOG_HIGHLIGHTS, CATALOG_SITE_PHOTOS, HIGHLIGHTS_SITE_PHOTOS, PROJECT_ROOT
from lib.site_photos import (
    assign_site_photo_ids,
    build_catalog_from_sources,
    encode_webp,
    index_source_photos,
    load_site_photos_catalog,
    merge_photo_records,
    output_path_for_photo,
    photo_record_from_filename,
    repo_relative,
    scan_photo_files,
    write_site_photos_catalog,
)

DEFAULT_CATALOG = CATALOG_HIGHLIGHTS
DEFAULT_SOURCE = Path(
    "/Volumes/NPS_ADSB_Data/E_Ruebush_2026_Files/cardinal_photos"
)
DEFAULT_OUTPUT = HIGHLIGHTS_SITE_PHOTOS


@dataclass
class PhotoCopyResult:
    photo_id: str
    site_key: str
    taken_date: str
    source: str | None
    output: str | None
    status: str  # ok, skipped, no_meta, failed, dry_run
    notes: str | None = None


def load_catalog(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_catalog(path: Path, clips: list[dict]) -> None:
    path.write_text(json.dumps(clips, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def copy_source_photo(
    source: Path,
    output_root: Path,
    *,
    execute: bool,
    force: bool,
) -> PhotoCopyResult:
    meta = photo_record_from_filename(source.name)
    if not meta:
        return PhotoCopyResult(
            photo_id=source.stem,
            site_key="",
            taken_date="",
            source=str(source),
            output=None,
            status="no_meta",
            notes="could not parse photo metadata from filename",
        )

    photo_id = meta["id"]
    dest = output_path_for_photo(output_root, photo_id)
    output_rel = repo_relative(dest)

    if dest.exists() and not force:
        return PhotoCopyResult(
            photo_id=photo_id,
            site_key=meta["site_key"],
            taken_date=meta["taken_date"],
            source=str(source),
            output=output_rel,
            status="skipped",
            notes="output exists (use --force)",
        )

    if not execute:
        return PhotoCopyResult(
            photo_id=photo_id,
            site_key=meta["site_key"],
            taken_date=meta["taken_date"],
            source=str(source),
            output=output_rel,
            status="dry_run",
        )

    try:
        encode_webp(source, dest)
    except OSError as exc:
        return PhotoCopyResult(
            photo_id=photo_id,
            site_key=meta["site_key"],
            taken_date=meta["taken_date"],
            source=str(source),
            output=None,
            status="failed",
            notes=str(exc),
        )

    return PhotoCopyResult(
        photo_id=photo_id,
        site_key=meta["site_key"],
        taken_date=meta["taken_date"],
        source=str(source),
        output=output_rel,
        status="ok",
    )


def sync_catalog(
    *,
    catalog_path: Path,
    photos_path: Path,
    output_root: Path,
    catalog: list[dict] | None = None,
    execute: bool = True,
) -> tuple[list[dict], list[dict], int]:
    if catalog is None:
        catalog = load_catalog(catalog_path)

    photos = scan_photo_files(output_root)
    assign_site_photo_ids(catalog, photos)

    assigned = sum(1 for clip in catalog if clip.get("site_photo_id"))

    if execute:
        write_site_photos_catalog(photos, photos_path)
        write_catalog(catalog_path, catalog)

    return catalog, photos, assigned


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build site photo WebPs and update catalogs.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--photos-catalog", type=Path, default=CATALOG_SITE_PHOTOS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute", action="store_true", help="Write files and update catalogs")
    parser.add_argument("--force", action="store_true", help="Overwrite existing WebP outputs")
    parser.add_argument(
        "--sync-catalog",
        action="store_true",
        help="Rescan highlights/site_photos/, rebuild site_photos.json, reassign clip ids",
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
    photos_path = args.photos_catalog.resolve()
    output_root = args.output.resolve()
    catalog = load_catalog(catalog_path)

    if args.sync_catalog:
        _, photos, assigned = sync_catalog(
            catalog_path=catalog_path,
            photos_path=photos_path,
            output_root=output_root,
            catalog=catalog,
            execute=args.execute,
        )
        if args.execute:
            print(
                f"Synced catalogs: {len(photos)} photo(s), "
                f"{assigned}/{len(catalog)} clip(s) with site_photo_id"
            )
        else:
            print(
                f"Dry-run sync: would write {len(photos)} photo(s), "
                f"assign {assigned}/{len(catalog)} clip(s)"
            )
            print("\nRe-run with --execute to apply.")
        return 0

    source_by_site = index_source_photos(args.source.resolve())
    source_paths = [path for paths in source_by_site.values() for path in paths]
    if not source_paths:
        print(f"Warning: no source photos found at {args.source}", file=sys.stderr)

    results: list[PhotoCopyResult] = []
    for source in source_paths:
        results.append(
            copy_source_photo(
                source,
                output_root,
                execute=args.execute,
                force=args.force,
            )
        )

    source_records = build_catalog_from_sources(source_by_site)
    disk_records = scan_photo_files(output_root) if output_root.is_dir() else []
    photos = merge_photo_records(
        load_site_photos_catalog(photos_path),
        merge_photo_records(source_records, disk_records),
    )

    if args.execute:
        photos = merge_photo_records(photos, scan_photo_files(output_root))
        assign_site_photo_ids(catalog, photos)
        write_site_photos_catalog(photos, photos_path)
        write_catalog(catalog_path, catalog)
        assigned = sum(1 for clip in catalog if clip.get("site_photo_id"))
        print(
            f"Updated catalogs: {len(photos)} photo(s), "
            f"{assigned}/{len(catalog)} clip(s) with site_photo_id"
        )

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    print("\n=== Site photos summary ===")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    failures = [result for result in results if result.status == "failed"]
    if failures:
        print("\nFailures:")
        for result in failures:
            print(f"  {result.photo_id}: {result.notes}")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps([asdict(result) for result in results], indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nReport: {args.report}")

    if not args.execute:
        print("\nDry-run only. Re-run with --execute to write WebPs and update catalogs.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
