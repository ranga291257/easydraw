"""Offscreen regression tests; recovery files are confined to a temporary directory."""
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QEvent, Qt
from PyQt6.QtGui import (QInputDevice, QPointingDevice, QTabletEvent, QColor, QImage,
                         QMouseEvent, QEnterEvent)
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from simple_sketch import PAGE_W, PAGE_H, SketchApp


class SketchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "recovery.png")
        self.window = SketchApp(self.path)
        self.window.canvas.resize(1000, 700)
        x, y, w, h = self.window.canvas.fit()
        self.center = QPointF(x + w / 2, y + h / 2)

    def tearDown(self):
        self.window.autosave_timer.stop()
        self.window.deleteLater()
        self.tmp.cleanup()

    def stroke(self, point=None):
        point = self.center if point is None else point
        self.window.canvas.start_stroke(point)
        self.window.canvas.finish_stroke()

    def test_bounds_width_history_clear_and_copy(self):
        c = self.window.canvas
        self.assertEqual(c.width_px, 3)
        self.stroke(QPointF(0, 0))
        self.assertFalse(c.dirty)
        self.assertFalse(c.undo_stack)
        self.stroke()
        self.assertTrue(c.dirty)
        self.assertEqual(c.image.pixelColor(PAGE_W // 2, PAGE_H // 2), QColor("black"))
        c.undo()
        self.assertFalse(c.dirty)
        c.redo()
        self.assertTrue(c.dirty)
        self.window.copy_image()
        self.assertEqual(QApplication.clipboard().image().size(), c.image.size())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.window.clear()
        self.assertEqual(c.image.pixelColor(PAGE_W // 2, PAGE_H // 2), QColor("black"))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.window.clear()
        self.assertEqual(c.image.pixelColor(PAGE_W // 2, PAGE_H // 2), QColor("white"))
        c.undo()
        self.assertEqual(c.image.pixelColor(PAGE_W // 2, PAGE_H // 2), QColor("black"))

    def test_thickness_and_eraser_cursor(self):
        c = self.window.canvas
        original = c.cursor().shape()
        self.window.size_button.menu().actions()[1].trigger()
        self.assertEqual(c.width_px, 10)
        self.window.size_button.menu().actions()[0].trigger()
        self.assertEqual(c.width_px, 3)
        self.window.eraser_button.setChecked(True)
        self.assertTrue(c.eraser)
        self.assertEqual(c.cursor().shape(), Qt.CursorShape.BlankCursor)
        self.assertTrue(c.hasMouseTracking())
        self.window.eraser_button.setChecked(False)
        self.assertFalse(c.eraser)
        self.assertEqual(c.cursor().shape(), original)

    def test_eraser_overlay_hover_leave_and_export(self):
        c = self.window.canvas
        self.window.eraser_button.setChecked(True)
        self.assertIsNone(c.eraser_pos)
        pos = self.center
        move = lambda p: QMouseEvent(QEvent.Type.MouseMove, p, p, Qt.MouseButton.NoButton,
                                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        c.mouseMoveEvent(move(pos))
        self.assertEqual(c.eraser_pos, pos)
        self.assertFalse(c.dirty)
        self.assertEqual(c.image.pixelColor(PAGE_W // 2, PAGE_H // 2), QColor("white"))
        # The square is rendered over the widget but not the backing image.
        rendered = QImage(c.size(), QImage.Format.Format_RGB32)
        c.render(rendered)
        self.assertEqual(rendered.pixelColor(int(pos.x()) - 11, int(pos.y())), QColor("black"))
        other = QPointF(pos.x() + 50, pos.y() + 30)
        c.mouseMoveEvent(move(other))
        self.assertEqual(c.eraser_pos, other)
        c.leaveEvent(QEvent(QEvent.Type.Leave))
        self.assertIsNone(c.eraser_pos)
        c.enterEvent(QEnterEvent(pos, pos, pos))
        self.assertEqual(c.eraser_pos, pos)
        c.set_eraser_pos(QPointF(-5, -5))
        self.assertIsNone(c.eraser_pos)
        c.mouseMoveEvent(move(pos))
        exported = os.path.join(self.tmp.name, "overlay.png")
        with patch.object(QFileDialog, "getSaveFileName", return_value=(exported, "")):
            self.assertTrue(self.window.save_png())
        self.assertEqual(QImage(exported).pixelColor(PAGE_W // 2, PAGE_H // 2), QColor("white"))
        self.window.eraser_button.setChecked(False)
        self.assertIsNone(c.eraser_pos)
        c.mouseMoveEvent(move(other))
        c.leaveEvent(QEvent(QEvent.Type.Leave))
        c.enterEvent(QEnterEvent(pos, pos, pos))
        self.assertIsNone(c.eraser_pos)
        c.render(rendered)
        self.assertNotEqual(rendered.pixelColor(int(pos.x()) - 11, int(pos.y())), QColor("black"))

    def test_tablet_hover_updates_eraser_overlay(self):
        c = self.window.canvas
        device = QPointingDevice("stylus", 2, QInputDevice.DeviceType.Stylus,
                                QPointingDevice.PointerType.Pen,
                                QInputDevice.Capability.Position | QInputDevice.Capability.Hover, 1, 1)
        self.window.eraser_button.setChecked(True)
        for point in (self.center, QPointF(self.center.x() + 60, self.center.y())):
            ev = QTabletEvent(QEvent.Type.TabletMove, device, point, point, 0, 0, 0, 0, 0, 0,
                              Qt.KeyboardModifier.NoModifier, Qt.MouseButton.NoButton,
                              Qt.MouseButton.NoButton)
            c.tabletEvent(ev)
            self.assertTrue(ev.isAccepted())
            self.assertEqual(c.eraser_pos, point)
        self.assertFalse(c.drawing)
        self.assertFalse(c.dirty)
        c.leaveEvent(QEvent(QEvent.Type.Leave))
        self.assertIsNone(c.eraser_pos)

    def test_tablet_eraser_and_fixed_width(self):
        device = QPointingDevice("stylus", 1, QInputDevice.DeviceType.Stylus,
                                QPointingDevice.PointerType.Eraser,
                                QInputDevice.Capability.Position | QInputDevice.Capability.Pressure, 1, 1)
        self.stroke()
        for kind, pressure in ((QEvent.Type.TabletPress, .01), (QEvent.Type.TabletMove, 1.0),
                               (QEvent.Type.TabletRelease, 0.0)):
            ev = QTabletEvent(kind, device, self.center, self.center, pressure, 0, 0, 0, 0, 0,
                              Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton,
                              Qt.MouseButton.LeftButton)
            self.window.canvas.tabletEvent(ev)
            self.assertTrue(ev.isAccepted())
        self.assertEqual(self.window.canvas.image.pixelColor(PAGE_W // 2, PAGE_H // 2), QColor("white"))
        self.assertEqual(len(self.window.canvas.undo_stack), 2)
        self.window.canvas.undo()
        self.assertEqual(self.window.canvas.image.pixelColor(PAGE_W // 2, PAGE_H // 2), QColor("black"))
        self.window.set_width(20, "Thick")
        self.window.set_color(QColor("red"), "Red")
        self.stroke()
        self.assertEqual(self.window.canvas.image.pixelColor(PAGE_W // 2 + 8, PAGE_H // 2), QColor("red"))
        self.assertEqual(self.window.canvas.image.pixelColor(PAGE_W // 2 + 12, PAGE_H // 2), QColor("white"))

    def test_exports_and_failures(self):
        self.stroke()
        png = os.path.join(self.tmp.name, "image.png")
        pdf = os.path.join(self.tmp.name, "image.pdf")
        with patch.object(QFileDialog, "getSaveFileName", return_value=(png, "")):
            self.assertTrue(self.window.save_png())
        self.assertEqual(QImage(png).size(), self.window.canvas.image.size())
        with patch.object(QFileDialog, "getSaveFileName", return_value=(pdf, "")):
            self.assertTrue(self.window.save_pdf())
        with open(pdf, "rb") as stream:
            self.assertEqual(stream.read(5), b"%PDF-")
        info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, check=True).stdout
        self.assertIn("Pages:           1", info)
        self.assertIn("A4", info)
        self.assertIn("842 x 595", info)
        bad = os.path.join(self.tmp.name, "missing", "bad.png")
        with patch.object(QFileDialog, "getSaveFileName", return_value=(bad, "")), \
             patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(self.window.save_png())
            warning.assert_called_once()
        self.assertFalse(os.path.exists(bad))
        with patch.object(QFileDialog, "getSaveFileName", return_value=(os.path.join(self.tmp.name, "missing", "bad.pdf"), "")), \
             patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(self.window.save_pdf())
            warning.assert_called_once()

    def test_autosave_recovery_open_and_cancel_close(self):
        self.stroke()
        self.window.autosave()
        self.assertTrue(os.path.exists(self.path))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            recovered = SketchApp(self.path)
        self.assertTrue(recovered.canvas.dirty)
        recovered.autosave_timer.stop()
        recovered.deleteLater()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(self.window.close())
        self.assertTrue(os.path.exists(self.path))
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard):
            self.assertTrue(self.window.close())
        self.assertFalse(os.path.exists(self.path))
        with patch.object(QFileDialog, "getOpenFileName", return_value=(os.path.join(self.tmp.name, "absent.png"), "")), \
             patch.object(QMessageBox, "warning") as warning:
            self.window.open_png()
            warning.assert_called_once()

    def test_open_fits_png_and_discard_cancel_keeps_recovery(self):
        self.stroke()
        self.window.autosave()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard), \
             patch.object(QFileDialog, "getOpenFileName", return_value=("", "")):
            self.window.open_png()
        self.assertTrue(self.window.canvas.dirty)
        self.assertTrue(os.path.isfile(self.path))
        other = os.path.join(self.tmp.name, "other.png")
        image = QImage(50, 50, QImage.Format.Format_RGB32)
        image.fill(QColor("red"))
        self.assertTrue(image.save(other, "PNG"))
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard), \
             patch.object(QFileDialog, "getOpenFileName", return_value=(other, "")):
            self.window.open_png()
        self.assertFalse(self.window.canvas.dirty)
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.window.canvas.image.pixelColor(PAGE_W // 2, PAGE_H // 2), QColor("red"))
        self.window.canvas.undo()
        self.assertTrue(self.window.canvas.dirty)

    def test_transparent_png_and_active_stroke_recovery(self):
        transparent = os.path.join(self.tmp.name, "transparent.png")
        image = QImage(PAGE_W, PAGE_H, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        image.setPixelColor(PAGE_W // 2, PAGE_H // 2, QColor("blue"))
        self.assertTrue(image.save(transparent, "PNG"))
        with patch.object(QFileDialog, "getOpenFileName", return_value=(transparent, "")):
            self.window.open_png()
        self.assertEqual(self.window.canvas.image.pixelColor(0, 0), QColor("white"))
        self.assertEqual(self.window.canvas.image.pixelColor(PAGE_W // 2, PAGE_H // 2), QColor("blue"))
        self.window.canvas.start_stroke(self.center)
        self.assertTrue(self.window.canvas.dirty)
        self.window.autosave()
        self.assertTrue(os.path.isfile(self.path))
        self.window.canvas.finish_stroke()

    def test_save_cancel_protects_close_and_open(self):
        self.stroke()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Save), \
             patch.object(QFileDialog, "getSaveFileName", return_value=("", "")):
            self.assertFalse(self.window.close())
            with patch.object(QFileDialog, "getOpenFileName") as open_dialog:
                self.window.open_png()
                open_dialog.assert_not_called()
        self.assertTrue(self.window.canvas.dirty)


if __name__ == "__main__":
    unittest.main()
