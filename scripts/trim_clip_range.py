#!/usr/bin/env python3
"""
Trim highlight MP3 clips to a time range (or from start to end time).

Backs up originals to archive/pre_trim/ before overwriting. Uses sample-accurate
librosa slicing and re-encodes to 192k MP3 mono (same as other trim scripts).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import librosa
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "catalog" / "highlights.json"
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "archive" / "pre_trim"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


@dataclass
class TrimSpec:
    clip_id: str
    start_sec: float
    end_sec: float | None = None  # None = keep through end of file
    output_path: str | None = None  # relative to project root; default = in-place


@dataclass
class TrimResult:
    clip_id: str
    audio_path: str
    status: str
    original_duration_sec: float | None = None
    new_duration_sec: float | None = None
    start_sec: float | None = None
    end_sec: float | None = None
    error: str | None = None


def parse_time(value: str) -> float:
    """Parse seconds (float) or M:SS / H:MM:SS."""
    value = value.strip()
    if re.fullmatch(r"\d+(\.\d+)?", value):
        return float(value)
    parts = value.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError(f"Invalid time: {value!r}")


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


def write_mp3(y, sr: int, dest: Path) -> None:
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


def load_catalog(catalog_path: Path) -> list[dict]:
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def find_clip(catalog: list[dict], clip_id: str) -> dict:
    for clip in catalog:
        if clip["id"] == clip_id:
            return clip
    raise KeyError(f"clip not found in catalog: {clip_id}")


def trim_audio_file(
    audio_path: Path,
    *,
    start_sec: float,
    end_sec: float | None,
    dest_path: Path,
) -> tuple[float, float]:
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    original_duration = len(y) / sr
    start_sample = max(0, int(round(start_sec * sr)))
    end_sample = len(y) if end_sec is None else min(len(y), int(round(end_sec * sr)))
    if end_sample <= start_sample:
        raise ValueError(
            f"invalid range: {start_sec}s–{end_sec}s on {original_duration:.3f}s clip"
        )
    trimmed = y[start_sample:end_sample]
    write_mp3(trimmed, sr, dest_path)
    return original_duration, len(trimmed) / sr


def trim_spec(
    spec: TrimSpec,
    *,
    catalog_path: Path,
    backup_root: Path,
    execute: bool,
) -> TrimResult:
    catalog = load_catalog(catalog_path)
    clip = find_clip(catalog, spec.clip_id)
    rel_audio = spec.output_path or clip["audio_path"]
    audio_path = PROJECT_ROOT / rel_audio

    if not audio_path.exists() and spec.output_path is None:
        source = PROJECT_ROOT / clip["audio_path"]
        if source.exists():
            audio_path = source
            rel_audio = clip["audio_path"]
        else:
            return TrimResult(
                clip_id=spec.clip_id,
                audio_path=rel_audio,
                status="failed",
                error=f"missing file: {audio_path}",
            )
    elif spec.output_path and not audio_path.parent.exists():
        audio_path.parent.mkdir(parents=True, exist_ok=True)

    source_path = PROJECT_ROOT / clip["audio_path"]
    if not source_path.exists():
        return TrimResult(
            clip_id=spec.clip_id,
            audio_path=rel_audio,
            status="failed",
            error=f"missing source: {source_path}",
        )

    dest_path = audio_path if spec.output_path else source_path

    try:
        y, sr = librosa.load(source_path, sr=None, mono=True)
        original_duration = len(y) / sr
        end = spec.end_sec if spec.end_sec is not None else original_duration
        new_duration = max(0.0, end - spec.start_sec)

        if not execute:
            return TrimResult(
                clip_id=spec.clip_id,
                audio_path=rel_audio,
                status="dry_run",
                original_duration_sec=round(original_duration, 3),
                new_duration_sec=round(new_duration, 3),
                start_sec=spec.start_sec,
                end_sec=spec.end_sec,
            )

        if not spec.output_path:
            backup_audio(source_path, backup_root)

        _, new_duration = trim_audio_file(
            source_path,
            start_sec=spec.start_sec,
            end_sec=spec.end_sec,
            dest_path=dest_path,
        )
        rel_audio = str(dest_path.relative_to(PROJECT_ROOT))

        return TrimResult(
            clip_id=spec.clip_id,
            audio_path=rel_audio,
            status="ok",
            original_duration_sec=round(original_duration, 3),
            new_duration_sec=round(new_duration, 3),
            start_sec=spec.start_sec,
            end_sec=spec.end_sec,
        )
    except Exception as exc:  # noqa: BLE001
        return TrimResult(
            clip_id=spec.clip_id,
            audio_path=rel_audio,
            status="failed",
            error=str(exc),
        )


def update_catalog_durations(
    catalog_path: Path,
    updates: dict[str, tuple[float, str | None]],
) -> None:
    """Map clip_id -> (duration_sec, audio_path or None to keep existing)."""
    catalog = load_catalog(catalog_path)
    by_id = {clip["id"]: clip for clip in catalog}
    for clip_id, (duration_sec, audio_path) in updates.items():
        clip = by_id[clip_id]
        clip["duration_sec"] = round(duration_sec, 1)
        if audio_path:
            clip["audio_path"] = audio_path
            path = PROJECT_ROOT / audio_path
            if path.exists():
                clip["file_size_bytes"] = path.stat().st_size
    catalog_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trim highlight MP3 clips to a time range.")
    parser.add_argument("--clip-id", required=True)
    parser.add_argument("--start", required=True, help="Start time (seconds or M:SS)")
    parser.add_argument("--end", help="End time (seconds or M:SS); omit to keep through EOF")
    parser.add_argument(
        "--output-audio",
        help="Relative output audio path (for splits); default overwrites catalog path",
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    spec = TrimSpec(
        clip_id=args.clip_id,
        start_sec=parse_time(args.start),
        end_sec=parse_time(args.end) if args.end else None,
        output_path=args.output_audio,
    )
    catalog_path = args.catalog.resolve()
    result = trim_spec(
        spec,
        catalog_path=catalog_path,
        backup_root=args.backup_root.resolve(),
        execute=args.execute,
    )
    if result.status == "ok" and result.new_duration_sec is not None:
        update_catalog_durations(
            catalog_path,
            {result.clip_id: (result.new_duration_sec, result.audio_path)},
        )
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.status in {"ok", "dry_run"} else 1


if __name__ == "__main__":
    sys.exit(main())
