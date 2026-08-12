#!/usr/bin/env python3
"""
Batch-generate log-frequency spectrogram PNGs for the NPS acoustic highlights set.

Walks highlights/audio/ recursively, mirrors the folder tree under highlights/spectrograms/,
writes gallery WebP thumbnails to highlights/spectrograms_thumbs/, and writes a JSON report to
data/reports/spectrogram_generation_report.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import librosa
import librosa.display
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "highlights" / "audio"
DEFAULT_OUTPUT = PROJECT_ROOT / "highlights" / "spectrograms"
DEFAULT_THUMB_OUTPUT = PROJECT_ROOT / "highlights" / "spectrograms_thumbs"
REPORT_PATH = PROJECT_ROOT / "data" / "reports" / "spectrogram_generation_report.json"

FIGSIZE = (12, 4)  # 1200x400 px at 100 dpi
DPI = 100
CMAP = "magma"
DEFAULT_N_FFT = 2048
HOP_RATIO = 4
THUMB_MAX_WIDTH = 480
THUMB_WEBP_QUALITY = 82

AUDIO_EXTENSIONS = {".wav", ".mp3"}


@dataclass
class FileReport:
    source: str
    outputs: list[str] = field(default_factory=list)
    duration_s: float | None = None
    sample_rate: int | None = None
    render_time_s: float | None = None
    png_size_kb: float | None = None
    thumb_size_kb: float | None = None
    status: str = "ok"
    error: str | None = None


def is_audio_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def discover_audio_files(input_root: Path) -> list[Path]:
    return sorted(
        path
        for path in input_root.rglob("*")
        if is_audio_file(path)
    )


def discover_png_files(png_root: Path) -> list[Path]:
    return sorted(path for path in png_root.rglob("*.png") if path.is_file())


def spectrogram_path_for(
    source: Path,
    input_root: Path,
    output_root: Path,
) -> Path:
    """Return the output PNG path for a source audio file."""
    rel = source.relative_to(input_root)
    return output_root / rel.with_suffix(".png")


def thumb_path_for(png_path: Path, png_root: Path, thumb_root: Path) -> Path:
    """Return the gallery WebP thumb path for a full spectrogram PNG."""
    rel = png_path.relative_to(png_root)
    return thumb_root / rel.with_suffix(".webp")


def output_is_current(source: Path, output: Path) -> bool:
    return output.is_file() and output.stat().st_mtime >= source.stat().st_mtime


def outputs_are_current(source: Path, output_paths: list[Path]) -> bool:
    if not output_paths:
        return False
    if not all(path.exists() for path in output_paths):
        return False
    source_mtime = source.stat().st_mtime
    return all(path.stat().st_mtime >= source_mtime for path in output_paths)


def write_spectrogram_thumb(png_path: Path, thumb_path: Path) -> float:
    """Resize a full spectrogram PNG to a gallery WebP thumb; return size in KB."""
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(png_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        if width > THUMB_MAX_WIDTH:
            new_height = round(height * (THUMB_MAX_WIDTH / width))
            image = image.resize((THUMB_MAX_WIDTH, new_height), Image.Resampling.LANCZOS)
        image.save(
            thumb_path,
            format="WEBP",
            quality=THUMB_WEBP_QUALITY,
            method=6,
        )
    return thumb_path.stat().st_size / 1024


def load_audio(path: Path) -> tuple[np.ndarray, int, float, float]:
    """Load full audio; return waveform, sample rate, duration, and decode seconds."""
    t0 = time.perf_counter()
    y, sr = librosa.load(path, sr=None, mono=True)
    elapsed = time.perf_counter() - t0
    duration = len(y) / sr
    return y, sr, duration, elapsed


def render_spectrogram(
    y: np.ndarray,
    sr: int,
    out_path: Path,
    *,
    n_fft: int = DEFAULT_N_FFT,
) -> float:
    """Render a log-frequency spectrogram PNG; return render seconds."""
    hop_length = max(1, n_fft // HOP_RATIO)
    t0 = time.perf_counter()

    stft = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
    magnitude = np.abs(stft)
    db = librosa.amplitude_to_db(magnitude, ref=np.max)

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    librosa.display.specshow(
        db,
        sr=sr,
        hop_length=hop_length,
        x_axis="time",
        y_axis="log",
        cmap=CMAP,
        ax=ax,
    )
    ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, facecolor="white")
    plt.close(fig)

    return time.perf_counter() - t0


def ensure_thumb(
    png_path: Path,
    thumb_path: Path,
    *,
    force: bool,
) -> tuple[bool, float | None]:
    """Write thumb when missing or stale relative to PNG. Returns (written, size_kb)."""
    if not png_path.is_file():
        return False, None
    if not force and output_is_current(png_path, thumb_path):
        return False, thumb_path.stat().st_size / 1024
    thumb_kb = write_spectrogram_thumb(png_path, thumb_path)
    return True, thumb_kb


def process_file(
    source: Path,
    input_root: Path,
    output_root: Path,
    thumb_root: Path,
    *,
    force: bool,
    dry_run: bool,
    thumbs_only: bool,
) -> FileReport:
    png_path = spectrogram_path_for(source, input_root, output_root)
    thumb_path = thumb_path_for(png_path, output_root, thumb_root)

    png_current = png_path.is_file() and (
        thumbs_only or outputs_are_current(source, [png_path])
    )
    thumb_current = thumb_path.is_file() and png_path.is_file() and output_is_current(
        png_path, thumb_path
    )

    if not force and png_current and thumb_current:
        return FileReport(
            source=str(source),
            outputs=[str(png_path), str(thumb_path)],
            png_size_kb=round(png_path.stat().st_size / 1024, 1),
            thumb_size_kb=round(thumb_path.stat().st_size / 1024, 1),
            status="skipped",
        )

    if dry_run:
        outputs = [str(png_path)]
        if not thumbs_only:
            outputs.append(str(thumb_path))
        else:
            outputs = [str(thumb_path)]
        return FileReport(
            source=str(source),
            outputs=outputs,
            status="dry_run",
        )

    duration_s: float | None = None
    sample_rate: int | None = None
    render_time_s: float | None = None

    if thumbs_only:
        if not png_path.is_file():
            return FileReport(
                source=str(source),
                outputs=[str(thumb_path)],
                status="failed",
                error=f"PNG not found for thumb: {png_path}",
            )
    elif not png_current or force:
        try:
            y, sr, duration_s, decode_s = load_audio(source)
        except Exception as exc:  # noqa: BLE001
            return FileReport(
                source=str(source),
                outputs=[str(png_path), str(thumb_path)],
                status="failed",
                error=f"Load failed: {exc}",
            )

        try:
            render_total_s = render_spectrogram(y, sr, png_path)
            render_time_s = round(decode_s + render_total_s, 3)
            sample_rate = sr
            duration_s = round(duration_s, 2)
        except Exception as exc:  # noqa: BLE001
            return FileReport(
                source=str(source),
                outputs=[],
                duration_s=round(duration_s, 2) if duration_s is not None else None,
                sample_rate=sample_rate,
                render_time_s=render_time_s,
                status="failed",
                error=f"Render failed: {exc}",
            )

    try:
        _, thumb_kb = ensure_thumb(png_path, thumb_path, force=force)
    except Exception as exc:  # noqa: BLE001
        return FileReport(
            source=str(source),
            outputs=[str(png_path)],
            duration_s=duration_s,
            sample_rate=sample_rate,
            render_time_s=render_time_s,
            png_size_kb=round(png_path.stat().st_size / 1024, 1) if png_path.is_file() else None,
            status="failed",
            error=f"Thumb failed: {exc}",
        )

    png_kb = round(png_path.stat().st_size / 1024, 1) if png_path.is_file() else None
    return FileReport(
        source=str(source),
        outputs=[str(png_path), str(thumb_path)],
        duration_s=duration_s,
        sample_rate=sample_rate,
        render_time_s=render_time_s,
        png_size_kb=png_kb,
        thumb_size_kb=round(thumb_kb or 0, 1) if thumb_kb is not None else None,
        status="ok",
    )


def process_png_thumb(
    png_path: Path,
    png_root: Path,
    thumb_root: Path,
    *,
    force: bool,
    dry_run: bool,
) -> FileReport:
    thumb_path = thumb_path_for(png_path, png_root, thumb_root)
    source_label = str(png_path)

    if not force and thumb_path.is_file() and output_is_current(png_path, thumb_path):
        return FileReport(
            source=source_label,
            outputs=[str(thumb_path)],
            png_size_kb=round(png_path.stat().st_size / 1024, 1),
            thumb_size_kb=round(thumb_path.stat().st_size / 1024, 1),
            status="skipped",
        )

    if dry_run:
        return FileReport(
            source=source_label,
            outputs=[str(thumb_path)],
            status="dry_run",
        )

    try:
        _, thumb_kb = ensure_thumb(png_path, thumb_path, force=force)
    except Exception as exc:  # noqa: BLE001
        return FileReport(
            source=source_label,
            outputs=[str(thumb_path)],
            status="failed",
            error=f"Thumb failed: {exc}",
        )

    return FileReport(
        source=source_label,
        outputs=[str(thumb_path)],
        png_size_kb=round(png_path.stat().st_size / 1024, 1),
        thumb_size_kb=round(thumb_kb or 0, 1),
        status="ok",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate spectrogram PNGs and gallery WebP thumbs for the highlights set.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input audio root (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output spectrogram root (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--thumb-output",
        type=Path,
        default=DEFAULT_THUMB_OUTPUT,
        help=f"Output gallery thumb root (default: {DEFAULT_THUMB_OUTPUT})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even when outputs are newer than source",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List work without loading audio or writing files",
    )
    parser.add_argument(
        "--thumbs-only",
        action="store_true",
        help="Only (re)build WebP thumbs from existing PNGs; skip audio decode/render",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N audio files (for testing)",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        type=Path,
        default=None,
        help="Process only these audio file paths (relative to --input or absolute)",
    )
    return parser.parse_args(argv)


def print_summary(reports: list[FileReport], elapsed_s: float) -> None:
    counts = {
        status: sum(1 for report in reports if report.status == status)
        for status in ("ok", "skipped", "failed", "dry_run")
    }
    png_count = sum(
        1
        for report in reports
        if report.status in ("ok", "skipped")
        for output in report.outputs
        if output.endswith(".png")
    )
    thumb_count = sum(
        1
        for report in reports
        if report.status in ("ok", "skipped")
        for output in report.outputs
        if output.endswith(".webp")
    )
    total_png_kb = sum(report.png_size_kb or 0 for report in reports if report.status == "ok")
    total_thumb_kb = sum(report.thumb_size_kb or 0 for report in reports if report.status == "ok")

    print("\n=== Highlights spectrogram generation summary ===\n")
    print(f"Total source files: {len(reports)}")
    print(f"Succeeded:          {counts['ok']}")
    print(f"Skipped:            {counts['skipped']}")
    print(f"Failed:             {counts['failed']}")
    if counts["dry_run"]:
        print(f"Dry run:            {counts['dry_run']}")
    print(f"PNG files:            {png_count}")
    print(f"Thumb WebP files:     {thumb_count}")
    print(f"PNG disk size (ok):   {total_png_kb / 1024:.1f} MB")
    print(f"Thumb disk size (ok): {total_thumb_kb / 1024:.1f} MB")
    print(f"Elapsed:              {elapsed_s / 60:.1f} min ({elapsed_s:.1f} s)")

    failures = [report for report in reports if report.status == "failed"]
    if failures:
        print("\nFailures:")
        for report in failures:
            print(f"  - {report.source}")
            print(f"    {report.error}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_root = args.input.resolve()
    output_root = args.output.resolve()
    thumb_root = args.thumb_output.resolve()

    if args.thumbs_only:
        if not output_root.is_dir():
            print(f"Spectrogram directory not found: {output_root}", file=sys.stderr)
            return 2
        png_files = discover_png_files(output_root)
        if args.limit is not None:
            png_files = png_files[: args.limit]
        if not png_files:
            print(f"No PNG files found under {output_root}", file=sys.stderr)
            return 2

        output_root.mkdir(parents=True, exist_ok=True)
        thumb_root.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.perf_counter()
        reports: list[FileReport] = []
        for index, png_path in enumerate(png_files, start=1):
            rel = png_path.relative_to(output_root)
            print(f"[{index}/{len(png_files)}] {rel}")
            reports.append(
                process_png_thumb(
                    png_path,
                    output_root,
                    thumb_root,
                    force=args.force,
                    dry_run=args.dry_run,
                )
            )
        elapsed_s = time.perf_counter() - t0
        print_summary(reports, elapsed_s)
        report_payload = {
            "mode": "thumbs_only",
            "png_root": str(output_root),
            "thumb_root": str(thumb_root),
            "elapsed_s": round(elapsed_s, 3),
            "files": [asdict(report) for report in reports],
        }
        REPORT_PATH.write_text(json.dumps(report_payload, indent=2))
        print(f"\nJSON report: {REPORT_PATH}")
        failed = [report for report in reports if report.status == "failed"]
        return 1 if failed else 0

    if not input_root.is_dir():
        print(f"Input directory not found: {input_root}", file=sys.stderr)
        return 2

    if args.files:
        audio_files = []
        for file_arg in args.files:
            candidate = file_arg if file_arg.is_absolute() else (PROJECT_ROOT / file_arg)
            resolved = candidate.resolve()
            if not resolved.is_file():
                print(f"Audio file not found: {resolved}", file=sys.stderr)
                return 2
            audio_files.append(resolved)
        audio_files = sorted(audio_files)
    else:
        audio_files = discover_audio_files(input_root)
        if args.limit is not None:
            audio_files = audio_files[: args.limit]

    if not audio_files:
        print(f"No audio files found under {input_root}", file=sys.stderr)
        return 2

    output_root.mkdir(parents=True, exist_ok=True)
    thumb_root.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    reports: list[FileReport] = []

    for index, source in enumerate(audio_files, start=1):
        rel = source.relative_to(input_root)
        print(f"[{index}/{len(audio_files)}] {rel}")
        reports.append(
            process_file(
                source,
                input_root,
                output_root,
                thumb_root,
                force=args.force,
                dry_run=args.dry_run,
                thumbs_only=False,
            )
        )

    elapsed_s = time.perf_counter() - t0
    print_summary(reports, elapsed_s)

    report_payload = {
        "input_root": str(input_root),
        "output_root": str(output_root),
        "thumb_root": str(thumb_root),
        "elapsed_s": round(elapsed_s, 3),
        "files": [asdict(report) for report in reports],
    }
    REPORT_PATH.write_text(json.dumps(report_payload, indent=2))
    print(f"\nJSON report: {REPORT_PATH}")

    failed = [report for report in reports if report.status == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
