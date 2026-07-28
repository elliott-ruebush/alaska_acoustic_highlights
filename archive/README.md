# Archive

Ephemeral local backups from audio processing scripts (gitignored, safe to delete):

- `pre_loudness_normalize/` — originals before `scripts/normalize_clip_loudness.py --execute`
- `pre_trim/` — originals before `scripts/trim_clip_range.py`
- `trim_backups/` — originals before `scripts/trim_leading_silence.py`
- `removed_duplicates/` — clips removed from the highlights set

Production assets live in `highlights/audio/`. Curation source of truth is `data/highlights_catalog.json`.
