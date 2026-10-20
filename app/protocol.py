"""PRINT-01b: rendering, print preview and PDF export for the protocol
documents - QTextDocument + QPrinter, no QtWebKit.

The HTML comes from protocol_data (build_summary_html / build_person_html);
this module only lays it out on A4 and paints it. Pages are painted by our
own loop (render()) so every page gets "Strana X / Y" - identically for a
PDF export, a real printer and the print preview, which all go through
render().

The GUI (main.py, karta Cvičení - PRINT-01c) loads the data, builds the
HTML and calls show_preview() / export_pdf() directly.
"""

import os

from PyQt5 import QtCore, QtGui, QtPrintSupport, sip

from logger_config import logger
from protocol_data import LOGO

# Absolute - the app runs from app/, tests from anywhere: never rely on cwd.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGO_PATH = os.path.join(_ROOT, LOGO)
MARGIN_MM = 15
FOOTER_MM = 8           # reserved below the content for "Strana X / Y"
PAGE_TEXT = "Strana %d / %d"

# PRINT-02 corrective: the summary table (souhrnná Zpráva) grew too wide
# for A4 portrait once it gained a "Spotřeba (l/min)" column - headers
# broke into unreadable single characters. Printed landscape instead.
# The individual Potvrzení (a handful of label/value rows, never a wide
# table) stays portrait. Preview, physical printing and PDF export all
# go through make_printer(), so all three always agree.
PERSON_ORIENTATION = QtPrintSupport.QPrinter.Portrait
SUMMARY_ORIENTATION = QtPrintSupport.QPrinter.Landscape


def site_logo_path(site) -> str:
    """SITE-CONFIG-01: the image registered as the logo resource - [SITE]
    logo (a local file; relative = to the repository root) or LOGO_PATH."""
    if not site.logo:
        return LOGO_PATH
    return os.path.join(_ROOT, os.path.expanduser(site.logo))


def make_printer(output_pdf=None, orientation=PERSON_ORIENTATION) -> QtPrintSupport.QPrinter:
    """A4, 15 mm margins, the given orientation (Portrait by default).
    With output_pdf the printer writes that PDF file; without it it is
    ready for a print dialog/preview."""
    printer = QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.HighResolution)
    printer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.A4))
    printer.setOrientation(orientation)
    printer.setPageMargins(MARGIN_MM, MARGIN_MM, MARGIN_MM, MARGIN_MM, QtPrintSupport.QPrinter.Millimeter)
    if output_pdf:
        printer.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
        printer.setOutputFileName(output_pdf)
    return printer


def _footer_height(printer) -> float:
    return FOOTER_MM * printer.resolution() / 25.4


def _add_logo(document, logo_path) -> None:
    """Register the logo under the name the HTML uses. A missing or
    unreadable logo never blocks the document: a blank placeholder is
    registered instead (so Qt doesn't go looking relative to the cwd)
    and a warning is logged."""
    image = QtGui.QImage(logo_path) if logo_path else QtGui.QImage()
    if image.isNull():
        logger.warning(f"Protocol logo not found or unreadable: {logo_path} - printing without it")
        image = QtGui.QImage(1, 1, QtGui.QImage.Format_ARGB32)
        image.fill(QtCore.Qt.transparent)
    document.addResource(QtGui.QTextDocument.ImageResource, QtCore.QUrl(LOGO), image)


def make_document(html, printer, logo_path=LOGO_PATH) -> QtGui.QTextDocument:
    """Lay the HTML out on the printer itself (its resolution and page
    size) - laid out on the screen instead, fonts come out too large and
    table columns wrap mid-date. The page height excludes the footer
    strip, so QTextDocument paginates the content (tables keep their
    <thead> on every page) and render() draws the page number below."""
    document = QtGui.QTextDocument()
    document.documentLayout().setPaintDevice(printer)
    page = printer.pageRect()  # device pixels, inside the margins
    document.setPageSize(QtCore.QSizeF(page.width(), page.height() - _footer_height(printer)))
    document.setDocumentMargin(0)
    _add_logo(document, logo_path)
    document.setHtml(html)
    return document


def render(document, printer) -> int:
    """Paint every page of the document onto the printer with
    "Strana X / Y" under the content. Used by export_pdf(), the print
    preview and real printing alike. Returns the number of pages."""
    painter = QtGui.QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Cannot start painting on the printer")
    try:
        width = document.pageSize().width()
        height = document.pageSize().height()
        pages = max(1, document.pageCount())
        footer = QtCore.QRectF(0, height, width, _footer_height(printer))
        font = QtGui.QFont("Arial", 9)
        for page in range(pages):
            if page:
                printer.newPage()
            painter.save()
            painter.translate(0, -page * height)
            document.drawContents(painter, QtCore.QRectF(0, page * height, width, height))
            painter.restore()
            painter.setFont(font)
            painter.drawText(footer, QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom, PAGE_TEXT % (page + 1, pages))
    finally:
        painter.end()
    return pages


def export_pdf(html, path, logo_path=LOGO_PATH, orientation=PERSON_ORIENTATION) -> int:
    """Write the HTML as an A4 PDF in the given orientation; returns the
    number of pages."""
    printer = make_printer(output_pdf=path, orientation=orientation)
    return render(make_document(html, printer, logo_path), printer)


def _paint_preview(html, printer, logo_path):
    """paintRequested slot. An exception escaping a Qt slot aborts the
    whole application (PyQt5), so a rendering error is logged instead."""
    try:
        render(make_document(html, printer, logo_path), printer)
    except Exception as e:
        logger.error(f"Protocol preview rendering failed: {e}")


def show_preview(html, parent=None, logo_path=LOGO_PATH, orientation=PERSON_ORIENTATION):
    """Modal print preview in the given orientation; printing from it goes
    through render() too. The document is laid out for whatever printer
    the dialog paints to.

    The printer must stay referenced for the dialog's whole life:
    QPrintPreviewDialog does not take ownership, and a temporary
    make_printer() was freed by Python right away - the dialog then used
    a dangling QPrinter and the app died with SIGSEGV on exec_()."""
    printer = make_printer(orientation=orientation)
    dialog = QtPrintSupport.QPrintPreviewDialog(printer, parent)
    dialog.paintRequested.connect(lambda target: _paint_preview(html, target, logo_path))
    try:
        return dialog.exec_()
    finally:
        sip.delete(dialog)  # destroy the dialog now, before `printer` goes out of scope

