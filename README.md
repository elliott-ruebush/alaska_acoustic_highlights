# Soundscapes of Alaska

Searchable library of Alaskan National Park acoustic highlights — audio clips with spectrograms.

Audio from [NPS Natural Sounds and Night Skies Division](https://www.nps.gov/subjects/sound/measure.htm).

**Site:** [freerange-elliott.com/alaska_acoustic_highlights](https://freerange-elliott.com/alaska_acoustic_highlights)  

**Adding clips:** see [ADD_CLIPS.md](ADD_CLIPS.md) (development setup, filename format, ingest workflow).

## Site (local dev)

```bash
cd site && npm install && npm run dev
```

## Python environment

For ingest and media scripts. Full workflow: [ADD_CLIPS.md](ADD_CLIPS.md).

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-lock.txt
```

Requires Python 3.12+ and **ffmpeg** on your PATH. Script inventory: [scripts/README.md](scripts/README.md).
