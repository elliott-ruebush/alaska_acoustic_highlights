#!/usr/bin/env python3
"""
Batch-generate log-frequency spectrogram PNGs for the NPS acoustic highlights set.

Walks highlights/audio/ recursively, mirrors the folder tree under highlights/spectrograms/,
and writes a JSON report to data/spectrogram_generation_report.json.
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "highlights" / "audio"
DEFAULT_OUTPUT = PROJECT_ROOT / "highlights" / "spectrograms"
REPORT_PATH = PROJECT_ROOT / "data" / "spectrogram_generation_report.json"

FIGSIZE = (12, 4)  # 1200x400 px at 100 dpi
DPI = 100
CMAP = "magma"
DEFAULT_N_FFT = 2048
HOP_RATIO = 4
LOW_FREQ_MAX_HZ = 2000.0

AUDIO_EXTENSIONS = {".wav", ".mp3"}


@dataclass
class FileReport:
    source: str
    outputs: list[str] = field(default_factory=list)
    duration_s: float | None = None
    sample_rate: int | None = None
    render_time_s: float | None = None
    png_size_kb: float | None = None
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


def spectrogram_paths_for(
    source: Path,
    input_root: Path,
    output_root: Path,
) -> list[tuple[Path, float | None]]:
    """Return (output_path, fmax) pairs for a source audio file."""
    rel = source.relative_to(input_root)
    full_path = output_root / rel.with_suffix(".png")
    paths: list[tuple[Path, float | None]] = [(full_path, None)]

    if rel.parts and rel.parts[0].upper() == "GEOPHONY":
        lowfreq_path = full_path.with_name(f"{full_path.stem}_lowfreq{full_path.suffix}")
        paths.append((lowfreq_path, LOW_FREQ_MAX_HZ))

    return paths


def outputs_are_current(source: Path, output_paths: list[Path]) -> bool:
    if not output_paths:
        return False
    if not all(path.exists() for path in output_paths):
        return False
    source_mtime = source.stat().st_mtime
    return all(path.stat().st_mtime >= source_mtime for path in output_paths)


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
    fmax: float | None = None,
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
        fmax=fmax,
    )
    if fmax is not None:
        ax.set_ylim(20, fmax)
    ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, facecolor="white")
    plt.close(fig)

    return time.perf_counter() - t0


def process_file(
    source: Path,
    input_root: Path,
    output_root: Path,
    *,
    force: bool,
    dry_run: bool,
) -> FileReport:
    variants = spectrogram_paths_for(source, input_root, output_root)
    output_paths = [path for path, _fmax in variants]

    if not force and outputs_are_current(source, output_paths):
        total_kb = sum(path.stat().st_size for path in output_paths) / 1024
        return FileReport(
            source=str(source),
            outputs=[str(path) for path in output_paths],
            png_size_kb=round(total_kb, 1),
            status="skipped",
        )

    if dry_run:
        return FileReport(
            source=str(source),
            outputs=[str(path) for path, _fmax in variants],
            status="dry_run",
        )

    try:
        y, sr, duration_s, decode_s = load_audio(source)
    except Exception as exc:  # noqa: BLE001
        return FileReport(
            source=str(source),
            outputs=[str(path) for path, _fmax in variants],
            status="failed",
            error=f"Load failed: {exc}",
        )

    render_total_s = 0.0
    written_outputs: list[str] = []

    try:
        for out_path, fmax in variants:
            render_total_s += render_spectrogram(y, sr, out_path, fmax=fmax)
            written_outputs.append(str(out_path))
    except Exception as exc:  # noqa: BLE001
        return FileReport(
            source=str(source),
            outputs=written_outputs,
            duration_s=round(duration_s, 2),
            sample_rate=sr,
            render_time_s=round(decode_s + render_total_s, 3),
            status="failed",
            error=f"Render failed: {exc}",
        )

    total_kb = sum(Path(path).stat().st_size for path in written_outputs) / 1024
    return FileReport(
        source=str(source),
        outputs=written_outputs,
        duration_s=round(duration_s, 2),
        sample_rate=sr,
        render_time_s=round(decode_s + render_total_s, 3),
        png_size_kb=round(total_kb, 1),
        status="ok",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate spectrogram PNGs for the acoustic highlights set.",
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
        "--force",
        action="store_true",
        help="Regenerate even when outputs are newer than source",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List work without loading audio or writing PNGs",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N audio files (for testing)",
    )
    return parser.parse_args(argv)


def print_summary(reports: list[FileReport], elapsed_s: float) -> None:
    counts = {
        status: sum(1 for report in reports if report.status == status)
        for status in ("ok", "skipped", "failed", "dry_run")
    }
    png_count = sum(len(report.outputs) for report in reports if report.status == "ok")
    total_kb = sum(report.png_size_kb or 0 for report in reports if report.status == "ok")

    print("\n=== Highlights spectrogram generation summary ===\n")
    print(f"Total source files: {len(reports)}")
    print(f"Succeeded:          {counts['ok']}")
    print(f"Skipped:            {counts['skipped']}")
    print(f"Failed:             {counts['failed']}")
    if counts["dry_run"]:
        print(f"Dry run:            {counts['dry_run']}")
    print(f"PNG files written:  {png_count}")
    print(f"PNG disk size:      {total_kb / 1024:.1f} MB")
    print(f"Elapsed:            {elapsed_s / 60:.1f} min ({elapsed_s:.1f} s)")

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

    if not input_root.is_dir():
        print(f"Input directory not found: {input_root}", file=sys.stderr)
        return 2

    audio_files = discover_audio_files(input_root)
    if args.limit is not None:
        audio_files = audio_files[: args.limit]

    if not audio_files:
        print(f"No audio files found under {input_root}", file=sys.stderr)
        return 2

    output_root.mkdir(parents=True, exist_ok=True)
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
                force=args.force,
                dry_run=args.dry_run,
            )
        )

    elapsed_s = time.perf_counter() - t0
    print_summary(reports, elapsed_s)

    report_payload = {
        "input_root": str(input_root),
        "output_root": str(output_root),
        "elapsed_s": round(elapsed_s, 3),
        "files": [asdict(report) for report in reports],
    }
    REPORT_PATH.write_text(json.dumps(report_payload, indent=2))
    print(f"\nJSON report: {REPORT_PATH}")

    failed = [report for report in reports if report.status == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
