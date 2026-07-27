#!/usr/bin/env python3
"""
Batch LUFS loudness normalization for highlight MP3 clips.

Measures and (optionally) normalizes clips to a target integrated loudness using
ffmpeg's two-pass loudnorm filter (EBU R128). Originals are NEVER modified.

Workflow
--------
1. Dry-run (default): measure all clips, write report, no file changes.
2. --execute:
   - Copy each source MP3 to archive/pre_loudness_normalize/ (once, idempotent).
   - Write normalized MP3s to highlights/audio_normalized/ (mirrored tree), or
     copy results into highlights/audio/ after review.

Production highlights/audio/ is loudness-normalized. Pre-normalize originals are
kept under archive/pre_loudness_normalize/.

Target defaults: -18 LUFS integrated, -1.5 dBFS true peak, LRA 11.
Boost is capped at +12 dB by default so quiet/windy clips are not over-amplified.
Loud clips are still attenuated to the target.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "highlights_catalog.json"
DEFAULT_REPORT_JSON = PROJECT_ROOT / "data" / "clip_loudness_normalize_report.json"
DEFAULT_REPORT_CSV = PROJECT_ROOT / "data" / "clip_loudness_normalize_report.csv"
DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "archive" / "pre_loudness_normalize"
DEFAULT_OUTPUT_AUDIO_ROOT = PROJECT_ROOT / "highlights" / "audio_normalized"

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
MP3_BITRATE = "192k"

TARGET_I = -18.0
TARGET_TP = -1.5
TARGET_LRA = 11.0
DEFAULT_MAX_GAIN_DB = 12.0  # cap boost to limit wind/ambient noise amplification

HIGH_GAIN_DB = 10.0  # flag if uncapped boost would exceed this
LOUD_INPUT_LUFS = -14.0  # flag if already loud
HOT_PEAK_DB = -0.5  # flag if input true peak near clipping

JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)

CSV_FIELDS = [
    "id",
    "title",
    "source_path",
    "archive_path",
    "output_path",
    "status",
    "input_i_lufs",
    "input_tp_db",
    "input_lra",
    "effective_target_lufs",
    "target_offset_db",
    "applied_gain_db",
    "uncapped_gain_db",
    "flags",
    "notes",
]


@dataclass
class NormalizeResult:
    id: str
    title: str
    source_path: str
    archive_path: str | None = None
    output_path: str | None = None
    status: str = "pending"  # measured, ok, skipped, failed, dry_run
    input_i_lufs: float | None = None
    input_tp_db: float | None = None
    input_lra: float | None = None
    effective_target_lufs: float | None = None
    target_offset_db: float | None = None
    applied_gain_db: float | None = None
    uncapped_gain_db: float | None = None
    flags: str = ""
    notes: str = ""
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize highlight MP3 loudness (LUFS) without touching originals.",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help=f"Catalog JSON (default: {DEFAULT_CATALOG.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--target-i",
        type=float,
        default=TARGET_I,
        help=f"Target integrated loudness in LUFS (default: {TARGET_I})",
    )
    parser.add_argument(
        "--target-tp",
        type=float,
        default=TARGET_TP,
        help=f"Target true peak in dBFS (default: {TARGET_TP})",
    )
    parser.add_argument(
        "--target-lra",
        type=float,
        default=TARGET_LRA,
        help=f"Target loudness range (default: {TARGET_LRA})",
    )
    parser.add_argument(
        "--max-gain",
        type=float,
        default=DEFAULT_MAX_GAIN_DB,
        help=(
            f"Maximum boost in dB for quiet clips (default: {DEFAULT_MAX_GAIN_DB}). "
            "Loud clips are still reduced to --target-i."
        ),
    )
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=DEFAULT_ARCHIVE_ROOT,
        help="Where to archive originals before normalization",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_AUDIO_ROOT,
        help="Normalized MP3 output directory (mirrors highlights/audio/)",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=DEFAULT_REPORT_JSON,
    )
    parser.add_argument(
        "--report-csv",
        type=Path,
        default=DEFAULT_REPORT_CSV,
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Archive originals and write normalized MP3s (default: measure only)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-normalize even if output MP3 already exists",
    )
    return parser.parse_args()


def load_catalog(catalog_path: Path) -> list[dict]:
    with catalog_path.open(encoding="utf-8") as f:
        return json.load(f)


def audio_rel_path(audio_path: str) -> Path:
    """highlights/audio/BIRDS/foo.mp3 -> BIRDS/foo.mp3"""
    prefix = "highlights/audio/"
    if audio_path.startswith(prefix):
        return Path(audio_path[len(prefix) :])
    return Path(audio_path)


def archive_dest(archive_root: Path, audio_path: str) -> Path:
    return archive_root / "highlights" / "audio" / audio_rel_path(audio_path)


def output_dest(output_root: Path, audio_path: str) -> Path:
    return output_root / audio_rel_path(audio_path)


def measure_loudnorm(
    source: Path,
    *,
    target_i: float,
    target_tp: float,
    target_lra: float,
) -> dict[str, float]:
    af = f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json"
    proc = subprocess.run(
        [
            FFMPEG,
            "-hide_banner",
            "-nostats",
            "-i",
            str(source),
            "-af",
            af,
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffmpeg loudnorm measure failed")

    combined = proc.stderr
    matches = JSON_BLOCK_RE.findall(combined)
    if not matches:
        raise RuntimeError("Could not parse loudnorm JSON from ffmpeg output")

    # Use the last JSON block (the measurement summary).
    data = json.loads(matches[-1])
    return {
        "input_i": float(data["input_i"]),
        "input_tp": float(data["input_tp"]),
        "input_lra": float(data["input_lra"]),
        "input_thresh": float(data["input_thresh"]),
        "target_offset": float(data["target_offset"]),
    }


def apply_loudnorm(
    source: Path,
    dest: Path,
    metrics: dict[str, float],
    *,
    target_i: float,
    target_tp: float,
    target_lra: float,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    af = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:"
        f"measured_I={metrics['input_i']}:"
        f"measured_TP={metrics['input_tp']}:"
        f"measured_LRA={metrics['input_lra']}:"
        f"measured_thresh={metrics['input_thresh']}:"
        f"offset={metrics['target_offset']}:"
        f"linear=true:print_format=summary"
    )
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-af",
            af,
            "-codec:a",
            "libmp3lame",
            "-b:a",
            MP3_BITRATE,
            str(dest),
        ],
        check=True,
    )


def effective_target_lufs(input_i: float, target_i: float, max_gain_db: float) -> float:
    """Cap boost for quiet clips; allow full attenuation for loud ones."""
    uncapped_gain = target_i - input_i
    if uncapped_gain > max_gain_db:
        return input_i + max_gain_db
    return target_i


def build_flags(
    metrics: dict[str, float],
    *,
    target_i: float,
    effective_i: float,
    max_gain_db: float,
) -> tuple[str, str]:
    flags: list[str] = []
    notes: list[str] = []

    uncapped_gain = target_i - metrics["input_i"]
    applied_gain = effective_i - metrics["input_i"]

    if uncapped_gain > max_gain_db:
        flags.append("gain_capped")
        notes.append(
            f"boost capped at {applied_gain:.1f} dB (would have been {uncapped_gain:.1f} dB)"
        )
    elif uncapped_gain > HIGH_GAIN_DB:
        flags.append("high_gain")
        notes.append(f"boost ~{uncapped_gain:.1f} dB — may raise background noise")
    if metrics["input_i"] > LOUD_INPUT_LUFS:
        flags.append("already_loud")
        notes.append(f"input {metrics['input_i']:.1f} LUFS — attenuated to {effective_i:.1f}")
    if metrics["input_tp"] > HOT_PEAK_DB:
        flags.append("hot_peak")
        notes.append(f"input peak {metrics['input_tp']:.1f} dBFS — limiter will engage")

    return "|".join(flags), "; ".join(notes)


def archive_source(source: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if not archive_path.exists():
        shutil.copy2(source, archive_path)


def process_clip(
    clip: dict,
    *,
    target_i: float,
    target_tp: float,
    target_lra: float,
    max_gain_db: float,
    archive_root: Path,
    output_root: Path,
    execute: bool,
    force: bool,
) -> NormalizeResult:
    clip_id = clip["id"]
    title = clip.get("title", clip_id)
    rel_audio = clip["audio_path"]
    source = PROJECT_ROOT / rel_audio

    result = NormalizeResult(
        id=clip_id,
        title=title,
        source_path=rel_audio,
    )

    if not source.is_file():
        result.status = "failed"
        result.error = f"source not found: {source}"
        return result

    archive_path = archive_dest(archive_root, rel_audio)
    output_path = output_dest(output_root, rel_audio)
    result.archive_path = str(archive_path.relative_to(PROJECT_ROOT))
    result.output_path = str(
        Path("highlights/audio_normalized") / audio_rel_path(rel_audio)
    )

    if output_path.exists() and not force and execute:
        result.status = "skipped"
        result.notes = "output exists (use --force to redo)"
        return result

    try:
        metrics = measure_loudnorm(
            source,
            target_i=target_i,
            target_tp=target_tp,
            target_lra=target_lra,
        )
    except (RuntimeError, subprocess.CalledProcessError, KeyError, ValueError) as exc:
        result.status = "failed"
        result.error = str(exc)
        return result

    effective_i = effective_target_lufs(metrics["input_i"], target_i, max_gain_db)
    uncapped_gain = target_i - metrics["input_i"]
    applied_gain = effective_i - metrics["input_i"]

    if abs(effective_i - target_i) > 0.05:
        try:
            metrics = measure_loudnorm(
                source,
                target_i=effective_i,
                target_tp=target_tp,
                target_lra=target_lra,
            )
        except (RuntimeError, subprocess.CalledProcessError, KeyError, ValueError) as exc:
            result.status = "failed"
            result.error = str(exc)
            return result

    result.input_i_lufs = round(metrics["input_i"], 2)
    result.input_tp_db = round(metrics["input_tp"], 2)
    result.input_lra = round(metrics["input_lra"], 2)
    result.effective_target_lufs = round(effective_i, 2)
    result.target_offset_db = round(metrics["target_offset"], 2)
    result.uncapped_gain_db = round(uncapped_gain, 2)
    result.applied_gain_db = round(applied_gain, 2)
    result.flags, flag_notes = build_flags(
        metrics,
        target_i=target_i,
        effective_i=effective_i,
        max_gain_db=max_gain_db,
    )
    if flag_notes:
        result.notes = flag_notes

    if not execute:
        result.status = "dry_run"
        return result

    try:
        archive_source(source, archive_path)
        apply_loudnorm(
            source,
            output_path,
            metrics,
            target_i=effective_i,
            target_tp=target_tp,
            target_lra=target_lra,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        result.status = "failed"
        result.error = str(exc)
        return result

    result.status = "ok"
    return result


def format_progress_line(
    index: int,
    total: int,
    result: NormalizeResult,
    *,
    elapsed_sec: float,
) -> str:
    gain = result.applied_gain_db
    gain_str = f"{gain:+.1f} dB" if gain is not None else "n/a"
    input_i = result.input_i_lufs
    input_str = f"{input_i:.1f} LUFS" if input_i is not None else "n/a"
    target = result.effective_target_lufs
    target_str = f"→ {target:.1f}" if target is not None else ""
    capped = " [capped]" if result.flags and "gain_capped" in result.flags else ""
    title = result.title[:45] + ("…" if len(result.title) > 45 else "")
    return (
        f"[{index}/{total}] {result.status:7s} {elapsed_sec:5.1f}s  "
        f"{input_str} {gain_str}{target_str}{capped}  {title}"
    )


def write_reports(results: list[NormalizeResult], json_path: Path, csv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(r) for r in results]
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = asdict(r)
            writer.writerow(row)

    print(f"Wrote {json_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {csv_path.relative_to(PROJECT_ROOT)}")


def print_summary(results: list[NormalizeResult], *, execute: bool) -> None:
    ok = sum(1 for r in results if r.status in ("ok", "dry_run", "measured"))
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    capped = sum(1 for r in results if "gain_capped" in (r.flags or ""))
    flagged = sum(1 for r in results if r.flags)

    mode = "EXECUTE" if execute else "DRY-RUN"
    print(f"\n=== Loudness normalize ({mode}) ===")
    print(f"Processed: {len(results)}  ok/measured: {ok}  skipped: {skipped}  failed: {failed}")
    print(f"Gain capped: {capped}  other flags: {flagged - capped}")

    if failed:
        print("\nFailures:")
        for r in results:
            if r.status == "failed":
                print(f"  {r.id}: {r.error}")

    review = [r for r in results if r.flags]
    if review:
        print("\nReview queue (sorted by |gain|):")
        review.sort(key=lambda r: abs(r.applied_gain_db or 0), reverse=True)
        for r in review[:20]:
            gain = r.applied_gain_db if r.applied_gain_db is not None else 0
            print(
                f"  {gain:+6.1f} dB  [{r.flags}]  {r.id} — {r.title[:50]}"
            )

    if not execute:
        print(
            "\nNo files written. Re-run with --execute to archive originals and "
            f"write normalized MP3s to {DEFAULT_OUTPUT_AUDIO_ROOT.relative_to(PROJECT_ROOT)}/"
        )
    else:
        print(
            f"\nOriginals archived under {DEFAULT_ARCHIVE_ROOT.relative_to(PROJECT_ROOT)}/"
        )
        print(
            f"Normalized MP3s written to {DEFAULT_OUTPUT_AUDIO_ROOT.relative_to(PROJECT_ROOT)}/"
        )
        print("highlights/audio/ is UNCHANGED — swap after sign-off.")


def main() -> int:
    args = parse_args()
    if not Path(FFMPEG).is_file():
        print(f"ffmpeg not found: {FFMPEG}", file=sys.stderr)
        return 1

    catalog = load_catalog(args.catalog)
    results: list[NormalizeResult] = []
    t0 = time.time()
    total = len(catalog)
    mode = "EXECUTE" if args.execute else "DRY-RUN"

    print(
        f"\n=== Loudness normalize ({mode}) ===\n"
        f"Clips: {total}  target: {args.target_i} LUFS  "
        f"max boost: {args.max_gain} dB  peak limit: {args.target_tp} dBFS\n",
        flush=True,
    )

    for i, clip in enumerate(catalog, 1):
        clip_t0 = time.time()
        result = process_clip(
            clip,
            target_i=args.target_i,
            target_tp=args.target_tp,
            target_lra=args.target_lra,
            max_gain_db=args.max_gain,
            archive_root=args.archive_root,
            output_root=args.output_root,
            execute=args.execute,
            force=args.force,
        )
        results.append(result)
        elapsed = time.time() - clip_t0
        print(format_progress_line(i, total, result, elapsed_sec=elapsed), flush=True)
        if result.status == "failed" and result.error:
            print(f"         error: {result.error}", flush=True)

    write_reports(results, args.report_json, args.report_csv)
    print_summary(results, execute=args.execute)
    print(f"Elapsed: {time.time() - t0:.1f}s")
    return 1 if any(r.status == "failed" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
