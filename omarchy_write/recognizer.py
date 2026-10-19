"""PP-OCRv6 Chinese handwriting recognition via onnxruntime (no torch).

Model + charset are the official PaddlePaddle PP-OCRv6 rec model and dict
(downloaded on first use to ``models/``). One model covers both Simplified and
Traditional Chinese (18,708 chars).
"""
from __future__ import annotations

import os
import shutil
import urllib.request

import numpy as np

MODEL_FILENAME = "ppocrv6_small_rec.onnx"
DICT_FILENAME = "ppocrv6_dict.txt"

MODEL_URL = (
    "https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec_onnx/resolve/main/inference.onnx"
)
DICT_URL = (
    "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/ppocr/utils/dict/ppocrv6_dict.txt"
)


def _model_dir() -> str:
    env = os.environ.get("OMARCHY_WRITE_MODELS")
    if env:
        return env
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))


def _download(url: str, dest: str) -> None:
    tmp = dest + ".part"
    with urllib.request.urlopen(url, timeout=180) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(tmp, dest)


def ensure_models() -> tuple[str, str]:
    """Return (model_path, dict_path), downloading if missing."""
    d = _model_dir()
    os.makedirs(d, exist_ok=True)
    mp = os.path.join(d, MODEL_FILENAME)
    dp = os.path.join(d, DICT_FILENAME)
    if not os.path.exists(mp):
        _download(MODEL_URL, mp)
    if not os.path.exists(dp):
        _download(DICT_URL, dp)
    return mp, dp


class Recognizer:
    def __init__(self):
        self._session = None
        self._dict: list[str] = []
        self._num_classes = 0
        self._error: str | None = None

    @property
    def ready(self) -> bool:
        return self._session is not None

    @property
    def error(self) -> str | None:
        return self._error

    def load(self, lang_key: str = "cht") -> None:
        """Load model + dict. Blocks; run in a worker thread (downloads on first use)."""
        try:
            import onnxruntime as ort

            mp, dp = ensure_models()
            self._session = ort.InferenceSession(mp, providers=["CPUExecutionProvider"])
            with open(dp, encoding="utf-8") as f:
                self._dict = [ln.rstrip("\n") for ln in f if ln.rstrip("\n")]
            # blank(0) + N chars + unknown(N+1)
            self._num_classes = len(self._dict) + 2
            self._error = None
        except Exception as e:  # noqa: BLE001
            self._session = None
            self._error = str(e)

    def recognize_tensor(self, tensor) -> list[tuple[str, float]]:
        """Return candidate list [(text, score), ...] for an input tensor."""
        if self._session is None or tensor is None:
            return []
        try:
            out = self._session.run(None, {"x": tensor})[0]
        except Exception:  # noqa: BLE001
            return []
        logits = np.asarray(out)
        if logits.ndim == 3:
            logits = logits[0]  # [T, C]
        return self._decode(logits)

    def recognize_strokes(self, norm_strokes) -> list[tuple[str, float]]:
        from .render import strokes_to_tensor

        return self.recognize_tensor(strokes_to_tensor(norm_strokes))

    # -- decoding ------------------------------------------------------
    def _decode(self, logits: np.ndarray) -> list[tuple[str, float]]:
        # PP-OCRv6 inference.onnx already applies softmax (values in [0,1],
        # each timestep sums to 1), so use the output directly as probabilities.
        probs = np.asarray(logits, dtype=np.float32)  # [T, C]

        greedy = self._ctc_collapse(probs.argmax(axis=1))

        # Top-N single chars via max-over-time (CTC peak confidence).
        mp = probs.max(axis=0)  # [C]
        char_probs = mp[1:-1]  # exclude blank(0) and unknown(last)
        k = min(6, len(char_probs))
        idx = np.argpartition(char_probs, -k)[-k:]
        idx = idx[np.argsort(char_probs[idx])[::-1]]

        cands: list[tuple[str, float]] = []
        for i in idx:
            i = int(i)
            if 0 <= i < len(self._dict):
                cands.append((self._dict[i], float(char_probs[i])))

        if len(greedy) > 1:
            # User wrote a short word/phrase: lead with the full decoding.
            cands = [(greedy, float(mp.max()))] + cands

        seen: set[str] = set()
        out: list[tuple[str, float]] = []
        for t, s in cands:
            if t and t not in seen:
                seen.add(t)
                out.append((t, s))
        return out

    def _ctc_collapse(self, idx_seq: np.ndarray) -> str:
        chars: list[str] = []
        prev = -1
        for idx in idx_seq:
            i = int(idx)
            if i == prev:
                continue
            prev = i
            if i == 0 or i == self._num_classes - 1:  # blank / unknown
                continue
            if 1 <= i <= len(self._dict):
                chars.append(self._dict[i - 1])
        return "".join(chars)
