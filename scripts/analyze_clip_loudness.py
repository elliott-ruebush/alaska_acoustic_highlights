#!/usr/bin/env python3
"""
Analyze volume balance across NPS acoustic highlight clips.

Measures per-clip loudness (RMS dBFS; LUFS if pyloudnorm is available), peak level,
and dynamic-range proxy. Writes data/reports/clip_loudness_report.csv and prints summary stats.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import librosa
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "catalog" / "highlights.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "reports" / "clip_loudness_report.csv"

LOUDNESS_STD_THRESHOLD = 2.0
PEAK_CLIP_THRESHOLD_DB = -1.0
VERY_QUIET_LUFS_THRESHOLD = -30.0
VERY_QUIET_RMS_THRESHOLD_DB = -40.0

try:
    import pyloudnorm as pyln

    HAS_PYLOUDNORM = True
except ImportError:
    HAS_PYLOUDNORM = False


@dataclass
class ClipMetrics:
    id: str
    title: str
    duration_sec: float
    integrated_lufs: float | None = None
    rms_db: float | None = None
    peak_db: float | None = None
    dynamic_range_db: float | None = None
    flags: list[str] = field(default_factory=list)
    notes: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze loudness balance for highlight MP3 clips.",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help=f"Highlights catalog JSON (default: {DEFAULT_CATALOG.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV report path (default: {DEFAULT_OUTPUT.relative_to(PROJECT_ROOT)})",
    )
    return parser.parse_args()


def db_from_amplitude(amplitude: float) -> float:
    if amplitude <= 0:
        return float("-inf")
    return float(20.0 * np.log10(amplitude))


def measure_clip(audio_path: Path, catalog_duration: float | None) -> ClipMetrics:
    entry_id = audio_path.stem
    title = audio_path.stem
    notes: list[str] = []

    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    duration_sec = len(y) / sr if sr else 0.0
    if catalog_duration is not None and abs(duration_sec - catalog_duration) > 0.5:
        notes.append(f"duration mismatch (file={duration_sec:.1f}s)")

    rms = float(np.sqrt(np.mean(np.square(y))))
    peak = float(np.max(np.abs(y)))
    rms_db = db_from_amplitude(rms)
    peak_db = db_from_amplitude(peak)
    dynamic_range_db = peak_db - rms_db if np.isfinite(peak_db) and np.isfinite(rms_db) else None

    integrated_lufs: float | None = None
    if HAS_PYLOUDNORM:
        meter = pyln.Meter(sr)
        integrated_lufs = float(meter.integrated_loudness(y))
    else:
        notes.append("LUFS unavailable (pyloudnorm not installed); using RMS dBFS")

    return ClipMetrics(
        id=entry_id,
        title=title,
        duration_sec=round(duration_sec, 2),
        integrated_lufs=round(integrated_lufs, 2) if integrated_lufs is not None else None,
        rms_db=round(rms_db, 2) if np.isfinite(rms_db) else None,
        peak_db=round(peak_db, 2) if np.isfinite(peak_db) else None,
        dynamic_range_db=round(dynamic_range_db, 2) if dynamic_range_db is not None else None,
        notes="; ".join(notes),
    )


def loudness_value(metrics: ClipMetrics) -> float | None:
    if metrics.integrated_lufs is not None:
        return metrics.integrated_lufs
    return metrics.rms_db


def flag_outliers(results: list[ClipMetrics]) -> None:
    values = [v for m in results if (v := loudness_value(m)) is not None]
    if not values:
        return

    mean = float(np.mean(values))
    std = float(np.std(values))
    median = float(np.median(values))

    for metrics in results:
        value = loudness_value(metrics)
        flags: list[str] = []

        if value is not None and std > 0:
            z = (value - mean) / std
            if z > LOUDNESS_STD_THRESHOLD:
                flags.append("loud_outlier")
            elif z < -LOUDNESS_STD_THRESHOLD:
                flags.append("quiet_outlier")

        if metrics.peak_db is not None and metrics.peak_db >= PEAK_CLIP_THRESHOLD_DB:
            flags.append("clipping_risk")

        if metrics.integrated_lufs is not None:
            if metrics.integrated_lufs < VERY_QUIET_LUFS_THRESHOLD:
                flags.append("very_quiet")
        elif metrics.rms_db is not None and metrics.rms_db < VERY_QUIET_RMS_THRESHOLD_DB:
            flags.append("very_quiet")

        metrics.flags = flags

        if not metrics.notes and median is not None and value is not None:
            metrics.notes = f"delta_from_median={value - median:+.1f} dB"


def write_csv(results: list[ClipMetrics], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "title",
                "duration_sec",
                "integrated_lufs",
                "rms_db",
                "peak_db",
                "dynamic_range_db",
                "flags",
                "notes",
            ],
        )
        writer.writeheader()
        for metrics in results:
            writer.writerow(
                {
                    "id": metrics.id,
                    "title": metrics.title,
                    "duration_sec": metrics.duration_sec,
                    "integrated_lufs": metrics.integrated_lufs if metrics.integrated_lufs is not None else "",
                    "rms_db": metrics.rms_db if metrics.rms_db is not None else "",
                    "peak_db": metrics.peak_db if metrics.peak_db is not None else "",
                    "dynamic_range_db": metrics.dynamic_range_db if metrics.dynamic_range_db is not None else "",
                    "flags": ";".join(metrics.flags),
                    "notes": metrics.notes,
                }
            )


def print_summary(results: list[ClipMetrics], metric_label: str) -> None:
    values = [(m, v) for m in results if (v := loudness_value(m)) is not None]
    if not values:
        print("No loudness values computed.")
        return

    loudness_values = [v for _, v in values]
    median = float(np.median(loudness_values))
    min_val = float(np.min(loudness_values))
    max_val = float(np.max(loudness_values))

    outlier_count = sum(1 for m in results if m.flags)
    loud_outliers = sum(1 for m in results if "loud_outlier" in m.flags)
    quiet_outliers = sum(1 for m in results if "quiet_outlier" in m.flags)
    clipping = sum(1 for m in results if "clipping_risk" in m.flags)
    very_quiet = sum(1 for m in results if "very_quiet" in m.flags)

    sorted_by_loudness = sorted(values, key=lambda item: item[1])

    print(f"\n=== Loudness Summary ({metric_label}) ===")
    print(f"Clips analyzed: {len(results)}")
    print(f"Median: {median:.2f} dB")
    print(f"Range: {min_val:.2f} to {max_val:.2f} dB (span {max_val - min_val:.2f} dB)")
    print(f"Mean: {np.mean(loudness_values):.2f} dB, Std: {np.std(loudness_values):.2f} dB")
    print(
        f"Outliers: {outlier_count} clips flagged "
        f"({loud_outliers} loud, {quiet_outliers} quiet, {clipping} clipping risk, {very_quiet} very quiet)"
    )

    print("\n--- 10 Quietest ---")
    for metrics, value in sorted_by_loudness[:10]:
        flag_str = f" [{','.join(metrics.flags)}]" if metrics.flags else ""
        print(f"  {value:7.2f} dB  {metrics.id[:40]}{flag_str}")

    print("\n--- 10 Loudest ---")
    for metrics, value in sorted_by_loudness[-10:][::-1]:
        flag_str = f" [{','.join(metrics.flags)}]" if metrics.flags else ""
        print(f"  {value:7.2f} dB  {metrics.id[:40]}{flag_str}")


def main() -> int:
    args = parse_args()
    catalog_path: Path = args.catalog
    output_path: Path = args.output

    if not catalog_path.is_file():
        print(f"Catalog not found: {catalog_path}", file=sys.stderr)
        return 1

    with catalog_path.open(encoding="utf-8") as handle:
        catalog = json.load(handle)

    results: list[ClipMetrics] = []
    errors: list[str] = []

    for entry in catalog:
        audio_rel = entry.get("audio_path")
        if not audio_rel:
            errors.append(f"{entry.get('id', '?')}: missing audio_path")
            continue

        audio_path = PROJECT_ROOT / audio_rel
        if not audio_path.is_file():
            errors.append(f"{entry.get('id', '?')}: file not found ({audio_rel})")
            continue

        try:
            metrics = measure_clip(audio_path, entry.get("duration_sec"))
            metrics.id = entry.get("id", metrics.id)
            metrics.title = entry.get("title", metrics.title)
            results.append(metrics)
        except Exception as exc:  # noqa: BLE001 - collect per-file errors for batch report
            errors.append(f"{entry.get('id', '?')}: {exc}")

    flag_outliers(results)
    write_csv(results, output_path)

    metric_label = "LUFS" if HAS_PYLOUDNORM else "RMS dBFS"
    print(f"Wrote {output_path} ({len(results)} clips)")
    if errors:
        print(f"\nErrors ({len(errors)}):", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)

    print_summary(results, metric_label)
    if not HAS_PYLOUDNORM:
        print(
            "\nNote: pyloudnorm not installed; report uses RMS dBFS as loudness proxy. "
            "LUFS accounts for perceptual weighting and is preferred for normalization targets."
        )

    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
