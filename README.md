# ChromaDAM

**An AI-driven digital asset management platform with subject-aware color segmentation and multimodal search.**

A complete single-user final-year project: an interactive dashboard, FastAPI backend, persistent SQLite library, actual MobileSAM/CLIP adapters, K-means color analysis, and WCAG text contrast checks. No paid API or OpenAI API key is needed.

## Start on Windows

1. Install Python 3.10 or newer and Git if they are not installed.
2. Open this folder and double-click **start.cmd**. The first launch installs the core Python dependencies.
3. Keep the terminal open and visit **http://127.0.0.1:8000**.
4. For the full neural pipeline, double-click **install-ai.cmd**, wait for the model downloads, then restart the app. This downloads roughly 380 MB of model checkpoints, plus PyTorch and other packages. A CPU works; a recent laptop with 8 GB RAM or more is recommended, but performance depends on hardware.

Without the AI installation, uploads, K-means, exports, filters, and contrast checks still work. Segmentation is labelled **GrabCut fallback** and text search **keyword fallback**. These are not substitutes for validating the full AI project. Transparent PNGs correctly use **Image alpha**, even when MobileSAM is installed.

For an existing Python environment:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
.venv\Scripts\python.exe scripts/setup_models.py
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

macOS/Linux: replace `.venv\Scripts\python.exe` with `.venv/bin/python`. PyTorch compatibility and wheel availability depend on your Python/OS version; Python 3.10–3.12 is a sensible starting point.

## Try the workflow

- Upload a JPEG, PNG, or WebP product image (up to 20 MB / 25 megapixels).
- Open its card. Compare **Original** and **Subject cutout**. Use **Refine subject** and click a foreground point if the mask needs correction.
- Read 3–5 dominant subject swatches, hex/RGB values, and ratios. Click a hex code to copy it.
- Search `running shoe + at least 40% red`, or combine the search box with the color selector and minimum percentage.
- Choose **Custom hex** to use a color picker. Adjust ΔE tolerance to control approximate swatch matching.
- Use **Find visually similar** from an asset to search by its CLIP image embedding.
- Save tags, rename assets, favorite them, and export palettes as JSON, Tailwind v3 configuration, or Tailwind v4 CSS tokens.
- Open **Color & accessibility** to check text/background contrast.
- After enabling CLIP, open **AI pipeline → Rebuild missing embeddings** for earlier uploads. Re-upload or refine earlier images to recalculate masks with MobileSAM.

Optional sample illustrations are generated locally by `python scripts/make_samples.py`. Upload them from `samples/`. They are deliberately simple demo illustrations, not a real-world benchmark. Transparent samples exercise alpha masking; use the opaque sample to exercise MobileSAM.

## Architecture

```text
Browser dashboard (HTML/CSS/JavaScript)
       │ same-origin HTTP
FastAPI + validated endpoints
       ├── Image verification, EXIF orientation, max 1600px analysis copy
       ├── Existing alpha / MobileSAM point-prompted mask / labelled GrabCut fallback
       ├── CIELAB K-means → all foreground pixel assignments → palette ratios
       ├── OpenAI CLIP ViT-B/32 → normalized 512-dimensional image embeddings
       ├── SQLite metadata + embeddings, local PNG originals/cutouts
       └── Text/image cosine ranking + color-share filters + palette exports
```

The app stores a resized, orientation-corrected PNG analysis copy as `original.png`. This is not an archival replacement for the uploaded source file; retain your original files separately. The frontend uses system fonts and works without a frontend build step.

### Source layout

```text
backend/app.py       HTTP API, validation, upload/search/export workflow
backend/ai.py        actual MobileSAM and OpenAI CLIP adapters
backend/colors.py    CIELAB K-means, color families, ΔE matching, WCAG formula
backend/store.py     SQLite persistence
frontend/            responsive dashboard and asset inspector
scripts/             Windows launcher, model setup, sample generator
tests/               deterministic color/contrast and API integration tests
docs/PROJECT.md      scope, algorithms, evaluation plan, viva notes
data/                created at runtime; database, assets and model weights
```

### Important interpretation details

- **MobileSAM is promptable segmentation, not an automatic main-subject detector.** This implementation supplies an initial GrabCut foreground estimate to choose a point and bounding box, plus four corner background prompts by default. Off-center, multiple-subject, full-frame, or complex images may need a user click. The corners are assumptions, not verified background labels.
- The initial GrabCut proposal is computed at a maximum of 384 px, then resized to the analysis dimensions. Solid-color opaque images skip object segmentation entirely and are labelled **Full image (uniform color)**; there is no distinguishable subject in a solid swatch. Upload rows show elapsed processing time.
- K-means fits at most 16,000 sampled foreground pixels with a fixed seed in CIELAB. All foreground pixels are then assigned to clusters in batches; counts determine percentages. Swatches are the RGB means of their assigned pixels, so hex values are representative colors, not exact colors of every member pixel. Very low-color images can produce fewer than three swatches.
- The analysis is a maximum 1600px copy. Transparent input pixels with alpha >127 are counted once; semi-transparent coverage is not alpha-weighted.
- **Hex search** sums percentages of swatches within a ΔE76 distance (default 25) of the chosen hex. This is approximate palette matching, not an exact per-pixel red measurement. **Named families** use documented HSV rules in `colors.py`. “At least 40% red” means the sum of red-labelled cluster shares is ≥40% of the selected foreground.
- CLIP embeds the original analysis image to preserve context. Text-to-image and image-to-image searches rank normalized cosine similarity. The scores are not probabilities, and there is no universal relevance threshold. All matching indexed assets are returned in ranked order.
- The color lab checks solid foreground/background pairs against WCAG 2.2 text contrast thresholds. It does not certify a whole image, layout, or brand as accessible or safe.
- Model failures are visible on **AI pipeline**. Fallback modes always retain their actual provenance on each asset.

## Verification

```powershell
python -m unittest discover -s tests -v
node --check frontend/app.js
```

Tests use a temporary database, require the core dependencies, and do not download models. See `docs/VERIFICATION.md` for this build's actual verification results and limits.

The interactive API reference is at **http://127.0.0.1:8000/docs**.

## Data and deployment

By default, data is saved under this project's `data/` folder. Set `CHROMADAM_DATA` to an absolute directory before starting to use another location. Back up the folder while the app is stopped. Removing an asset deletes its database record and stored images.

This implementation binds to localhost and has no account system. To share it online, host the Python process on a suitable VM/container with persistent disk and add authentication, authorization, quotas, HTTPS, and appropriate background job handling. The Python ML backend cannot run inside a static website host or Cloudflare Worker. No public deployment is included in this deliverable.

## Upstream references

- [MobileSAM official repository](https://github.com/ChaoningZhang/MobileSAM) — model and predictor API; upstream licensing applies to code and weights.
- [OpenAI CLIP official repository](https://github.com/openai/CLIP) — image/text encoders and model download with checksum validation.
- [WCAG 2.2 contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum) — contrast thresholds and large-text definitions.

The included source pins CLIP and MobileSAM repository revisions. Python package versions allow compatible ranges; this is a student project baseline rather than a fully locked production release.
