#!/usr/bin/env python3
"""
Generate a labeled spectrogram guide image for the About page.

Uses the Fox Sparrow / Thunder / Swainson's Thrush clip with a cropped window
and matplotlib callouts. Re-run after tweaking CROP_* or ANNOTATIONS below.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import librosa
import librosa.display
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIO = (
    PROJECT_ROOT
    / "highlights"
    / "audio"
    / "BIRDS"
    / "DENAWOCR_20150624_202549 Fox Sparrow Song With Thunder and Swainson's Thrush TRIM.mp3"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "site" / "public" / "about" / "spectrogram-guide.png"

FIGSIZE = (12, 5)
DPI = 120
CMAP = "magma"
# Balance frequency detail vs time sharpness (large n_fft smears short notes).
N_FFT = 4096
HOP_LENGTH = 256

CROP_START_SEC = 18.0
CROP_END_SEC = 29.1

CALLOUT_STYLE: dict[str, Any] = {
    "fontsize": 9,
    "color": "white",
    "bbox": {
        "boxstyle": "round,pad=0.35",
        "facecolor": "black",
        "alpha": 0.75,
        "edgecolor": "none",
    },
}
ARROW_STYLE: dict[str, Any] = {
    "arrowstyle": "->",
    "color": "white",
    "lw": 1.4,
}

# text_xy in axes fraction; arrows as (seconds, Hz, rad) tuples
ANNOTATIONS = [
    {
        "label": "Low-frequency rumble\n(thunder)",
        "text_xy": (0.06, 0.16),
        "arrows": [(23.5, 64, 0.0)],
    },
    {
        "label": "Fox Sparrow song",
        "text_xy": (0.34, 0.90),
        "arrows": [(20.0, 4096, 0.18)],
    },
    {
        "label": "Swainson's Thrush —\nrising frequency",
        "text_xy": (0.72, 0.90),
        "arrows": [(22.5, 4200, -0.12), (28.0, 4096, 0.12)],
    },
]


def draw_callout(ax: plt.Axes, item: dict[str, Any]) -> None:
    text_xy = item["text_xy"]
    ax.text(
        text_xy[0],
        text_xy[1],
        item["label"],
        transform=ax.transAxes,
        ha="center",
        va="center",
        zorder=5,
        **CALLOUT_STYLE,
    )
    for seconds, hz, rad in item["arrows"]:
        ax.annotate(
            "",
            xy=(seconds, hz),
            xycoords="data",
            xytext=text_xy,
            textcoords="axes fraction",
            arrowprops={
                **ARROW_STYLE,
                "connectionstyle": f"arc3,rad={rad}",
            },
            zorder=4,
        )


def render_guide(
    audio_path: Path,
    output_path: Path,
    *,
    crop_start: float = CROP_START_SEC,
    crop_end: float = CROP_END_SEC,
    n_fft: int = N_FFT,
    hop_length: int = HOP_LENGTH,
) -> None:
    y, sr = librosa.load(audio_path, sr=None, mono=True)

    start_sample = int(crop_start * sr)
    end_sample = int(crop_end * sr)
    y_crop = y[start_sample:end_sample]

    stft = librosa.stft(y_crop, n_fft=n_fft, hop_length=hop_length)
    db = librosa.amplitude_to_db(np.abs(stft), ref=np.max)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    times = librosa.times_like(db, sr=sr, hop_length=hop_length) + crop_start

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    librosa.display.specshow(
        db,
        x_coords=times,
        y_coords=freqs,
        x_axis="time",
        y_axis="log",
        cmap=CMAP,
        ax=ax,
    )
    ax.set_xlabel("Time (seconds)", fontsize=10)
    ax.set_ylabel("Frequency (Hz)", fontsize=10)
    ax.tick_params(labelsize=9)
    ax.set_xlim(crop_start, crop_end)

    for item in ANNOTATIONS:
        draw_callout(ax, item)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=DPI, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate About-page spectrogram guide PNG.")
    parser.add_argument("--audio", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--crop-start", type=float, default=CROP_START_SEC)
    parser.add_argument("--crop-end", type=float, default=CROP_END_SEC)
    parser.add_argument("--n-fft", type=int, default=N_FFT)
    parser.add_argument("--hop-length", type=int, default=HOP_LENGTH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audio_path = args.audio.resolve()
    if not audio_path.is_file():
        raise SystemExit(f"Audio file not found: {audio_path}")

    render_guide(
        audio_path,
        args.output.resolve(),
        crop_start=args.crop_start,
        crop_end=args.crop_end,
        n_fft=args.n_fft,
        hop_length=args.hop_length,
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
