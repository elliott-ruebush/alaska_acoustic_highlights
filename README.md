# Soundscapes of Alaska

Searchable library of Alaskan National Park acoustic highlights — audio clips with spectrograms.

Audio from [NPS Natural Sounds and Night Skies Division](https://www.nps.gov/subjects/sound/measure.htm).

**Clone size:** on the order of **~300 MB** today (mostly media under `highlights/` — audio, spectrograms, gallery thumbs, site photos — and grows as clips are added). A fresh clone is usually quick; older clones may need a reset after history is rewritten (see below).

**Site:** [freerange-elliott.com/alaska_acoustic_highlights](https://freerange-elliott.com/alaska_acoustic_highlights)  

**Adding clips:** see [ADD_CLIPS.md](ADD_CLIPS.md) (development setup, filename format, ingest workflow).

### Already cloned? After a history rewrite

If `git pull` fails with unrelated histories, either **re-clone** or reset your local `main` to match GitHub:

```bash
git fetch origin
git checkout main
git reset --hard origin/main
```

Discard any unpushed local commits first, or stash/copy work elsewhere.

## Site (local dev)

Requires **Node >=22.12.0** (see `site/package.json`).

```bash
cd site && npm install && npm run dev
```

`npm run dev` and `npm run build` run `site/scripts/link-public-assets.mjs` first (via `predev`/`prebuild`) to symlink `site/public/highlights` → `../../highlights`.

## Python environment

For ingest and media scripts. Full workflow: [ADD_CLIPS.md](ADD_CLIPS.md).

Requires **Python 3.12+** and **ffmpeg** on your PATH. Direct dependencies live in `pyproject.toml`; `requirements-lock.txt` pins the full tree.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-lock.txt
```

Run Python unit tests from the repo root:

```bash
pytest
```

Script inventory: [scripts/README.md](scripts/README.md).
