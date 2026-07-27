# Deployment: Git, LFS, and GitHub Pages

## Asset sizes

| Path | Size | Role |
|------|------|------|
| `highlights/audio/` | ~298 MB | 126 MP3 192k clips |
| `highlights/spectrograms/` | ~47 MB | 156 PNGs |
| `data/` | ~2 MB | Catalogs + run reports |
| **Deploy total** | **~345 MB** | Fits GitHub Pages soft 1 GB site limit |

---

## Git LFS: do we need it?

**Recommendation for MVP: skip LFS, commit media directly.**

| Approach | Pros | Cons |
|----------|------|------|
| **Plain git** (recommended) | GitHub Pages serves files as-is; no LFS install; simple clone/push | ~345 MB clone; large repo history if assets churn |
| **Git LFS** | Keeps git history small when swapping clips | Requires `git-lfs` locally; Pages needs `lfs: true` in Actions checkout; free tier = 1 GB storage + 1 GB/month bandwidth |
| **External CDN** (S3/R2) | Best for scale | Extra infra; defer until needed |

Our files are well under GitHub's 100 MB per-file limit (largest MP3s ~25 MB). A 345 MB repo is large but workable for a media MVP.

### If you later want LFS

```bash
brew install git-lfs
git lfs install
git lfs track "highlights/**/*.mp3" "highlights/**/*.png"
git add .gitattributes
# Uncomment the LFS lines in .gitattributes if using the template
```

---

## Suggested repo structure for static site

Two common patterns:

### Option A — Monorepo (recommended)

```
alaska_acoustic_highlights/
  highlights/          # media (tracked in git)
  data/                # highlights_catalog.json
  scripts/             # build pipeline
  site/                # Astro / Vite / 11ty app
    public/            # empty — or symlink highlights/ at build time
    src/
  .github/workflows/
    pages.yml          # build site + deploy
```

Build step copies or references `../highlights/` and `../data/highlights_catalog.json` into the site output. One repo, one deploy.

### Option B — Split deploy branch

- `main`: code + small data only
- `gh-pages` or Actions artifact: built HTML + copied assets

More moving parts; only worth it if `main` should stay lightweight for contributors without media.

---

## GitHub Pages setup

1. **Enable Pages** in repo Settings → Pages → Source: **GitHub Actions**
2. **Workflow** (`.github/workflows/pages.yml`) should:
   - `checkout` with `fetch-depth: 0`
   - Install Node, build `site/`
   - Copy `highlights/` and `data/highlights_catalog.json` into publish dir
   - Upload artifact + deploy via `actions/deploy-pages`

3. **Paths in the site** should be relative, e.g.:
   - `/highlights/audio/BIRDS/...mp3`
   - `/highlights/spectrograms/BIRDS/...png`
   - Catalog JSON at `/data/highlights_catalog.json` or bundled at build time

4. **Custom domain** (optional): `soundscapes.alaska...` — free HTTPS via GitHub

### Bandwidth

GitHub Pages free tier: ~100 GB/month soft bandwidth. At ~2–3 MB per page view (audio + spectrogram), that's plenty for an MVP/educational site unless a clip goes viral.

---

## What to commit vs ignore

**Commit:**
- `highlights/` (audio + spectrograms)
- `data/highlights_catalog.json`, `audio_clips_catalog.csv`, `CATALOG_README.md`
- `scripts/`, `docs/`, `SCOPING.md`, `README.md`
- `archive/` (small, historical)
- Audit reports (`metadata_fix_report.csv`, etc.) — optional

**Ignore** (`.gitignore`):
- `.venv/`, `.matplotlib/`, `__pycache__/`
- `site/node_modules/`, `site/dist/`
- `output/` (deleted prototype dir)
- Local secrets (`.env`)

**Never commit:**
- NPS source volume paths or credentials
- Full 44 GB master WAV tree

---

## First push checklist

```bash
git init
git remote add origin https://github.com/elliott-ruebush/alaska_acoustic_highlights.git
git add README.md SCOPING.md docs/ scripts/ data/ highlights/ archive/ .gitignore .gitattributes
git commit -m "Initial commit: highlights pipeline and 126-clip MVP assets"
git branch -M main
git push -u origin main
```

Expect the first push to take several minutes (~345 MB upload).
