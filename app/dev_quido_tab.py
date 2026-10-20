"""DEV-QUIDO-01: read-only QUIDO diagnostics tab - only with ./bin/polygon --dev.

Shows every physical QUIDO Input and Output with its [QUIDO_IN] / [QUIDO_OUT]
name, the module states and the last value changes. It never talks to QUIDO
itself: MainWindow hands it the same reads the quido-in / quido-out workers
make for the normal UI (show_inputs / show_outputs). No control of any kind,
the change history lives in RAM only (empty after a restart). DEV-LOG-01:
the same reads also go to the run's file log (dev_quido_log.DevQuidoLog).
"""
from collections import deque
from datetime import datetime

from PyQt5 import QtCore
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget, QVBoxLayout, QWidget

import polygon_map
import theme

INPUT_COUNT = 104    # QUIDO Input module: 13 bytes of states
OUTPUT_COUNT = 32    # QUIDO Output module: 4 bytes of states
INPUT_COLUMNS = 8
OUTPUT_COLUMNS = 4
HISTORY_SIZE = 50
HIGHLIGHT_MS = 2000  # a changed value stays highlighted this long

WAITING, OK, UNKNOWN = "ČEKÁ", "OK", "UNKNOWN"
NO_NAME = "—"

INPUT, OUTPUT = "INPUT", "OUTPUT"


def input_names(quido_in):
    """{0-based input: "floor_46 / floor_55"} from [QUIDO_IN] (a shared input lists all)."""
    names = {}
    for name, value in quido_in.items():
        try:
            names.setdefault(int(value), []).append(name)
        except ValueError:
            continue
    return {index: " / ".join(sorted(group)) for index, group in names.items()}


def output_names(quido_out):
    """{1-based relay: name} from [QUIDO_OUT]."""
    names = {}
    for name, value in quido_out.items():
        try:
            names.setdefault(int(value), []).append(name)
        except ValueError:
            continue
    return {relay: " / ".join(sorted(group)) for relay, group in names.items()}


def input_labels(quido_in):
    """{0-based input: "Čidlo 46 / Čidlo 55"} - the map labels of its floors."""
    labels = {}
    for name, value in quido_in.items():
        try:
            index, label = int(value), f"Čidlo {polygon_map.segment_text(name)}"
        except (ValueError, StopIteration):
            continue
        labels.setdefault(index, []).append((name, label))
    return {index: " / ".join(label for _, label in sorted(group)) for index, group in labels.items()}


_STYLE = f"""
QLabel[devCell="true"] {{
    font-family: monospace; font-size: 12pt; font-weight: 700;
    padding: 3px 6px; border: 1px solid {theme.BORDER}; border-radius: 4px;
    background: {theme.WHITE}; color: {theme.TEXT};
}}
QLabel[devCell="true"][named="false"] {{ color: {theme.TEXT_MUTED}; }}
QLabel[devCell="true"][value="low"][named="true"] {{ background: {theme.DANGER_TINT}; }}
QLabel[devCell="true"][value="on"] {{ background: {theme.SUCCESS_TINT}; }}
QLabel[devCell="true"][value="unknown"] {{ background: {theme.NEUTRAL_TINT}; color: {theme.TEXT_MUTED}; }}
QLabel[devCell="true"][changed="true"] {{ background: {theme.WARNING}; color: {theme.TEXT}; }}
QLabel[devStatus="true"] {{ font-size: 13pt; font-weight: 700; padding: 4px 10px; }}
QListWidget#devHistory {{ font-family: monospace; font-size: 11pt; }}
"""


class DevQuidoTab(QWidget):
    """Big read-only grids of all QUIDO Inputs and Outputs + change history."""

    def __init__(self, quido_in, quido_out, clock=datetime.now, parent=None, log=None):
        super().__init__(parent)
        self.log = log  # DEV-LOG-01: DevQuidoLog or None
        self.setObjectName("tabDev")
        self.setStyleSheet(_STYLE)
        self._clock = clock
        self._input_names = input_names(quido_in)
        self._output_names = output_names(quido_out)
        self._inputs = None    # last known Input states (kept over an outage)
        self._outputs = None
        self._status = {INPUT: WAITING, OUTPUT: WAITING}
        self._last_snapshot = {INPUT: None, OUTPUT: None}
        self._history = deque(maxlen=HISTORY_SIZE)
        self._highlights = {}  # cell -> monotonic ms when the highlight ends
        self._highlight_timer = QtCore.QTimer(self)
        self._highlight_timer.setInterval(250)
        self._highlight_timer.timeout.connect(self._clear_old_highlights)
        self._clock_ms = QtCore.QElapsedTimer()
        self._clock_ms.start()

        layout = QVBoxLayout(self)
        status_row = QHBoxLayout()
        self.statusLabels = {}
        for kind in (INPUT, OUTPUT):
            label = QLabel()
            label.setProperty("devStatus", "true")
            self.statusLabels[kind] = label
            status_row.addWidget(label)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        body = QHBoxLayout()
        self.inputCells = self._grid(body, "QUIDO Input", INPUT_COUNT, INPUT_COLUMNS, stretch=3)
        right = QVBoxLayout()
        body.addLayout(right, 2)
        self.outputCells = self._grid(right, "QUIDO Output", OUTPUT_COUNT, OUTPUT_COLUMNS)
        history_box = QGroupBox(f"Poslední změny (max. {HISTORY_SIZE}, jen v paměti)")
        history_layout = QVBoxLayout(history_box)
        self.historyList = QListWidget()
        self.historyList.setObjectName("devHistory")
        history_layout.addWidget(self.historyList)
        right.addWidget(history_box, 1)
        layout.addLayout(body, 1)

        for index in range(INPUT_COUNT):
            self._show_cell(INPUT, index, None)
        for index in range(OUTPUT_COUNT):
            self._show_cell(OUTPUT, index, None)
        self._show_status()

    def _grid(self, parent_layout, title, count, columns, stretch=0):
        box = QGroupBox(title)
        grid = QGridLayout(box)
        grid.setSpacing(4)
        cells = []
        rows = -(-count // columns)
        for index in range(count):
            cell = QLabel()
            cell.setProperty("devCell", "true")
            grid.addWidget(cell, index % rows, index // rows)  # numbers run down the columns
            cells.append(cell)
        parent_layout.addWidget(box, stretch)
        return cells

    # --- data in (GUI thread, from MainWindow) -----------------------------

    def show_inputs(self, states):
        """All Input states of one quido-in read, or None = read failed."""
        if self.log is not None:
            self.log.inputs(states)
        self._inputs = self._update(INPUT, states, self._inputs, INPUT_COUNT)

    def show_outputs(self, states):
        """All Output states of one quido-out read, or None = read failed."""
        if self.log is not None:
            self.log.outputs(states)
        self._outputs = self._update(OUTPUT, states, self._outputs, OUTPUT_COUNT)

    def _update(self, kind, states, known, count):
        if states is None:
            self._status[kind] = UNKNOWN
            for index in range(count):
                self._show_cell(kind, index, None)
            self._show_status()
            return known  # last known values stay for the comparison after the outage
        values = [bool(v) for v in list(states)[:count]]
        values += [None] * (count - len(values))
        self._status[kind] = OK
        self._last_snapshot[kind] = self._clock()
        for index, value in enumerate(values):
            old = known[index] if known is not None else None
            changed = known is not None and old is not None and value is not None and old != value
            if changed:
                self._record(kind, index, old, value)
            self._show_cell(kind, index, value, changed)
        self._show_status()
        return values

    # --- presentation ---------------------------------------------------------

    def _number(self, kind, index):
        """The number as in the config: Inputs 0-based, Outputs 1-based (relay)."""
        return index if kind == INPUT else index + 1

    def _name(self, kind, index):
        names = self._input_names if kind == INPUT else self._output_names
        return names.get(self._number(kind, index), NO_NAME)

    @staticmethod
    def _value_text(kind, value):
        if value is None:
            return "?"
        if kind == INPUT:
            return "1" if value else "0"
        return "ON" if value else "OFF"

    def cell_text(self, kind, number):
        """Text of the cell for config number `number` (tests, diagnostics)."""
        cells = self.inputCells if kind == INPUT else self.outputCells
        return cells[number if kind == INPUT else number - 1].text()

    def _show_cell(self, kind, index, value, changed=False):
        cell = (self.inputCells if kind == INPUT else self.outputCells)[index]
        prefix = f"IN {self._number(kind, index):02d}" if kind == INPUT else f"OUT {self._number(kind, index):02d}"
        name = self._name(kind, index)
        cell.setText(f"{prefix}  {self._value_text(kind, value):<3} {name}")
        if value is None:
            state = "unknown"
        elif kind == INPUT:
            state = "high" if value else "low"
        else:
            state = "on" if value else "off"
        self._set(cell, "value", state)
        self._set(cell, "named", "false" if name == NO_NAME else "true")
        if changed:
            self._set(cell, "changed", "true")
            self._highlights[cell] = self._clock_ms.elapsed() + HIGHLIGHT_MS
            self._highlight_timer.start()

    def _show_status(self):
        for kind, label in self.statusLabels.items():
            last = self._last_snapshot[kind]
            when = f" – poslední snapshot {last:%H:%M:%S}" if last else ""
            label.setText(f"QUIDO {kind}: {self._status[kind]}{when}")
            if self._status[kind] != WAITING:
                theme.set_hw_state(label, self._status[kind] == OK)

    def _record(self, kind, index, old, new):
        entry = (self._clock(), kind, self._number(kind, index),
                 self._value_text(kind, old), self._value_text(kind, new), self._name(kind, index))
        self._history.appendleft(entry)
        when, kind, number, old_text, new_text, name = entry
        self.historyList.insertItem(0, f"{when:%H:%M:%S}  {kind:<6}  {number:>3}  {old_text:>3} -> {new_text:<3}  {name}")
        while self.historyList.count() > HISTORY_SIZE:
            self.historyList.takeItem(self.historyList.count() - 1)

    @property
    def history(self):
        """[(time, kind, number, old, new, name)], newest first."""
        return list(self._history)

    def status(self, kind):
        return self._status[kind]

    def _clear_old_highlights(self):
        now = self._clock_ms.elapsed()
        for cell, end in list(self._highlights.items()):
            if now >= end:
                self._set(cell, "changed", "false")
                del self._highlights[cell]
        if not self._highlights:
            self._highlight_timer.stop()

    @staticmethod
    def _set(widget, name, value):
        if widget.property(name) != value:
            widget.setProperty(name, value)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
