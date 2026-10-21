"""Real optional MobileSAM + OpenAI CLIP adapters, with explicit fallback provenance."""
import importlib.util
import os
from pathlib import Path
import threading
import cv2
import numpy as np
from PIL import Image

DATA = Path(os.environ.get('CHROMADAM_DATA', Path(__file__).resolve().parents[1] / 'data')).resolve()
MODELS = DATA / 'models'
LOCK = threading.RLock()
_sam = None
_clip = None
_preprocess = None
_errors = {}
MODEL_NAME = 'ViT-B/32'


def status():
    sam_ready = importlib.util.find_spec('mobile_sam') is not None and (MODELS / 'mobile_sam.pt').exists()
    clip_ready = importlib.util.find_spec('clip') is not None and (MODELS / 'ViT-B-32.pt').exists()
    return {'segmentation': 'MobileSAM' if sam_ready else 'GrabCut fallback',
            'search': 'CLIP ViT-B/32' if clip_ready else 'Keyword fallback',
            'sam_ready': sam_ready, 'clip_ready': clip_ready, 'errors': dict(_errors),
            'clip_loaded': _clip is not None, 'sam_loaded': _sam is not None}


def load_sam():
    global _sam
    with LOCK:
        if _sam is None:
            from mobile_sam import sam_model_registry, SamPredictor
            import torch
            torch.set_num_threads(min(4, os.cpu_count() or 1))
            model = sam_model_registry['vit_t'](checkpoint=str(MODELS / 'mobile_sam.pt'))
            model.to(device='cpu').eval()
            _sam = SamPredictor(model)
        return _sam


def load_clip():
    global _clip, _preprocess
    with LOCK:
        if _clip is None:
            import clip
            import torch
            torch.set_num_threads(min(4, os.cpu_count() or 1))
            if not (MODELS / 'ViT-B-32.pt').exists():
                raise RuntimeError('CLIP weights missing. Run install-ai.cmd first.')
            _clip, _preprocess = clip.load(str(MODELS / 'ViT-B-32.pt'), device='cpu', jit=False)
            _clip.eval()
        return _clip, _preprocess


def embedding(image=None, text=None):
    if not status()['clip_ready']:
        return None
    try:
        import clip
        import torch
        with LOCK, torch.no_grad():
            model, preprocess = load_clip()
            value = model.encode_image(preprocess(image).unsqueeze(0)) if image is not None else model.encode_text(clip.tokenize([text], truncate=True))
            value = value.float()
            value /= value.norm(dim=-1, keepdim=True)
            _errors.pop('clip', None)
            return value[0].cpu().numpy().tolist()
    except Exception as exc:
        _errors['clip'] = str(exc)
        return None


def grabcut_mask(rgb, point=None):
    # GrabCut is only a coarse prompt proposal for MobileSAM. Building its graph
    # on megapixel images can take minutes on a laptop, especially flat colors.
    # Bound that graph independently of the retained analysis image resolution.
    full_height, full_width = rgb.shape[:2]
    scale = min(1.0, 384 / max(full_height, full_width))
    if scale < 1:
        rgb = cv2.resize(rgb, (max(16, round(full_width * scale)), max(16, round(full_height * scale))), interpolation=cv2.INTER_AREA)
        if point is not None:
            point = (point[0] * rgb.shape[1] / full_width, point[1] * rgb.shape[0] / full_height)
    height, width = rgb.shape[:2]
    x, y = point if point is not None else (width * .5, height * .5)
    gc_mask = np.full((height, width), cv2.GC_PR_BGD, dtype=np.uint8)
    pad_x, pad_y = max(1, width // 15), max(1, height // 15)
    gc_mask[pad_y:height-pad_y, pad_x:width-pad_x] = cv2.GC_PR_FGD
    gc_mask[:2] = gc_mask[-2:] = cv2.GC_BGD
    gc_mask[:, :2] = gc_mask[:, -2:] = cv2.GC_BGD
    # An explicit click is definite foreground. Without a click, do not force
    # the image center: the center may fall outside an off-center product.
    if point is not None:
        px, py = int(np.clip(x, 2, width - 3)), int(np.clip(y, 2, height - 3))
        gc_mask[max(2, py - 2):py + 3, max(2, px - 2):px + 3] = cv2.GC_FGD
    cv2.grabCut(rgb, gc_mask, None, np.zeros((1, 65)), np.zeros((1, 65)), 3, cv2.GC_INIT_WITH_MASK)
    mask = (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD)
    if mask.mean() < .001:
        raise ValueError('Empty foreground')
    if mask.shape != (full_height, full_width):
        mask = cv2.resize(mask.astype(np.uint8), (full_width, full_height), interpolation=cv2.INTER_NEAREST) > 0
    return mask


def segment(image, point=None):
    rgba = np.asarray(image.convert('RGBA'))
    rgb = np.ascontiguousarray(rgba[:, :, :3])
    alpha = rgba[:, :, 3]
    if np.any(alpha < 250) and point is None:
        mask = alpha > 127
        if mask.any():
            return mask, 'Image alpha', None
    # A solid swatch has no distinguishable foreground/background. Do not ask
    # graph cut or a neural model to invent an object in a constant image.
    if np.all(rgb == rgb[0, 0]):
        return np.ones(rgb.shape[:2], dtype=bool), 'Full image (uniform color)', None
    height, width = rgb.shape[:2]
    x, y = point if point is not None else (width * .5, height * .5)
    seed_mask = None
    box = None
    if point is None:
        try:
            seed_mask = grabcut_mask(rgb)
            distance = cv2.distanceTransform(seed_mask.astype(np.uint8), cv2.DIST_L2, 5)
            y, x = np.unravel_index(distance.argmax(), distance.shape)
            ys, xs = np.where(seed_mask)
            box = np.array([max(0, xs.min()-5), max(0, ys.min()-5), min(width-1, xs.max()+5), min(height-1, ys.max()+5)])
        except (cv2.error, ValueError):
            pass
    if status()['sam_ready']:
        try:
            with LOCK:
                predictor = load_sam()
                predictor.set_image(rgb)
                points = np.array([[x, y], [1, 1], [width - 2, 1], [1, height - 2], [width - 2, height - 2]], dtype=np.float32)
                masks, scores, _ = predictor.predict(point_coords=points, point_labels=np.array([1, 0, 0, 0, 0]), box=box, multimask_output=True)
                valid = [i for i, m in enumerate(masks) if .001 <= m.mean() <= .95]
                if not valid:
                    raise ValueError('No plausible subject mask. Refine the subject point.')
                idx = max(valid, key=lambda i: float(scores[i]))
                _errors.pop('sam', None)
                return masks[idx], 'MobileSAM', float(scores[idx])
        except Exception as exc:
            _errors['sam'] = str(exc)
    # A usable, clearly labelled CPU baseline when neural weights are unavailable.
    try:
        mask = seed_mask if seed_mask is not None else grabcut_mask(rgb, point)
        return mask, 'GrabCut fallback', None
    except (cv2.error, ValueError):
        return np.ones((height, width), dtype=bool), 'Full image fallback', None
