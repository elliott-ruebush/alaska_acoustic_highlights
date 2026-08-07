# Scripts - FEEL FREE TO READ THIS - BUT IT'S MAINLY INTENDED FOR LLM AGENTS

Agent reference for the Python CLIs in this directory.

**Adding new clips:** see [ADD_CLIPS.md](../ADD_CLIPS.md). Preferred entry point: `ingest_clips.py` (dry-run by default; `--execute` runs the full pipeline from `ingest/`).

Production assets live in `highlights/audio/`. Curation source of truth is `data/catalog/highlights.json`. See `data/README.md`.

Ingest staging lives in `ingest/`. Optional per-clip metadata: `ingest/overrides.json` (see `ingest/overrides.example.json`; applied by `build_highlights_catalog.py`).

## Inventory

| Script | Purpose |
|--------|---------|
| `ingest_clips.py` | **Preferred entry point:** stage audio/photos from `ingest/` → `highlights/`; run spectrogram, transcode, metadata, catalog, and validation pipeline |
| `build_catalog.py` | Walk external NPS ADSB volume; parse filenames; merge Xeno-Canto Excel metadata → `data/catalog/audio_clips.csv` |
| `build_highlights_catalog.py` | Build site-facing JSON from `highlights/audio/` (+ spectrograms, CSV enrichment, site names, MP3 tags) → `data/catalog/highlights.json` |
| `build_site_names.py` | Build `data/catalog/site_names.csv` from `Complete_Metadata_AKR_2001-2025.xlsx` |
| `build_site_photos.py` | Match cardinal site photos from external drive (or manual drops); copy WebP → `highlights/site_photos/`; update catalog `site_photo_path` |
| `generate_highlights_spectrograms.py` | Batch log-frequency spectrogram PNGs; mirror `highlights/audio/` → `highlights/spectrograms/` |
| `generate_spectrogram_guide.py` | One-off labeled spectrogram crop for the About page → `site/public/about/spectrogram-guide.png` |
| `transcode_highlights.py` | WAV → MP3 via ffmpeg (default dry-run); optional WAV removal after verify |
| `fix_highlights_metadata.py` | Rewrite ID3 on highlight MP3s (title, artist, album, genre, dates, XC fields) using CSV enrichment |
| `analyze_clip_silence.py` | QC: leading/trailing silence + internal gaps → `data/reports/clip_silence_report.csv` |
| `trim_leading_silence.py` | Trim leading silence for flagged clips; backs up to `archive/trim_backups/`; imports logic from `analyze_clip_silence.py` |
| `analyze_clip_loudness.py` | QC: RMS/LUFS (if pyloudnorm), peak, dynamic range → `data/reports/clip_loudness_report.csv` |
| `normalize_clip_loudness.py` | Two-pass ffmpeg loudnorm; archives originals → `archive/pre_loudness_normalize/`; writes to `highlights/audio_normalized/` |
| `trim_clip_range.py` | Manual time-range trim of one clip; backs up to `archive/pre_trim/`; updates catalog durations |

## Organization

**Naming pattern:** `verb_noun.py` or `build_*_catalog.py`

**Clusters:**

- **Catalog:** `build_catalog`, `build_highlights_catalog`, `build_site_photos`
- **Media prep:** `generate_highlights_spectrograms`, `transcode_highlights`, `fix_highlights_metadata`
- **QC:** `analyze_clip_silence`, `analyze_clip_loudness`
- **Edit:** `trim_leading_silence`, `trim_clip_range`, `normalize_clip_loudness`

**Internal dependency:** `trim_leading_silence.py` imports from `analyze_clip_silence.py` (same directory).

## Runtime

| Layer | Details |
|-------|---------|
| Language | Python 3 only (`#!/usr/bin/env python3`) |
| System | **ffmpeg** required for transcode, loudness normalize, and trim scripts |
| Python packages | `pandas`, `librosa`, `soundfile`, `mutagen`, `matplotlib`, `numpy`, `PIL` (Pillow) |
| Optional | `pyloudnorm` in `analyze_clip_loudness.py` (falls back to RMS-only without it) |
| Env vars | None documented; paths are CLI args or hardcoded defaults |

## Invocation

From repo root:

```bash
python3 scripts/<script>.py [args]
```

**Dry-run vs execute:** Many scripts default to measure/preview only. Pass `--execute` to write files:

- `transcode_highlights.py`
- `trim_leading_silence.py`
- `trim_clip_range.py`
- `normalize_clip_loudness.py`
- `build_site_photos.py`

### Key CLI args

| Script | Notable args |
|--------|----------------|
| `ingest_clips.py` | `--execute`, `--force`, `--skip-photos`, `--photo-source` |
| `build_catalog.py` | `--root`, `--output` (defaults: NPS volume → `data/catalog/audio_clips.csv`) |
| `build_highlights_catalog.py` | `--input`, `--output`, `--spectrograms-dir`, `--catalog` |
| `generate_highlights_spectrograms.py` | `--input`, `--output`, `--force`, `--dry-run`, `--limit`, `--files` |
| `transcode_highlights.py` | `--bitrate 192k`, `--execute`, `--remove-wav`, `--force` |
| `fix_highlights_metadata.py` | `--input`, `--catalog`, `--dry-run`, `--report`, `--include-wav` (writes by default) |
| `analyze_clip_silence` / `analyze_clip_loudness` | `--catalog`, `--report` / `--output` |
| `trim_leading_silence.py` | `--report`, `--pre-roll 0.25`, `--execute`, `--ids` |
| `trim_clip_range.py` | `--clip-id`, `--start`, `--end`, `--output-audio`, `--execute` (required args) |
| `normalize_clip_loudness.py` | `--target-i -18`, `--target-tp -1.5`, `--max-gain 12`, `--execute`, `--force` |
| `build_site_photos.py` | `--source`, `--execute`, `--force`, `--sync-catalog` |

**Post-transcode chain** (from `transcode_highlights.py`):

`fix_highlights_metadata.py` → `build_highlights_catalog.py`

**Spectrogram order:** generate from WAV first, then transcode to MP3 (spectrogram PNGs are unaffected).

## Repo relationships

```
/Volumes/NPS_ADSB_Data/...          build_catalog.py, build_site_photos.py (external)
        ↓
data/catalog/audio_clips.csv        enrichment for metadata + highlights catalog
        ↓
highlights/audio/                   production MP3s
highlights/spectrograms/            generate_highlights_spectrograms.py
highlights/site_photos/             build_site_photos.py
        ↓
data/catalog/highlights.json        build_highlights_catalog.py (+ build_site_photos updates)
        ↓
site/src/lib/catalog.ts             reads ../data/catalog/highlights.json
site/public/highlights → ../../highlights   site/scripts/link-public-assets.mjs (Node, not here)
```

**`data/reports/`** (gitignored audit outputs): `clip_silence_report.csv`, `clip_loudness_report.csv`, `clip_loudness_normalize_report.{json,csv}`, `spectrogram_generation_report.json`, `transcode_highlights_report.csv`, `metadata_fix_report.csv`, `site_photos_report.json`, `trim_leading_silence_report.json`

**`archive/`** (gitignored backups): `pre_loudness_normalize/`, `pre_trim/`, `trim_backups/`

**Staging output:** `highlights/audio_normalized/` (normalize script; copy into `highlights/audio/` after review)

## Typical workflows

1. **Add new clips:** drop files in `ingest/` → `ingest_clips.py` (preview) → `ingest_clips.py --execute`. See [ADD_CLIPS.md](../ADD_CLIPS.md).
2. **Refresh site catalog after audio changes:** `build_highlights_catalog.py` (re-run `build_site_photos.py --sync-catalog` if photos changed).
3. **New WAV batch (manual):** `generate_highlights_spectrograms.py` → `transcode_highlights.py --execute` → `fix_highlights_metadata.py` → `build_highlights_catalog.py`.
4. **QC loop:** `analyze_clip_silence.py` → `trim_leading_silence.py --execute`; `analyze_clip_loudness.py` → `normalize_clip_loudness.py --execute`.
5. **Manual edit:** `trim_clip_range.py --clip-id ID --start M:SS --end M:SS --execute`.
6. **Full source inventory** (needs mounted NPS volume): `build_catalog.py`.

## Caution

Destructive scripts backup first but overwrite `highlights/audio/` in place when executed. Prefer dry-run first. `fix_highlights_metadata.py` writes tags unless `--dry-run` is passed.
