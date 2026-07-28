#!/usr/bin/env python3
"""
Trim leading silence from highlight MP3 clips flagged in data/reports/clip_silence_report.csv.

Uses the same RMS/silence detection as analyze_clip_silence.py. Backs up originals
to archive/trim_backups/ (mirroring highlights/audio/) before overwriting in place.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from analyze_clip_silence import (
    ABS_FLOOR_DB,
    DB_BELOW_PEAK,
    DEFAULT_REPORT,
    FRAME_LENGTH,
    HOP_LENGTH,
    measure_silence,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "archive" / "trim_backups"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
MIN_LEADING_TRIM_SEC = 0.5


@dataclass
class TrimResult:
    id: str
    audio_path: str
    status: str  # ok, skipped, failed, dry_run
    original_duration_sec: float | None = None
    new_duration_sec: float | None = None
    leading_silence_sec: float | None = None
    seconds_removed: float | None = None
    trim_start_sec: float | None = None
    error: str | None = None
    notes: str | None = None


def silent_mask(y: np.ndarray) -> np.ndarray:
    rms = librosa.feature.rms(
        y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH
    )[0]
    rms_db = librosa.amplitude_to_db(rms, ref=np.max)
    threshold_db = max(float(np.max(rms_db)) - DB_BELOW_PEAK, ABS_FLOOR_DB)
    return rms_db <= threshold_db


def first_nonsilent_frame(silent: np.ndarray) -> int | None:
    nonsilent = np.flatnonzero(~silent)
    if nonsilent.size == 0:
        return None
    return int(nonsilent[0])


def trim_start_sample(
    first_frame: int,
    sr: int,
    *,
    pre_roll_sec: float,
) -> int:
    pre_roll_samples = max(0, int(pre_roll_sec * sr))
    raw_start = first_frame * HOP_LENGTH
    return max(0, raw_start - pre_roll_samples)


def backup_audio(audio_path: Path, backup_root: Path) -> Path:
    try:
        rel = audio_path.relative_to(PROJECT_ROOT / "highlights" / "audio")
    except ValueError:
        rel = Path(audio_path.name)
    dest = backup_root / "highlights" / "audio" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(audio_path, dest)
    return dest


def write_mp3(y: np.ndarray, sr: int, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        sf.write(tmp_path, y, sr, subtype="PCM_16")
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(tmp_path),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "192k",
                "-ar",
                str(sr),
                "-ac",
                "1",
                str(dest),
            ],
            check=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


def load_flagged_rows(report_path: Path) -> list[dict[str, str]]:
    with report_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row for row in rows if "leading" in (row.get("flags") or "").split("|")]


def trim_clip(
    row: dict[str, str],
    *,
    pre_roll_sec: float,
    backup_root: Path,
    execute: bool,
) -> TrimResult:
    clip_id = row["id"]
    rel_audio = row["audio_path"]
    audio_path = PROJECT_ROOT / rel_audio

    if not audio_path.exists():
        return TrimResult(
            id=clip_id,
            audio_path=rel_audio,
            status="failed",
            error=f"missing file: {audio_path}",
        )

    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)
    except Exception as exc:  # noqa: BLE001
        return TrimResult(
            id=clip_id,
            audio_path=rel_audio,
            status="failed",
            error=f"load failed: {exc}",
        )

    original_duration = len(y) / sr
    metrics = measure_silence(y, sr)
    leading_sec = float(metrics["leading_silence_sec"])

    if leading_sec < MIN_LEADING_TRIM_SEC:
        return TrimResult(
            id=clip_id,
            audio_path=rel_audio,
            status="skipped",
            original_duration_sec=round(original_duration, 3),
            leading_silence_sec=leading_sec,
            notes=f"leading silence {leading_sec:.3f}s below trim threshold {MIN_LEADING_TRIM_SEC}s",
        )

    silent = silent_mask(y)
    first_frame = first_nonsilent_frame(silent)
    if first_frame is None:
        return TrimResult(
            id=clip_id,
            audio_path=rel_audio,
            status="skipped",
            original_duration_sec=round(original_duration, 3),
            leading_silence_sec=leading_sec,
            notes="entire clip is silent",
        )

    start_sample = trim_start_sample(first_frame, sr, pre_roll_sec=pre_roll_sec)
    if start_sample <= 0:
        return TrimResult(
            id=clip_id,
            audio_path=rel_audio,
            status="skipped",
            original_duration_sec=round(original_duration, 3),
            leading_silence_sec=leading_sec,
            notes="nothing to trim",
        )

    trim_start_sec = start_sample / sr
    seconds_removed = trim_start_sec
    trimmed = y[start_sample:]
    new_duration = len(trimmed) / sr

    if not execute:
        return TrimResult(
            id=clip_id,
            audio_path=rel_audio,
            status="dry_run",
            original_duration_sec=round(original_duration, 3),
            new_duration_sec=round(new_duration, 3),
            leading_silence_sec=leading_sec,
            seconds_removed=round(seconds_removed, 3),
            trim_start_sec=round(trim_start_sec, 3),
        )

    try:
        backup_audio(audio_path, backup_root)
        write_mp3(trimmed, sr, audio_path)
    except Exception as exc:  # noqa: BLE001
        return TrimResult(
            id=clip_id,
            audio_path=rel_audio,
            status="failed",
            original_duration_sec=round(original_duration, 3),
            error=str(exc),
        )

    verify_y, verify_sr = librosa.load(audio_path, sr=None, mono=True)
    verify_metrics = measure_silence(verify_y, verify_sr)

    return TrimResult(
        id=clip_id,
        audio_path=rel_audio,
        status="ok",
        original_duration_sec=round(original_duration, 3),
        new_duration_sec=round(len(verify_y) / verify_sr, 3),
        leading_silence_sec=leading_sec,
        seconds_removed=round(seconds_removed, 3),
        trim_start_sec=round(trim_start_sec, 3),
        notes=(
            f"new leading silence {verify_metrics['leading_silence_sec']:.3f}s"
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trim leading silence from flagged highlight MP3 clips.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Silence report CSV with flags column",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        default=DEFAULT_BACKUP_ROOT,
        help="Backup root mirroring highlights/audio/",
    )
    parser.add_argument(
        "--pre-roll",
        type=float,
        default=0.25,
        help="Seconds of audio to keep before first non-silent frame (default: 0.25)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write trimmed MP3s in place (default is dry-run)",
    )
    parser.add_argument(
        "--ids",
        nargs="*",
        help="Optional clip IDs to process (default: all leading-flagged rows)",
    )
    parser.add_argument(
        "--results-json",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "trim_leading_silence_report.json",
        help="JSON report path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.execute and not Path(FFMPEG).exists():
        print(f"error: ffmpeg not found at {FFMPEG}", file=sys.stderr)
        return 2

    rows = load_flagged_rows(args.report)
    if args.ids:
        wanted = set(args.ids)
        rows = [row for row in rows if row["id"] in wanted]

    if not rows:
        print("No leading-flagged clips to process.", file=sys.stderr)
        return 0

    results: list[TrimResult] = []
    for index, row in enumerate(rows, start=1):
        print(f"[{index}/{len(rows)}] {row['id']}", file=sys.stderr)
        results.append(
            trim_clip(
                row,
                pre_roll_sec=max(0.0, args.pre_roll),
                backup_root=args.backup_root,
                execute=args.execute,
            )
        )

    args.results_json.parent.mkdir(parents=True, exist_ok=True)
    args.results_json.write_text(
        json.dumps([asdict(result) for result in results], indent=2),
        encoding="utf-8",
    )

    print("\n=== Leading silence trim summary ===", file=sys.stderr)
    for status in ("ok", "dry_run", "skipped", "failed"):
        count = sum(1 for result in results if result.status == status)
        if count:
            print(f"{status}: {count}", file=sys.stderr)

    for result in results:
        if result.status in {"ok", "dry_run"}:
            print(
                f"  {result.id}: removed {result.seconds_removed:.3f}s "
                f"({result.original_duration_sec:.3f}s -> {result.new_duration_sec:.3f}s)",
                file=sys.stderr,
            )
        elif result.status == "skipped":
            print(f"  {result.id}: skipped — {result.notes}", file=sys.stderr)
        elif result.status == "failed":
            print(f"  {result.id}: failed — {result.error}", file=sys.stderr)

    print(f"\nReport: {args.results_json}", file=sys.stderr)
    if not args.execute:
        print("Dry-run only. Re-run with --execute to trim.", file=sys.stderr)

    failed = [result for result in results if result.status == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
