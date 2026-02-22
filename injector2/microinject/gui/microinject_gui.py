#!/usr/bin/env python3
"""
microinject_gui.py — Cross-platform GUI for the Microinjector Arduino firmware.

Requirements:
    pip install PyQt6 pyserial

Usage:
    python microinject_gui.py

Protocol summary (firmware: microinject.ino, 9600 baud, newline line-ending):
    IDLE state  → send single char command + '\n'
    M           → firmware prompts Direction, Distance, Speed, Accel in sequence
    P + A       → firmware prompts Direction, Distance, Speed, Accel for new step
    P + D n     → delete step n (1-based)
    P + Q       → exit program editor back to menu
    R           → run all program steps
    S           → show program (firmware prints table, then menu)
    C           → clear program
    X           → abort current move
"""

import sys
import time
import queue
import threading
from dataclasses import dataclass
from typing import Optional

import serial
import serial.tools.list_ports

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QObject, pyqtSlot
)
from PyQt6.QtGui import QFont, QColor, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTextEdit, QTabWidget, QGroupBox, QRadioButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QStatusBar, QDialog,
    QDialogButtonBox, QFormLayout, QMessageBox, QSplitter, QFrame,
    QSlider, QSizePolicy
)

# ─────────────────────────────────────────────────────────────────────────────
#  Colour palette
# ─────────────────────────────────────────────────────────────────────────────
DARK_BG     = "#1e1e2e"

# Physical constants (lead screw: 0.8 mm/rev, 2048 steps/rev)
MM_PER_STEP = 0.8 / 2048        # mm of linear travel per motor step
STEPS_PER_MM = 2048 / 0.8       # motor steps per mm
PANEL_BG    = "#2a2a3e"
CARD_BG     = "#313145"
ACCENT      = "#00c8c8"   # teal
ACCENT2     = "#7c5cbf"   # purple
DANGER      = "#e05260"
SUCCESS     = "#4caf89"
TEXT_PRI    = "#e8e8f0"
TEXT_SEC    = "#9090a8"
BORDER      = "#44445a"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRI};
    font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', sans-serif;
    font-size: 13px;
}}
QGroupBox {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px;
    font-weight: 600;
    color: {ACCENT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 12px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {PANEL_BG};
    border-radius: 6px;
}}
QTabBar::tab {{
    background: {CARD_BG};
    color: {TEXT_SEC};
    padding: 8px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background: {PANEL_BG};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT_PRI};
    background: #3a3a55;
}}
QPushButton {{
    background-color: {CARD_BG};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 500;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: #3e3e58;
    border-color: {ACCENT};
    color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: #252535;
}}
QPushButton:disabled {{
    color: {TEXT_SEC};
    border-color: {BORDER};
    background-color: {CARD_BG};
}}
QPushButton#accentBtn {{
    background-color: {ACCENT};
    color: #0d0d1a;
    border: none;
    font-weight: 700;
    font-size: 14px;
}}
QPushButton#accentBtn:hover {{
    background-color: #00dddd;
    color: #0d0d1a;
}}
QPushButton#accentBtn:disabled {{
    background-color: #2a4444;
    color: #3a7070;
}}
QPushButton#dangerBtn {{
    background-color: {DANGER};
    color: white;
    border: none;
    font-weight: 700;
    font-size: 14px;
}}
QPushButton#dangerBtn:hover {{
    background-color: #f06070;
}}
QPushButton#dangerBtn:disabled {{
    background-color: #4a2530;
    color: #7a4050;
}}
QPushButton#successBtn {{
    background-color: {SUCCESS};
    color: #0d1a14;
    border: none;
    font-weight: 700;
}}
QPushButton#successBtn:hover {{
    background-color: #5ccf9f;
}}
QPushButton#successBtn:disabled {{
    background-color: #1e3328;
    color: #3a6050;
}}
QComboBox {{
    background-color: {CARD_BG};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 10px;
    min-height: 26px;
}}
QComboBox:hover {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; }}
QComboBox QAbstractItemView {{
    background-color: {CARD_BG};
    color: {TEXT_PRI};
    selection-background-color: {ACCENT};
    selection-color: #0d0d1a;
    border: 1px solid {BORDER};
}}
QSpinBox, QDoubleSpinBox {{
    background-color: {CARD_BG};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 6px;
    min-height: 26px;
}}
QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {PANEL_BG};
    border: none;
    width: 18px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QTextEdit {{
    background-color: #0d0d14;
    color: #a0ffb0;
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: 'Courier New', 'Consolas', monospace;
    font-size: 12px;
    padding: 6px;
}}
QTableWidget {{
    background-color: {CARD_BG};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT};
    selection-color: #0d0d1a;
}}
QTableWidget::item {{ padding: 4px 8px; }}
QHeaderView::section {{
    background-color: {PANEL_BG};
    color: {ACCENT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px;
    font-weight: 600;
}}
QRadioButton {{
    color: {TEXT_PRI};
    spacing: 8px;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid {BORDER};
    background: {CARD_BG};
}}
QRadioButton::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QStatusBar {{
    background-color: {PANEL_BG};
    color: {TEXT_SEC};
    border-top: 1px solid {BORDER};
    padding: 2px 8px;
}}
QLabel#sectionLabel {{
    color: {TEXT_SEC};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#valueLabel {{
    color: {ACCENT};
    font-size: 20px;
    font-weight: 700;
    font-family: 'Courier New', monospace;
}}
QFrame#divider {{
    background: {BORDER};
    max-height: 1px;
}}
QDialog {{
    background-color: {PANEL_BG};
}}
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}
"""

# ─────────────────────────────────────────────────────────────────────────────
#  Data model
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class ProgramStep:
    forward: bool   = True
    distance: int   = 2048
    speed: int      = 300
    accel: int      = 100


# ─────────────────────────────────────────────────────────────────────────────
#  Serial worker — runs in its own QThread
# ─────────────────────────────────────────────────────────────────────────────
class SerialWorker(QObject):
    """Owns the serial port; emits line_received for every line from Arduino."""
    line_received   = pyqtSignal(str)
    connected       = pyqtSignal(str)   # port name
    disconnected    = pyqtSignal(str)   # reason
    error           = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._port: Optional[serial.Serial] = None
        self._send_queue: queue.Queue = queue.Queue()
        self._running = False
        self._lock = threading.Lock()

    # ---- public API (call from GUI thread) ----------------------------------
    def open(self, port: str, baud: int = 9600):
        try:
            ser = serial.Serial(port, baud, timeout=0.1)
            time.sleep(1.5)          # wait for Arduino reset
            with self._lock:
                self._port = ser
            self.connected.emit(port)
        except serial.SerialException as e:
            self.error.emit(str(e))

    def close(self):
        with self._lock:
            if self._port and self._port.is_open:
                try:
                    self._port.close()
                except Exception:
                    pass
            self._port = None
        self.disconnected.emit("User disconnected")

    def send(self, text: str):
        """Queue text to be sent (adds \\n if not present)."""
        if not text.endswith("\n"):
            text += "\n"
        self._send_queue.put(text)

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._port is not None and self._port.is_open

    # ---- QThread run loop ---------------------------------------------------
    def run(self):
        self._running = True
        buf = ""
        while self._running:
            with self._lock:
                port = self._port

            if port is None or not port.is_open:
                time.sleep(0.05)
                continue

            # Send queued data
            while not self._send_queue.empty():
                try:
                    data = self._send_queue.get_nowait()
                    port.write(data.encode("ascii", errors="replace"))
                    port.flush()
                except (serial.SerialException, OSError) as e:
                    self.disconnected.emit(str(e))
                    with self._lock:
                        self._port = None
                    break

            # Read incoming data
            try:
                raw = port.read(256)
            except (serial.SerialException, OSError) as e:
                self.disconnected.emit(str(e))
                with self._lock:
                    self._port = None
                continue

            if raw:
                buf += raw.decode("ascii", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.rstrip("\r")
                    self.line_received.emit(line)
                # Firmware sends prompts via Serial.print() — no trailing \n.
                # Flush them when the buffer ends with '>' so the GUI can react.
                if buf.rstrip().endswith(">"):
                    self.line_received.emit(buf.strip())
                    buf = ""

        with self._lock:
            if self._port and self._port.is_open:
                self._port.close()

    def stop(self):
        self._running = False


# ─────────────────────────────────────────────────────────────────────────────
#  Add Step dialog
# ─────────────────────────────────────────────────────────────────────────────
class AddStepDialog(QDialog):
    def __init__(self, parent=None, step: Optional[ProgramStep] = None,
                 ul_mode: bool = False, steps_per_ul: float = 0.0,
                 vol_unit: str = "µL", vol_scale: float = 1.0):
        super().__init__(parent)
        self._ul_mode = ul_mode
        self._steps_per_ul = steps_per_ul
        self._vol_unit = vol_unit
        self._vol_scale = vol_scale
        self.setWindowTitle("Add Program Step")
        self.setMinimumWidth(360)
        self.setStyleSheet(STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("New Program Step")
        title.setStyleSheet(f"color: {ACCENT}; font-size: 15px; font-weight: 700;")
        layout.addWidget(title)

        # Unit badge
        if ul_mode:
            badge = QLabel(f"🧪 {vol_unit} input mode active")
            badge.setStyleSheet(
                f"background: {ACCENT}22; color: {ACCENT}; border: 1px solid {ACCENT};"
                f" border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 600;")
            layout.addWidget(badge)

        form = QFormLayout()
        form.setSpacing(10)

        # Direction
        dir_widget = QWidget()
        dir_layout = QHBoxLayout(dir_widget)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        self.rb_fwd = QRadioButton("Forward")
        self.rb_bwd = QRadioButton("Backward")
        self.rb_fwd.setChecked(step.forward if step else True)
        self.rb_bwd.setChecked(not step.forward if step else False)
        dir_layout.addWidget(self.rb_fwd)
        dir_layout.addWidget(self.rb_bwd)
        dir_layout.addStretch()
        form.addRow("Direction:", dir_widget)

        if ul_mode and steps_per_ul > 0:
            ul_per_step = 1.0 / steps_per_ul
            display_scale = self._vol_scale
            unit = self._vol_unit

            # Distance in µL
            self.spin_dist = QDoubleSpinBox()
            self.spin_dist.setDecimals(3)
            self.spin_dist.setRange(0.001, 999999.0 * ul_per_step * display_scale)
            self.spin_dist.setValue(
                round(step.distance * ul_per_step * display_scale, 3) if step else round(2048 * ul_per_step * display_scale, 3))
            self.spin_dist.setSuffix(f"  {unit}")
            form.addRow(f"Volume ({unit}):", self.spin_dist)

            # Speed in display unit/s
            self.spin_speed = QDoubleSpinBox()
            self.spin_speed.setDecimals(4)
            max_disp_s = 1000.0 * ul_per_step * display_scale
            self.spin_speed.setRange(0.0001, max_disp_s)
            self.spin_speed.setValue(
                round((step.speed if step else 300) * ul_per_step * display_scale, 4))
            self.spin_speed.setSuffix(f"  {unit}/s")
            form.addRow(f"Flow rate ({unit}/s):", self.spin_speed)

            # Accel in display unit/s²
            self.spin_accel = QDoubleSpinBox()
            self.spin_accel.setDecimals(4)
            self.spin_accel.setRange(0.0, max_disp_s)
            self.spin_accel.setSpecialValueText("0  (constant speed)")
            self.spin_accel.setValue(
                round((step.accel if step else 100) * ul_per_step * display_scale, 4))
            self.spin_accel.setSuffix(f"  {unit}/s²")
            form.addRow(f"Acceleration ({unit}/s²):", self.spin_accel)

            hint_text = f"steps/µL: {steps_per_ul:.2f}  ·  {unit}/step: {ul_per_step * display_scale:.6f}"
        else:
            # mm mode (default) — all values in mm
            self.spin_dist = QDoubleSpinBox()
            self.spin_dist.setRange(0.001, round(999999 * MM_PER_STEP, 1))
            self.spin_dist.setValue(round((step.distance if step else 2048) * MM_PER_STEP, 3))
            self.spin_dist.setSingleStep(0.01)
            self.spin_dist.setDecimals(3)
            self.spin_dist.setSuffix("  mm")
            form.addRow("Distance:", self.spin_dist)

            self.spin_speed = QDoubleSpinBox()
            self.spin_speed.setRange(round(MM_PER_STEP, 5), round(1000 * MM_PER_STEP, 4))
            self.spin_speed.setValue(round((step.speed if step else 300) * MM_PER_STEP, 4))
            self.spin_speed.setDecimals(4)
            self.spin_speed.setSuffix("  mm/s")
            form.addRow("Speed:", self.spin_speed)

            self.spin_accel = QDoubleSpinBox()
            self.spin_accel.setRange(0, round(1000 * MM_PER_STEP, 4))
            self.spin_accel.setValue(round((step.accel if step else 100) * MM_PER_STEP, 4))
            self.spin_accel.setDecimals(4)
            self.spin_accel.setSuffix("  mm/s²")
            self.spin_accel.setSpecialValueText("0  (constant speed)")
            form.addRow("Acceleration:", self.spin_accel)

            hint_text = f"1 rev = 0.8 mm  ·  Accel 0 = constant speed"

        # Duration (linked to speed — edit either one)
        self._dlg_updating = False
        self.spin_dur = QDoubleSpinBox()
        self.spin_dur.setRange(0.01, 999999.0)
        self.spin_dur.setDecimals(2)
        self.spin_dur.setSuffix("  s")
        self.spin_dur.setMinimumWidth(120)
        form.addRow("Duration:", self.spin_dur)
        self._dlg_sync_dur()   # initial value
        self.spin_speed.valueChanged.connect(self._dlg_on_speed_changed)
        self.spin_dur.valueChanged.connect(self._dlg_on_dur_changed)
        if hasattr(self, 'spin_dist'):
            self.spin_dist.valueChanged.connect(self._dlg_sync_dur)

        layout.addLayout(form)

        hint = QLabel(hint_text)
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 11px;")
        layout.addWidget(hint)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ---- Duration ↔ Speed sync helpers --------------------------------
    def _dlg_sync_dur(self, *_):
        """Recompute duration from current speed and distance."""
        if self._dlg_updating:
            return
        spd = float(self.spin_speed.value())
        dist = float(self.spin_dist.value())
        if spd > 0 and dist > 0:
            self._dlg_updating = True
            self.spin_dur.setValue(dist / spd)
            self._dlg_updating = False

    def _dlg_on_speed_changed(self, *_):
        self._dlg_sync_dur()

    def _dlg_on_dur_changed(self, *_):
        if self._dlg_updating:
            return
        dur = self.spin_dur.value()
        dist = float(self.spin_dist.value())
        if dur > 0 and dist > 0:
            new_spd = dist / dur
            self._dlg_updating = True
            # Clamp to spinner limits
            new_spd = max(self.spin_speed.minimum(),
                          min(self.spin_speed.maximum(), new_spd))
            self.spin_speed.setValue(new_spd)
            self._dlg_updating = False

    def get_step(self) -> ProgramStep:
        if self._ul_mode and self._steps_per_ul > 0:
            scale_to_ul = 1.0 / self._vol_scale
            return ProgramStep(
                forward=self.rb_fwd.isChecked(),
                distance=max(1, round(self.spin_dist.value() * scale_to_ul * self._steps_per_ul)),
                speed=max(1, min(1000, round(self.spin_speed.value() * scale_to_ul * self._steps_per_ul))),
                accel=max(0, min(1000, round(self.spin_accel.value() * scale_to_ul * self._steps_per_ul))),
            )
        return ProgramStep(
            forward=self.rb_fwd.isChecked(),
            distance=max(1, round(self.spin_dist.value() / MM_PER_STEP)),
            speed=max(1, min(1000, round(self.spin_speed.value() / MM_PER_STEP))),
            accel=max(0, min(1000, round(self.spin_accel.value() / MM_PER_STEP))),
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):

    # Motor states
    ST_IDLE    = "idle"
    ST_MOVING  = "moving"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Microinjector Control Panel")
        self.resize(1100, 720)
        self.setMinimumSize(920, 600)
        self.setStyleSheet(STYLESHEET)

        # ── data ──────────────────────────────────────────────────────────────
        self._program: list[ProgramStep] = []
        self._motor_state = self.ST_IDLE
        self._prompt_pending: Optional[str] = None   # which parameter prompt awaits
        self._manual_step: Optional[ProgramStep] = None
        self._prog_add_step: Optional[ProgramStep] = None
        self._in_prog_menu = False   # True while firmware is in P sub-menu
        self._updating_dur = False   # prevents signal loops in speed↔duration
        self._prog_cmd_queue: list = []  # commands to send on next '>' prompt

        # ── volume units ──────────────────────────────────────────────────────
        self._vol_unit = "µL"
        self._vol_scales = {
            "nL": 1000.0,
            "µL": 1.0,
            "mL": 0.001
        }

        # ── countdown timer ───────────────────────────────────────────────────
        self._countdown_remaining: float = 0.0
        self._countdown_timer = QTimer()
        self._countdown_timer.setInterval(100)   # 100 ms ticks
        self._countdown_timer.timeout.connect(self._on_countdown_tick)

        # ── serial ────────────────────────────────────────────────────────────
        self._worker = SerialWorker()
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.line_received.connect(self._on_line)
        self._worker.connected.connect(self._on_connected)
        self._worker.disconnected.connect(self._on_disconnected)
        self._worker.error.connect(self._on_serial_error)
        self._thread.start()

        # ── build UI ──────────────────────────────────────────────────────────
        self._build_ui()
        self._refresh_ports()
        self._set_motor_state(self.ST_IDLE)
        self._update_controls_for_connection(False)

    # =========================================================================
    #  UI construction
    # =========================================================================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(10)

        # ── Top bar: port selector + connect ─────────────────────────────────
        root.addWidget(self._build_connection_bar())

        # ── Divider ───────────────────────────────────────────────────────────
        div = QFrame()
        div.setObjectName("divider")
        div.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(div)

        # ── Main splitter: controls (left) | log (right) ──────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_log_panel())
        splitter.setSizes([480, 280])
        root.addWidget(splitter, 1)

        # ── Status bar ───────────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._lbl_port_status = QLabel("⬤  Disconnected")
        self._lbl_port_status.setStyleSheet(f"color: {DANGER};")
        self._lbl_motor_status = QLabel("Motor: IDLE")
        self._lbl_motor_status.setStyleSheet(f"color: {TEXT_SEC};")
        self._status_bar.addWidget(self._lbl_port_status)
        self._status_bar.addPermanentWidget(self._lbl_motor_status)

    # ── Connection bar ────────────────────────────────────────────────────────
    def _build_connection_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl = QLabel("Port:")
        lbl.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 600;")
        lbl.setFixedWidth(36)
        layout.addWidget(lbl)

        self._combo_port = QComboBox()
        self._combo_port.setFixedWidth(200)
        self._combo_port.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._combo_port)

        self._btn_refresh = QPushButton("⟳  Refresh")
        self._btn_refresh.setFixedWidth(100)
        self._btn_refresh.clicked.connect(self._refresh_ports)
        layout.addWidget(self._btn_refresh)

        lbl_baud = QLabel("Baud:")
        lbl_baud.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 600;")
        layout.addWidget(lbl_baud)

        self._combo_baud = QComboBox()
        for b in ["9600", "19200", "38400", "57600", "115200"]:
            self._combo_baud.addItem(b)
        self._combo_baud.setFixedWidth(90)
        layout.addWidget(self._combo_baud)

        self._btn_connect = QPushButton("Connect")
        self._btn_connect.setObjectName("successBtn")
        self._btn_connect.setFixedWidth(110)
        self._btn_connect.clicked.connect(self._toggle_connect)
        layout.addWidget(self._btn_connect)

        layout.addStretch()

        # Abort — always visible
        self._btn_abort = QPushButton("⛔  ABORT")
        self._btn_abort.setObjectName("dangerBtn")
        self._btn_abort.setFixedWidth(130)
        self._btn_abort.setFixedHeight(36)
        self._btn_abort.clicked.connect(self._do_abort)
        layout.addWidget(self._btn_abort)

        # Countdown display
        self._lbl_countdown = QLabel("⏱  --")
        self._lbl_countdown.setStyleSheet(
            f"color: {TEXT_SEC}; font-family: 'Courier New', monospace;"
            f" font-size: 18px; font-weight: 700; min-width: 90px;"
        )
        self._lbl_countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._lbl_countdown)

        return bar

    # ── Left panel (tabs) ─────────────────────────────────────────────────────
    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_manual_tab(), "Manual Move")
        self._tabs.addTab(self._build_program_tab(), "Program")
        self._tabs.addTab(self._build_syringe_tab(), "🧪 Syringe")
        vbox.addWidget(self._tabs)

        return panel

    # ── Manual Move tab ───────────────────────────────────────────────────────
    def _build_manual_tab(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(14)

        # Unit mode toggle (enabled once syringe is confirmed)
        unit_row = QHBoxLayout()
        unit_lbl = QLabel("Input units:")
        unit_lbl.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 600;")
        self._rb_unit_steps = QRadioButton("mm")
        self._rb_unit_ul    = QRadioButton("µL")
        self._rb_unit_steps.setChecked(True)
        self._rb_unit_ul.setEnabled(False)
        self._rb_unit_steps.toggled.connect(self._on_unit_mode_changed)
        unit_row.addWidget(unit_lbl)
        unit_row.addWidget(self._rb_unit_steps)
        unit_row.addWidget(self._rb_unit_ul)
        unit_row.addStretch()
        self._lbl_ul_badge = QLabel("(confirm syringe settings to unlock)")
        self._lbl_ul_badge.setStyleSheet(f"color: {TEXT_SEC}; font-size: 11px;")
        unit_row.addWidget(self._lbl_ul_badge)
        vbox.addLayout(unit_row)

        # Direction
        dir_group = QGroupBox("Direction")
        dir_layout = QHBoxLayout(dir_group)
        self.rb_man_fwd = QRadioButton("⬆  Forward")
        self.rb_man_bwd = QRadioButton("⬇  Backward")
        self.rb_man_fwd.setChecked(True)
        dir_layout.addWidget(self.rb_man_fwd)
        dir_layout.addWidget(self.rb_man_bwd)
        dir_layout.addStretch()
        vbox.addWidget(dir_group)

        # Distance
        dist_group = QGroupBox("Distance")
        dist_layout = QVBoxLayout(dist_group)
        dist_row = QHBoxLayout()
        self._spin_dist = QDoubleSpinBox()
        self._spin_dist.setRange(0.001, round(999999 * MM_PER_STEP, 1))
        self._spin_dist.setValue(round(2048 * MM_PER_STEP, 3))   # 1 rev = 0.8 mm
        self._spin_dist.setSingleStep(0.01)
        self._spin_dist.setDecimals(3)
        self._spin_dist.setSuffix("  mm")
        self._spin_dist.setMinimumWidth(130)
        dist_row.addWidget(self._spin_dist)
        dist_row.addStretch()
        lbl_rev = QLabel()
        lbl_rev.setStyleSheet(f"color: {ACCENT}; font-size: 16px; font-weight: 700;")
        dist_row.addWidget(lbl_rev)
        self._lbl_rev = lbl_rev
        dist_layout.addLayout(dist_row)
        self._spin_dist.valueChanged.connect(self._update_rev_label)
        self._update_rev_label(2048)
        vbox.addWidget(dist_group)

        # Speed + Duration (linked: edit either one to update the other)
        speed_group = QGroupBox("Speed / Duration")
        self._speed_group = speed_group
        speed_vlay = QVBoxLayout(speed_group)
        speed_row = QHBoxLayout()
        self._slider_speed = QSlider(Qt.Orientation.Horizontal)
        self._slider_speed.setRange(1, 1000)
        self._slider_speed.setValue(300)
        self._spin_speed = QDoubleSpinBox()
        self._spin_speed.setRange(round(MM_PER_STEP, 5), round(1000 * MM_PER_STEP, 4))
        self._spin_speed.setValue(round(300 * MM_PER_STEP, 4))
        self._spin_speed.setDecimals(4)
        self._spin_speed.setSuffix(" mm/s")
        self._spin_speed.setFixedWidth(130)
        self._slider_speed.valueChanged.connect(
            lambda v: self._spin_speed.setValue(round(v * MM_PER_STEP, 4))
            if not self._rb_unit_ul.isChecked() else None)
        self._spin_speed.valueChanged.connect(
            lambda v: self._slider_speed.setValue(max(1, int(round(v / MM_PER_STEP))))
            if not self._rb_unit_ul.isChecked() else None)
        speed_row.addWidget(self._slider_speed, 1)
        speed_row.addWidget(self._spin_speed)
        speed_vlay.addLayout(speed_row)

        # Duration row (auto-computes speed = distance ÷ duration)
        dur_row = QHBoxLayout()
        lbl_dur = QLabel("Duration:")
        lbl_dur.setStyleSheet(f"color: {TEXT_SEC}; font-size: 12px;")
        self._spin_dur = QDoubleSpinBox()
        self._spin_dur.setRange(0.01, 999999.0)
        self._spin_dur.setDecimals(2)
        self._spin_dur.setSuffix("  s")
        self._spin_dur.setMinimumWidth(110)
        dur_row.addWidget(lbl_dur)
        dur_row.addWidget(self._spin_dur)
        dur_row.addStretch()
        speed_vlay.addLayout(dur_row)
        # Wire signals
        self._spin_speed.valueChanged.connect(self._on_speed_changed)
        self._spin_dur.valueChanged.connect(self._on_dur_changed)
        # distance changes also update duration
        self._spin_dist.valueChanged.connect(self._sync_dur_from_speed)
        self._sync_dur_from_speed()
        vbox.addWidget(speed_group)

        # Acceleration
        accel_group = QGroupBox("Acceleration")
        self._accel_group = accel_group
        accel_layout = QHBoxLayout(accel_group)
        self._slider_accel = QSlider(Qt.Orientation.Horizontal)
        self._slider_accel.setRange(0, 1000)
        self._slider_accel.setValue(100)
        self._spin_accel = QDoubleSpinBox()
        self._spin_accel.setRange(0, round(1000 * MM_PER_STEP, 4))
        self._spin_accel.setValue(round(100 * MM_PER_STEP, 4))
        self._spin_accel.setDecimals(4)
        self._spin_accel.setSuffix(" mm/s²")
        self._spin_accel.setSpecialValueText("0  (constant speed)")
        self._spin_accel.setFixedWidth(130)
        self._slider_accel.valueChanged.connect(
            lambda v: self._spin_accel.setValue(round(v * MM_PER_STEP, 4))
            if not self._rb_unit_ul.isChecked() else None)
        self._spin_accel.valueChanged.connect(
            lambda v: self._slider_accel.setValue(max(0, int(round(v / MM_PER_STEP))))
            if not self._rb_unit_ul.isChecked() else None)
        accel_layout.addWidget(self._slider_accel, 1)
        accel_layout.addWidget(self._spin_accel)
        vbox.addWidget(accel_group)

        vbox.addStretch()

        # Move button
        self._btn_move = QPushButton("▶  Move Motor")
        self._btn_move.setObjectName("accentBtn")
        self._btn_move.setMinimumHeight(44)
        self._btn_move.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._btn_move.clicked.connect(self._do_manual_move)
        vbox.addWidget(self._btn_move)

        return w

    # ── Program tab ───────────────────────────────────────────────────────────
    def _build_program_tab(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(10)

        # Table
        self._prog_table = QTableWidget(0, 5)
        self._prog_table.setHorizontalHeaderLabels(
            ["#", "Direction", "Distance (steps)", "Speed (sps)", "Accel (sps²)"])
        self._prog_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self._prog_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed)
        self._prog_table.setColumnWidth(0, 32)
        self._prog_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._prog_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._prog_table.setAlternatingRowColors(True)
        self._prog_table.setStyleSheet(
            self._prog_table.styleSheet() +
            f"QTableWidget {{ alternate-background-color: #2e2e44; }}")
        vbox.addWidget(self._prog_table, 1)

        # Toolbar row
        tool_row = QHBoxLayout()
        self._btn_add_step = QPushButton("➕  Add Step")
        self._btn_add_step.clicked.connect(self._do_add_step)
        self._btn_del_step = QPushButton("🗑  Delete Step")
        self._btn_del_step.clicked.connect(self._do_delete_step)
        self._btn_clear_prog = QPushButton("✖  Clear All")
        self._btn_clear_prog.clicked.connect(self._do_clear_program)
        tool_row.addWidget(self._btn_add_step)
        tool_row.addWidget(self._btn_del_step)
        tool_row.addWidget(self._btn_clear_prog)
        tool_row.addStretch()
        vbox.addLayout(tool_row)

        # Run button
        self._btn_run_prog = QPushButton("▶▶  Run Program")
        self._btn_run_prog.setObjectName("successBtn")
        self._btn_run_prog.setMinimumHeight(44)
        self._btn_run_prog.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._btn_run_prog.clicked.connect(self._do_run_program)
        vbox.addWidget(self._btn_run_prog)

        self._lbl_prog_duration = QLabel("")
        self._lbl_prog_duration.setStyleSheet(
            f"color: {ACCENT}; font-size: 13px; font-weight: 700;")
        self._lbl_prog_duration.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self._lbl_prog_duration)

        lbl_hint = QLabel("Up to 5 steps · 2048 steps = 1 revolution")
        lbl_hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 11px;")
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(lbl_hint)

        return w

    # ── Serial log panel ──────────────────────────────────────────────────────
    def _build_log_panel(self) -> QWidget:
        panel = QGroupBox("Serial Log")
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        vbox.addWidget(self._log)

        btn_row = QHBoxLayout()
        btn_clear_log = QPushButton("Clear Log")
        btn_clear_log.clicked.connect(self._log.clear)
        btn_row.addStretch()
        btn_row.addWidget(btn_clear_log)
        vbox.addLayout(btn_row)

        return panel

    # ── Syringe converter tab ─────────────────────────────────────────────────
    def _build_syringe_tab(self) -> QWidget:
        """
        Syringe setup + µL ↔ steps converter.
        Physics:
            pitch        = 0.8 mm/rev  (fixed)
            steps/rev    = 2048
            mm/step      = 0.8 / 2048
            µL/step      = (syringe_vol_µL / stroke_mm) × (0.8 / 2048)
            steps/µL     = 1 / µL_per_step
        """
        from PyQt6.QtWidgets import QDoubleSpinBox
        PITCH_MM = 0.8
        STEPS_PER_REV = 2048

        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(14)

        # ── Syringe setup ─────────────────────────────────────────────────────
        setup_group = QGroupBox("Syringe Setup")
        setup_form = QFormLayout(setup_group)
        setup_form.setSpacing(10)

        self._spin_syr_vol = QDoubleSpinBox()
        self._spin_syr_vol.setRange(0.1, 1000000.0)
        self._spin_syr_vol.setValue(50.0)
        self._spin_syr_vol.setSuffix(f"  {self._vol_unit}")
        self._spin_syr_vol.setDecimals(1)
        
        unit_selector = QComboBox()
        unit_selector.addItems(["nL", "µL", "mL"])
        unit_selector.setCurrentText(self._vol_unit)
        unit_selector.currentTextChanged.connect(self._on_vol_unit_changed)
        
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(self._spin_syr_vol, 1)
        vol_layout.addWidget(unit_selector)
        setup_form.addRow("Syringe volume:", vol_layout)

        self._spin_syr_stroke = QDoubleSpinBox()
        self._spin_syr_stroke.setRange(0.1, 500.0)
        self._spin_syr_stroke.setValue(30.0)
        self._spin_syr_stroke.setSuffix("  mm")
        self._spin_syr_stroke.setDecimals(2)
        setup_form.addRow("Plunger stroke:", self._spin_syr_stroke)

        lbl_pitch = QLabel(f"0.8 mm/rev  (fixed)")
        lbl_pitch.setStyleSheet(f"color: {TEXT_SEC};")
        setup_form.addRow("Lead screw pitch:", lbl_pitch)

        lbl_ul_step_title = QLabel("µL / step:")
        lbl_ul_step_title.setStyleSheet(f"color: {TEXT_SEC};")
        self._lbl_ul_per_step = QLabel("—")
        self._lbl_ul_per_step.setStyleSheet(f"color: {ACCENT}; font-weight: 700;")
        setup_form.addRow(lbl_ul_step_title, self._lbl_ul_per_step)

        lbl_step_ul_title = QLabel("steps / µL:")
        lbl_step_ul_title.setStyleSheet(f"color: {TEXT_SEC};")
        self._lbl_steps_per_ul = QLabel("—")
        self._lbl_steps_per_ul.setStyleSheet(f"color: {ACCENT}; font-weight: 700;")
        setup_form.addRow(lbl_step_ul_title, self._lbl_steps_per_ul)

        # Confirm checkbox — gates µL input mode
        self._chk_confirm = QCheckBox("✓  Confirm — enable µL input mode in Manual Move")
        self._chk_confirm.setStyleSheet(
            f"color: {TEXT_PRI}; font-weight: 600; padding: 4px 0;"
        )
        self._chk_confirm.toggled.connect(self._on_syringe_confirmed)
        setup_form.addRow("", self._chk_confirm)

        vbox.addWidget(setup_group)

        # ── Converter: µL → steps ─────────────────────────────────────────────
        ul_group = QGroupBox("Volume  →  Steps")
        ul_layout = QVBoxLayout(ul_group)
        ul_row = QHBoxLayout()
        self._spin_input_ul = QDoubleSpinBox()
        self._spin_input_ul.setRange(0.0, 1000000.0)
        self._spin_input_ul.setValue(1.0)
        self._spin_input_ul.setDecimals(3)
        self._spin_input_ul.setSuffix(f"  {self._vol_unit}")
        self._spin_input_ul.setMinimumWidth(130)
        lbl_arrow1 = QLabel("→")
        lbl_arrow1.setStyleSheet(f"color: {ACCENT}; font-size: 18px; font-weight: 700;")
        self._lbl_ul_to_steps = QLabel("—")
        self._lbl_ul_to_steps.setStyleSheet(
            f"color: {ACCENT}; font-size: 16px; font-weight: 700;"
            f" font-family: 'Courier New', monospace;")
        ul_row.addWidget(self._spin_input_ul)
        ul_row.addWidget(lbl_arrow1)
        ul_row.addWidget(self._lbl_ul_to_steps)
        ul_row.addStretch()
        ul_layout.addLayout(ul_row)

        btn_use_manual = QPushButton("→ Set in Manual Move")
        btn_use_manual.clicked.connect(self._apply_ul_to_manual)
        ul_layout.addWidget(btn_use_manual)
        vbox.addWidget(ul_group)

        # ── Converter: mm → µL (was Steps → Volume) ─────────────────────────────────
        st_group = QGroupBox("mm  →  Volume")
        st_layout = QHBoxLayout(st_group)
        self._spin_input_mm = QDoubleSpinBox()
        self._spin_input_mm.setRange(0.0, round(999999 * MM_PER_STEP, 1))
        self._spin_input_mm.setValue(round(2048 * MM_PER_STEP, 3))
        self._spin_input_mm.setDecimals(3)
        self._spin_input_mm.setSuffix("  mm")
        self._spin_input_mm.setMinimumWidth(130)
        lbl_arrow2 = QLabel("→")
        lbl_arrow2.setStyleSheet(f"color: {ACCENT}; font-size: 18px; font-weight: 700;")
        self._lbl_mm_to_ul = QLabel("—")
        self._lbl_mm_to_ul.setStyleSheet(
            f"color: {ACCENT}; font-size: 16px; font-weight: 700;"
            f" font-family: 'Courier New', monospace;")
        st_layout.addWidget(self._spin_input_mm)
        st_layout.addWidget(lbl_arrow2)
        st_layout.addWidget(self._lbl_mm_to_ul)
        st_layout.addStretch()
        vbox.addWidget(st_group)

        vbox.addStretch()

        # Wire signals — also connect syringe spinners to re-run confirm logic
        self._spin_syr_vol.valueChanged.connect(self._update_syringe_calcs)
        self._spin_syr_vol.valueChanged.connect(
            lambda: self._chk_confirm.setChecked(False) if self._chk_confirm.isChecked() else None)
        self._spin_syr_stroke.valueChanged.connect(self._update_syringe_calcs)
        self._spin_syr_stroke.valueChanged.connect(
            lambda: self._chk_confirm.setChecked(False) if self._chk_confirm.isChecked() else None)
        self._spin_input_ul.valueChanged.connect(self._update_syringe_calcs)
        self._spin_input_mm.valueChanged.connect(self._update_syringe_calcs)
        self._update_syringe_calcs()

        return w

    # =========================================================================
    #  Port helpers
    # =========================================================================
    def _refresh_ports(self):
        self._combo_port.clear()
        ports = sorted(serial.tools.list_ports.comports(), key=lambda p: p.device)
        for p in ports:
            self._combo_port.addItem(f"{p.device}  —  {p.description}", p.device)
        if not ports:
            self._combo_port.addItem("No ports found", "")

    def _toggle_connect(self):
        if self._worker.is_connected:
            self._worker.close()
        else:
            port = self._combo_port.currentData()
            baud = int(self._combo_baud.currentText())
            if not port:
                QMessageBox.warning(self, "No Port", "Please select a valid serial port.")
                return
            self._worker.open(port, baud)

    # =========================================================================
    #  Serial signal handlers
    # =========================================================================
    @pyqtSlot(str)
    def _on_connected(self, port: str):
        self._lbl_port_status.setText(f"⬤  {port}")
        self._lbl_port_status.setStyleSheet(f"color: {SUCCESS};")
        self._btn_connect.setText("Disconnect")
        self._btn_connect.setObjectName("dangerBtn")
        self._btn_connect.setStyleSheet("")    # force style refresh
        self._btn_connect.setStyleSheet(STYLESHEET)
        self._update_controls_for_connection(True)
        self._log_line(f"[Connected to {port}]", color=SUCCESS)

    @pyqtSlot(str)
    def _on_disconnected(self, reason: str):
        self._lbl_port_status.setText("⬤  Disconnected")
        self._lbl_port_status.setStyleSheet(f"color: {DANGER};")
        self._btn_connect.setText("Connect")
        self._btn_connect.setObjectName("successBtn")
        self._btn_connect.setStyleSheet("")
        self._btn_connect.setStyleSheet(STYLESHEET)
        self._update_controls_for_connection(False)
        self._set_motor_state(self.ST_IDLE)
        self._log_line(f"[Disconnected: {reason}]", color=DANGER)
        self._prompt_pending = None
        self._in_prog_menu = False
        self._prog_cmd_queue.clear()

    @pyqtSlot(str)
    def _on_serial_error(self, msg: str):
        QMessageBox.critical(self, "Serial Error", msg)
        self._log_line(f"[ERROR] {msg}", color=DANGER)

    @pyqtSlot(str)
    def _on_line(self, line: str):
        """Called for every line received from Arduino."""
        self._log_line(line)
        self._parse_arduino_line(line)

    # =========================================================================
    #  Arduino line parser / protocol state machine
    # =========================================================================
    def _parse_arduino_line(self, line: str):
        stripped = line.strip()
        upper = stripped.upper()

        # ── Motor state transitions ───────────────────────────────────────────
        if "STARTING MOVE" in upper or "STARTING..." in upper:
            self._set_motor_state(self.ST_MOVING)
            return

        if "[DONE]" in upper or "[ABORTED]" in upper:
            self._set_motor_state(self.ST_IDLE)
            self._prompt_pending = None
            self._in_prog_menu = False
            return

        # ── Prompt detection & auto-reply ─────────────────────────────────────
        # Manual move prompts
        if "DIRECTION" in upper and ">" in line and self._manual_step is not None:
            direction = "F" if self._manual_step.forward else "B"
            self._send_raw(direction)
            return

        if "DISTANCE" in upper and ">" in line and self._manual_step is not None:
            self._send_raw(str(self._manual_step.distance))
            return

        if "SPEED" in upper and ">" in line and self._manual_step is not None:
            self._send_raw(str(self._manual_step.speed))
            return

        if "ACCEL" in upper and ">" in line and self._manual_step is not None:
            self._send_raw(str(self._manual_step.accel))
            self._manual_step = None   # done replying
            return

        # Program editor prompts (adding a step)
        if "DIRECTION" in upper and ">" in line and self._prog_add_step is not None:
            direction = "F" if self._prog_add_step.forward else "B"
            self._send_raw(direction)
            return

        if "DISTANCE" in upper and ">" in line and self._prog_add_step is not None:
            self._send_raw(str(self._prog_add_step.distance))
            return

        if "SPEED" in upper and ">" in line and self._prog_add_step is not None:
            self._send_raw(str(self._prog_add_step.speed))
            return

        if "ACCEL" in upper and ">" in line and self._prog_add_step is not None:
            self._send_raw(str(self._prog_add_step.accel))
            self._prog_add_step = None
            return

        # Step added/deleted → queue Q so we exit when editor re-shows '> '
        if "STEP ADDED" in upper or "STEP DELETED" in upper:
            self._prog_cmd_queue.append("Q")
            return

        # Program editor sub-menu prompt '>' — send next queued command
        if stripped == ">" and self._in_prog_menu:
            if self._prog_cmd_queue:
                cmd = self._prog_cmd_queue.pop(0)
                if cmd.upper() == "Q":
                    self._in_prog_menu = False
                self._send_raw(cmd)
            return

        # Show program — parse table lines to sync GUI state
        if stripped.startswith("#") or "DIR" in upper:
            return  # header line, skip

        # Parse data row "1  F    2048             300         100"
        self._try_parse_show_line(stripped)

    def _try_parse_show_line(self, line: str):
        """Try to parse a program table row from S command output."""
        parts = line.split()
        if len(parts) >= 5:
            try:
                idx = int(parts[0])
                if idx < 1:
                    return
                direction = parts[1].upper()
                distance = int(parts[2])
                speed = int(parts[3])
                accel = int(parts[4])
                step = ProgramStep(
                    forward=(direction == "F"),
                    distance=distance,
                    speed=speed,
                    accel=accel,
                )
                # Extend list if needed
                while len(self._program) < idx:
                    self._program.append(ProgramStep())
                self._program[idx - 1] = step
                self._refresh_program_table()
            except (ValueError, IndexError):
                pass

    # =========================================================================
    #  Send helpers
    # =========================================================================
    def _send_raw(self, text: str):
        if self._worker.is_connected:
            self._log_line(f"→ {text}", color=ACCENT)
            self._worker.send(text)

    # =========================================================================
    #  Speed ↔ Duration sync (Manual Move tab)
    # =========================================================================
    def _sync_dur_from_speed(self, *_):
        """Recompute duration = distance ÷ speed and display it."""
        if self._updating_dur:
            return
        spd = self._spin_speed.value()
        dist = self._spin_dist.value()
        if spd > 0 and dist > 0:
            self._updating_dur = True
            self._spin_dur.setValue(dist / spd)
            self._updating_dur = False

    def _on_speed_changed(self, *_):
        if self._rb_unit_steps.isChecked():
            v = self._spin_speed.value()
            self._slider_speed.setValue(int(v))
        self._sync_dur_from_speed()

    def _on_dur_changed(self, *_):
        if self._updating_dur:
            return
        dur = self._spin_dur.value()
        dist = self._spin_dist.value()
        if dur > 0 and dist > 0:
            new_spd = dist / dur
            new_spd = max(self._spin_speed.minimum(),
                          min(self._spin_speed.maximum(), new_spd))
            self._updating_dur = True
            self._spin_speed.setValue(new_spd)
            if self._rb_unit_steps.isChecked():
                self._slider_speed.setValue(int(new_spd))
            self._updating_dur = False

    # =========================================================================
    #  Syringe converter helpers
    # =========================================================================
    PITCH_MM   = 0.8
    STEPS_REV  = 2048
    MM_PER_STEP = PITCH_MM / STEPS_REV      # 0.000390625 mm/step

    def _update_syringe_calcs(self, *_):
        unit_scale = self._vol_scales[self._vol_unit]
        vol_ul    = self._spin_syr_vol.value() / unit_scale  # always µL internal
        stroke_mm = self._spin_syr_stroke.value()            # mm
        if stroke_mm <= 0 or vol_ul <= 0:
            return
        
        ul_per_step  = (vol_ul / stroke_mm) * MM_PER_STEP
        steps_per_ul = 1.0 / ul_per_step if ul_per_step > 0 else 0.0
        ul_per_mm    = ul_per_step / MM_PER_STEP   # = vol_ul / stroke_mm
        mm_per_ul    = 1.0 / ul_per_mm if ul_per_mm > 0 else 0.0
        
        disp_per_step = ul_per_step * unit_scale
        disp_per_mm   = ul_per_mm * unit_scale
        
        self._lbl_ul_per_step.setText(f"{disp_per_step:.6f} {self._vol_unit}/step  =  {disp_per_mm:.6f} {self._vol_unit}/mm")
        self._lbl_steps_per_ul.setText(f"{steps_per_ul / unit_scale:.2f} steps/{self._vol_unit}")
        
        # Converter: Display Unit → mm
        vol_in = self._spin_input_ul.value()
        vol_ul_in = vol_in / unit_scale
        steps_out = round(vol_ul_in * steps_per_ul)
        mm_out = vol_ul_in * mm_per_ul
        self._lbl_ul_to_steps.setText(f"{steps_out:,} steps  /  {mm_out:.3f} mm")
        
        # Converter: mm → Display Unit
        mm_in = self._spin_input_mm.value()
        vol_ul_from_mm = mm_in * ul_per_mm
        vol_disp_from_mm = vol_ul_from_mm * unit_scale
        self._lbl_mm_to_ul.setText(f"{vol_disp_from_mm:.6f} {self._vol_unit}")

    def _apply_ul_to_manual(self):
        """Copy the Volume→mm result into the Manual Move distance spinner."""
        unit_scale = self._vol_scales[self._vol_unit]
        vol_ul    = self._spin_syr_vol.value() / unit_scale
        stroke_mm = self._spin_syr_stroke.value()
        if stroke_mm <= 0 or vol_ul <= 0:
            return
        
        ul_per_step  = (vol_ul / stroke_mm) * MM_PER_STEP
        steps_per_ul = 1.0 / ul_per_step if ul_per_step > 0 else 0.0
        
        vol_in = self._spin_input_ul.value()
        vol_ul_in = vol_in / unit_scale
        steps_out = max(1, round(vol_ul_in * steps_per_ul))

        if self._rb_unit_ul.isChecked():
            self._spin_dist.setValue(round(vol_in, 3))
        else:
            # mm mode: set mm value
            self._spin_dist.setValue(max(0.001, round(steps_out * MM_PER_STEP, 3)))
        self._tabs.setCurrentIndex(0)   # switch to Manual Move tab

    # =========================================================================
    #  Syringe confirm / unit mode
    # =========================================================================
    def _steps_per_ul_current(self) -> float:
        """Return current steps/µL from syringe settings, or 0 if not valid."""
        vol    = self._spin_syr_vol.value()
        stroke = self._spin_syr_stroke.value()
        if stroke <= 0 or vol <= 0:
            return 0.0
        ul_per_step = (vol / stroke) * self.MM_PER_STEP
        return 1.0 / ul_per_step if ul_per_step > 0 else 0.0

    @pyqtSlot(bool)
    def _on_syringe_confirmed(self, checked: bool):
        """Called when the confirm checkbox is toggled on the Syringe tab."""
        self._rb_unit_ul.setEnabled(checked)
        if checked:
            spu = self._steps_per_ul_current()
            ul_per_mm = spu * MM_PER_STEP
            
            unit = self._vol_unit
            scale = self._vol_scales[unit]
            
            badge_txt = f"{unit} unlocked  ({ul_per_mm * scale:.4f} {unit}/mm  |  {spu / scale:.2f} steps/{unit})"
            self._lbl_ul_badge.setText(badge_txt)
            self._lbl_ul_badge.setStyleSheet(
                f"background: {ACCENT}22; color: {ACCENT}; border: 1px solid {ACCENT};"
                f" border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: 600;"
            )
        else:
            # Force back to steps mode
            self._rb_unit_steps.setChecked(True)
            self._lbl_ul_badge.setText("(confirm syringe settings to unlock)")
            self._lbl_ul_badge.setStyleSheet(f"color: {TEXT_SEC}; font-size: 11px;")

    @pyqtSlot(bool)
    def _on_unit_mode_changed(self, steps_is_checked: bool):
        """Switch all Manual Move spinners between mm and Volume modes."""
        ul_mode = not steps_is_checked
        spu = self._steps_per_ul_current() if ul_mode else 0.0
        ul_per_step = 1.0 / spu if spu > 0 else 1.0
        
        unit = self._vol_unit
        scale = self._vol_scales[unit]
        
        # Convenience: Unit per mm (for direct mm↔Unit conversion)
        unit_per_mm = (ul_per_step / MM_PER_STEP) * scale # Incorrect logic in previous version?
        # Actually:
        # 1 mm = (1/MM_PER_STEP) steps
        # steps * ul_per_step = µL
        # µL * scale = Display Unit
        # So: 1 mm = (1/MM_PER_STEP) * ul_per_step * scale Display Units
        unit_per_mm = (ul_per_step * scale) / MM_PER_STEP

        if ul_mode:
            # mm → Display Unit
            cur_mm = self._spin_dist.value()
            self._spin_dist.setDecimals(3)
            self._spin_dist.setSingleStep(0.001)
            self._spin_dist.setRange(0.001, 999999.0 * ul_per_step * scale)
            self._spin_dist.setSuffix(f"  {unit}")
            self._spin_dist.setValue(round(cur_mm * unit_per_mm, 3))
            
            # Speed mm/s → Unit/s
            cur_speed_mm = self._spin_speed.value()
            max_unit_s = 1000.0 * ul_per_step * scale
            self._spin_speed.setDecimals(4)
            self._spin_speed.setSingleStep(ul_per_step * scale)
            self._spin_speed.setRange(0.0001, max_unit_s)
            self._spin_speed.setSuffix(f"  {unit}/s")
            self._spin_speed.setValue(round(cur_speed_mm * unit_per_mm, 4))
            
            self._sync_dur_from_speed()
            
            # Accel mm/s² → Unit/s²
            cur_accel_mm = self._spin_accel.value()
            self._spin_accel.setDecimals(4)
            self._spin_accel.setSingleStep(ul_per_step * scale)
            self._spin_accel.setRange(0.0, max_unit_s)
            self._spin_accel.setSuffix(f"  {unit}/s²")
            self._spin_accel.setValue(round(cur_accel_mm * unit_per_mm, 4))
            
            self._slider_speed.setVisible(False)
            self._slider_accel.setVisible(False)
            self._lbl_rev.setText("")
        else:
            # Unit → mm
            cur_unit = self._spin_dist.value()
            dist_steps = round((cur_unit / scale) * spu) if spu > 0 else 2048
            self._spin_dist.setDecimals(3)
            self._spin_dist.setSingleStep(0.01)
            self._spin_dist.setRange(0.001, round(999999 * MM_PER_STEP, 1))
            self._spin_dist.setSuffix("  mm")
            self._spin_dist.setValue(max(0.001, round(dist_steps * MM_PER_STEP, 3)))
            
            # Speed Unit/s → mm/s
            cur_speed_unit = self._spin_speed.value()
            speed_steps = max(1, min(1000, round((cur_speed_unit / scale) * spu)))
            self._spin_speed.setDecimals(4)
            self._spin_speed.setSingleStep(MM_PER_STEP)
            self._spin_speed.setRange(round(MM_PER_STEP, 5), round(1000 * MM_PER_STEP, 4))
            self._spin_speed.setSuffix(" mm/s")
            self._spin_speed.setValue(round(speed_steps * MM_PER_STEP, 4))
            
            self._sync_dur_from_speed()
            
            # Accel Unit/s² → mm/s²
            cur_accel_unit = self._spin_accel.value()
            accel_steps = max(0, min(1000, round((cur_accel_unit / scale) * spu)))
            self._spin_accel.setDecimals(4)
            self._spin_accel.setSingleStep(MM_PER_STEP)
            self._spin_accel.setRange(0, round(1000 * MM_PER_STEP, 4))
            self._spin_accel.setSuffix(" mm/s²")
            self._spin_accel.setValue(round(accel_steps * MM_PER_STEP, 4))
            
            self._slider_speed.setValue(speed_steps)
            self._slider_accel.setValue(accel_steps)
            self._slider_speed.setVisible(True)
            self._slider_accel.setVisible(True)
            self._update_rev_label(self._spin_dist.value())
        
        self._refresh_program_table()

    # =========================================================================
    #  Move duration calculator & countdown
    # =========================================================================
    @staticmethod
    def _calculate_step_duration(step: ProgramStep) -> float:
        """Estimated move time (s) using AccelStepper trapezoid kinematics."""
        d = float(step.distance)
        v = float(step.speed)
        a = float(step.accel)
        if a <= 0 or v <= 0:
            return d / v if v > 0 else 0.0   # constant speed
        d_accel = v * v / (2.0 * a)           # steps to reach full speed
        if 2.0 * d_accel >= d:                # triangle profile
            peak = (a * d) ** 0.5
            return 2.0 * peak / a
        else:                                  # trapezoidal profile
            t_ramp = v / a
            t_flat = (d - 2.0 * d_accel) / v
            return 2.0 * t_ramp + t_flat

    def _start_countdown(self, duration_s: float):
        self._countdown_remaining = duration_s
        self._lbl_countdown.setStyleSheet(
            f"color: {ACCENT}; font-family: 'Courier New', monospace;"
            f" font-size: 18px; font-weight: 700; min-width: 90px;"
        )
        self._update_countdown_label()
        self._countdown_timer.start()

    def _on_countdown_tick(self):
        self._countdown_remaining -= 0.1
        if self._countdown_remaining <= 0:
            self._countdown_remaining = 0.0
            self._countdown_timer.stop()
        self._update_countdown_label()

    def _update_countdown_label(self):
        secs = self._countdown_remaining
        if secs >= 60:
            m = int(secs) // 60
            s = secs - m * 60
            self._lbl_countdown.setText(f"⏱ {m}:{s:04.1f}")
        else:
            self._lbl_countdown.setText(f"⏱ {secs:.1f}s")

    # =========================================================================
    #  Action handlers
    # =========================================================================
    def _do_manual_move(self):
        ul_mode = self._rb_unit_ul.isChecked()
        if ul_mode:
            spu = self._steps_per_ul_current()
            dist_steps  = max(1, round(self._spin_dist.value()  * spu))
            speed_steps = max(1, min(1000, round(self._spin_speed.value() * spu)))
            accel_steps = max(0, min(1000, round(self._spin_accel.value() * spu)))
        else:
            # mm mode — convert to steps
            dist_steps  = max(1, round(self._spin_dist.value()  / MM_PER_STEP))
            speed_steps = max(1, min(1000, round(self._spin_speed.value() / MM_PER_STEP)))
            accel_steps = max(0, min(1000, round(self._spin_accel.value() / MM_PER_STEP)))
        step = ProgramStep(
            forward=self.rb_man_fwd.isChecked(),
            distance=dist_steps,
            speed=speed_steps,
            accel=accel_steps,
        )
        self._manual_step = step
        self._start_countdown(self._calculate_step_duration(step))
        self._send_raw("M")

    def _do_abort(self):
        self._countdown_timer.stop()
        self._lbl_countdown.setText("⏱  --")
        self._lbl_countdown.setStyleSheet(
            f"color: {TEXT_SEC}; font-family: 'Courier New', monospace;"
            f" font-size: 18px; font-weight: 700; min-width: 90px;")
        self._send_raw("X")

    def _do_add_step(self):
        if len(self._program) >= 5:
            QMessageBox.warning(self, "Program Full",
                                "The program is full (max 5 steps). Delete a step first.")
            return
        spu = self._steps_per_ul_current() if self._chk_confirm.isChecked() else 0.0
        ul_mode = self._rb_unit_ul.isChecked() and spu > 0
        dlg = AddStepDialog(
            self, ul_mode=ul_mode, steps_per_ul=spu,
            vol_unit=self._vol_unit, vol_scale=self._vol_scales[self._vol_unit]
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        step = dlg.get_step()
        self._program.append(step)
        # Refresh Program table to match new unit
        self._refresh_program_table()
        # Send to Arduino: enter P editor; 'A' will fire when '>' prompt arrives
        self._prog_add_step = step
        self._in_prog_menu = True
        self._prog_cmd_queue = ["A"]
        self._send_raw("P")

    @pyqtSlot(str)
    def _on_vol_unit_changed(self, unit):
        """Called when nL/µL/mL unit is changed in setup dropdown."""
        old_unit = self._vol_unit
        old_scale = self._vol_scales[old_unit]
        new_scale = self._vol_scales[unit]
        
        self._vol_unit = unit
        
        # Update suffixes in syringe tab
        self._spin_syr_vol.setSuffix(f"  {unit}")
        self._spin_input_ul.setSuffix(f"  {unit}")
        
        # Scale current values in syringe tab
        ratio = new_scale / old_scale
        self._spin_syr_vol.setValue(self._spin_syr_vol.value() * ratio)
        self._spin_input_ul.setValue(self._spin_input_ul.value() * ratio)
        
        # If in volume mode, update Manual Move spinners too
        if self._rb_unit_ul.isChecked():
            self._spin_dist.setSuffix(f"  {unit}")
            self._spin_speed.setSuffix(f"  {unit}/s")
            self._spin_accel.setSuffix(f"  {unit}/s²")
            # Trigger a full mode refresh to rescale values and ranges
            self._on_unit_mode_changed(False)
        else:
            # Just update syringe calcs labels
            self._update_syringe_calcs()
            self._refresh_program_table()

    def _do_delete_step(self):
        rows = self._prog_table.selectedItems()
        if not rows:
            QMessageBox.information(self, "Select a Row",
                                    "Please select a step to delete.")
            return
        row = self._prog_table.currentRow()
        step_num = row + 1  # 1-based
        if step_num < 1 or step_num > len(self._program):
            return
        del self._program[row]
        self._refresh_program_table()
        # Send to Arduino: enter P editor; 'D n' will fire when '>' prompt arrives
        self._in_prog_menu = True
        self._prog_cmd_queue = [f"D {step_num}"]
        self._send_raw("P")

    def _do_clear_program(self):
        reply = QMessageBox.question(
            self, "Clear Program",
            "Delete all stored program steps?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._program.clear()
            self._refresh_program_table()
            self._send_raw("C")

    def _do_run_program(self):
        if not self._program:
            QMessageBox.information(self, "Empty Program",
                                    "Add steps to the program first.")
            return
        total_s = sum(self._calculate_step_duration(s) for s in self._program)
        self._start_countdown(total_s)
        self._send_raw("R")

    # =========================================================================
    #  UI helpers
    # =========================================================================
    def _update_rev_label(self, val):
        if self._rb_unit_ul.isChecked():
            self._lbl_rev.setText("")
            return
        # val is in mm; show the integer step count that will be sent
        steps = int(round(float(val) / MM_PER_STEP))
        self._lbl_rev.setText(f"{steps} steps")

    def _refresh_program_table(self):
        ul_mode = self._rb_unit_ul.isChecked()
        spu = self._steps_per_ul_current() if ul_mode else 0.0
        ul_per_step = 1.0 / spu if spu > 0 else 0.0

        # Update column headers to match current unit
        if ul_mode and spu > 0:
            unit = self._vol_unit
            self._prog_table.setHorizontalHeaderLabels(
                ["#", "Direction", f"Volume ({unit})", f"Flow ({unit}/s)", f"Accel ({unit}/s²)"])
        else:
            self._prog_table.setHorizontalHeaderLabels(
                ["#", "Direction", "Distance (mm)", "Speed (mm/s)", "Accel (mm/s²)"])

        self._prog_table.setRowCount(0)
        total_s = 0.0
        for i, step in enumerate(self._program):
            total_s += self._calculate_step_duration(step)
            self._prog_table.insertRow(i)
            if ul_mode and spu > 0:
                unit = self._vol_unit
                scale = self._vol_scales[unit]
                dist_str  = f"{step.distance  * ul_per_step * scale:.3f}"
                speed_str = f"{step.speed     * ul_per_step * scale:.4f}"
                accel_str = f"{step.accel     * ul_per_step * scale:.4f}" if step.accel > 0 else "0 (const)"
            else:
                # mm mode
                dist_str  = f"{step.distance  * MM_PER_STEP:.3f}"
                speed_str = f"{step.speed     * MM_PER_STEP:.4f}"
                accel_str = f"{step.accel     * MM_PER_STEP:.4f}" if step.accel > 0 else "0 (const)"
            items = [
                str(i + 1),
                "Forward" if step.forward else "Backward",
                dist_str,
                speed_str,
                accel_str,
            ]
            for col, val in enumerate(items):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setForeground(QColor(TEXT_SEC))
                elif col == 1:
                    item.setForeground(
                        QColor(ACCENT) if step.forward else QColor(ACCENT2))
                self._prog_table.setItem(i, col, item)

        # Total duration summary
        if self._program:
            if total_s >= 60:
                m = int(total_s) // 60
                s = total_s - m * 60
                dur_txt = f"⏱ Total: {m}m {s:.1f}s"
            else:
                dur_txt = f"⏱ Total: {total_s:.1f}s"
            self._lbl_prog_duration.setText(dur_txt)
        else:
            self._lbl_prog_duration.setText("")

    def _set_motor_state(self, state: str):
        self._motor_state = state
        moving = (state == self.ST_MOVING)
        self._btn_move.setEnabled(not moving and self._worker.is_connected)
        self._btn_run_prog.setEnabled(not moving and self._worker.is_connected)
        self._btn_abort.setEnabled(moving)
        self._btn_add_step.setEnabled(not moving and self._worker.is_connected)
        self._btn_del_step.setEnabled(not moving and self._worker.is_connected)
        self._btn_clear_prog.setEnabled(not moving and self._worker.is_connected)

        if moving:
            self._lbl_motor_status.setText("Motor: RUNNING  ●")
            self._lbl_motor_status.setStyleSheet(f"color: {SUCCESS}; font-weight: 700;")
        else:
            self._lbl_motor_status.setText("Motor: IDLE")
            self._lbl_motor_status.setStyleSheet(f"color: {TEXT_SEC};")
            # Stop and reset countdown when move finishes
            self._countdown_timer.stop()
            self._lbl_countdown.setText("⏱  --")
            self._lbl_countdown.setStyleSheet(
                f"color: {TEXT_SEC}; font-family: 'Courier New', monospace;"
                f" font-size: 18px; font-weight: 700; min-width: 90px;")

    def _update_controls_for_connection(self, connected: bool):
        self._btn_move.setEnabled(connected)
        self._btn_run_prog.setEnabled(connected)
        self._btn_abort.setEnabled(False)
        self._btn_add_step.setEnabled(connected)
        self._btn_del_step.setEnabled(connected)
        self._btn_clear_prog.setEnabled(connected)

    def _log_line(self, text: str, color: Optional[str] = None):
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if color:
            fmt = cursor.charFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
        cursor.insertText(text + "\n")
        if color:
            # Reset to default green
            fmt = cursor.charFormat()
            fmt.setForeground(QColor("#a0ffb0"))
            cursor.setCharFormat(fmt)
        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()

    # =========================================================================
    #  Cleanup
    # =========================================================================
    def closeEvent(self, event):
        self._worker.stop()
        self._worker.close()
        self._thread.quit()
        self._thread.wait(2000)
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Microinjector Control Panel")
    app.setOrganizationName("Lab")

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
