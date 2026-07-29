#!/usr/bin/env python3
"""Build data/catalog/site_names.csv from the AKR metadata spreadsheet."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.paths import CATALOG_SITE_NAMES, PROJECT_ROOT

DEFAULT_SOURCE = PROJECT_ROOT / "Complete_Metadata_AKR_2001-2025.xlsx"

# Sites not yet in the spreadsheet (new deployments, etc.)
MANUAL_ENTRIES: dict[tuple[str, str], str] = {
    ("DENA", "ROCK"): "Rock Creek",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build site_names.csv from AKR metadata spreadsheet.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Excel workbook (default: {DEFAULT_SOURCE.name})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CATALOG_SITE_NAMES,
        help=f"Output CSV path (default: {CATALOG_SITE_NAMES.relative_to(PROJECT_ROOT)})",
    )
    return parser.parse_args(argv)


def build_index(source: Path) -> dict[tuple[str, str], str]:
    df = pd.read_excel(source, sheet_name=0)
    df["unit"] = df["unit"].astype(str).str.strip().str.upper()
    df["code"] = df["code"].astype(str).str.strip().str.upper()
    df["site"] = df["site"].astype(str).str.strip()

    index: dict[tuple[str, str], str] = {}
    for _, row in df.iterrows():
        if row["unit"] in ("NAN",) or row["code"] in ("NAN",):
            continue
        key = (row["unit"], row["code"])
        if key not in index:
            index[key] = row["site"]

    index.update(MANUAL_ENTRIES)
    return index


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source.resolve()
    output = args.output.resolve()

    if not source.is_file():
        print(f"Source not found: {source}", file=sys.stderr)
        return 1

    index = build_index(source)
    rows = sorted(
        (
            {"park_code": park, "site_code": site, "site_name": name}
            for (park, site), name in index.items()
        ),
        key=lambda row: (row["park_code"], row["site_code"]),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["park_code", "site_code", "site_name"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} site name(s) to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
