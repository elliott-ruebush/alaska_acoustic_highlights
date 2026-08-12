#!/usr/bin/env python3
"""
Ingest new highlight clips from ingest/audio/ and optional site photos.

Default is dry-run. Pass --execute to copy files and run the highlights pipeline.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.ingest_photos import resolve_photo_id
from lib.nps_filename import file_prefix, parse_filename
from lib.paths import (
    HIGHLIGHTS_AUDIO,
    HIGHLIGHTS_SITE_PHOTOS,
    INGEST_AUDIO,
    INGEST_OVERRIDES,
    INGEST_SITE_PHOTOS,
    PROJECT_ROOT,
    resolve_ingest_category,
)

SCRIPTS_DIR = Path(__file__).resolve().parent
AUDIO_EXTENSIONS = {".wav", ".mp3"}
PHOTO_EXTENSIONS = {".webp", ".jpg", ".jpeg", ".png"}


@dataclass
class AudioPlan:
    source: Path
    dest: Path
    category_folder: str
    clip_id: str
    warning: str | None = None
    action: str = "copy"  # copy, skip


@dataclass
class PhotoPlan:
    source: Path
    dest: Path
    photo_id: str
    match_method: str = "filename"
    action: str = "copy"  # copy, skip, unmatched


@dataclass(frozen=True)
class PipelineStep:
    label: str
    script: str
    args: tuple[str, ...] = ()


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def clip_id_from_audio(path: Path) -> str:
    return file_prefix(path.name).lower() or path.stem.lower()


def discover_audio() -> list[Path]:
    if not INGEST_AUDIO.is_dir():
        return []
    return sorted(
        path
        for path in INGEST_AUDIO.rglob("*")
        if path.is_file()
        and path.suffix.lower() in AUDIO_EXTENSIONS
        and path.name != ".gitkeep"
    )


def discover_photos() -> list[Path]:
    if not INGEST_SITE_PHOTOS.is_dir():
        return []
    return sorted(
        path
        for path in INGEST_SITE_PHOTOS.rglob("*")
        if path.is_file()
        and path.suffix.lower() in PHOTO_EXTENSIONS
        and path.name != ".gitkeep"
    )


def should_skip_copy(source: Path, dest: Path, *, force: bool) -> bool:
    if force or not dest.is_file():
        return False
    source_stat = source.stat()
    dest_stat = dest.stat()
    return dest_stat.st_size == source_stat.st_size and dest_stat.st_mtime >= source_stat.st_mtime


def should_skip_photo_copy(dest: Path, *, force: bool) -> bool:
    """Skip when canonical WebP output already exists (matches build_site_photos)."""
    return not force and dest.is_file()


def plan_audio(files: list[Path], *, force: bool) -> list[AudioPlan]:
    plans: list[AudioPlan] = []
    for source in files:
        _display_category, category_folder = resolve_ingest_category(source)
        dest = HIGHLIGHTS_AUDIO / category_folder / source.name
        parsed = parse_filename(source.name)
        warning = None
        if not parsed["prefix"]:
            warning = "filename missing NPS prefix pattern"
        action = (
            "copy"
            if force or not should_skip_copy(source, dest, force=False)
            else "skip"
        )
        plans.append(
            AudioPlan(
                source=source,
                dest=dest,
                category_folder=category_folder,
                clip_id=clip_id_from_audio(source),
                warning=warning,
                action=action,
            )
        )
    return plans


def plan_photos(
    files: list[Path],
    *,
    force: bool,
) -> list[PhotoPlan]:
    plans: list[PhotoPlan] = []
    for source in files:
        photo_id, match_method = resolve_photo_id(source)
        if photo_id is None:
            plans.append(
                PhotoPlan(
                    source=source,
                    dest=HIGHLIGHTS_SITE_PHOTOS / f"{source.stem.lower()}.webp",
                    photo_id=source.stem.lower(),
                    match_method="unmatched",
                    action="unmatched",
                )
            )
            continue
        dest = HIGHLIGHTS_SITE_PHOTOS / f"{photo_id}.webp"
        action = (
            "copy"
            if force or not should_skip_photo_copy(dest, force=False)
            else "skip"
        )
        plans.append(
            PhotoPlan(
                source=source,
                dest=dest,
                photo_id=photo_id,
                match_method=match_method,
                action=action,
            )
        )
    return plans


def print_copy_table(audio_plans: list[AudioPlan], photo_plans: list[PhotoPlan]) -> None:
    if not audio_plans and not photo_plans:
        print("No files to copy.")
        return

    print("\n=== Planned copies ===\n")

    for index, plan in enumerate(audio_plans, start=1):
        print(
            f"{index}. audio · {plan.clip_id} · {plan.category_folder} · {plan.action}"
        )
        print(f"   {repo_relative(plan.source)}")
        print(f"   → {repo_relative(plan.dest)}\n")

    photo_start = len(audio_plans) + 1
    for offset, plan in enumerate(photo_plans):
        index = photo_start + offset
        match_note = (
            f" · {plan.match_method}" if plan.match_method != "filename" else ""
        )
        print(f"{index}. photo · {plan.photo_id}{match_note} · {plan.action}")
        print(f"   {repo_relative(plan.source)}")
        print(f"   → {repo_relative(plan.dest)}\n")


def print_warnings(audio_plans: list[AudioPlan], photo_plans: list[PhotoPlan]) -> None:
    warnings = [plan for plan in audio_plans if plan.warning]
    unmatched = [plan for plan in photo_plans if plan.action == "unmatched"]
    if warnings:
        print("\n=== Warnings ===\n")
        for plan in warnings:
            print(f"  {repo_relative(plan.source)}: {plan.warning}")
    if unmatched:
        print("\n=== Unmatched photos ===\n")
        for plan in unmatched:
            print(
                f"  {repo_relative(plan.source)}: could not parse photo id "
                "(use CardinalPhotoComposite_DENASITE_YYYYMMDD, DENASITE_YYYY, or DENASITE_YYYYMMDD)"
            )
    if INGEST_OVERRIDES.is_file():
        print(f"\nMetadata overrides: {repo_relative(INGEST_OVERRIDES)} (applied at catalog build)")


def build_pipeline_steps(
    audio_plans: list[AudioPlan],
    *,
    skip_photos: bool,
    photo_source: Path | None,
) -> list[PipelineStep]:
    steps: list[PipelineStep] = []

    spectrogram_paths = spectrogram_inputs_for(audio_plans)
    if spectrogram_paths:
        steps.extend(
            [
                PipelineStep(
                    "Generate spectrograms",
                    "generate_highlights_spectrograms.py",
                    ("--files", *[str(path) for path in spectrogram_paths]),
                ),
                PipelineStep(
                    "Transcode to MP3",
                    "transcode_highlights.py",
                    ("--execute", "--remove-wav"),
                ),
                PipelineStep(
                    "Fix MP3 metadata",
                    "fix_highlights_metadata.py",
                ),
            ]
        )

    if audio_plans or not skip_photos:
        steps.append(
            PipelineStep("Build highlights catalog", "build_highlights_catalog.py")
        )

    if not skip_photos:
        steps.append(
            PipelineStep(
                "Sync site photos to catalog",
                "build_site_photos.py",
                ("--sync-catalog", "--execute"),
            )
        )
        if photo_source is not None and photo_source.is_dir():
            steps.append(
                PipelineStep(
                    "Import site photos",
                    "build_site_photos.py",
                    ("--execute", "--source", str(photo_source)),
                )
            )

    steps.append(PipelineStep("Validate catalog", "validate_highlights_catalog.py"))
    return steps


def print_pipeline_steps(
    *,
    execute: bool,
    audio_plans: list[AudioPlan],
    skip_photos: bool,
    photo_source: Path | None,
) -> None:
    steps = build_pipeline_steps(
        audio_plans,
        skip_photos=skip_photos,
        photo_source=photo_source,
    )
    mode = "Would run" if not execute else "Running"
    print(f"\n=== Pipeline ({mode.lower()}) ===\n")

    for index, step in enumerate(steps, start=1):
        command = step.script
        if step.args:
            command = f"{command} {' '.join(step.args)}"
        print(f"  {index}. {step.label}")
        print(f"     {command}")


def spectrogram_inputs_for(audio_plans: list[AudioPlan]) -> list[Path]:
    """Prefer WAV destination paths for spectrogram generation."""
    by_stem: dict[str, Path] = {}
    for plan in audio_plans:
        dest = plan.dest
        stem = dest.stem
        if dest.suffix.lower() == ".wav":
            by_stem[stem] = dest
        elif stem not in by_stem:
            by_stem[stem] = dest
    return sorted(by_stem.values())


def copy_audio(plans: list[AudioPlan], *, execute: bool, force: bool) -> list[AudioPlan]:
    copied: list[AudioPlan] = []
    for plan in plans:
        if plan.action == "skip" and not force:
            continue
        if not execute:
            copied.append(plan)
            continue
        plan.dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(plan.source, plan.dest)
        copied.append(plan)
    return copied


def copy_photos(plans: list[PhotoPlan], *, execute: bool, force: bool) -> list[PhotoPlan]:
    copied: list[PhotoPlan] = []
    for plan in plans:
        if plan.action == "skip" and not force:
            continue
        if not execute:
            copied.append(plan)
            continue
        from lib.site_photos import encode_webp

        encode_webp(plan.source, plan.dest)
        copied.append(plan)
    return copied


def run_script(script_name: str, *args: str) -> int:
    script = SCRIPTS_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode


def run_pipeline(
    audio_plans: list[AudioPlan],
    *,
    skip_photos: bool,
    photo_source: Path | None,
) -> int:
    steps = build_pipeline_steps(
        audio_plans,
        skip_photos=skip_photos,
        photo_source=photo_source,
    )
    total = len(steps)

    for index, step in enumerate(steps, start=1):
        print(f"\n=== Step {index}/{total}: {step.label} ===\n", flush=True)
        code = run_script(step.script, *step.args)
        if code != 0:
            return code

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest highlight audio and optional site photos from ingest/.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Copy files and run the highlights pipeline (default: dry-run)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing destination files even when size/mtime match",
    )
    parser.add_argument(
        "--skip-photos",
        action="store_true",
        help="Skip all site photo copy and catalog photo steps",
    )
    parser.add_argument(
        "--photo-source",
        type=Path,
        default=None,
        help="Optional cardinal photos directory for build_site_photos.py --execute",
    )
    return parser.parse_args()


def print_summary(
    audio_plans: list[AudioPlan],
    photo_plans: list[PhotoPlan],
    *,
    execute: bool,
    pipeline_code: int | None,
) -> None:
    audio_copy = sum(1 for plan in audio_plans if plan.action == "copy")
    audio_skip = sum(1 for plan in audio_plans if plan.action == "skip")
    photo_copy = sum(1 for plan in photo_plans if plan.action == "copy")
    photo_skip = sum(1 for plan in photo_plans if plan.action == "skip")

    print("\n=== Ingest summary ===\n")
    print(f"Audio discovered:  {len(audio_plans)}")
    print(f"  to copy:         {audio_copy}")
    print(f"  skipped:         {audio_skip}")
    if photo_plans:
        print(f"Photos discovered: {len(photo_plans)}")
        print(f"  to copy:         {photo_copy}")
        print(f"  skipped:         {photo_skip}")

    if not execute:
        print("\nDry-run only. Re-run with --execute to copy files and run the pipeline.")
    elif pipeline_code is not None:
        if pipeline_code == 0:
            print("\nPipeline completed successfully.")
        else:
            print(f"\nPipeline finished with errors (exit {pipeline_code}).", file=sys.stderr)


def main() -> int:
    args = parse_args()

    audio_files = discover_audio()
    photo_files = [] if args.skip_photos else discover_photos()

    if not audio_files and not photo_files:
        print("No audio or photos found under ingest/.")
        print(f"  Drop files in {repo_relative(INGEST_AUDIO)}/<CATEGORY>/")
        print(f"  Optional photos: {repo_relative(INGEST_SITE_PHOTOS)}/DENASITE_YYYY.jpg")
        return 0

    audio_plans = plan_audio(audio_files, force=args.force)
    photo_plans = plan_photos(photo_files, force=args.force) if photo_files else []

    print_copy_table(audio_plans, photo_plans)
    print_warnings(audio_plans, photo_plans)

    photo_source = args.photo_source.resolve() if args.photo_source else None
    if photo_source is not None and not photo_source.is_dir():
        print(f"\nWarning: --photo-source not found: {photo_source}", file=sys.stderr)
        photo_source = None

    print_pipeline_steps(
        execute=args.execute,
        audio_plans=audio_plans,
        skip_photos=args.skip_photos,
        photo_source=photo_source,
    )

    pipeline_code: int | None = None
    if args.execute:
        copy_audio(audio_plans, execute=True, force=args.force)
        if photo_plans:
            copy_photos(
                [plan for plan in photo_plans if plan.action != "unmatched"],
                execute=True,
                force=args.force,
            )

        pipeline_audio = [
            plan for plan in audio_plans if plan.dest.is_file() and plan.action == "copy"
        ]
        new_photos = any(plan.action == "copy" for plan in photo_plans)

        if pipeline_audio or new_photos or (photo_plans and not args.skip_photos):
            pipeline_code = run_pipeline(
                pipeline_audio,
                skip_photos=args.skip_photos,
                photo_source=photo_source,
            )

    print_summary(
        audio_plans,
        photo_plans,
        execute=args.execute,
        pipeline_code=pipeline_code,
    )
    return pipeline_code or 0


if __name__ == "__main__":
    raise SystemExit(main())
