"""MAP-01: floor-plan map of the polygon (tab Polygon).

Geometry of every segment, taken 1:1 from the former QLabel floor_XX map
in ui_mainwindow.py (setGeometry / raise_() / setText / setAlignment),
and PolygonMapWidget, which paints it with QPainter scaled uniformly to
its current size. Segment names are the [QUIDO_IN] keys.

MAP-02: a floor marked faulty by the operator (an OPEN SENSOR_FAULT in
the operation log) shows FAULTY over its QUIDO state. The two are kept
apart: QUIDO keeps updating the floor's state underneath, and clearing
the fault shows the latest QUIDO state at once.
"""

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QSizePolicy, QToolTip, QWidget

import theme

IDLE = "idle"          # input known, no step
ACTIVE = "active"      # step on the segment
UNKNOWN = "unknown"    # QUIDO Input unavailable / no valid read yet
UNMAPPED = "unmapped"  # segment not in the current [QUIDO_IN]
STATES = (IDLE, ACTIVE, UNKNOWN, UNMAPPED)
STATIC = "static"      # tile style of STATIC_SEGMENTS (roura) - not a floor state
FAULTY = "faulty"      # MAP-02 overlay: marked faulty by the operator - not a QUIDO state

# Logical floor-plan coordinates - the former groupBox_5 pixels.
# Tuple order IS the z-order: the first segment is painted at the bottom,
# the last one on top (the former raise_() sequence). The overlaps in the
# middle and right part are intentional: the lower tile shows only as an
# L-shape/strip, and its label sits in that visible part.
#
# (name, x, y, w, h, text, label position)
FLOOR_SEGMENTS = (
    ("floor_59", 1570, 450, 100, 100, "59", "center"),
    ("floor_53", 1610, 520, 100, 100, "53", "left"),
    ("floor_55", 1470, 150, 100, 100, "55", "left"),
    ("floor_56", 1570, 150, 100, 100, "56", "left"),
    ("floor_57", 1570, 250, 100, 100, "57", "center"),
    ("floor_58", 1570, 350, 100, 100, "58", "center"),
    ("floor_54", 1640, 190, 100, 100, "54", "left"),
    ("floor_42", 1150, 250, 100, 100, "42", "center"),
    ("floor_39", 1050, 250, 100, 100, "39", "bottom-left"),
    ("floor_36", 1150, 50, 100, 100, "36", "center"),
    ("floor_37", 1050, 50, 100, 100, "37", "bottom"),
    ("floor_29", 950, 50, 100, 100, "29", "bottom-left"),
    ("floor_38", 1050, 150, 100, 100, "38", "top"),
    ("floor_28", 950, 150, 100, 100, "28", "top-left"),
    ("floor_45", 1050, 350, 100, 100, "45", "bottom-left"),
    ("roura", 1150, 350, 100, 100, "Roura", "bottom"),
    ("floor_02", 350, 350, 100, 100, "2", "center"),
    ("floor_03", 250, 350, 100, 100, "3", "center"),
    ("floor_04", 250, 450, 100, 100, "4", "center"),
    ("floor_05", 150, 450, 100, 100, "5", "center"),
    ("floor_06", 50, 450, 100, 100, "6", "center"),
    ("floor_07", 50, 350, 100, 100, "7", "center"),
    ("floor_08", 150, 350, 100, 100, "8", "center"),
    ("floor_09", 150, 250, 100, 100, "9", "center"),
    ("floor_10", 50, 250, 100, 100, "10", "center"),
    ("floor_11", 50, 150, 100, 100, "11", "center"),
    ("floor_12", 50, 50, 100, 100, "12", "center"),
    ("floor_13", 150, 50, 100, 100, "13", "center"),
    ("floor_14", 150, 150, 100, 100, "14", "center"),
    ("floor_15", 250, 150, 100, 100, "15", "center"),
    ("floor_16", 250, 50, 100, 100, "16", "center"),
    ("floor_17", 350, 50, 100, 100, "17", "center"),
    ("floor_18", 350, 150, 100, 100, "18", "center"),
    ("floor_19", 450, 150, 100, 100, "19", "center"),
    ("floor_20", 550, 150, 100, 100, "20", "center"),
    ("floor_01", 350, 450, 100, 100, "1", "center"),
    ("floor_21", 550, 250, 100, 100, "21", "center"),
    ("floor_22", 550, 350, 100, 100, "22", "center"),
    ("floor_23", 650, 350, 100, 100, "23", "center"),
    ("floor_24", 650, 250, 100, 100, "24", "center"),
    ("floor_25", 650, 150, 100, 100, "25", "center"),
    ("floor_26", 750, 150, 100, 100, "26", "center"),
    ("floor_27", 850, 150, 100, 100, "27", "center"),
    ("floor_30", 850, 50, 100, 100, "30", "bottom"),
    ("floor_31", 880, 20, 100, 100, "31", "center"),
    ("floor_32", 980, 20, 100, 100, "32", "center"),
    ("floor_33", 980, 190, 100, 100, "33", "center"),
    ("floor_34", 1080, 190, 100, 100, "34", "center"),
    ("floor_40", 1080, 320, 100, 100, "40", "center"),
    ("floor_41", 1180, 320, 100, 100, "41", "center"),
    ("floor_43", 1150, 450, 100, 100, "43", "center"),
    ("floor_44", 1050, 450, 100, 100, "44", "center"),
    ("floor_46", 1610, 20, 100, 100, "46", "center"),
    ("floor_47", 1610, 120, 100, 100, "47", "center"),
    ("floor_48", 1710, 120, 100, 100, "48", "center"),
    ("floor_49", 1710, 220, 100, 100, "49", "center"),
    ("floor_50", 1710, 320, 100, 100, "50", "center"),
    ("floor_51", 1710, 420, 100, 100, "51", "center"),
    ("floor_52", 1710, 520, 100, 100, "52", "center"),
    ("floor_35", 1080, 20, 100, 100, "35", "center"),
)

# Static drawing only - no QUIDO input, never changes state.
STATIC_SEGMENTS = frozenset({"roura"})

# The whole logical floor plan incl. margins (segments span x 50..1810,
# y 20..620), scaled uniformly and centered by the widget.
MAP_WIDTH = 1860
MAP_HEIGHT = 640

FLOOR_NAMES = tuple(s[0] for s in FLOOR_SEGMENTS if s[0] not in STATIC_SEGMENTS)

# MAP-01e: legend of the tile styles, in the empty space between the left
# and the middle part of the plan (logical coordinates, overlaps no segment).
LEGEND = (
    (IDLE, "Čidlo v klidu"),
    (ACTIVE, "Aktivní došlap"),
    (UNKNOWN, "Stav neznámý / QUIDO nedostupné"),
    (UNMAPPED, "QUIDO vstup nepřiřazen"),
    (STATIC, "Statický prvek mapy"),
    (FAULTY, "Nefunkční čidlo"),
)
LEGEND_X, LEGEND_Y = 480, 482
LEGEND_ROW = 26                  # row pitch
LEGEND_SWATCH = (36, 20)         # w, h
LEGEND_TEXT_GAP = 10
LEGEND_FONT_SIZE = 13            # logical units
MIN_LEGEND_FONT_PX = 9          # the longest text still clears floor_44 down to scale 0.35

# MAP-02: shown (instead of a "no faults" map) while the fault register
# can't be read - in the empty space under floors 1-6.
FAULT_REGISTER_WARNING = ("Evidence závad nedostupná –", "stav nefunkčních čidel nelze ověřit")
WARNING_RECT = (50, 564, 420, 62)   # x, y, w, h

_HATCH_PATTERN = {FAULTY: QtCore.Qt.DiagCrossPattern}   # default BDiagPattern
_BORDER_WIDTH = {FAULTY: 3}                            # default 1 px
FAULTY_MARK = "!"
HW_STATE_TEXT = {IDLE: "klid", ACTIVE: "aktivní došlap", UNKNOWN: "neznámý",
                 UNMAPPED: "nemapováno v QUIDO_IN"}

_LABEL_FLAGS = {
    "center": QtCore.Qt.AlignCenter,
    "left": QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
    "top": QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop,
    "bottom": QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom,
    "top-left": QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop,
    "bottom-left": QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom,
}
LABEL_PADDING = 6      # logical units between a non-centered label and the tile edge
FONT_SIZE = 15         # logical units, ~ the former 11pt QLabel text at full size
MIN_FONT_PX = 10       # numbers stay readable on a small map


def segment_text(name):
    """The label of segment `name` on the map ("17", "Roura")."""
    return next(s[5] for s in FLOOR_SEGMENTS if s[0] == name)


def tile_text(style, text):
    """The label of a tile in `style` - FAULTY gets the "!" marker."""
    if style == FAULTY:
        return f"{FAULTY_MARK}{text}"
    return text


class PolygonMapWidget(QWidget):
    """The polygon floor plan: FLOOR_SEGMENTS painted in z-order, scaled
    uniformly (aspect ratio kept) and centered in the widget.

    Every floor starts UNKNOWN; floors left out of set_mapped_floors()
    are UNMAPPED and ignore state updates. roura is a static drawing.
    A FAULTY overlay (set_floor_fault) is drawn over any floor state.
    Right click on a floor emits floorContextRequested(name, global pos).
    """

    floorContextRequested = QtCore.pyqtSignal(str, QtCore.QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._states = {name: UNKNOWN for name in FLOOR_NAMES}   # QUIDO (base) state
        self._faults = {}                                        # name -> tooltip detail
        self._fault_register_available = True

    def sizeHint(self):
        return QtCore.QSize(MAP_WIDTH // 2, MAP_HEIGHT // 2)

    def minimumSizeHint(self):
        return QtCore.QSize(MAP_WIDTH // 4, MAP_HEIGHT // 4)

    # --- state API ---------------------------------------------------------

    def floor_state(self, name):
        """QUIDO state of floor `name` (also under FAULTY), None for roura /
        an unknown name."""
        return self._states.get(name)

    def display_state(self, name):
        """What the map shows: FAULTY over the QUIDO state, STATIC for roura."""
        if name in STATIC_SEGMENTS:
            return STATIC
        if name in self._faults:
            return FAULTY
        return self._states.get(name)

    def is_floor_faulty(self, name):
        return name in self._faults

    def set_floor_fault(self, name, faulty, detail=""):
        """MAP-02 overlay on/off for one floor; detail = tooltip lines of the
        fault. roura / unknown names: False, nothing changes."""
        if name not in self._states:
            return False
        if faulty:
            changed = self._faults.get(name) != detail
            self._faults[name] = detail
        else:
            changed = self._faults.pop(name, None) is not None
        if changed:
            self.update()
        return True

    def set_floor_faults(self, faults):
        """Replace every FAULTY overlay: {name: detail} (from the operation log)."""
        faults = {name: detail for name, detail in faults.items() if name in self._states}
        if faults != self._faults:
            self._faults = faults
            self.update()

    def fault_register_available(self):
        return self._fault_register_available

    def set_fault_register_available(self, available):
        """False: the operation log can't be read - the map shows a warning
        (and keeps the FAULTY overlays it knows); it never claims "no faults"."""
        if self._fault_register_available != bool(available):
            self._fault_register_available = bool(available)
            self.update()

    def set_mapped_floors(self, names):
        """Floors in `names` (the [QUIDO_IN] keys) become UNKNOWN until the
        first valid read, all others UNMAPPED."""
        names = set(names)
        self._apply({n: (UNKNOWN if n in names else UNMAPPED) for n in self._states})

    def set_floor_state(self, name, state):
        """Set one mapped floor to IDLE/ACTIVE/UNKNOWN. Unknown names,
        roura and UNMAPPED floors are ignored (returns False)."""
        return self.set_floor_states({name: state}) == 1

    def set_floor_states(self, states):
        """Batch of set_floor_state(), one repaint. Returns the number of
        floors accepted."""
        accepted = {}
        for name, state in states.items():
            if state not in (IDLE, ACTIVE, UNKNOWN):
                raise ValueError(f"Invalid floor state {state!r} for {name}")
            if self._states.get(name, UNMAPPED) != UNMAPPED:
                accepted[name] = state
        self._apply(accepted)
        return len(accepted)

    def set_input_available(self, available):
        """False: QUIDO Input lost - every mapped floor becomes UNKNOWN and
        its last value is dropped, so it only leaves UNKNOWN with a fresh
        read (set_floor_state(s)). True changes nothing by itself."""
        if not available:
            self._apply({n: UNKNOWN for n, s in self._states.items() if s != UNMAPPED})

    def _apply(self, states):
        changed = False
        for name, state in states.items():
            if self._states[name] != state:
                self._states[name] = state
                changed = True
        if changed:
            self.update()

    # --- painting ----------------------------------------------------------

    def map_transform(self):
        """Logical floor plan -> widget pixels: uniform scale, centered."""
        scale = min(self.width() / MAP_WIDTH, self.height() / MAP_HEIGHT)
        dx = (self.width() - MAP_WIDTH * scale) / 2
        dy = (self.height() - MAP_HEIGHT * scale) / 2
        return QtGui.QTransform(scale, 0, 0, scale, dx, dy)

    def segment_rect(self, name):
        """Widget-pixel rectangle of segment `name`."""
        for seg_name, x, y, w, h, *_ in FLOOR_SEGMENTS:
            if seg_name == name:
                return self.map_transform().mapRect(QtCore.QRectF(x, y, w, h))
        raise KeyError(name)

    def floor_at(self, pos):
        """Segment name under widget point `pos` (roura included), None
        outside the plan. Searches top-down (reverse z-order), so an
        overlapped tile is only hit in its visible part."""
        logical, invertible = self.map_transform().inverted()
        if not invertible:
            return None
        point = logical.map(QtCore.QPointF(pos))
        for name, x, y, w, h, *_ in reversed(FLOOR_SEGMENTS):
            if x <= point.x() < x + w and y <= point.y() < y + h:
                return name
        return None

    def contextMenuEvent(self, event):
        name = self.floor_at(event.pos())
        if name is None or name in STATIC_SEGMENTS:
            event.ignore()
            return
        self.floorContextRequested.emit(name, event.globalPos())
        event.accept()

    def tooltip_text(self, name):
        """Tooltip/detail of segment `name`."""
        text = segment_text(name)
        if name in STATIC_SEGMENTS:
            return f"{text} – statický prvek mapy"
        lines = [f"Čidlo {text}"]
        if name in self._faults:
            lines[0] += " – NEFUNKČNÍ"
            if self._faults[name]:
                lines.append(self._faults[name])
        elif not self._fault_register_available:
            lines.append("Stav závady nelze ověřit – evidence závad nedostupná")
        lines.append(f"Aktuální HW stav: {HW_STATE_TEXT[self._states[name]]}")
        return "\n".join(lines)

    def event(self, event):
        if event.type() == QtCore.QEvent.ToolTip:
            name = self.floor_at(event.pos())
            if name is None:
                QToolTip.hideText()
                event.ignore()
            else:
                QToolTip.showText(event.globalPos(), self.tooltip_text(name), self)
            return True
        return super().event(event)

    def legend_swatch_rect(self, index):
        """Widget-pixel rectangle of the legend swatch in LEGEND row `index`."""
        w, h = LEGEND_SWATCH
        rect = QtCore.QRectF(LEGEND_X, LEGEND_Y + index * LEGEND_ROW, w, h)
        return QtCore.QRectF(self.map_transform().mapRect(rect).toAlignedRect())

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        transform = self.map_transform()
        scale = transform.m11()
        font = QtGui.QFont(self.font())
        font.setPixelSize(max(MIN_FONT_PX, round(FONT_SIZE * scale)))
        padding = max(2.0, LABEL_PADDING * scale)
        for name, x, y, w, h, text, position in FLOOR_SEGMENTS:
            style = self.display_state(name)
            # Snap to whole pixels, so the 1px borders stay crisp at any scale
            rect = QtCore.QRectF(transform.mapRect(QtCore.QRectF(x, y, w, h)).toAlignedRect())
            self._paint_tile(painter, rect, style)
            self._paint_tile_text(painter, rect.adjusted(padding, padding, -padding, -padding),
                                  style, font, _LABEL_FLAGS[position], text)
        self._paint_legend(painter, scale)
        if not self._fault_register_available:
            self._paint_fault_register_warning(painter, transform, scale)
        painter.end()

    def _paint_tile_text(self, painter, rect, style, font, flags, text):
        _fill, _border, color, _hatch, _dashed, bold = theme.FLOOR_TILE_STYLE[style]
        font.setWeight(QtGui.QFont.Bold if bold else QtGui.QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(color))
        painter.drawText(rect, flags, tile_text(style, text))

    def _paint_fault_register_warning(self, painter, transform, scale):
        x, y, w, h = WARNING_RECT
        rect = QtCore.QRectF(transform.mapRect(QtCore.QRectF(x, y, w, h)).toAlignedRect())
        painter.fillRect(rect, QtGui.QColor(theme.DANGER_TINT))
        painter.setPen(QtGui.QPen(QtGui.QColor(theme.DANGER), 2))
        painter.drawRect(rect.adjusted(1, 1, -1, -1))
        font = QtGui.QFont(self.font())
        font.setPixelSize(max(MIN_LEGEND_FONT_PX, round(LEGEND_FONT_SIZE * scale)))
        font.setWeight(QtGui.QFont.Bold)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(theme.DANGER_DARK))
        painter.drawText(rect, QtCore.Qt.AlignCenter, "\n".join(FAULT_REGISTER_WARNING))

    def _paint_tile(self, painter, rect, style):
        """Fill + hatch + border of one tile in theme.FLOOR_TILE_STYLE[style];
        shared by the segments and the legend swatches."""
        fill, border, _color, hatch, dashed, _bold = theme.FLOOR_TILE_STYLE[style]
        painter.fillRect(rect, QtGui.QColor(fill))
        if hatch:
            pattern = _HATCH_PATTERN.get(style, QtCore.Qt.BDiagPattern)
            painter.fillRect(rect, QtGui.QBrush(QtGui.QColor(hatch), pattern))
        width = _BORDER_WIDTH.get(style, 1)
        painter.setPen(QtGui.QPen(QtGui.QColor(border), width, QtCore.Qt.DashLine if dashed else QtCore.Qt.SolidLine))
        inset = width / 2
        painter.drawRect(rect.adjusted(inset, inset, -inset, -inset))

    def _paint_legend(self, painter, scale):
        font = QtGui.QFont(self.font())
        font.setPixelSize(max(MIN_LEGEND_FONT_PX, round(LEGEND_FONT_SIZE * scale)))
        painter.setFont(font)
        gap = LEGEND_TEXT_GAP * scale
        for index, (style, text) in enumerate(LEGEND):
            swatch = self.legend_swatch_rect(index)
            self._paint_tile(painter, swatch, style)
            if tile_text(style, ""):  # the same marker as on the map ("!" of FAULTY)
                self._paint_tile_text(painter, swatch, style, QtGui.QFont(font), QtCore.Qt.AlignCenter, "")
                painter.setFont(font)
            painter.setPen(QtGui.QColor(theme.TEXT_MUTED))
            text_rect = QtCore.QRectF(swatch.right() + gap, swatch.top(), self.width(), swatch.height())
            painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, text)
