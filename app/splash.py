"""SPLASH-01: startup splash screen in the style of a Linux boot.

A dark window with the program name and a console that lists the real
start-up steps as boot lines ("[  OK  ] ...", "[FAILED] ..."): config,
login, DB connect, main window init, then camera, DB, QUIDO and run mode -
read by main() from the same widgets the status bar shows. It holds a few
seconds on the result and closes; the main window is then on screen.

Pure startup/presentation layer: no DB, no QUIDO, no config of its own. Any
failure here is logged and the application starts without the splash.
A click on the splash skips the rest of it.
"""

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QSplashScreen

import theme
from logger_config import logger
from version import APP_NAME, APP_VERSION

STEP_MS = 300               # minimum pause after each boot line
HOLD_MS = 4000              # final pause on the result before closing

WIDTH = 760
HEADER_H = 92
CONSOLE_LINES = 12          # more lines scroll, the last ones stay visible
CONSOLE_FONT_PX = 14
CONSOLE_LINE_H = 22
CONSOLE_PAD = 14
CONSOLE_BG = "#111418"
CONSOLE_TEXT = "#cbd2d9"

# status -> (tag text, tag color); None = plain line without a tag.
BOOT_TAGS = {
    "ok": ("  OK  ", "#3fb950"),
    "failed": ("FAILED", "#ff5c5c"),
    "warn": (" WARN ", theme.WARNING),
    "sim": (" SIM  ", "#ff8a3d"),
    "dev": (" DEV  ", "#ff8a3d"),
    "info": None,
}


def _console_font():
    font = QtGui.QFont("Monospace")
    font.setStyleHint(QtGui.QFont.TypeWriter)
    font.setPixelSize(CONSOLE_FONT_PX)
    return font


def splash_pixmap():
    """Background: header with name/version over an empty console
    (the lines are painted by BootSplash.drawContents())."""
    height = HEADER_H + CONSOLE_LINES * CONSOLE_LINE_H + 2 * CONSOLE_PAD
    pixmap = QtGui.QPixmap(WIDTH, height)
    pixmap.fill(QtGui.QColor(CONSOLE_BG))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
    painter.fillRect(0, 0, WIDTH, HEADER_H, QtGui.QColor(theme.CHROME))
    painter.fillRect(0, HEADER_H - 3, WIDTH, 3, QtGui.QColor(theme.PRIMARY))
    font = QtGui.QFont(QApplication.font())
    font.setPointSizeF(26)
    font.setWeight(QtGui.QFont.Black)
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#ffffff"))
    painter.drawText(QtCore.QRect(CONSOLE_PAD + 4, 0, WIDTH, HEADER_H - 3),
                     QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, APP_NAME)
    font.setPointSizeF(13)
    font.setWeight(QtGui.QFont.DemiBold)
    painter.setFont(font)
    painter.setPen(QtGui.QColor(theme.CHROME_TEXT))
    painter.drawText(QtCore.QRect(0, 0, WIDTH - CONSOLE_PAD - 4, HEADER_H - 3),
                     QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight, f"Verze {APP_VERSION}")
    painter.end()
    return pixmap


class BootSplash(QSplashScreen):
    """The splash window. log() appends a boot line and pauses STEP_MS with a
    local event loop (the GUI and the main window's timers keep running);
    finish_boot() holds HOLD_MS and closes. A click skips all pauses."""

    def __init__(self, pixmap, step_ms=STEP_MS, hold_ms=HOLD_MS):
        super().__init__(pixmap, QtCore.Qt.WindowStaysOnTopHint)
        self.step_ms, self.hold_ms = step_ms, hold_ms
        self.lines = []  # [(text, status)]
        self.skipped = False
        self._loop = None

    def log(self, text, status="info"):
        self.lines.append((text, status))
        logger.info(f"Boot: [{status}] {text}")
        self.repaint()
        self.wait(self.step_ms)

    def finish_boot(self):
        self.wait(self.hold_ms)
        self.close()

    def wait(self, ms):
        if self.skipped or not self.isVisible():
            return
        self._loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(ms, self._loop.quit)
        self._loop.exec_()
        self._loop = None

    def drawContents(self, painter):
        font = _console_font()
        painter.setFont(font)
        fm = QtGui.QFontMetrics(font)
        tag_w = fm.horizontalAdvance("[FAILED] ")
        y = HEADER_H + CONSOLE_PAD
        x = CONSOLE_PAD + 4
        elide_w = self.pixmap().width() - x - tag_w - CONSOLE_PAD
        for text, status in self.lines[-CONSOLE_LINES:]:
            baseline = y + (CONSOLE_LINE_H + fm.ascent() - fm.descent()) // 2
            tag = BOOT_TAGS.get(status)
            if tag:
                label, color = tag
                painter.setPen(QtGui.QColor(CONSOLE_TEXT))
                painter.drawText(x, baseline, "[")
                painter.setPen(QtGui.QColor(color))
                painter.drawText(x + fm.horizontalAdvance("["), baseline, label)
                painter.setPen(QtGui.QColor(CONSOLE_TEXT))
                painter.drawText(x + fm.horizontalAdvance("[" + label), baseline, "]")
            painter.setPen(QtGui.QColor(CONSOLE_TEXT))
            painter.drawText(x + tag_w, baseline, fm.elidedText(text, QtCore.Qt.ElideRight, elide_w))
            y += CONSOLE_LINE_H

    def mousePressEvent(self, event):
        self.skipped = True
        if self._loop is not None:
            self._loop.quit()
        self.hide()


class _NoSplash:
    """Stand-in when the splash can't be built - start-up just goes on."""
    skipped = True

    def log(self, text, status="info"):
        logger.info(f"Boot: [{status}] {text}")

    def wait(self, ms):
        pass

    def finish_boot(self):
        pass

    def close(self):
        pass


def build_splash(step_ms=STEP_MS, hold_ms=HOLD_MS):
    return BootSplash(splash_pixmap(), step_ms, hold_ms)


def start_boot_splash(**kwargs):
    """Show the boot splash; never raises - a broken splash must not stop the
    application from starting (returns a no-op stand-in instead)."""
    try:
        splash = build_splash(**kwargs)
        splash.show()
        QApplication.processEvents()
        return splash
    except Exception as e:
        logger.warning(f"Startup splash skipped: {e}")
        return _NoSplash()
