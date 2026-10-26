# EasyDraw

A small A4 landscape (3508 × 2480 pixel) sketch pad for Linux, written in Python and PyQt6. Draw with a mouse or tablet stylus; strokes have fixed widths (Thin: 3 px, Thick: 10 px), independent of pen pressure. The toolbar offers four colors, an eraser, undo/redo, clear, PNG import, PNG/PDF export, and copy-to-clipboard. Unsaved changes are periodically saved to an app-data recovery image, with a recovery prompt on next launch. Tablet support is implemented via Qt tablet events; actual XP-Pen Deco01 hardware behavior depends on the local input/desktop setup and is not hardware-validated here.

## Arch Linux: install and run

```sh
sudo pacman -S python python-pyqt6
python3 easydraw.py
```

Run the commands from this repository directory (or pass an absolute path to `easydraw.py`). Sketches and recovery images are not part of the source repository. Save your work using the Save menu; the recovery image is not a substitute for an export.

## Tests

The offscreen test suite also needs `pdfinfo` from Poppler:

```sh
sudo pacman -S poppler
QT_QPA_PLATFORM=offscreen python3 -m unittest -v test_easydraw
```

Tests create temporary recovery and export files; they do not require a display or tablet hardware.

## Optional desktop launcher (per-user)

`easydraw.desktop.in` is a portable template, not a ready-to-run launcher. To install a separate copy for your user:

```sh
install -Dm644 easydraw.py "$HOME/.local/share/easydraw/easydraw.py"
install -Dm644 easydraw.desktop.in "$HOME/.local/share/applications/easydraw.desktop"
```

Edit `~/.local/share/applications/easydraw.desktop`: replace `@APP_SCRIPT@` in `Exec` with the **absolute** path to your installed `easydraw.py` (typically under your home directory). Keep the double quotes around the path if it contains spaces. The template uses a generic icon; no personal path, sketches, or recovery file are bundled. This installation is optional and does not change the original app or its location. If you update the source later, reinstall the copied script.
