# Soundscapes of Alaska

Searchable library of Alaskan National Park acoustic highlights — audio clips with spectrograms.

Audio from [NPS Natural Sounds and Night Skies Division](https://www.nps.gov/subjects/sound/measure.htm).

**Site:** [freerange-elliott.com/alaska_acoustic_highlights](https://freerange-elliott.com/alaska_acoustic_highlights)  

**Adding clips:** see [ADD_CLIPS.md](ADD_CLIPS.md).

## Site (local dev)

```bash
cd site && npm install && npm run dev
```

## Python scripts (ingest, catalog, spectrograms)

Requires Python 3.12+ and **ffmpeg** on your PATH.

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-lock.txt
```

Use `requirements.txt` for the direct dependency list; `requirements-lock.txt` pins the full tree for reproducible installs.
