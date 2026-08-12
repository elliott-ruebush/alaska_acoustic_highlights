# Adding highlight clips

Central guide for staging new clips and running ingest. Script reference: [scripts/README.md](scripts/README.md).

## Prerequisites

- **Python 3.12+** and **ffmpeg** on your PATH
- Project venv with dependencies installed

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-lock.txt
```

Run ingest with the venv Python (from repo root):

```bash
python scripts/ingest_clips.py          # Windows / activated venv
# or: .venv/bin/python scripts/ingest_clips.py
```

Direct dependencies are in `pyproject.toml`; `requirements-lock.txt` pins the full install tree.

## Audio filename format

Use the NPS prefix pattern so the catalog gets a stable id, park/site codes, and recorded date/time:

```
PARK(4)SITE_YYYYMMDD_HHMMSS Description.ext
```

**Example:** `DENATOKO_20160513_130223 Animal Movement, Bird Chorus, and River.wav`

| Segment | Meaning |
|---------|---------|
| `PARK` | Four-letter park code (e.g. `DENA`, `GAAR`) |
| `SITE` | Site code (e.g. `TOKO`, `WOCR`) |
| `YYYYMMDD` / `HHMMSS` | Recording date and time |
| `Description` | Human-readable title source; processing suffixes stripped for display |

**Processing suffixes** (optional, stripped from the site title): `TRIM`, `AMPLIFY`, `BANDPASS`, `NOISE REDUCTION`, etc. Full list: [scripts/lib/nps_filename.py](scripts/lib/nps_filename.py).

**Category** comes from the folder under `ingest/audio/` (`BIRDS/`, `MAMMALS/`, `GEOPHONY/`, `INSECTS/`, `GENERAL/`) — not from the filename.

**Cross-platform filenames:** avoid `:` in filenames (invalid on Windows and breaks `git clone` there). Use a dash or comma instead (e.g. `Wolves Howling - Solo Voice` rather than `Wolves Howling: Solo Voice`).

### If the prefix is missing

Ingest will **warn** but still copy the file. You get a weaker metadata catalog entry: fallback clip id, no park/site/date fields, and site photos won't match by prefix. Follow the pattern above for production clips.

## 1. Drop files

**Audio** — copy `.wav` or `.mp3` into a category folder:

```
ingest/audio/BIRDS/
ingest/audio/MAMMALS/
ingest/audio/GEOPHONY/
ingest/audio/INSECTS/
ingest/audio/GENERAL/
```

Lowercase folder names (`birds/`, `geophony/`, …) also work.

**Site photos** (optional) — `ingest/site_photos/` (subfolders allowed). Filenames must encode park/site and when the photo was taken:

- `CardinalPhotoComposite_DENASITE_YYYYMMDD.jpg` (preferred cardinal composite)
- `DENASITE_YYYYMMDD.jpg` or `DENASITE_YYYY.jpg` (year-only → January 1)

Photos are stored once per site/date as `highlights/site_photos/{photo_id}.webp` (e.g. `denatoko_20160513.webp`). Clips reference the shared photo via `site_photo_id` in the catalog — assigned automatically to the closest photo date at the same site.

Unparseable filenames are reported in dry-run; fix the name and re-run.

**Metadata overrides** (optional) — copy `ingest/overrides.example.json` → `ingest/overrides.json` (gitignored) to tweak title, species, dates, or `site_photo_id` per clip id or file prefix. Applied when the catalog is rebuilt during ingest.

`ingest/` contents are gitignored; only the folder structure is tracked.

## 2. Preview

```bash
.venv/bin/python scripts/ingest_clips.py
```

Review planned copies, warnings, unmatched photos, and pipeline steps. Fix filenames before executing.

## 3. Run

```bash
.venv/bin/python scripts/ingest_clips.py --execute
```

This copies staged files into `highlights/`, then runs:

1. Spectrogram generation (new audio only)
2. WAV → MP3 transcode
3. ID3 metadata fix
4. Full catalog rebuild
5. Site photo catalog sync (`build_site_photos.py --sync-catalog --execute`)
6. Catalog validation

**Note:** `--execute` runs the full pipeline, which rebuilds the catalog when it runs (new audio copies, photo sync, etc.) and runs metadata fix across all clips, not just new ones. For a catalog-only refresh without ingest, run `build_highlights_catalog.py` (and `build_site_photos.py --sync-catalog --execute` if photos changed) directly. `highlights/audio/` is the source of truth.

Optional flags: `--force`, `--skip-photos`, `--photo-source /path/to/cardinal_photos`.

**Timing (M1 MacBook Air, ~117 clips):** adding one new clip is about **10 s** end-to-end; a full catalog rebuild without regenerating spectrograms is about **5 s**. Regenerating all spectrograms is the slow path (~**7 min**).

## 4. Commit

Commit generated production assets — not ingest staging files:

- `highlights/audio/`
- `highlights/spectrograms/`
- `highlights/spectrograms_thumbs/` (gallery WebP thumbnails; full PNGs remain for clip pages)
- `highlights/site_photos/` (if added)
- `data/catalog/highlights.json`
- `data/catalog/site_photos.json`
