"""Central look of the application (GUI facelift, control-room style).

One place for colors and QSS instead of setStyleSheet() strings scattered
through ui_mainwindow.py/main.py. Pure presentation - no data, no
business logic.

Widget rules are emitted per tab listed in STYLED_TABS (the facelift goes
tab by tab); tabs not listed keep the plain Fusion look inside the shared
chrome (window frame, tab bar, status bar).

Colors carry operational meaning:
PŘIPRAVEN = neutral slate, UVNITŘ = red, DOKONČENO = green,
HW OK = green, HW error = red, DEV MODE / QUIDO simulator = orange,
DB: local = orange, live = neutral, live while in DEV mode = red.
"""

import os

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QHeaderView, QPushButton, QStyle,
                             QStyledItemDelegate, QStyleOptionViewItem)

# GUI-ICONS-01: Polygon relay button icon geometry (see apply_relay_icons()).
RELAY_ICON_SIZE = 40
RELAY_ICON_GAP = 7          # transparent strip in the pixmap; Qt adds ~4 px more
RELAY_PADDING_LEFT = 14

# --- color tokens ---------------------------------------------------------
CHROME = "#1f2933"          # window frame, tab strip, status bar
CHROME_TEXT = "#cbd2d9"
BACKGROUND = "#d3d8de"      # tab page
SURFACE = "#eceff3"         # panels, tables - deliberately not white
SURFACE_ALT = "#e3e7ec"     # alternate table rows
HEADER = "#d8dde4"          # table header
WHITE = "#ffffff"           # input fields, secondary buttons, map tiles
DIALOG_BG = "#f7f9fc"       # dialogs - lightest layer, "sheet on top" of the grey window
BORDER = "#cbd2d9"
DIVIDER = "#e4e7eb"
TEXT = "#1f2933"
TEXT_MUTED = "#616e7c"
SELECTION = "#c3d9f7"

PRIMARY = "#1565c0"
PRIMARY_DARK = "#0d47a1"
SUCCESS = "#2e7d32"
SUCCESS_DARK = "#1b5e20"
DANGER = "#c62828"
DANGER_DARK = "#8e1b1b"
DANGER_TINT = "#fde7e7"
SUCCESS_TINT = "#d3ecd7"
NEUTRAL_TINT = "#cdd4dc"
DEV = "#e65100"
WARNING = "#f0b429"

DISABLED_BG = "#dde2e8"
DISABLED_TEXT = "#9aa5b1"
DISABLED_BORDER = "#b3bcc6"

STYLED_TABS = ("#tabProvoz", "#tabPerson", "#tabTraining", "#tabPolygon", "#tabLogbook")

# --- shared chrome ----------------------------------------------------------
_CHROME_QSS = f"""
QMainWindow#MainWindow {{ background: {CHROME}; }}
QTabWidget#ptabWidget::pane {{
    background: {BACKGROUND}; border: none; border-radius: 6px; top: -1px;
}}
/* Font on the bar, not on ::tab - QTabBar sizes tabs from its own font,
   a bigger ::tab font would be clipped at both ends. */
QTabWidget#ptabWidget > QTabBar {{ font-size: 12pt; font-weight: 600; }}
QTabWidget#ptabWidget > QTabBar::tab {{
    background: transparent; color: {CHROME_TEXT};
    padding: 10px 30px; margin-right: 2px;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}}
QTabWidget#ptabWidget > QTabBar::tab:hover:!selected {{ background: #323f4b; color: #ffffff; }}
QTabWidget#ptabWidget > QTabBar::tab:selected {{
    background: {BACKGROUND}; color: {TEXT}; border-top: 3px solid {PRIMARY};
}}
QStatusBar#statusbar {{ background: {CHROME}; color: {CHROME_TEXT}; font-size: 10pt; }}
QStatusBar#statusbar::item {{ border: none; }}
QStatusBar#statusbar QLabel {{
    color: #ffffff; border-radius: 4px; padding: 3px 10px; margin: 3px 2px; font-weight: 600;
}}
QStatusBar#statusbar QLabel[hw="ok"] {{ background: {SUCCESS}; }}
QStatusBar#statusbar QLabel[hw="error"] {{ background: {DANGER}; }}
QStatusBar#statusbar QLabel[hw="mock"] {{ background: {DEV}; }}
QStatusBar#statusbar QLabel#devModeLabel {{ background: {DEV}; }}
QStatusBar#statusbar QLabel#emergencyStatusLabel {{ background: {DANGER}; }}
QStatusBar#statusbar QLabel[db="local"] {{ background: {DEV}; }}
QStatusBar#statusbar QLabel[db="live"] {{ background: transparent; color: {CHROME_TEXT}; font-weight: normal; }}
QStatusBar#statusbar QLabel[db="live-dev"] {{ background: {DANGER}; }}
QStatusBar#statusbar QLabel#userLabel {{ background: transparent; color: {CHROME_TEXT}; font-weight: normal; padding: 3px 4px; }}
/* UI-ABOUT-01: version as a link - opens O aplikaci / Přehled změn. */
QStatusBar#statusbar QPushButton#versionButton {{
    background: transparent; border: none; color: {CHROME_TEXT}; font-size: 10pt;
    text-decoration: underline; padding: 3px 4px 3px 8px; min-width: 0;
}}
QStatusBar#statusbar QPushButton#versionButton:hover {{ color: #ffffff; }}

/* Dialogs (Osoba, Hodnoty, přihlášení, message boxes). */
QDialog {{ background: {DIALOG_BG}; border: 1px solid #52606d; border-top: 4px solid {PRIMARY}; }}
QDialog QLabel {{ color: {TEXT}; }}
QDialog QGroupBox {{ border: 1px solid {BORDER}; border-radius: 6px; margin-top: 22px; padding-top: 8px; }}
QDialog QGroupBox::title {{ subcontrol-origin: margin; left: 8px; color: {TEXT_MUTED}; font-weight: 700; }}
QDialog QLineEdit {{
    background: {WHITE}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 4px;
    padding: 2px 8px;
}}
QDialog QLineEdit:focus {{ border: 2px solid {PRIMARY}; }}
QDialog QLineEdit:disabled {{ background: {SURFACE_ALT}; color: {DISABLED_TEXT}; }}
QDialog QPushButton {{
    background: {WHITE}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 5px 18px; min-width: 70px; font-size: 11pt; font-weight: 600;
}}
QDialog QPushButton:hover {{ background: {SURFACE_ALT}; border-color: {TEXT_MUTED}; }}
QDialog QPushButton:pressed {{ background: {HEADER}; }}
QDialog QPushButton:default {{ background: {PRIMARY}; color: #ffffff; border-color: {PRIMARY}; }}
QDialog QPushButton:default:hover {{ background: #1976d2; }}
QDialog QPushButton:disabled {{ background: {DISABLED_BG}; color: {DISABLED_TEXT}; border: 1px dashed {DISABLED_BORDER}; }}

/* Button categories - set via the "variant" dynamic property (set_variant()). */
QPushButton[variant] {{
    border-radius: 6px; padding: 6px 16px; font-size: 11pt; font-weight: 600;
    border: 1px solid transparent; color: #ffffff;
}}
QPushButton[variant]:disabled {{
    background: {DISABLED_BG}; color: {DISABLED_TEXT}; border: 1px dashed {DISABLED_BORDER};
}}
QPushButton[variant="primary"] {{ background: {PRIMARY}; }}
QPushButton[variant="primary"]:hover {{ background: #1976d2; }}
QPushButton[variant="primary"]:pressed {{ background: {PRIMARY_DARK}; }}
QPushButton[variant="success"] {{ background: {SUCCESS}; }}
QPushButton[variant="success"]:hover {{ background: #388e3c; }}
QPushButton[variant="success"]:pressed {{ background: {SUCCESS_DARK}; }}
QPushButton[variant="danger"] {{ background: {DANGER}; }}
QPushButton[variant="danger"]:hover {{ background: #d32f2f; }}
QPushButton[variant="danger"]:pressed {{ background: {DANGER_DARK}; }}
QPushButton[variant="secondary"] {{ background: {WHITE}; color: {TEXT}; border-color: {BORDER}; }}
QPushButton[variant="secondary"]:hover {{ background: {SURFACE_ALT}; border-color: {TEXT_MUTED}; }}
QPushButton[variant="secondary"]:pressed {{ background: {HEADER}; }}
QPushButton[variant="destructive"] {{ background: transparent; color: {DANGER}; border-color: {DANGER}; }}
QPushButton[variant="destructive"]:hover {{ background: {DANGER_TINT}; }}
QPushButton[variant="destructive"]:pressed {{ background: #f8caca; }}
QPushButton[variant="destructive"]:disabled {{ background: transparent; color: {DISABLED_TEXT}; border: 1px dashed {DISABLED_BORDER}; }}
/* EMERGENCY-01: relay buttons locked by the emergency mode still show ON (green, dashed = locked). */
QPushButton[variant="success"][locked="true"]:disabled {{ background: {SUCCESS}; color: #ffffff; border: 2px dashed {SUCCESS_DARK}; }}
/* HW-IO: relay button whose QUIDO Output state is not known (always disabled). */
QPushButton[variant="unknown"], QPushButton[variant="unknown"]:disabled {{ background: {NEUTRAL_TINT}; color: {TEXT_MUTED}; border: 1px dashed {TEXT_MUTED}; }}
QPushButton[variant="warning"] {{ background: {WARNING}; color: {TEXT}; }}
QPushButton[variant="warning"]:hover {{ background: #f7c948; }}
QPushButton[variant="warning"]:pressed {{ background: #de911d; }}
QPushButton[size="xl"] {{ font-size: 15pt; font-weight: 700; }}
QPushButton[size="lg"] {{ font-size: 13pt; font-weight: 700; }}
/* GUI-ICONS-01: Polygon relay buttons - icon at a fixed x on the left, text
   left-aligned right after it (not the icon+text block centered). */
QPushButton[variant][relay="true"] {{ text-align: left; padding-left: {RELAY_PADDING_LEFT}px; }}
"""

# --- per-tab widget rules (SCOPE -> each of STYLED_TABS) --------------------
_SCOPED_QSS = f"""
SCOPE {{ color: {TEXT}; }}
SCOPE QGroupBox {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    margin-top: 26px; padding: 12px 10px 10px 10px;
}}
SCOPE QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 2px; padding: 0 4px 4px 4px; background: transparent;
    color: {TEXT_MUTED}; font-size: 10.5pt; font-weight: 700;
}}
SCOPE QTableView {{
    background: {SURFACE}; alternate-background-color: {SURFACE_ALT};
    border: 1px solid {BORDER}; border-radius: 6px;
    selection-background-color: {SELECTION}; selection-color: {TEXT};
    font-size: 11.5pt; outline: 0;
}}
SCOPE QTableView::item {{ padding-left: 10px; }}
SCOPE QHeaderView::section {{
    background: {HEADER}; color: #3e4c59; font-size: 10pt; font-weight: 700;
    padding: 8px 12px; border: none; border-bottom: 2px solid {BORDER};
}}
SCOPE QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
SCOPE QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 40px; }}
SCOPE QScrollBar::handle:vertical:hover {{ background: #9aa5b1; }}
SCOPE QScrollBar::add-line, SCOPE QScrollBar::sub-line {{ height: 0; width: 0; }}
SCOPE QScrollBar::add-page, SCOPE QScrollBar::sub-page {{ background: transparent; }}
SCOPE QGroupBox#groupBox_5 {{ background: {SURFACE_ALT}; margin-top: 0; }}
SCOPE QSlider::groove:vertical {{ background: {BORDER}; width: 6px; border-radius: 3px; }}
SCOPE QSlider::handle:vertical {{ background: {PRIMARY}; height: 18px; margin: 0 -7px; border-radius: 9px; }}
SCOPE QSlider::add-page:vertical {{ background: {PRIMARY}; border-radius: 3px; }}
SCOPE QSplitter::handle:vertical {{ height: 10px; background: transparent; }}
SCOPE QLineEdit {{
    background: {WHITE}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 4px 10px; font-size: 11.5pt;
}}
SCOPE QLineEdit:focus {{ border: 2px solid {PRIMARY}; }}
SCOPE QLabel {{ font-size: 11pt; }}
SCOPE QLabel#selectedMemberLabel {{ font-size: 13pt; font-weight: 600; padding: 6px 2px 2px 2px; }}

/* "N UVNITŘ" counter tile - state property set by MainWindow. */
SCOPE QLabel#insideCountLabel {{
    font-size: 22pt; font-weight: 800; padding: 10px 22px; border-radius: 8px;
    background: {SURFACE}; color: {TEXT_MUTED}; border: 1px solid {BORDER};
}}
SCOPE QLabel#insideCountLabel[state="inside"] {{ background: {DANGER}; color: #ffffff; border-color: {DANGER_DARK}; }}
SCOPE QLabel#insideCountLabel[state="unknown"] {{ background: {DANGER_TINT}; color: {DANGER_DARK}; border: 2px solid {DANGER}; }}
SCOPE QLabel#cameraStateLabel, SCOPE QLabel#recordingStateLabel {{ font-size: 10.5pt; font-weight: 700; padding: 4px 12px; border-radius: 4px; }}
"""


def stylesheet():
    scoped = "".join(_SCOPED_QSS.replace("SCOPE", tab) for tab in STYLED_TABS)
    return _CHROME_QSS + scoped


def apply_theme(app):
    """Fusion (same on every Linux desktop, fully QSS-stylable) + the app QSS."""
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())


def _set_property(widget, name, value):
    """Set a style property; repolish only on a real change (some callers
    run on the 600 ms QUIDO timer)."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    repolish(widget)


def repolish(widget):
    """Re-evaluate QSS after a dynamic property change."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_variant(button, variant, size=None):
    """Button category: primary / success / danger / secondary / destructive
    (+ warning for the emergency button)."""
    if size:
        button.setProperty("size", size)
    _set_property(button, "variant", variant)


def set_state(widget, state):
    """Dynamic "state" style hook (insideCountLabel) - see the QSS above."""
    _set_property(widget, "state", state)


def set_hw_state(label, ok, mock=False):
    """QUIDO status label: ok = green, error = red, mock (simulator) = orange."""
    _set_property(label, "hw", "mock" if mock else ("ok" if ok else "error"))


def set_emergency_locked(button, locked):
    """EMERGENCY-01: a disabled relay button keeps showing its ON state."""
    _set_property(button, "locked", "true" if locked else "")


def set_relay_state(button, on):
    """Polygon relay button: on = green, off = neutral, None = UNKNOWN
    (HW-IO: QUIDO Output state not known - grey, dashed)."""
    set_variant(button, "unknown" if on is None else ("success" if on else "secondary"))
    on = bool(on)
    icons = getattr(button, "_relay_icons", None)
    if icons and getattr(button, "_relay_icon_on", None) != on:
        button._relay_icon_on = on
        button.setIcon(icons[1 if on else 0])


# GUI-ICONS-01: Polygon tab relay buttons. The PNGs are white on transparent;
# off (white button) gets a TEXT-colored copy, on (green) the white original.
# Path from this file, not the cwd - bin/polygon may be started from anywhere.
ICON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "files", "icons"))
RELAY_ICONS = {
    "fan12Button": "01_ventilator.png",
    "fan34Button": "01_ventilator.png",
    "fanControlRoomButton": "01_ventilator.png",
    "glowButton": "02_zhaveni_zadymeni.png",
    "smokeButton": "03_zadymeni.png",
    "louverButton": "04_zaluzie.png",
    "stroboButton": "05_zablesky.png",
    "hotZoneButton": "06_tepla_zona.png",
    "polygonLight1Button": "07_svetlo_univerzal.png",
    "polygonLight2Button": "07_svetlo_univerzal.png",
    "polygonLight3Button": "07_svetlo_univerzal.png",
    "hotZoneLightButton": "07_svetlo_univerzal.png",
    "stressRoomLightButton": "07_svetlo_univerzal.png",
    "controlRoomLightButton": "07_svetlo_univerzal.png",
    "helpLightButton": "07_svetlo_univerzal.png",
    "infraLightButton": "08_infra_osvetleni.png",
}

# AUDIO-02: the sound effect toggle looks and behaves like a relay button.
SOUND_ICONS = {"pushButton_19": "09_zvuk.png"}


def _relay_pixmap(pixmap, color=None):
    """pixmap (optionally recolored, alpha kept) with a transparent strip on
    the right - Fusion puts the text only ~4 px from the icon."""
    gap = pixmap.width() * RELAY_ICON_GAP // RELAY_ICON_SIZE
    out = QtGui.QPixmap(pixmap.width() + gap, pixmap.height())
    out.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(out)
    painter.drawPixmap(0, 0, pixmap)
    if color:
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        painter.fillRect(out.rect(), QtGui.QColor(color))
    painter.end()
    return out


# CAMERA-LIFECYCLE-01: Kamery block on the Polygon tab
CAMERA_ICON = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "files", "video.png"))
CAMERA_ICON_SIZE = 24


def apply_camera_icons(camera_buttons, folder_button, icon_path=CAMERA_ICON):
    """Camera outline (in the text color, like the relay icons) on
    camera_buttons, the style's folder icon on folder_button. A missing
    camera icon only leaves those buttons text-only; returns False then."""
    size = QtCore.QSize(CAMERA_ICON_SIZE, CAMERA_ICON_SIZE)
    folder_button.setIcon(QApplication.style().standardIcon(QStyle.SP_DirOpenIcon))
    folder_button.setIconSize(size)
    pixmap = QtGui.QPixmap(icon_path)
    if pixmap.isNull():
        return False
    pixmap = _relay_pixmap(pixmap, TEXT)
    icon = QtGui.QIcon(pixmap)
    for button in camera_buttons:
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(CAMERA_ICON_SIZE * pixmap.width() // pixmap.height(), CAMERA_ICON_SIZE))
    return True


def apply_relay_icons(root, icon_dir=ICON_DIR, icons=RELAY_ICONS):
    """Attach icons to the relay buttons under root (or the buttons in icons,
    e.g. SOUND_ICONS). A missing/unreadable icon only leaves that button
    text-only; returns the files not loaded."""
    missing = []
    for name, filename in icons.items():
        button = root.findChild(QPushButton, name)
        if button is None:
            continue
        _set_property(button, "relay", "true")
        pixmap = QtGui.QPixmap(os.path.join(icon_dir, filename))
        if pixmap.isNull():
            missing.append(filename)
            continue
        button._relay_icons = (QtGui.QIcon(_relay_pixmap(pixmap, TEXT)), QtGui.QIcon(_relay_pixmap(pixmap)))
        button._relay_icon_on = None
        button.setIconSize(QtCore.QSize(RELAY_ICON_SIZE + RELAY_ICON_GAP, RELAY_ICON_SIZE))
        set_relay_state(button, button.property("variant") == "success")
    return sorted(set(missing))


# Polygon map tiles (QUIDO inputs, MAP-01 PolygonMapWidget) per state -
# fill, border, text, hatch (None = solid), dashed border, bold text.
FLOOR_TILE_STYLE = {
    "idle": (WHITE, BORDER, TEXT, None, False, False),
    "active": (DANGER, DANGER_DARK, "#ffffff", None, False, True),
    "unknown": (NEUTRAL_TINT, DISABLED_TEXT, TEXT, DISABLED_TEXT, False, False),  # grey, hatched
    "unmapped": (SURFACE, DISABLED_BORDER, TEXT_MUTED, None, True, False),        # muted, dashed
    "static": ("#d9e2ec", "#9fb3c8", TEXT, None, False, False),  # roura - plan element, no input: blue-grey
    # MAP-02: sensor marked faulty by the operator - amber, cross-hatched, thick dark
    # border and "!" (never by color alone; not WARNING yellow / DEV orange)
    "faulty": ("#ffc857", "#7a3e00", TEXT, "#e0a030", False, True),
}


# LOGBOOK-01: the Kniha provozu tab while operation_log can't be read
LOGBOOK_BANNER_STYLE = (f"background: {DANGER_TINT}; color: {DANGER_DARK}; border: 2px solid {DANGER}; "
                        f"border-radius: 6px; padding: 8px 12px; font-weight: 700; font-size: 12pt;")


# Camera indicator (Provoz) - background/text per CameraState name.
CAMERA_STATE_STYLE = {
    "DISABLED": f"background: {WHITE}; color: {TEXT_MUTED}; border: 1px solid {BORDER};",
    "STARTING": f"background: {WHITE}; color: {TEXT_MUTED}; border: 1px dashed {BORDER};",
    "STOPPING": f"background: {WHITE}; color: {TEXT_MUTED}; border: 1px dashed {BORDER};",
    "READY": f"background: {SUCCESS_TINT}; color: {SUCCESS_DARK};",
    "RECORDING": f"background: {DANGER_TINT}; color: {DANGER_DARK}; border: 1px solid {DANGER};",
    "ERROR": f"background: {DANGER}; color: #ffffff;",
}

# CAMERA-UI-02: camera tiles on the (dark, usually fullscreen) camera window.
CAMERA_TILE_BG = "#000000"
CAMERA_TILE_STYLE = f"background: {CHROME};"
CAMERA_VIEW_STYLE = f"background: {CAMERA_TILE_BG};"
CAMERA_TILE_NAME_STYLE = f"color: {CHROME_TEXT}; font-weight: bold; font-size: 15px; padding: 3px 8px;"
CAMERA_TILE_STATUS_STYLE = {
    True: f"color: #ffffff; background: {SUCCESS}; font-weight: bold; font-size: 13px; "
          "padding: 2px 8px; border-radius: 3px;",
    False: f"color: #ffffff; background: {DANGER}; font-weight: bold; font-size: 13px; "
           "padding: 2px 8px; border-radius: 3px;",
}
CAMERA_TILE_NO_SIGNAL_STYLE = (f"background: {CAMERA_TILE_BG}; color: {DANGER}; "
                               "font-weight: bold; font-size: 22px;")
# CAMERA-UI-03: one camera focused over the whole camera window.
CAMERA_DETAIL_STYLE = f"background: {CHROME};"
CAMERA_DETAIL_NAME_STYLE = f"color: {CHROME_TEXT}; font-weight: bold; font-size: 22px; padding: 4px 8px;"
CAMERA_DETAIL_BACK_STYLE = (f"color: {CHROME_TEXT}; background: #323f4b; border: 1px solid #52606d; "
                            "font-weight: bold; font-size: 16px; padding: 6px 16px; border-radius: 3px;")
CAMERA_DETAIL_NO_SIGNAL_STYLE = (f"background: {CAMERA_TILE_BG}; color: {DANGER}; "
                                 "font-weight: bold; font-size: 48px;")

TABLE_ROW_HEIGHT = 40


def style_table(view):
    """Common table setup for the styled tabs: taller rows, no row numbers,
    left-aligned headers, last column fills the remaining width."""
    view.setShowGrid(False)
    view.setAlternatingRowColors(True)
    view.verticalHeader().setVisible(False)
    view.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
    view.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
    header = view.horizontalHeader()
    header.setDefaultAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    header.setHighlightSections(False)
    header.setStretchLastSection(True)
    view.setSelectionBehavior(QAbstractItemView.SelectRows)


# Stav badge (PŘIPRAVEN / UVNITŘ / DOKONČENO) - stav_code 0/1/2.
_STAV_BADGE = {
    0: (NEUTRAL_TINT, "#3e4c59"),
    1: (DANGER, "#ffffff"),
    2: (SUCCESS_TINT, SUCCESS_DARK),
}


class StavBadgeDelegate(QStyledItemDelegate):
    """Draws the Stav cell as a colored pill. Reads the hidden stav_code
    column of the same row - never parses the Czech text."""

    def __init__(self, stav_code_column, parent=None):
        super().__init__(parent)
        self.stav_code_column = stav_code_column

    def paint(self, painter, option, index):
        # Row background / selection first, without the text.
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)

        code = index.model().index(index.row(), self.stav_code_column).data()
        colors = _STAV_BADGE.get(code)
        if not text or colors is None:
            return
        bg, fg = colors
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        font = QtGui.QFont(opt.font)
        font.setBold(True)
        font.setPointSizeF(max(font.pointSizeF() - 1.0, 8.0))
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        pad_x, height = 12, metrics.height() + 8
        width = metrics.horizontalAdvance(text) + 2 * pad_x
        rect = option.rect
        pill = QtCore.QRectF(rect.left() + 8, rect.center().y() - height / 2 + 1, width, height)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(bg))
        painter.drawRoundedRect(pill, height / 2, height / 2)
        painter.setPen(QtGui.QColor(fg))
        painter.drawText(pill, QtCore.Qt.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QtCore.QSize(size.width() + 40, size.height())
