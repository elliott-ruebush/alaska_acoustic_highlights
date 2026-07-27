#!/usr/bin/env python3
"""
Transcode WAV files in the highlights set to MP3 for web hosting.

Run spectrogram generation from WAV first, then use this script to produce
compressed audio for the site. Pre-rendered spectrogram PNGs are unaffected.

Default is dry-run. Use --execute to write MP3s; add --remove-wav only after
you have verified the MP3s and rebuilt the catalog.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "highlights" / "audio"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "transcode_highlights_report.csv"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


@dataclass
class TranscodeResult:
    source: str
    output: str
    source_mb: float
    output_mb: float | None
    pct_reduction: float | None
    encode_seconds: float | None
    status: str  # ok, skipped, dry_run, failed
    error: str | None = None


def find_wav_files(input_root: Path) -> list[Path]:
    return sorted(
        path
        for path in input_root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".wav"
    )


def transcode_wav_to_mp3(
    source: Path,
    dest: Path,
    *,
    bitrate: str,
    execute: bool,
) -> TranscodeResult:
    source_mb = source.stat().st_size / (1024 * 1024)
    rel_source = str(source)
    rel_dest = str(dest)

    if dest.exists() and dest.stat().st_mtime >= source.stat().st_mtime:
        out_mb = dest.stat().st_size / (1024 * 1024)
        pct = (1 - dest.stat().st_size / source.stat().st_size) * 100
        return TranscodeResult(
            source=rel_source,
            output=rel_dest,
            source_mb=round(source_mb, 2),
            output_mb=round(out_mb, 2),
            pct_reduction=round(pct, 1),
            encode_seconds=None,
            status="skipped",
        )

    if not execute:
        return TranscodeResult(
            source=rel_source,
            output=rel_dest,
            source_mb=round(source_mb, 2),
            output_mb=None,
            pct_reduction=None,
            encode_seconds=None,
            status="dry_run",
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    try:
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                bitrate,
                "-ar",
                "44100",
                "-ac",
                "1",
                str(dest),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        return TranscodeResult(
            source=rel_source,
            output=rel_dest,
            source_mb=round(source_mb, 2),
            output_mb=None,
            pct_reduction=None,
            encode_seconds=None,
            status="failed",
            error=str(exc),
        )

    elapsed = time.perf_counter() - t0
    out_mb = dest.stat().st_size / (1024 * 1024)
    pct = (1 - dest.stat().st_size / source.stat().st_size) * 100
    return TranscodeResult(
        source=rel_source,
        output=rel_dest,
        source_mb=round(source_mb, 2),
        output_mb=round(out_mb, 2),
        pct_reduction=round(pct, 1),
        encode_seconds=round(elapsed, 2),
        status="ok",
    )


def write_report(path: Path, results: list[TranscodeResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source",
                "output",
                "source_mb",
                "output_mb",
                "pct_reduction",
                "encode_seconds",
                "status",
                "error",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))


def print_summary(results: list[TranscodeResult], *, removed_wav: int) -> None:
    by_status = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    src_mb = sum(r.source_mb for r in results)
    out_mb = sum(r.output_mb or 0 for r in results if r.status in {"ok", "skipped"})

    print("\n=== Highlights transcode summary ===\n")
    print(f"WAV files found:     {len(results)}")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")
    print(f"Source WAV total:    {src_mb:.1f} MB")
    if out_mb:
        print(f"Output MP3 total:    {out_mb:.1f} MB (existing + new)")
    if removed_wav:
        print(f"WAV files removed:   {removed_wav}")

    failures = [r for r in results if r.status == "failed"]
    if failures:
        print("\nFailures:")
        for r in failures:
            print(f"  - {r.source}: {r.error}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcode highlight WAV files to MP3 for web hosting.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Audio root (default: {DEFAULT_INPUT.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--bitrate",
        default="192k",
        help="MP3 bitrate (default: 192k)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually transcode (default is dry-run)",
    )
    parser.add_argument(
        "--remove-wav",
        action="store_true",
        help="Delete source WAV after successful transcode (requires --execute)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-encode even if MP3 already exists",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"CSV report path (default: {DEFAULT_REPORT.relative_to(PROJECT_ROOT)})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.remove_wav and not args.execute:
        print("error: --remove-wav requires --execute", file=sys.stderr)
        return 2

    if not Path(FFMPEG).exists():
        print(f"error: ffmpeg not found at {FFMPEG}", file=sys.stderr)
        return 2

    input_root = args.input.resolve()
    if not input_root.is_dir():
        print(f"error: input directory not found: {input_root}", file=sys.stderr)
        return 2

    wav_files = find_wav_files(input_root)
    if not wav_files:
        print("No WAV files found.")
        return 0

    results: list[TranscodeResult] = []
    removed_wav = 0

    for source in wav_files:
        dest = source.with_suffix(".mp3")
        if args.force and dest.exists() and args.execute:
            dest.unlink()

        result = transcode_wav_to_mp3(
            source,
            dest,
            bitrate=args.bitrate,
            execute=args.execute,
        )
        results.append(result)

        rel = source.relative_to(input_root)
        if result.status == "dry_run":
            print(f"[dry-run] {rel} -> {dest.name}")
        elif result.status == "skipped":
            print(f"[skip] {rel} (MP3 up to date)")
            if args.remove_wav and dest.exists():
                source.unlink()
                removed_wav += 1
        elif result.status == "ok":
            print(
                f"[ok] {rel} -> {dest.name} "
                f"({result.source_mb:.1f} -> {result.output_mb:.1f} MB, "
                f"-{result.pct_reduction:.0f}%)"
            )
            if args.remove_wav:
                source.unlink()
                removed_wav += 1
        else:
            print(f"[fail] {rel}: {result.error}")

    write_report(args.report, results)
    print_summary(results, removed_wav=removed_wav)
    print(f"\nReport: {args.report}")

    if not args.execute:
        print("\nDry-run only. Re-run with --execute to transcode.")
        print("Then: fix_highlights_metadata.py, build_highlights_catalog.py")
        if args.remove_wav:
            print("(pass --remove-wav with --execute to delete WAVs after transcode)")

    failed = [r for r in results if r.status == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
