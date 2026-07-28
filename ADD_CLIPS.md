# Adding highlight clips

## Prerequisites

- Python 3.12+ and **ffmpeg** — see [README.md](README.md#python-scripts-ingest-catalog-spectrograms) for venv setup
- Activate the venv before running scripts below

## 1. Drop files

Copy audio into the matching folder under `ingest/audio/` (e.g. `ingest/audio/GEOPHONY/`). Use the usual NPS filename pattern when possible.

Optionally add site photos under `ingest/site_photos/` — by clip id, audio filename prefix, or site key (see [ingest/README.md](ingest/README.md)).

Optionally copy `ingest/overrides.example.json` → `ingest/overrides.json` for per-clip title/species/date tweaks.

## 2. Preview

```bash
python3 scripts/ingest_clips.py
```

Review the planned copies and pipeline steps.

## 3. Run

```bash
python3 scripts/ingest_clips.py --execute
```

This copies files into `highlights/`, generates spectrograms, transcodes WAV → MP3, fixes metadata, rebuilds the catalog, syncs photo paths, and validates.

Optional flags: `--force`, `--skip-photos`, `--photo-source /path/to/cardinal_photos`.

## 4. Commit

Commit the generated assets and catalog — not the ingest staging files:

- `highlights/audio/`
- `highlights/spectrograms/`
- `highlights/site_photos/` (if added)
- `data/catalog/highlights.json`

`ingest/` contents are gitignored; only the folder structure is tracked.
