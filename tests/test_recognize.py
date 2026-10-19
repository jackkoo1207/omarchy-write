"""Standalone recognition smoke test (run: .venv/bin/python -m tests.test_recognize)."""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from omarchy_write.recognizer import Recognizer  # noqa: E402


def find_cjk_font():
    import subprocess

    for cand in [
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSerifCJK-Regular.ttc",
    ]:
        if os.path.exists(cand):
            return cand
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{file}", ":lang=zh"], capture_output=True, text=True
        )
        path = out.stdout.strip()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    return None


def glyph_to_tensor(char: str, font_path: str, target_h: int = 48):
    # Render glyph large, then crop + resize to height 48 + normalize.
    size = 200
    font = ImageFont.truetype(font_path, size)
    img = Image.new("L", (size * 2, size * 2), 255)
    d = ImageDraw.Draw(img)
    d.text((20, 20), char, fill=0, font=font)
    bbox = img.getbbox()
    if bbox is None:
        return None
    cropped = img.crop(bbox)
    scale = target_h / cropped.height
    tw = max(int(round(cropped.width * scale)), 8)
    resized = np.array(cropped.resize((tw, target_h), Image.BILINEAR), dtype=np.float32)
    norm = resized / 127.5 - 1.0
    t = norm[np.newaxis, np.newaxis, :, :]
    t = np.repeat(t, 3, axis=1)
    return np.ascontiguousarray(t, dtype=np.float32)


def main():
    rec = Recognizer()
    rec.load()
    if rec.error:
        print("LOAD ERROR:", rec.error)
        return 1

    sess = rec._session
    print("input :", [(i.name, i.shape, i.type) for i in sess.get_inputs()])
    print("output:", [(o.name, o.shape, o.type) for o in sess.get_outputs()])
    print("num_classes:", rec._num_classes, "dict_len:", len(rec._dict))

    font = find_cjk_font()
    print("font:", font)
    if not font:
        print("NO CJK FONT FOUND")
        return 1

    for char in ["中", "國", "學", "龍", "寫"]:
        t = glyph_to_tensor(char, font)
        if t is None:
            continue
        cands = rec.recognize_tensor(t)
        top = ", ".join(f"{c}({s:.3f})" for c, s in cands[:5])
        ok = "✓" if cands and cands[0][0] == char else "✗"
        print(f"{ok} '{char}' -> {top}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
