"""UI-ABOUT-01: clickable version in the status bar + "O aplikaci" dialog.

Read-only: shows APP_NAME/APP_VERSION (version.py) and CHANGELOG.md from
the repository root. The changelog path is derived from this file, never
from the working directory (bin/polygon may be started from anywhere).
A missing or unreadable changelog shows CHANGELOG_UNAVAILABLE instead.

SPLASH-01: tab "Autoři" - ASCII portraits of the authors (files/authors/,
drawn like a terminal: light characters on a dark background, the content
as is) and CREDITS.md (authors, thanks; edited as text).
"""

import os

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
                             QTextBrowser, QVBoxLayout, QWidget)

from logger_config import logger
from version import APP_NAME, APP_VERSION

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CHANGELOG_PATH = os.path.normpath(os.path.join(_ROOT, "CHANGELOG.md"))
CHANGELOG_UNAVAILABLE = u"Přehled změn není dostupný."
CREDITS_PATH = os.path.normpath(os.path.join(_ROOT, "CREDITS.md"))
CREDITS_UNAVAILABLE = u"Seznam autorů není dostupný."
AUTHORS_DIR = os.path.normpath(os.path.join(_ROOT, "files", "authors"))
# (ASCII file in AUTHORS_DIR, name, role) - shown left to right
PORTRAITS = (
    ("vlastimil_wagner.txt", u"Vlastimil Wagner", u"původní autor"),
)
PORTRAIT_SIZE = QtCore.QSize(400, 320)  # one viewport for every portrait
PORTRAIT_CROP_TOP = 0.25    # share of the vertical overflow cut at the top (0.5 = center) - keeps the head
ASCII_FONT_PX = 10          # render size; the result is scaled to PORTRAIT_SIZE
ASCII_BG = "#111418"        # terminal look: light characters on dark
ASCII_FG = "#e4e7eb"


def version_text():
    return u"Verze %s" % APP_VERSION


def load_changelog(path=CHANGELOG_PATH):
    """CHANGELOG.md text, or None when it is missing, unreadable or empty."""
    return _load_text(path, "Changelog")


def load_credits(path=CREDITS_PATH):
    """CREDITS.md text, or None when it is missing, unreadable or empty."""
    return _load_text(path, "Credits")


def _load_text(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"{what} not available ({path}): {e}")
        return None
    return text if text.strip() else None


def load_ascii(path):
    """Lines of the ASCII portrait (formatting kept), or None if the file is
    missing, unreadable or empty (the tab then shows only the credits)."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"ASCII portrait not loaded ({path}): {e}")
        return None
    while lines and not lines[-1].strip():
        lines.pop()
    return lines or None


def _ascii_font():
    # Not QFontDatabase.systemFont(FixedFont): on some setups it resolves to
    # a proportional font (seen: Noto Sans). Glyphs go on a fixed grid anyway.
    font = QtGui.QFont("Monospace")
    font.setStyleHint(QtGui.QFont.TypeWriter)
    font.setPixelSize(ASCII_FONT_PX)
    return font


def _stretch_levels(image, low=0.01, high=0.99):
    """Grayscale copy with the low..high luminance percentiles stretched to
    ASCII_BG..ASCII_FG - downscaling the glyphs averages the contrast away."""
    gray = image.convertToFormat(QtGui.QImage.Format_Grayscale8)
    w, h, bpl = gray.width(), gray.height(), gray.bytesPerLine()
    data = bytes(gray.constBits().asarray(bpl * h))
    counts = [0] * 256
    for value in data:
        counts[value] += 1
    total, seen, lo, hi = len(data), 0, 0, 255
    for value, count in enumerate(counts):
        seen += count
        if seen <= total * low:
            lo = value + 1
        if seen < total * high:
            hi = value + 1
    hi = max(hi, lo + 1)
    dark, light = QtGui.QColor(ASCII_BG).lightness(), QtGui.QColor(ASCII_FG).lightness()
    table = bytes(min(light, max(dark, dark + (v - lo) * (light - dark) // (hi - lo))) for v in range(256))
    out = QtGui.QImage(data.translate(table), w, h, bpl, QtGui.QImage.Format_Grayscale8)
    return out.copy()  # own the buffer


def render_ascii(lines, size, crop_top=PORTRAIT_CROP_TOP):
    """Terminal-style image of the ASCII lines (light on dark, as drawn):
    every character on a fixed grid cell, so the layout holds even if the
    font is not truly monospace. Exactly size, like CSS object-fit: cover -
    scaled with the aspect ratio kept until it covers size, then cropped:
    horizontally centered, vertically crop_top of the overflow from the top."""
    font = _ascii_font()
    fm = QtGui.QFontMetrics(font)
    cell_w, cell_h = fm.horizontalAdvance("M"), fm.lineSpacing()
    cols = max(len(line) for line in lines)
    image = QtGui.QImage(cell_w * cols, cell_h * len(lines), QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor(ASCII_BG))
    painter = QtGui.QPainter(image)
    painter.setFont(font)
    painter.setPen(QtGui.QColor(ASCII_FG))
    for row, line in enumerate(lines):
        y = row * cell_h + fm.ascent()
        for col, char in enumerate(line):
            if char != " ":
                painter.drawText(col * cell_w, y, char)
    painter.end()
    scaled = image.scaled(size, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
    x = (scaled.width() - size.width()) // 2
    y = int((scaled.height() - size.height()) * crop_top)
    return QtGui.QPixmap.fromImage(_stretch_levels(scaled.copy(x, y, size.width(), size.height())))


class AboutDialog(QDialog):
    def __init__(self, parent=None, changelog_path=CHANGELOG_PATH, credits_path=CREDITS_PATH,
                 authors_dir=AUTHORS_DIR):
        QDialog.__init__(self, parent)
        self.setWindowTitle(u"O aplikaci %s" % APP_NAME)
        self.resize(920, 600)
        layout = QVBoxLayout(self)
        self.nameLabel = QLabel(APP_NAME, self)
        self.nameLabel.setStyleSheet("font-size: 16pt; font-weight: 700;")
        layout.addWidget(self.nameLabel)
        self.versionLabel = QLabel(version_text(), self)
        layout.addWidget(self.versionLabel)

        self.tabs = QTabWidget(self)
        self.changelogView = QTextBrowser(self)  # read-only, scrollable
        text = load_changelog(changelog_path)
        if text is None:
            self.changelogView.setPlainText(CHANGELOG_UNAVAILABLE)
        else:
            self.changelogView.setMarkdown(text)
        self.tabs.addTab(self.changelogView, u"Přehled změn")
        self.tabs.addTab(self._credits_tab(credits_path, authors_dir), u"Autoři")
        layout.addWidget(self.tabs)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Close, self)
        self.buttonBox.button(QDialogButtonBox.Close).setText(u"Zavřít")
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

    def _credits_tab(self, credits_path, authors_dir):
        tab = QWidget(self)
        row = QHBoxLayout(tab)  # portraits left, credits text right (full height)
        grid = QGridLayout()  # row 0 portraits, row 1 captions - same heights for all
        self.portraitLabels = []
        for filename, name, role in PORTRAITS:
            lines = load_ascii(os.path.join(authors_dir, filename))
            if not lines:
                continue
            col = len(self.portraitLabels)
            picture = QLabel(tab)
            picture.setFixedSize(PORTRAIT_SIZE)
            picture.setPixmap(render_ascii(lines, PORTRAIT_SIZE))
            caption = QLabel(u"<b>%s</b><br>%s" % (name, role), tab)
            caption.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
            grid.addWidget(picture, 0, col, QtCore.Qt.AlignHCenter)
            grid.addWidget(caption, 1, col)
            grid.setColumnStretch(col, 1)
            self.portraitLabels.append(picture)
        if self.portraitLabels:
            grid.setRowStretch(2, 1)  # keep them at the top
            row.addLayout(grid)
        self.creditsView = QTextBrowser(tab)
        self.creditsView.setOpenExternalLinks(True)
        text = load_credits(credits_path)
        if text is None:
            self.creditsView.setPlainText(CREDITS_UNAVAILABLE)
        else:
            self.creditsView.setMarkdown(text)
        row.addWidget(self.creditsView, 1)
        return tab


def make_version_button(parent, on_click):
    """Flat, link-styled status bar button "Verze X" (QSS: theme.py,
    #versionButton) calling on_click()."""
    button = QPushButton(version_text(), parent)
    button.setObjectName("versionButton")
    button.setFlat(True)
    button.setCursor(QtCore.Qt.PointingHandCursor)
    button.setFocusPolicy(QtCore.Qt.NoFocus)
    button.setToolTip(u"O aplikaci a přehled změn")
    # Direct, no lambda: a lambda around a bound method of the parent made
    # a parent -> button -> lambda -> parent reference cycle (TEST-SEGV-01).
    button.clicked.connect(on_click)
    return button
