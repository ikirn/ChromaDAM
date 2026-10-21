# Build verification — 16 October 2026

## Upload fix — 17 October 2026

A real upload exposed slow full-resolution GrabCut graph construction on a 1000×1000 solid-color image. The proposal graph is now capped at 384 px and three iterations, while the output mask retains the analysis image dimensions. Constant opaque images bypass segmentation and use the whole image with explicit provenance. Upload rows now show elapsed CPU processing time.

All **6 tests pass**, including regressions that assert the graph resolution cap and full-size output mask, and that uniform images never invoke GrabCut or MobileSAM. The real-model smoke test also passes after this change (synthetic shoe IoU 0.9789; 512-dimensional normalized CLIP vectors; correct shoe/headphone query ordering). The pending uniform green upload was recovered through the HTTP API with a single #008000 swatch at 100%; it completed in 6.52 seconds including the first CLIP model load.

## Passed

- `python -m unittest discover -s tests -v`: **4 tests passed**, covering exact 60/40 foreground ratios with excluded transparent background, named/hex color shares, black/white 21:1 contrast, identical-color 1:1 contrast, AA threshold boundary pairs, upload/metadata validation, filter boundaries, natural-language color clause parsing, favorites, JSON/Tailwind/CSS export, media retrieval, and asset deletion.
- `node --check frontend/app.js`: passed.
- `scripts/setup_models.py`: downloaded upstream MobileSAM (38.8 MiB) and CLIP ViT-B/32 (337.6 MiB) checkpoints; CLIP SHA-256 verified against the upstream URL hash; both models loaded on CPU.
- `scripts/verify_ai.py`: passed against real model inference. On one synthetic opaque shoe illustration, MobileSAM foreground IoU against the original alpha mask was **0.9790**. A manual foreground prompt also produced a plausible MobileSAM mask.
- CLIP smoke test: 512-dimensional image embedding, norm **1.000000**. Query “a red running shoe” scored **0.3050** against the shoe and **0.1849** against the headphone illustration.
- Real-model smoke test completed in approximately **10.18 s** on this machine, including model loading and several inference calls. This is an observed run, not a performance guarantee or a workload benchmark.
- `scripts/seed_demo.py`: uploaded six demo illustrations through the FastAPI application; all six obtained CLIP embeddings; the opaque shoe used MobileSAM, and five transparent PNGs used their existing alpha masks. The health endpoint reported no AI runtime errors.
- Live HTTP request to `running shoe + at least 40% red`: **200**, semantic mode, shoe ranked first with **58.52%** red-family cluster share. A lower-ranked terracotta plant also met the color filter; semantic search ranks candidates rather than asserting a strict object category match.
- Windows launcher `scripts/launch.ps1` started the prepared environment and served the dashboard successfully.
- Browser checks: library rendering with six assets, combined query results, asset inspector, original/cutout toggle and palette display, and color lab showing **5.16:1** for white on `#6D4AFF` with the expected AA/AAA statuses.

## Tested environment

Windows, Python 3.10, CPU inference. Relevant installed versions:

| Component | Version |
|---|---|
| FastAPI | 0.135.1 |
| Uvicorn | 0.42.0 |
| python-multipart | 0.0.22 |
| NumPy | 2.2.6 |
| Pillow | 12.1.1 |
| OpenCV | 4.13.0.92 |
| PyTorch | 2.10.0 CPU |
| TorchVision | 0.25.0 |
| timm | 1.0.22 |
| ftfy | 6.3.1 |
| httpx | 0.28.1 |

The prepared environment inherits existing system packages, with AI adapters and missing dependencies installed in the project virtual environment. Fresh-machine setup uses the supplied requirements. OpenCV was tested using the installed desktop wheel; the portable requirements use the equivalent headless Python API.

## Limits of this verification

This establishes a working local integration, not general segmentation accuracy or retrieval quality. No real-world benchmark, multi-user load test, exhaustive browser automation, mobile-device test, or public deployment was completed. The synthetic IoU result must not be presented as dataset-wide model accuracy. A fresh-machine installation has not been reproduced on another operating system.

Automatic masks still need inspection. Color-family thresholds are heuristic and cluster colors are averages. Model-predicted mask quality is a raw regression output and can slightly exceed 1; it is not ground-truth IoU. Larger libraries use linear vector scans, and inference runs synchronously with a model lock. See `PROJECT.md` for a reproducible evaluation plan and extension work.

The source ZIP excludes model weights, the virtual environment, and runtime database/uploads. They remain in the prepared local project folder. Recreate them on another computer using the installation and sample scripts.
