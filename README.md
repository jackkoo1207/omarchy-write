<div align="center">
  <img src="assets/icon-128.png" alt="Alt text">
  <br>
  <h1 style="margin: 10px 0; font-size: 2.5rem;">Omarchy Handwrite board</h1>
  <h2 style="margin: 10px 0; font-size: 1.5rem;">繁簡手寫板</h2>
  <br>
  <span>Write
Traditional or Simplified Chinese characters with your trackpad/Mouse.</span>
</div>

<video controls src="assets/Demo.mp4" title="Title"></video>
## How it works

1. A frameless, always-on-top floating panel opens.
2. Draw on the white area (mouse, trackpad-with-button, stylus, or touchscreen).
3. ~0.5 s after you lift the pen, the strokes are rendered and recognized with
   the official **PP-OCRv6** recognition model (ONNX, via `onnxruntime` — no
   torch). One model covers both **Traditional and Simplified** Chinese
   (18,708 chars).
4. Candidate characters appear, with the **most likely one auto-selected**
   (highlighted blue) — it **auto-fills** into your app after a short pause.
   Use **↑ / ↓** to move the selection or **Super+Z** to confirm immediately
   before it fills, or click any candidate.

Insertion copies the text to the clipboard, refocuses the app you were last
using, then sends **Ctrl+V** with `wtype` — so the character lands back where
you were typing.

## Install

```bash
cd omarchy-write
uv venv --python 3.11
uv pip install -e .
# make the console scripts available on PATH
ln -sf "$PWD/.venv/bin/omarchy-write" ~/.local/bin/omarchy-write
ln -sf "$PWD/.venv/bin/omarchy-write-toggle" ~/.local/bin/omarchy-write-toggle
cp omarchy-write.desktop ~/.local/share/applications/
```

The model (21 MB) + charset are downloaded on first launch into
`omarchy-write/models/`.

## Touchpad writing (macOS-style)

By default, when the panel is **visible**, the touchpad is grabbed and becomes
a writing surface: draw with a finger, lift to recognize, then **tap** briefly
to insert the top candidate. Hide the panel (`SUPER+SHIFT+H`) to release the
touchpad. Toggle with the **✍** button.

Reading raw touchpad events requires one-time permission (the device is
`root:input`, and your user isn't in the `input` group):

```bash
sudo cp udev/99-omarchy-write-touchpad.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

Then toggle the panel off/on (or restart the app). Verify with:

```bash
ls -l /dev/input/event7   # should be owned by jack
```

## Hyprland integration (optional, recommended)

Add to `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + H", "手寫輸入", "omarchy-write-toggle")

-- Confirm the auto-selected (top) candidate. Super+Z is free; Super+Space
-- (launcher) and Super+X (cut) are already taken by Omarchy.
o.bind("SUPER + Z", "確認候選字", "omarchy-write-insert 1")
```

Add a window rule (e.g. at the bottom of `~/.config/hypr/hyprland.lua`) so the
panel floats, stays pinned on top, and is centered:

```lua
o.window("^omarchy-write$", {
  float = true, pin = true, center = true,
  size = { 470, 430 }, border_size = 0, opacity = "1 1",
})
```

Do **not** add `no_focus` — on Hyprland it also blocks pointer events, making
the panel unclickable and un-draggable. The app manages focus itself.

Reload: `hyprctl reload`.

## Usage

- **`SUPER+SHIFT+H`** (or the launcher entry) toggles the panel.
- Write a character; it's recognized and **auto-fills** into your app after a
  short pause (top candidate, highlighted blue).
- **`↑` / `↓`** move the highlight between candidates (restarts the auto-fill).
- **`SUPER+Z`** inserts the highlighted candidate immediately.
- **`←` / `→` / Backspace** pass through to your app so you can edit the text.
- Clicking any candidate also inserts it. **清** clears. **✕** hides.

## Files

```
omarchy_write/
├── app.py          main window (floating panel, candidates, toggle signal)
├── canvas.py       stroke capture widget
├── recognizer.py   onnxruntime PP-OCRv6 (top-N candidates)
├── render.py       strokes -> model input tensor
├── insert.py       wl-copy + wtype insertion
└── toggle.py       show/hide (SIGUSR1) or launch
models/
├── ppocrv6_small_rec.onnx   (downloaded on first run)
└── ppocrv6_dict.txt
```

## Notes / limitations

- Recognition is per-line: write one character (or a short word) at a time.
- Drag the header bar ("⠿ Omarchy Write · 繁簡手寫") with the mouse to move the panel.
- The panel takes focus when you click it, then refocuses your previous app
  before pasting — so the character lands back in the app you were typing in.
- Pin PySide6 to `<6.9` (`6.8.x` tested): `6.12.0` trips a shiboken refcount
  crash (`none_dealloc`) under paint on this setup.
- Model runs on CPU (ONNX Runtime); each recognition takes tens of ms.
