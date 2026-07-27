#!/usr/bin/env python3
"""Generate static log-frequency spectrogram PNGs for NPS acoustic highlight samples."""

from __future__ import annotations

import json
import re
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

BASE = Path("/Volumes/NPS_ADSB_Data/NPS_Type_1_Acoustic_Audio_Highlights")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "spectrograms"

FIGSIZE = (12, 4)  # 1200x400 px at 100 dpi
DPI = 100
CMAP = "magma"
DEFAULT_N_FFT = 2048
HOP_RATIO = 4


@dataclass
class FileSpec:
    label: str
    path: Path
    duration: float | None = None
    low_freq_view: bool = False
    fft_compare: bool = False
    fallbacks: list[Path] = field(default_factory=list)


@dataclass
class RenderResult:
    label: str
    source_path: str
    output_path: str | None
    duration_s: float | None
    sample_rate: int | None
    decode_render_s: float | None
    png_size_kb: float | None
    n_fft: int | None = None
    freq_range: str = "full"
    status: str = "ok"
    error: str | None = None
    notes: str | None = None


FILE_SPECS = [
    FileSpec(
        label="muldrow_geologic",
        path=BASE
        / "DENABMUL_20210401_091907 Muldrow surge long cut, extensive low-frequency rumbling features.wav",
        duration=90.0,
        low_freq_view=True,
    ),
    FileSpec(
        label="wolf_howls",
        path=BASE / "MAMMAL REFERENCE" / "WRSTBLMT_20170128_072543 excellent wolf pack howling.wav",
    ),
    FileSpec(
        label="whale_breaching",
        path=BASE
        / "MAMMAL REFERENCE"
        / "GLBAMCLEOD_20220903_234345 Humpback Whale breathing, breaching.wav",
    ),
    FileSpec(
        label="bird_chorus",
        path=BASE
        / "BIRD ID"
        / "GAARARRI_20180608_073133 chorus with Golden-crowned Sparrow full.MP3",
        fallbacks=[
            BASE
            / "BIRD ID"
            / "2019_metadata entered"
            / "GAARARRI_20180608_073133 chorus with Golden-crowned Sparrow full.wav",
            BASE
            / "BIRD ID"
            / "2019_metadata entered"
            / "GAARFLOR_20180618_053001 Common Loon with rich avian chorus.wav",
        ],
        fft_compare=True,
    ),
    FileSpec(
        label="insect_wingbeats",
        path=BASE / "INSECTS" / "DENABICR_20130715_230139 insect flight with pulsed behavior.wav",
    ),
    FileSpec(
        label="geophony_rockslide",
        path=BASE
        / "GEOPHONY"
        / "DENABACK_20140609_004005 pronounced rock slide with several phases.wav",
    ),
]


def safe_stem(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"[^\w\-. ]+", "_", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem[:180]


def resolve_audio_path(spec: FileSpec) -> tuple[Path | None, str | None]:
    candidates = [spec.path, *spec.fallbacks]
    for candidate in candidates:
        if not (candidate.exists() and candidate.is_file()):
            continue
        try:
            librosa.load(candidate, sr=None, mono=True, duration=0.25)
        except Exception:
            continue
        if candidate == spec.path:
            return candidate, None
        return candidate, f"Substituted path: {candidate}"
    return None, f"No readable file among {len(candidates)} candidate path(s)"


def load_audio(path: Path, duration: float | None) -> tuple[np.ndarray, int, float]:
    t0 = time.perf_counter()
    y, sr = librosa.load(path, sr=None, mono=True, duration=duration, offset=0.0)
    elapsed = time.perf_counter() - t0
    audio_duration = len(y) / sr
    return y, sr, audio_duration, elapsed


def render_spectrogram(
    y: np.ndarray,
    sr: int,
    out_path: Path,
    *,
    n_fft: int = DEFAULT_N_FFT,
    fmax: float | None = None,
    title_suffix: str = "",
) -> float:
    hop_length = max(1, n_fft // HOP_RATIO)
    t0 = time.perf_counter()

    stft = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
    magnitude = np.abs(stft)
    db = librosa.amplitude_to_db(magnitude, ref=np.max)

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    img = librosa.display.specshow(
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
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    if title_suffix:
        ax.set_title(title_suffix, fontsize=10)
    fig.colorbar(img, ax=ax, format="%+2.0f dB", pad=0.01)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return time.perf_counter() - t0


def process_spec(spec: FileSpec) -> list[RenderResult]:
    results: list[RenderResult] = []
    resolved, path_note = resolve_audio_path(spec)
    if resolved is None:
        return [
            RenderResult(
                label=spec.label,
                source_path=str(spec.path),
                output_path=None,
                duration_s=None,
                sample_rate=None,
                decode_render_s=None,
                png_size_kb=None,
                status="failed",
                error=path_note,
            )
        ]

    try:
        y, sr, audio_duration, decode_s = load_audio(resolved, spec.duration)
    except Exception as exc:  # noqa: BLE001
        return [
            RenderResult(
                label=spec.label,
                source_path=str(resolved),
                output_path=None,
                duration_s=None,
                sample_rate=None,
                decode_render_s=None,
                png_size_kb=None,
                status="failed",
                error=f"Load failed: {exc}",
                notes=path_note,
            )
        ]

    stem = safe_stem(resolved)
    variants: list[tuple[str, int, float | None, str]] = [
        ("spectrogram", DEFAULT_N_FFT, None, ""),
    ]

    if spec.low_freq_view:
        variants.append(("spectrogram_lowfreq_0-2000Hz", DEFAULT_N_FFT, 2000.0, "0–2000 Hz"))

    if spec.fft_compare:
        variants.extend(
            [
                ("spectrogram_nfft1024", 1024, None, "n_fft=1024"),
                ("spectrogram_nfft4096", 4096, None, "n_fft=4096"),
            ]
        )

    for suffix, n_fft, fmax, title_suffix in variants:
        out_path = OUTPUT_DIR / f"{stem}_{suffix}.png"
        try:
            render_s = render_spectrogram(
                y,
                sr,
                out_path,
                n_fft=n_fft,
                fmax=fmax,
                title_suffix=title_suffix,
            )
            total_s = decode_s + render_s
            size_kb = out_path.stat().st_size / 1024
            freq_range = "0-2000 Hz" if fmax == 2000.0 else "full"
            results.append(
                RenderResult(
                    label=spec.label,
                    source_path=str(resolved),
                    output_path=str(out_path),
                    duration_s=round(audio_duration, 2),
                    sample_rate=sr,
                    decode_render_s=round(total_s, 3),
                    png_size_kb=round(size_kb, 1),
                    n_fft=n_fft,
                    freq_range=freq_range,
                    notes=path_note,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                RenderResult(
                    label=spec.label,
                    source_path=str(resolved),
                    output_path=str(out_path),
                    duration_s=round(audio_duration, 2),
                    sample_rate=sr,
                    decode_render_s=None,
                    png_size_kb=None,
                    n_fft=n_fft,
                    freq_range="0-2000 Hz" if fmax == 2000.0 else "full",
                    status="failed",
                    error=f"Render failed: {exc}",
                    notes=path_note,
                )
            )

    return results


def print_summary(results: list[RenderResult]) -> None:
    print("\n=== Spectrogram generation summary ===\n")
    header = (
        f"{'Label':<22} {'Duration':>9} {'SR':>7} {'Time(s)':>8} "
        f"{'PNG(KB)':>8} {'n_fft':>6} {'Range':<12} Status"
    )
    print(header)
    print("-" * len(header))

    for r in results:
        dur = f"{r.duration_s:.1f}s" if r.duration_s is not None else "—"
        sr = str(r.sample_rate) if r.sample_rate else "—"
        t = f"{r.decode_render_s:.3f}" if r.decode_render_s is not None else "—"
        kb = f"{r.png_size_kb:.1f}" if r.png_size_kb is not None else "—"
        nfft = str(r.n_fft) if r.n_fft else "—"
        status = r.status if r.status == "ok" else f"FAIL: {r.error}"
        print(
            f"{r.label:<22} {dur:>9} {sr:>7} {t:>8} {kb:>8} {nfft:>6} "
            f"{r.freq_range:<12} {status}"
        )
        if r.notes:
            print(f"  note: {r.notes}")
        if r.output_path and r.status == "ok":
            print(f"  -> {r.output_path}")


def main() -> int:
    labels = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    specs = FILE_SPECS
    if labels:
        specs = [s for s in FILE_SPECS if s.label in labels]
        if not specs:
            print(f"No matching labels. Choose from: {[s.label for s in FILE_SPECS]}")
            return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_results: list[RenderResult] = []

    for spec in specs:
        print(f"Processing: {spec.label} ...")
        all_results.extend(process_spec(spec))

    print_summary(all_results)

    report_path = OUTPUT_DIR / "generation_report.json"
    report_path.write_text(json.dumps([asdict(r) for r in all_results], indent=2))
    print(f"\nJSON report: {report_path}")

    failed = [r for r in all_results if r.status != "ok"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
