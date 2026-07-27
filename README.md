# Soundscapes of Alaska

Public-facing library of NPS Alaska acoustic highlights — searchable audio clips with pre-rendered spectrograms.

**Remote:** [github.com/elliott-ruebush/alaska_acoustic_highlights](https://github.com/elliott-ruebush/alaska_acoustic_highlights)

## Repo layout

```
highlights/
  audio/           # 126 MP3 clips (~298 MB)
  spectrograms/    # 156 PNGs (~47 MB)
data/
  highlights_catalog.json    # MVP site catalog (126 clips)
  audio_clips_catalog.csv    # Full source catalog (4,210 files)
scripts/                     # Build pipeline
archive/                     # Superseded prototypes & MVP curation tools
```

## Pipeline

```bash
python -m venv .venv && .venv/bin/pip install librosa matplotlib mutagen pandas soundfile

.venv/bin/python scripts/build_highlights_catalog.py
.venv/bin/python scripts/generate_highlights_spectrograms.py
.venv/bin/python scripts/transcode_highlights.py --execute --remove-wav
.venv/bin/python scripts/fix_highlights_metadata.py --report
.venv/bin/python scripts/build_highlights_catalog.py
```

See [SCOPING.md](SCOPING.md) for project background and [docs/DEPLOY.md](docs/DEPLOY.md) for git LFS and GitHub Pages setup.

## Status

- ✅ 126-clip highlights set curated
- ✅ Spectrograms + MP3 transcode complete
- 🔲 Static site scaffold
- 🔲 Legal/privacy sign-off before public launch
