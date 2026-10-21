# ChromaDAM — technical project notes

## Problem and objective

Creative teams often organize images with filenames, folders, and manual tags. ChromaDAM adds subject-restricted color analysis and natural-language visual ranking to an image library. The central question is whether foreground color filtering finds relevant assets more precisely than whole-image palettes when backgrounds have strong colors.

The supplied brief describes MobileSAM as a Meta model. More precisely, MobileSAM is a lightweight SAM adaptation by Chaoning Zhang and collaborators; Meta developed the original Segment Anything Model. Cite both appropriately in your college report.

## Implemented scope

- Single-user persistent image library with upload, rename, tags, favorite, delete, and detail view.
- Real MobileSAM predictor using an automatically estimated foreground point and box plus negative corner prompts. The user can replace the foreground point by clicking.
- Existing alpha mask support and explicitly labelled OpenCV GrabCut/full-image fallbacks.
- Deterministic K-means with k-means++ initialization in CIELAB, at most 16,000 fit samples, and all-pixel foreground assignment.
- Real OpenAI CLIP ViT-B/32 image/text embeddings, text and image similarity ranking.
- Combined color-family/custom-hex filters and minimum foreground color share, plus basic parsing of `at least N% color`.
- WCAG 2.2 text contrast checker, JSON exports, Tailwind v3 CJS config and v4 CSS tokens.
- CPU execution, SQLite persistence, FastAPI interactive API documentation.

## Mathematical foundation

### Segmentation

MobileSAM returns multiple candidate Boolean masks and predicted IoU scores for supplied prompts. Reject masks with <0.1% or >95% image coverage, then select the remaining mask with the highest predicted IoU. The initial point and box come from a GrabCut foreground estimate (deepest interior pixel and foreground bounds); if that fails, the point defaults to the image center. This is a heuristic for an isolated object. It is not semantic detection of the “most important” object. Mask refinement is essential for ambiguous scenes.

### Subject palette

Convert selected RGB pixels to floating-point CIELAB (L* approximately 0–100). Fit K-means by minimizing within-cluster squared Euclidean distance. Assign every foreground pixel to its nearest fitted center. For cluster i:

`share_i = 100 × selected_pixels_assigned_to_i / all_selected_pixels`

The displayed swatch is the arithmetic mean RGB value of assigned pixels, rounded to 8-bit channels. Color percentages may differ slightly from 100 after display rounding. Cluster counts are retained in JSON exports.

### Color filters

Named colors use hue/saturation/value rules. The exact thresholds live in `backend/colors.py`; these are an explainable baseline, not learned universal color names. A custom hex filter computes Euclidean CIELAB ΔE76 from its color to each representative swatch and sums shares for swatches within the selected tolerance.

### Multimodal search

CLIP provides two encoders, `f(image)` and `g(text)`. Normalize each output by its L2 norm. Rank image i by `score_i = normalized_g(query) dot normalized_f(image_i)`. Image similarity uses another asset's image vector as the query vector. Apply color and favorite filters before returning the ranking.

No softmax probability is shown: its values would depend on the candidate library and could imply unwarranted certainty. Assets without embeddings are excluded from semantic ranking and surfaced as an index notice. Fallback keyword search uses filenames and tags and is labelled clearly.

### WCAG contrast

Linearize each sRGB channel c in [0,1]: c/12.92 if c≤0.04045, otherwise ((c+0.055)/1.055)^2.4. Relative luminance is `0.2126R + 0.7152G + 0.0722B`. Contrast is `(L_lighter+0.05)/(L_darker+0.05)`.

Compare the unrounded ratio to AA thresholds (4.5 normal/3 large) and AAA thresholds (7 normal/4.5 large). The UI rounds only for display.

## Evaluation plan for a final-year submission

Do not claim accuracy, latency, or retrieval quality until measured on a defined dataset. The included synthetic examples are for demos, not scientific evidence.

1. Assemble at least 50–100 appropriately licensed images with varied backgrounds, off-center subjects, multiple objects, and transparent inputs. Keep images and evaluation queries separate from tuning examples.
2. Hand-label foreground masks for a subset. Measure segmentation IoU against ground truth, before and after a user refinement click. Record failure examples.
3. Compare whole-image and foreground palettes against manually measured foreground color shares. Report absolute percentage-point error for named/brand color queries and explain the color definition used.
4. Create text, color-only, and combined relevance queries with human relevance judgments. Compare keyword baseline, CLIP-only ranking, and CLIP plus foreground color filters using Precision@5, Recall@10, or nDCG@10.
5. Measure first-load and warm upload latency, segmentation time, palette time, and search latency. State CPU, RAM, image dimensions, model versions, library size, and whether weights were already cached.
6. Test transparent images, all-one-color subjects, tiny/invalid/oversized files, no matching assets, missing models, and persistence after restart.

## Suggested demonstration

1. Show pipeline availability and explain the local models.
2. Upload an opaque product image against a contrasting background.
3. Compare original/cutout, refine if needed, inspect the foreground ratios.
4. Search its subject with a minimum named-color share. Explain approximate clustering and color-family rules.
5. Search a visual style phrase and discuss ranked CLIP results.
6. Export a palette and demonstrate a WCAG passing and failing color pair.

## Limitations and further work

- Automatic main-subject detection would require an object detector, saliency model, or robust automatic-mask ranking rather than the current point heuristic.
- SQLite JSON vectors and linear scans fit a small student library. Larger collections should use vector indexes and pagination.
- Synchronous inference serializes model access and may be slow under concurrent load. A production version should use background jobs, model workers, task status, and resource limits.
- Add authentication, per-user libraries, source-file retention, duplicate detection, soft deletion, robust upload-body limits, and storage quotas before shared deployment.
- Preset brand colors, brand-specific tolerances, and an actual brand rules engine are future extensions; the current color lab is a text contrast calculator.
- Input color profiles are not normalized to calibrated sRGB. Professional color workflows need ICC-aware conversion, calibration, and more advanced perceptual matching such as CIEDE2000.
- No model training occurs here. The contribution is integration, subject-restricted color analytics, combined retrieval, interaction design, and evaluation.

## References

- MobileSAM: https://github.com/ChaoningZhang/MobileSAM
- CLIP: https://github.com/openai/CLIP
- CLIP paper: https://arxiv.org/abs/2103.00020
- WCAG 2.2: https://www.w3.org/TR/WCAG22/
