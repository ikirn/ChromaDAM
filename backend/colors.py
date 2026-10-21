"""Deterministic K-means in CIELAB; ratios count all selected subject pixels."""
import colorsys
import cv2
import numpy as np


def hex_rgb(value):
    value = value.lstrip('#')
    if len(value) != 6 or any(c not in '0123456789abcdefABCDEF' for c in value):
        raise ValueError('Use a six-digit hexadecimal color, such as #E53935.')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def family(rgb):
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    if v < .17:
        return 'black'
    if s < .12:
        return 'white' if v > .86 else 'gray'
    h *= 360
    if h < 18 or h >= 345:
        return 'red'
    if h < 45:
        return 'brown' if v < .65 else 'orange'
    if h < 70:
        return 'yellow'
    if h < 165:
        return 'green'
    if h < 195:
        return 'cyan'
    if h < 255:
        return 'blue'
    if h < 290:
        return 'purple'
    return 'pink'


def extract_palette(rgb, mask, k=5):
    pixels = rgb[mask > 0]
    if not len(pixels):
        raise ValueError('No subject pixels found. Try selecting a subject point.')
    # Bounded, repeatable sample for fitting. Assignment below uses every pixel.
    rng = np.random.default_rng(42)
    sample = pixels[rng.choice(len(pixels), min(16000, len(pixels)), replace=False)]
    lab = cv2.cvtColor(sample.reshape(1, -1, 3).astype(np.float32) / 255, cv2.COLOR_RGB2LAB).reshape(-1, 3)
    k = min(k, len(np.unique(sample, axis=0)))
    # Local NumPy Lloyd iterations avoid process-global OpenCV RNG races.
    centers = [lab[rng.integers(len(lab))]]
    for _ in range(1, k):
        d2 = np.min(np.sum((lab[:, None] - np.array(centers)[None]) ** 2, axis=2), axis=1)
        centers.append(lab[rng.choice(len(lab), p=d2 / d2.sum())])
    centers = np.array(centers)
    for _ in range(35):
        labels = np.argmin(np.sum((lab[:, None] - centers[None]) ** 2, axis=2), axis=1)
        updated = np.array([lab[labels == i].mean(0) if np.any(labels == i) else centers[i] for i in range(k)])
        if np.max(np.abs(updated - centers)) < .02:
            centers = updated
            break
        centers = updated
    counts = np.zeros(k, dtype=np.int64)
    sums = np.zeros((k, 3), dtype=np.float64)
    for start in range(0, len(pixels), 30000):
        chunk = pixels[start:start + 30000]
        clab = cv2.cvtColor(chunk.reshape(1, -1, 3).astype(np.float32) / 255, cv2.COLOR_RGB2LAB).reshape(-1, 3)
        ids = np.argmin(np.sum((clab[:, None] - centers[None]) ** 2, axis=2), axis=1)
        counts += np.bincount(ids, minlength=k)
        for i in range(k):
            sums[i] += chunk[ids == i].sum(axis=0)
    result = []
    for i in np.argsort(-counts):
        if not counts[i]:
            continue
        color = np.rint(sums[i] / counts[i]).astype(int).tolist()
        result.append({'hex': '#' + ''.join(f'{c:02X}' for c in color), 'rgb': color,
                       'percentage': round(float(counts[i]) * 100 / len(pixels), 4),
                       'pixels': int(counts[i]), 'family': family(color)})
    return result


def color_share(palette, color, tolerance=25):
    if not color:
        return 100.0
    if not color.startswith('#'):
        return sum(p['percentage'] for p in palette if p['family'] == color.lower())
    target = np.array(hex_rgb(color), dtype=np.float32).reshape(1, 1, 3) / 255
    tlab = cv2.cvtColor(target, cv2.COLOR_RGB2LAB)[0, 0]
    colors = np.array([p['rgb'] for p in palette], dtype=np.float32).reshape(1, -1, 3) / 255
    labs = cv2.cvtColor(colors, cv2.COLOR_RGB2LAB)[0]
    return sum(p['percentage'] for p, distance in zip(palette, np.linalg.norm(labs - tlab, axis=1)) if distance <= tolerance)


def contrast(foreground, background):
    def luminance(color):
        c = np.array(hex_rgb(color)) / 255
        linear = np.where(c <= .04045, c / 12.92, ((c + .055) / 1.055) ** 2.4)
        return float(linear @ np.array([.2126, .7152, .0722]))
    a, b = sorted((luminance(foreground), luminance(background)))
    ratio = (b + .05) / (a + .05)
    return {'ratio': round(ratio, 3), 'aa_normal': ratio >= 4.5, 'aa_large': ratio >= 3,
            'aaa_normal': ratio >= 7, 'aaa_large': ratio >= 4.5}
