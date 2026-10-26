#!/usr/bin/env python3
"""Simple A4 landscape sketch pad for Linux tablets."""
import os
import sys

from PyQt6.QtCore import Qt, QPointF, QRect, QStandardPaths, QTimer, QSaveFile, pyqtSignal
from PyQt6.QtGui import (QColor, QImage, QPainter, QPen, QTabletEvent,
                         QPointingDevice, QPdfWriter, QPageSize, QPageLayout, QAction)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QToolBar,
                             QFileDialog, QMessageBox, QToolButton, QMenu)

COLORS = [("Black", QColor("#000000")), ("Blue", QColor("#1565c0")),
          ("Green", QColor("#16833b")), ("Red", QColor("#d02020"))]
PAGE_W, PAGE_H = 3508, 2480  # A4 landscape at 300 DPI


class Canvas(QWidget):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(500, 350)
        self.setAttribute(Qt.WidgetAttribute.WA_TabletTracking, True)
        self.setMouseTracking(True)
        self.image = self.blank_image()
        self.color = COLORS[0][1]
        self.width_px = 3
        self.eraser = False
        self.eraser_pos = None  # Widget coordinates; never painted into the export image.
        self.stroke_eraser = False
        self.last = None
        self.drawing = False
        self.undo_stack = []
        self.redo_stack = []
        self.revision = 0
        self.saved_revision = 0
        self.next_revision = 1
        self.before_stroke = None

    @staticmethod
    def blank_image():
        image = QImage(PAGE_W, PAGE_H, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        return image

    @property
    def dirty(self):
        return self.revision != self.saved_revision or self.before_stroke is not None

    def snapshot(self):
        # Compressed snapshots keep a bounded history affordable for an A4 canvas.
        from PyQt6.QtCore import QByteArray, QBuffer, QIODevice
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not self.image.save(buffer, "PNG"):
            raise RuntimeError("Could not record sketch history")
        return bytes(data)

    def restore(self, data):
        image = QImage.fromData(data, "PNG")
        if image.isNull():
            raise RuntimeError("Could not restore sketch history")
        self.image = image.convertToFormat(QImage.Format.Format_RGB32)
        self.update()
        self.changed.emit()

    def push_undo(self, snapshot):
        self.undo_stack.append((snapshot, self.revision))
        self.undo_stack = self.undo_stack[-20:]
        self.redo_stack.clear()
        self.revision = self.next_revision
        self.next_revision += 1
        self.changed.emit()

    def finish_stroke(self):
        if self.drawing and self.before_stroke is not None:
            self.push_undo(self.before_stroke)
        self.drawing = False
        self.before_stroke = None
        self.last = None

    def undo(self):
        self.finish_stroke()
        if self.undo_stack:
            self.redo_stack.append((self.snapshot(), self.revision))
            data, self.revision = self.undo_stack.pop()
            self.restore(data)

    def redo(self):
        self.finish_stroke()
        if self.redo_stack:
            self.undo_stack.append((self.snapshot(), self.revision))
            data, self.revision = self.redo_stack.pop()
            self.restore(data)

    def replace_image(self, image):
        self.finish_stroke()
        self.push_undo(self.snapshot())
        self.image = image.convertToFormat(QImage.Format.Format_RGB32)
        self.update()

    def clear(self):
        self.replace_image(self.blank_image())

    def fit(self):
        scale = min((self.width() - 24) / PAGE_W, (self.height() - 24) / PAGE_H)
        w, h = PAGE_W * scale, PAGE_H * scale
        return (self.width() - w) / 2, (self.height() - h) / 2, w, h

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#dddddd"))
        x, y, w, h = self.fit()
        p.drawImage(QPointF(x, y), self.image.scaled(max(1, int(w)), max(1, int(h)),
                    Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        p.setPen(QPen(QColor("#888888"), 1))
        p.drawRect(int(x), int(y), int(w), int(h))
        if self.eraser_pos is not None:
            # Widget-only overlay: no marker is written into self.image or exports.
            cx, cy = int(self.eraser_pos.x()), int(self.eraser_pos.y())
            p.setPen(QPen(QColor("white"), 3))
            p.drawRect(cx - 11, cy - 11, 22, 22)
            p.setPen(QPen(QColor("black"), 1))
            p.drawRect(cx - 11, cy - 11, 22, 22)

    def set_eraser_pos(self, pos):
        if pos is not None and (not self.eraser or not self.rect().contains(pos.toPoint())):
            pos = None
        if pos == self.eraser_pos:
            return
        for old in (self.eraser_pos, pos):
            if old is not None:
                self.update(QRect(int(old.x()) - 14, int(old.y()) - 14, 29, 29))
        self.eraser_pos = pos

    def set_eraser(self, on):
        self.eraser = on
        if on:
            # A native custom tablet cursor may not be displayed by every compositor.
            # Hide the native mouse cursor and draw our square where input events arrive.
            self.setCursor(Qt.CursorShape.BlankCursor)
        else:
            self.set_eraser_pos(None)
            self.unsetCursor()

    def enterEvent(self, event):
        self.set_eraser_pos(event.position())
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.set_eraser_pos(None)
        super().leaveEvent(event)

    def inside(self, pos):
        x, y, w, h = self.fit()
        return x <= pos.x() < x + w and y <= pos.y() < y + h

    def point(self, pos):
        x, y, w, h = self.fit()
        return QPointF(min(PAGE_W - 1, max(0, (pos.x() - x) * PAGE_W / w)),
                       min(PAGE_H - 1, max(0, (pos.y() - y) * PAGE_H / h)))

    def start_stroke(self, pos, eraser=False):
        if not self.inside(pos):
            return
        self.finish_stroke()
        self.before_stroke = self.snapshot()
        self.drawing = True
        self.last = None
        self.stroke_eraser = self.eraser or eraser
        self.draw_segment(pos)
        self.changed.emit()  # Start crash recovery even if the pen stays down.

    def draw_segment(self, pos):
        if not self.drawing:
            return
        if not self.inside(pos):
            self.finish_stroke()
            return
        pt = self.point(pos)
        painter = QPainter(self.image)
        pen = QPen(QColor("white") if self.stroke_eraser else self.color,
                   48 if self.stroke_eraser else self.width_px,
                   Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if self.last is None:
            painter.drawPoint(pt)
        else:
            painter.drawLine(self.last, pt)
        painter.end()
        self.last = pt
        self.update()

    def tabletEvent(self, event: QTabletEvent):
        kind = event.type()
        if kind in (QTabletEvent.Type.TabletPress, QTabletEvent.Type.TabletMove,
                    QTabletEvent.Type.TabletRelease):
            self.set_eraser_pos(event.position())
        if kind == QTabletEvent.Type.TabletPress:
            self.start_stroke(event.position(), event.pointerType() == QPointingDevice.PointerType.Eraser)
            event.accept()
        elif kind == QTabletEvent.Type.TabletMove:
            if self.drawing:
                self.draw_segment(event.position())
            event.accept()
        elif kind == QTabletEvent.Type.TabletRelease:
            self.finish_stroke()
            event.accept()
        else:
            event.ignore()

    def mousePressEvent(self, event):
        self.set_eraser_pos(event.position())
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_stroke(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        self.set_eraser_pos(event.position())
        if self.drawing and event.buttons() & Qt.MouseButton.LeftButton:
            self.draw_segment(event.position())
            event.accept()

    def mouseReleaseEvent(self, event):
        self.set_eraser_pos(event.position())
        if event.button() == Qt.MouseButton.LeftButton:
            self.finish_stroke()
            event.accept()


class SketchApp(QMainWindow):
    def __init__(self, autosave_path=None):
        super().__init__()
        self.setWindowTitle("EasySketch")
        self.resize(1100, 800)
        self.canvas = Canvas()
        self.setCentralWidget(self.canvas)
        state_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        self.autosave_path = autosave_path or os.path.join(state_dir, "recovery.png")
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(1000)
        self.autosave_timer.timeout.connect(self.autosave)
        self.canvas.changed.connect(self.schedule_autosave)

        bar = QToolBar("Sketch tools")
        bar.setMovable(False)
        self.addToolBar(bar)
        self.color_button = QToolButton()
        self.color_button.setText("Color: Black")
        color_menu = QMenu(self)
        for name, color in COLORS:
            color_menu.addAction(name).triggered.connect(
                lambda checked=False, n=name, c=color: self.set_color(c, n))
        self.color_button.setMenu(color_menu)
        self.color_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bar.addWidget(self.color_button)

        self.size_button = QToolButton()
        self.size_button.setText("Thickness: Thin")
        size_menu = QMenu(self)
        for name, width in (("Thin", 3), ("Thick", 10)):
            size_menu.addAction(name).triggered.connect(
                lambda checked=False, n=name, w=width: self.set_width(w, n))
        self.size_button.setMenu(size_menu)
        self.size_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bar.addWidget(self.size_button)

        self.eraser_button = QAction("Eraser: Off", self)
        self.eraser_button.setCheckable(True)
        self.eraser_button.toggled.connect(self.set_eraser)
        bar.addAction(self.eraser_button)
        bar.addAction("Undo", self.canvas.undo).setShortcut("Ctrl+Z")
        bar.addAction("Redo", self.canvas.redo).setShortcut("Ctrl+Shift+Z")
        bar.addAction("Copy image", self.copy_image).setShortcut("Ctrl+C")
        bar.addAction("Open PNG", self.open_png).setShortcut("Ctrl+O")
        save_button = QToolButton()
        save_button.setText("Save")
        save_menu = QMenu(self)
        save_menu.addAction("PNG", self.save_png)
        save_menu.addAction("PDF", self.save_pdf)
        save_button.setMenu(save_menu)
        save_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bar.addWidget(save_button)
        more_button = QToolButton()
        more_button.setText("More")
        more_menu = QMenu(self)
        more_menu.addAction("Clear page", self.clear)
        more_button.setMenu(more_menu)
        more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bar.addWidget(more_button)
        self.recover()

    def set_color(self, c, name):
        self.canvas.color = c
        self.eraser_button.setChecked(False)
        self.color_button.setText(f"Color: {name}")

    def set_width(self, w, name):
        self.canvas.width_px = w
        self.size_button.setText(f"Thickness: {name}")

    def set_eraser(self, on):
        self.canvas.set_eraser(on)
        self.eraser_button.setText("Eraser: On" if on else "Eraser: Off")

    def clear(self):
        if QMessageBox.question(self, "Clear page?", "Erase the whole page?") == QMessageBox.StandardButton.Yes:
            self.canvas.clear()

    def copy_image(self):
        self.canvas.finish_stroke()
        QApplication.clipboard().setImage(self.canvas.image.copy())

    def schedule_autosave(self):
        if self.canvas.dirty:
            self.autosave_timer.start()
        else:
            self.autosave_timer.stop()
            self.remove_autosave()

    def remove_autosave(self):
        try:
            os.remove(self.autosave_path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            QMessageBox.warning(self, "Recovery cleanup failed", str(exc))

    def autosave(self):
        if not self.canvas.dirty:
            return
        try:
            os.makedirs(os.path.dirname(self.autosave_path), exist_ok=True)
            file = QSaveFile(self.autosave_path)
            if not file.open(QSaveFile.OpenModeFlag.WriteOnly):
                raise OSError(file.errorString())
            if not self.canvas.image.save(file, "PNG") or not file.commit():
                raise OSError(file.errorString())
        except OSError as exc:
            QMessageBox.warning(self, "Autosave failed", str(exc))
        if self.canvas.drawing:
            self.autosave_timer.start()

    def recover(self):
        if not os.path.isfile(self.autosave_path):
            return
        answer = QMessageBox.question(self, "Recover sketch?", "Recover the autosaved sketch?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.Yes)
        if answer != QMessageBox.StandardButton.Yes:
            self.remove_autosave()
            return
        image = QImage(self.autosave_path)
        if image.isNull() or image.size() != self.canvas.image.size():
            QMessageBox.warning(self, "Recovery failed", "The recovery image is invalid; it was kept on disk.")
            return
        self.canvas.replace_image(image)

    def confirm_unsaved(self):
        self.canvas.finish_stroke()
        if not self.canvas.dirty:
            return True
        answer = QMessageBox.warning(self, "Unsaved sketch", "Save changes before continuing?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                     QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save)
        if answer == QMessageBox.StandardButton.Save:
            return self.save_png()
        if answer == QMessageBox.StandardButton.Discard:
            return True
        return False

    def open_png(self):
        if not self.confirm_unsaved():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open PNG", "", "PNG image (*.png)")
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "Open failed", "Could not open PNG image.")
            return
        # Composite transparency against white, and fit other sizes without stretching.
        page = Canvas.blank_image()
        fitted = (image if image.size() == page.size() else
                  image.scaled(PAGE_W, PAGE_H, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation))
        painter = QPainter(page)
        painter.drawImage((PAGE_W - fitted.width()) // 2, (PAGE_H - fitted.height()) // 2, fitted)
        painter.end()
        image = page
        self.canvas.replace_image(image)
        self.canvas.saved_revision = self.canvas.revision
        self.schedule_autosave()

    def save_png(self):
        self.canvas.finish_stroke()
        path, _ = QFileDialog.getSaveFileName(self, "Save PNG", "sketch.png", "PNG image (*.png)")
        if not path:
            return False
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            img = self.canvas.image.copy()
            img.setDotsPerMeterX(11811)
            img.setDotsPerMeterY(11811)
            if not img.save(path, "PNG"):
                raise OSError("Could not save PNG image.")
        except (OSError, RuntimeError) as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return False
        self.canvas.saved_revision = self.canvas.revision
        self.schedule_autosave()
        return True

    def save_pdf(self):
        self.canvas.finish_stroke()
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "sketch.pdf", "PDF document (*.pdf)")
        if not path:
            return False
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            writer = QPdfWriter(path)
            writer.setResolution(300)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageOrientation(QPageLayout.Orientation.Landscape)
            painter = QPainter()
            if not painter.begin(writer):
                raise OSError("Could not open PDF for writing.")
            painter.drawImage(writer.pageLayout().paintRectPixels(300), self.canvas.image)
            if not painter.end():
                raise OSError("Could not finish PDF.")
        except (OSError, RuntimeError) as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return False
        self.canvas.saved_revision = self.canvas.revision
        self.schedule_autosave()
        return True

    def closeEvent(self, event):
        if self.confirm_unsaved():
            self.autosave_timer.stop()
            self.remove_autosave()
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    window = SketchApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
