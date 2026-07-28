# Ingest staging

Drop new highlight clips here before running the ingest script.

## Audio

Place `.wav` or `.mp3` files in a category folder (created by default):

```
ingest/audio/BIRDS/
ingest/audio/MAMMALS/
ingest/audio/GEOPHONY/
ingest/audio/INSECTS/
ingest/audio/GENERAL/
```

Lowercase folder names (`birds/`, `geophony/`, …) also work.

## Site photos (optional)

Add photos under `ingest/site_photos/` (subfolders allowed). Matching order:

1. `{clip_id}.webp` / `.jpg` / `.png` — exact clip id (same as catalog)
2. Audio-style filename prefix — e.g. `DENABICR_20130809_020959.jpg`
3. Site key in filename — e.g. `DENATOKO_2018.jpg` matches a clip at that site (year-aware when possible)

Unmatched photos are reported in dry-run; rename or use clip id in the filename.

## Metadata overrides (optional)

Copy `overrides.example.json` to `overrides.json` (gitignored) to tweak titles, species, dates, etc. per clip. Keys are clip ids or file prefixes. Applied when the catalog is rebuilt during ingest.

## Run ingest

From the repo root:

```bash
python3 scripts/ingest_clips.py          # preview
python3 scripts/ingest_clips.py --execute
```

Requires the project venv — see root [README.md](../README.md#python-scripts-ingest-catalog-spectrograms).
