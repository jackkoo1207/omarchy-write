"""Render normalized pen strokes into the PP-OCRv6 rec model input tensor."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

TARGET_H = 48  # PP-OCRv6 recognition model input height


def strokes_to_tensor(norm_strokes, target_h: int = TARGET_H):
    """Convert strokes (list of list of (x, y) in [0,1]) into the ONNX input
    tensor of shape [1, 3, target_h, W], float32, values in [-1, 1].

    White background, black ink; ink is cropped to its bounding box + padding,
    then resized to ``target_h`` height preserving aspect ratio (bilinear),
    matching the PaddleOCR PP-OCRv6 preprocessing.
    """
    flat = [p for s in norm_strokes for p in s]
    if not flat:
        return None
    xs = [p[0] for p in flat]
    ys = [p[1] for p in flat]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    NOM = 256.0  # nominal render box
    pad_frac = 0.10
    bw = max(xmax - xmin, 1e-3)
    bh = max(ymax - ymin, 1e-3)
    cw = bw * NOM + 2 * pad_frac * NOM
    ch = bh * NOM + 2 * pad_frac * NOM
    # Enforce a minimum canvas while preserving the ink's aspect ratio.
    min_canvas = 200.0
    if cw < min_canvas or ch < min_canvas:
        scale = min_canvas / min(cw, ch)
        cw *= scale
        ch *= scale
    cw = int(cw)
    ch = int(ch)

    img = Image.new("L", (cw, ch), 255)
    d = ImageDraw.Draw(img)
    stroke_w = max(6, int(NOM * 0.035))
    ox = pad_frac * NOM - xmin * NOM
    oy = pad_frac * NOM - ymin * NOM

    for s in norm_strokes:
        pts = [(x * NOM + ox, y * NOM + oy) for x, y in s]
        if len(pts) == 1:
            r = stroke_w / 2
            d.ellipse(
                [pts[0][0] - r, pts[0][1] - r, pts[0][0] + r, pts[0][1] + r],
                fill=0,
            )
        else:
            d.line(pts, fill=0, width=stroke_w, joint="curve")

    arr = np.asarray(img, dtype=np.float32)  # [H, W]
    scale = target_h / arr.shape[0]
    tw = max(int(round(arr.shape[1] * scale)), 8)
    resized = np.array(
        Image.fromarray(arr.astype(np.uint8)).resize((tw, target_h), Image.BILINEAR),
        dtype=np.float32,
    )
    normalized = resized / 127.5 - 1.0  # -> [-1, 1]
    tensor = normalized[np.newaxis, np.newaxis, :, :]  # [1, 1, H, W]
    tensor = np.repeat(tensor, 3, axis=1)  # [1, 3, H, W]
    return np.ascontiguousarray(tensor, dtype=np.float32)
