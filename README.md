# EasyDraw

**Author:** Ranga Seshadri · **License:** MIT · **Repo:** https://github.com/ranga291257/easydraw

A small A4 landscape (3508 × 2480 pixel) sketch pad for Linux, written in Python and PyQt6. Draw with a mouse or tablet stylus; strokes have fixed widths (Thin: 3 px, Thick: 10 px), independent of pen pressure. The File menu covers PNG import, PNG/PDF export, copy-to-clipboard, and clear; the icon toolbar offers color, width, eraser, undo/redo, and an A4/Stretch view toggle (hover tooltips name each control). Stretch fills the window for tablet use; exports remain A4 either way. Unsaved changes are periodically saved to an app-data recovery image, with a recovery prompt on next launch. Tablet support is implemented via Qt tablet events; actual XP-Pen Deco01 hardware behavior depends on the local input/desktop setup and is not hardware-validated here.

## Arch Linux: install and run

```sh
sudo pacman -S python python-pyqt6
python3 easydraw.py
```

Run the commands from this repository directory (or pass an absolute path to `easydraw.py`). Sketches and recovery images are not part of the source repository. Save your work using File → Save as PNG… / Save as PDF…; the recovery image is not a substitute for an export.

## Controls

**File menu:** Open PNG, Save as PNG (`Ctrl+S`), Save as PDF, Copy to Clipboard (`Ctrl+C`), Clear Page, Quit (`Ctrl+Q`). Also `Ctrl+O` for Open.

**Toolbar** (icons; hover for names): Color, Width (Thin/Thick), Eraser, Undo (`Ctrl+Z`), Redo (`Ctrl+Shift+Z`), View.

**View:** A4 keeps true page proportions (gray margins if the window aspect differs). Stretch fills the window so a tablet like an XP-Pen Deco can use more of the surface. The sketch bitmap and exports stay A4 landscape either way.

## Tests

The offscreen test suite also needs `pdfinfo` from Poppler:

```sh
sudo pacman -S poppler
QT_QPA_PLATFORM=offscreen python3 -m unittest -v test_easydraw
```

Tests create temporary recovery and export files; they do not require a display or tablet hardware.

## Packaging / Omarchy & AUR

See [PACKAGING.md](PACKAGING.md) for MIT credit, PKGBUILD, AUR, Omarchy package repo, and community store submission. Ready-to-install files live under `packaging/`.

## Optional desktop launcher (per-user)

`easydraw.desktop.in` is a portable template, not a ready-to-run launcher. To install a separate copy for your user:

```sh
install -Dm644 easydraw.py "$HOME/.local/share/easydraw/easydraw.py"
install -Dm644 easydraw.desktop.in "$HOME/.local/share/applications/easydraw.desktop"
```

Edit `~/.local/share/applications/easydraw.desktop`: replace `@APP_SCRIPT@` in `Exec` with the **absolute** path to your installed `easydraw.py` (typically under your home directory). Keep the double quotes around the path if it contains spaces. The template uses a generic icon; no personal path, sketches, or recovery file are bundled. This installation is optional and does not change the original app or its location. If you update the source later, reinstall the copied script.
