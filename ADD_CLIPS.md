# Adding highlight clips

Central guide for staging new clips and running ingest. Script reference: [scripts/README.md](scripts/README.md).

## Prerequisites

- **Python 3.12+** and **ffmpeg** on your PATH
- Project venv with dependencies installed

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-lock.txt
```

Run ingest with the venv Python (from repo root):

```bash
.venv/bin/python scripts/ingest_clips.py
```

`requirements-lock.txt` pins the full tree; `requirements.txt` is the direct dependency list.

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

**Site photos** (optional) — `ingest/site_photos/` (subfolders allowed). Matching order:

1. `{clip_id}.webp` / `.jpg` / `.png` — exact clip id (same as catalog)
2. Audio-style filename prefix — e.g. `DENABICR_20130809_020959.jpg`
3. Site key in filename — e.g. `DENATOKO_2018.jpg` matches a clip at that site (year-aware when possible)

Unmatched photos are reported in dry-run; rename or use clip id in the filename.

**Metadata overrides** (optional) — copy `ingest/overrides.example.json` → `ingest/overrides.json` (gitignored) to tweak title, species, or dates per clip id or file prefix. Applied when the catalog is rebuilt during ingest.

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
5. Site photo path sync
6. Catalog validation

**Note:** `--execute` rebuilds the **entire** catalog and runs metadata fix across all clips, not just the new ones. `highlights/audio/` is the source of truth; a full rebuild keeps the catalog consistent with the filesystem.

Optional flags: `--force`, `--skip-photos`, `--photo-source /path/to/cardinal_photos`.

**Timing (M1 MacBook Air, ~117 clips):** adding one new clip is about **10 s** end-to-end; a full catalog rebuild without regenerating spectrograms is about **5 s**. Regenerating all spectrograms is the slow path (~**7 min**).

## 4. Commit

Commit generated production assets — not ingest staging files:

- `highlights/audio/`
- `highlights/spectrograms/`
- `highlights/site_photos/` (if added)
- `data/catalog/highlights.json`
