#!/usr/bin/env python3
"""
Analyze highlight MP3 clips for leading/trailing silence and internal dead-air gaps.

Methodology
-----------
- Load each clip mono at native sample rate via librosa.
- Compute frame-wise RMS (frame_length=2048, hop_length=512 ≈ 11.6 ms resolution).
- Convert RMS to dB relative to the clip peak (peak frame = 0 dB).
- Adaptive silence threshold: peak RMS − 40 dB, floored at −55 dB so very quiet
  clips still have a sensible absolute cutoff.
- Leading/trailing silence: contiguous silent frames from each end.
- Internal gaps: longest contiguous silent run between the first and last
  non-silent frames (excludes edge silence).
- Flag when leading OR trailing silence ≥ 1.0 s, or max internal gap ≥ 3.0 s.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import librosa
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "catalog" / "highlights.json"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "reports" / "clip_silence_report.csv"

FRAME_LENGTH = 2048
HOP_LENGTH = 512
DB_BELOW_PEAK = 40.0
ABS_FLOOR_DB = -55.0
LEADING_TRAILING_FLAG_SEC = 1.0
INTERNAL_GAP_FLAG_SEC = 3.0

CSV_FIELDS = [
    "id",
    "title",
    "audio_path",
    "duration_sec",
    "leading_silence_sec",
    "trailing_silence_sec",
    "max_internal_gap_sec",
    "flags",
    "notes",
]


def measure_silence(y: np.ndarray, sr: int) -> dict[str, float]:
    rms = librosa.feature.rms(
        y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH
    )[0]
    rms_db = librosa.amplitude_to_db(rms, ref=np.max)
    threshold_db = max(float(np.max(rms_db)) - DB_BELOW_PEAK, ABS_FLOOR_DB)
    silent = rms_db <= threshold_db

    frame_dur = HOP_LENGTH / sr

    leading_frames = 0
    for is_silent in silent:
        if not is_silent:
            break
        leading_frames += 1

    trailing_frames = 0
    for is_silent in reversed(silent):
        if not is_silent:
            break
        trailing_frames += 1

    max_gap_frames = 0
    nonsilent = np.flatnonzero(~silent)
    if nonsilent.size > 0:
        first_active = int(nonsilent[0])
        last_active = int(nonsilent[-1])
        gap_len = 0
        for is_silent in silent[first_active : last_active + 1]:
            if is_silent:
                gap_len += 1
                max_gap_frames = max(max_gap_frames, gap_len)
            else:
                gap_len = 0

    return {
        "duration_sec": round(len(y) / sr, 3),
        "leading_silence_sec": round(leading_frames * frame_dur, 3),
        "trailing_silence_sec": round(trailing_frames * frame_dur, 3),
        "max_internal_gap_sec": round(max_gap_frames * frame_dur, 3),
    }


def build_flags(metrics: dict[str, float]) -> tuple[str, str]:
    flags: list[str] = []
    notes: list[str] = []

    if metrics["leading_silence_sec"] >= LEADING_TRAILING_FLAG_SEC:
        flags.append("leading")
        notes.append(f"leading silence {metrics['leading_silence_sec']:.2f}s")
    if metrics["trailing_silence_sec"] >= LEADING_TRAILING_FLAG_SEC:
        flags.append("trailing")
        notes.append(f"trailing silence {metrics['trailing_silence_sec']:.2f}s")
    if metrics["max_internal_gap_sec"] >= INTERNAL_GAP_FLAG_SEC:
        flags.append("internal_gap")
        notes.append(f"internal gap {metrics['max_internal_gap_sec']:.2f}s")

    return "|".join(flags), "; ".join(notes)


def severity_score(row: dict[str, object]) -> float:
    return max(
        float(row["leading_silence_sec"]),
        float(row["trailing_silence_sec"]),
        float(row["max_internal_gap_sec"]),
    )


def analyze_catalog(catalog_path: Path, report_path: Path, top_n: int) -> list[dict]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows: list[dict] = []

    for index, entry in enumerate(catalog, start=1):
        audio_path = PROJECT_ROOT / entry["audio_path"]
        print(f"[{index}/{len(catalog)}] {entry['id']}", file=sys.stderr)

        row: dict[str, object] = {
            "id": entry["id"],
            "title": entry["title"],
            "audio_path": entry["audio_path"],
            "duration_sec": None,
            "leading_silence_sec": None,
            "trailing_silence_sec": None,
            "max_internal_gap_sec": None,
            "flags": "",
            "notes": "",
        }

        if not audio_path.exists():
            row["notes"] = f"missing file: {audio_path}"
            rows.append(row)
            continue

        try:
            y, sr = librosa.load(audio_path, sr=None, mono=True)
            metrics = measure_silence(y, sr)
            flags, notes = build_flags(metrics)
            row.update(metrics)
            row["flags"] = flags
            row["notes"] = notes
        except Exception as exc:  # noqa: BLE001 - per-file failure should not abort batch
            row["notes"] = f"error: {exc}"

        rows.append(row)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    flagged = [row for row in rows if row["flags"]]
    flagged.sort(key=severity_score, reverse=True)

    print("\n=== Clip silence analysis summary ===", file=sys.stderr)
    print(f"Analyzed: {len(rows)}", file=sys.stderr)
    print(f"Flagged:  {len(flagged)}", file=sys.stderr)
    print(
        f"Threshold: peak RMS − {DB_BELOW_PEAK:.0f} dB "
        f"(floor {ABS_FLOOR_DB:.0f} dB); "
        f"edge flag ≥ {LEADING_TRAILING_FLAG_SEC:.1f}s; "
        f"gap flag ≥ {INTERNAL_GAP_FLAG_SEC:.1f}s",
        file=sys.stderr,
    )
    print(f"Report: {report_path}", file=sys.stderr)

    print(f"\nTop {min(top_n, len(flagged))} worst offenders:")
    for rank, row in enumerate(flagged[:top_n], start=1):
        print(
            f"{rank:2d}. [{row['flags']}] {row['id']} — {row['title']}\n"
            f"    leading={row['leading_silence_sec']:.3f}s "
            f"trailing={row['trailing_silence_sec']:.3f}s "
            f"max_gap={row['max_internal_gap_sec']:.3f}s "
            f"({row['duration_sec']:.1f}s total)"
        )
        if row["notes"]:
            print(f"    {row['notes']}")

    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect leading/trailing silence and internal gaps in highlight clips."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help="Path to highlights catalog JSON",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Output CSV report path",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="Number of worst flagged clips to print",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analyze_catalog(args.catalog, args.report, args.top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
