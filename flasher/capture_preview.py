"""Standalone debug viewer: live game frame + ROI overlay + OCR readouts.

Runs as its own window:
    python flasher/capture_preview.py

Capture and OCR run in a worker thread; signals push results back to
the UI thread so we never block the event loop. Auto-refresh defaults
off (each capture+OCR cycle is ~3-10 s); the per-roi caching means
manual single-shot is what you'll use most of the time.
"""
from __future__ import annotations

import sys
import threading
import time
from datetime import datetime

from PIL import Image, ImageDraw
from PySide6 import QtCore, QtGui, QtWidgets

import capture as cap
import style


PREVIEW_WIDTH = 960  # downscaled-frame width on screen


def pil_to_qpixmap(pil: Image.Image) -> QtGui.QPixmap:
    """Convert a PIL.Image to QPixmap without writing to disk."""
    if pil.mode != "RGB":
        pil = pil.convert("RGB")
    data = pil.tobytes("raw", "RGB")
    qimg = QtGui.QImage(data, pil.width, pil.height, pil.width * 3,
                        QtGui.QImage.Format_RGB888)
    return QtGui.QPixmap.fromImage(qimg)


class CapturePreview(QtWidgets.QDialog):
    # Signals fire from worker thread → main thread (queued)
    frame_ready = QtCore.Signal(object, dict, float)  # PIL Image, ocr dict, latency_ms
    capture_failed = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Capture / OCR Preview")
        self.resize(1180, 760)

        self._busy = False
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.trigger_capture)

        self.frame_ready.connect(self._on_frame)
        self.capture_failed.connect(self._on_failed)

        self._build_ui()

    # ─── UI ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        main = QtWidgets.QHBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(12)

        # Left: preview image + status
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(8)

        self.status_label = QtWidgets.QLabel("尚未抓取")
        self.status_label.setStyleSheet(
            f"color: {style.TEXT_SECONDARY}; font-family: '{style.FAMILY_MONO}';"
        )
        left.addWidget(self.status_label)

        self.image_label = QtWidgets.QLabel()
        self.image_label.setMinimumSize(PREVIEW_WIDTH,
                                        int(PREVIEW_WIDTH * 1032 / 1920))
        self.image_label.setStyleSheet(
            f"background-color: {style.BG_INPUT}; "
            f"border: 1px solid {style.BORDER}; border-radius: 6px;"
        )
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setText("（按下「抓取」開始）")
        left.addWidget(self.image_label, stretch=1)

        # Controls row
        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(8)

        self.btn_grab = QtWidgets.QPushButton("抓取一次")
        self.btn_grab.clicked.connect(self.trigger_capture)
        controls.addWidget(self.btn_grab)

        self.cb_auto = QtWidgets.QCheckBox("自動重抓")
        self.cb_auto.toggled.connect(self._toggle_auto)
        controls.addWidget(self.cb_auto)

        controls.addWidget(QtWidgets.QLabel("間隔(秒):"))
        self.sp_interval = QtWidgets.QSpinBox()
        self.sp_interval.setRange(1, 60)
        self.sp_interval.setValue(5)
        controls.addWidget(self.sp_interval)

        self.cb_ocr = QtWidgets.QCheckBox("跑 OCR")
        self.cb_ocr.setChecked(True)
        controls.addWidget(self.cb_ocr)

        self.cb_overlay = QtWidgets.QCheckBox("畫 ROI 框")
        self.cb_overlay.setChecked(True)
        self.cb_overlay.toggled.connect(self._redraw_current)
        controls.addWidget(self.cb_overlay)

        controls.addStretch(1)
        left.addLayout(controls)

        main.addLayout(left, stretch=3)

        # Right: parsed values + raw OCR
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(8)

        right.addWidget(QtWidgets.QLabel("解析後數值"))
        self.values_box = QtWidgets.QPlainTextEdit()
        self.values_box.setReadOnly(True)
        self.values_box.setStyleSheet(
            f"background-color: {style.BG_INPUT}; "
            f"font-family: '{style.FAMILY_MONO}'; font-size: 11pt;"
        )
        self.values_box.setMaximumHeight(180)
        right.addWidget(self.values_box)

        right.addWidget(QtWidgets.QLabel("RapidOCR 原始輸出"))
        self.raw_box = QtWidgets.QPlainTextEdit()
        self.raw_box.setReadOnly(True)
        self.raw_box.setStyleSheet(
            f"background-color: {style.BG_INPUT}; "
            f"font-family: '{style.FAMILY_MONO}'; font-size: 10pt;"
        )
        right.addWidget(self.raw_box, stretch=1)

        main.addLayout(right, stretch=2)

        # Cache for redraw without recapture
        self._last_img: Image.Image | None = None
        self._last_ocr: dict | None = None

    # ─── Capture trigger ─────────────────────────────────────────

    def trigger_capture(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.btn_grab.setEnabled(False)
        self.status_label.setText("抓取中…")
        do_ocr = self.cb_ocr.isChecked()
        threading.Thread(target=self._worker, args=(do_ocr,), daemon=True).start()

    def _worker(self, do_ocr: bool) -> None:
        t0 = time.time()
        try:
            img = cap.grab_frame()
        except Exception as e:  # noqa: BLE001
            self.capture_failed.emit(str(e))
            return

        ocr = {}
        if do_ocr:
            try:
                ocr = cap.ocr_rois(img)
            except Exception as e:  # noqa: BLE001
                self.capture_failed.emit(f"OCR error: {e}")
                return

        latency_ms = (time.time() - t0) * 1000
        self.frame_ready.emit(img, ocr, latency_ms)

    # ─── Result handlers (main thread) ───────────────────────────

    def _on_frame(self, img: Image.Image, ocr: dict, latency_ms: float) -> None:
        self._last_img = img
        self._last_ocr = ocr
        self._busy = False
        self.btn_grab.setEnabled(True)

        ts = datetime.now().strftime("%H:%M:%S")
        self.status_label.setText(
            f"抓取於 {ts}  size={img.size[0]}×{img.size[1]}  "
            f"latency={latency_ms:.0f}ms  OCR={'on' if ocr else 'off'}"
        )

        self._redraw_current()
        self._populate_values(ocr)

    def _on_failed(self, msg: str) -> None:
        self._busy = False
        self.btn_grab.setEnabled(True)
        self.status_label.setText(f"[失敗] {msg}")

    def _redraw_current(self) -> None:
        if self._last_img is None:
            return
        img = self._last_img
        if self.cb_overlay.isChecked():
            img = img.copy()
            d = ImageDraw.Draw(img)
            for name, box in cap.ROI_1920x1032.items():
                d.rectangle(box, outline="lime", width=3)
                d.text((box[0] + 4, box[1] + 4), name, fill="lime")

        scaled_h = int(img.height * PREVIEW_WIDTH / img.width)
        scaled = img.resize((PREVIEW_WIDTH, scaled_h), Image.LANCZOS)
        self.image_label.setPixmap(pil_to_qpixmap(scaled))

    def _populate_values(self, ocr: dict) -> None:
        if not ocr:
            self.values_box.setPlainText("(此次未跑 OCR)")
            self.raw_box.setPlainText("")
            return

        # Parsed structured values
        import re
        rows = []
        if "hp_text" in ocr:
            hp = cap.parse_hpmp(ocr["hp_text"])
            rows.append(f"HP    : {hp[0]}/{hp[1]}" if hp else "HP    : ?")
        if "mp_text" in ocr:
            mp = cap.parse_hpmp(ocr["mp_text"])
            rows.append(f"MP    : {mp[0]}/{mp[1]}" if mp else "MP    : ?")
        if "level_exp" in ocr:
            joined = " ".join(ocr["level_exp"])
            m_lv = re.search(r"\b(\d{1,3})\b", joined)
            m_pct = re.search(r"([\d.]+)\s*%", joined)
            rows.append(f"LV    : {m_lv.group(1) if m_lv else '?'}")
            rows.append(f"EXP   : {m_pct.group(1) + '%' if m_pct else '?'}")
        if "lawful" in ocr:
            joined = " ".join(ocr["lawful"])
            m = re.search(r"(-?\d{4,5})", joined)
            rows.append(f"Lawful: {m.group(1) if m else '?'}")
        if "debuffs" in ocr:
            rows.append(f"Debuffs: {', '.join(ocr['debuffs'])}")
        if "action_bar" in ocr:
            rows.append(f"Action : {', '.join(ocr['action_bar'])}")
        chat_count = len(ocr.get("chat_log", []))
        rows.append(f"Chat  : {chat_count} 行")
        self.values_box.setPlainText("\n".join(rows))

        # Raw OCR per ROI
        raw = []
        for name, lines in ocr.items():
            raw.append(f"[{name}] ({len(lines)} hits)")
            for ln in lines:
                raw.append(f"  {ln}")
            raw.append("")
        self.raw_box.setPlainText("\n".join(raw))

    # ─── Auto-refresh ───────────────────────────────────────────

    def _toggle_auto(self, on: bool) -> None:
        if on:
            self._timer.start(self.sp_interval.value() * 1000)
        else:
            self._timer.stop()


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    style.load_bundled_fonts()
    style.ensure_icons()
    app.setStyleSheet(style.make_qss())
    app.setFont(QtGui.QFont(style.FAMILY_UI, 10 + style.FONT_DELTA))

    dlg = CapturePreview()
    dlg.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
