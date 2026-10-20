"""LOGBOOK-02: the printable Kniha provozu - scope, report data and HTML.

One HTML document per print/PDF request, built from a LogbookReport by
build_logbook_html() - a pure function (no DB, no widgets). protocol.py
only renders it (QTextDocument + QPrinter): the print preview, a real
printer and the PDF export all paint this same HTML, landscape A4.

Which records belong to a scope is decided by the caller (MainWindow)
through OperationLogService; LogbookScope only knows its kind, the dates
and the texts/file name derived from them. "Dnes" always means event_at
(the real time of the event), never created_at.

The report is read-only - nothing here writes to operation_log.
"""

import html
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

import polygon_map
from operation_log_repository import CANCELLED, OPEN, RESOLVED

SCOPE_TODAY = "TODAY"
SCOPE_SHIFT = "SHIFT"
SCOPE_PERIOD = "PERIOD"
SCOPE_OPEN = "OPEN"
SCOPE_ALL = "ALL"
# GUI order: code -> Czech label
SCOPE_LABELS = {
    SCOPE_TODAY: "Dnešní záznamy",
    SCOPE_SHIFT: "Dnes + otevřené (předávka směny)",
    SCOPE_PERIOD: "Období OD–DO",
    SCOPE_OPEN: "Pouze otevřené",
    SCOPE_ALL: "Všechny záznamy",
}
DEFAULT_SCOPE = SCOPE_SHIFT

TITLE = "Kniha provozu polygonu"
EMPTY_TEXT = "Ve zvoleném rozsahu nejsou žádné záznamy."
# A word longer than this (a pasted path/URL, a run of characters) gets
# zero-width break opportunities - QTextDocument would otherwise widen its
# column and squeeze the others.
LONG_WORD = 30


# -- formatting (shared with the logbook tab) ---------------------------------

def date_text(value: date) -> str:
    """14. 10. 2026 (Czech date)."""
    return f"{value.day}. {value.month}. {value.year}"


def format_datetime(value) -> str:
    """14. 10. 2026 08:35 (Czech date, no seconds); empty for None."""
    if value is None:
        return ""
    return f"{date_text(value)} {value:%H:%M}"


def location_text(record) -> str:
    """Místo / zařízení: the sensor of a floor-sensor record."""
    if record.floor_name:
        return f"Čidlo {polygon_map.segment_text(record.floor_name)}"
    return record.location_text or "—"


# -- scope ---------------------------------------------------------------------

def _day_start(day: date) -> datetime:
    return datetime.combine(day, time())


@dataclass(frozen=True)
class LogbookScope:
    kind: str
    today: date                       # the day of the request - fixed once, at the click
    date_from: Optional[date] = None  # SCOPE_PERIOD only, both days included
    date_to: Optional[date] = None

    def is_valid(self) -> bool:
        if self.kind not in SCOPE_LABELS:
            return False
        if self.kind == SCOPE_PERIOD:
            return self.date_from is not None and self.date_to is not None and self.date_from <= self.date_to
        return True

    def event_bounds(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """[from, to) on event_at for SCOPE_TODAY / SCOPE_PERIOD (the last
        day is whole: to = the next day's 00:00); (None, None) otherwise."""
        if self.kind == SCOPE_TODAY:
            return _day_start(self.today), _day_start(self.today + timedelta(days=1))
        if self.kind == SCOPE_PERIOD:
            return _day_start(self.date_from), _day_start(self.date_to + timedelta(days=1))
        return None, None

    def period_text(self) -> str:
        if self.kind == SCOPE_TODAY:
            return f"Dnešní záznamy – {date_text(self.today)}"
        if self.kind == SCOPE_SHIFT:
            return (f"Dnes + otevřené (předávka směny) – záznamy z {date_text(self.today)} "
                    "a všechny otevřené záznamy")
        if self.kind == SCOPE_PERIOD:
            return f"Období {date_text(self.date_from)} – {date_text(self.date_to)}"
        if self.kind == SCOPE_OPEN:
            return "Pouze otevřené záznamy"
        return "Všechny záznamy"

    def filename(self) -> str:
        """ASCII PDF name, e.g. kniha_provozu_predavka_2026-10-18.pdf."""
        today = self.today.isoformat()
        if self.kind == SCOPE_TODAY:
            middle = today
        elif self.kind == SCOPE_SHIFT:
            middle = f"predavka_{today}"
        elif self.kind == SCOPE_PERIOD:
            middle = f"{self.date_from.isoformat()}_az_{self.date_to.isoformat()}"
        elif self.kind == SCOPE_OPEN:
            middle = f"otevrene_{today}"
        else:
            middle = f"vse_{today}"
        return f"kniha_provozu_{middle}.pdf"


@dataclass
class LogbookReport:
    scope: LogbookScope
    generated_at: datetime
    generated_by: str
    records: List = field(default_factory=list)   # OperationLogRecord, oldest event first

    @property
    def open_count(self) -> int:
        return sum(1 for r in self.records if r.status == OPEN)


# -- HTML ----------------------------------------------------------------------

_STYLE = (
    "<style>"
    "body { font-family: Arial, sans-serif; font-size: 10pt; color: #000; }"
    "h1 { font-size: 14pt; text-transform: uppercase; }"
    ".org { font-size: 10pt; font-weight: bold; }"
    ".label { font-size: 8pt; text-transform: uppercase; }"
    "table.list th { font-size: 9pt; text-align: left; border-bottom: 1px solid #000; }"
    "table.list td { font-size: 9pt; border-bottom: 1px solid #999; }"
    ".closed { font-style: italic; }"
    "</style>"
)

# Landscape A4; % widths so the short fixed values are never squeezed.
_COLUMNS = (("ID", 4), ("Datum/čas", 10), ("Typ", 11), ("Místo / zařízení", 13), ("Popis", 40),
            ("Stav", 12), ("Zapsal", 10))


def _breakable(word: str) -> str:
    if len(word) <= LONG_WORD:
        return html.escape(word, quote=True)
    chunks = [word[i:i + LONG_WORD] for i in range(0, len(word), LONG_WORD)]
    return "&#8203;".join(html.escape(chunk, quote=True) for chunk in chunks)


def text_html(text) -> str:
    """Free text: escaped, every word kept (never shortened), its line
    breaks kept, over-long words made breakable."""
    lines = str(text or "").splitlines() or [""]
    return "<br>".join(" ".join(_breakable(word) for word in line.split(" ")) for line in lines)


def _when(value) -> str:
    """Date over time - a narrow column never breaks inside either."""
    if value is None:
        return ""
    return f"{date_text(value)}<br>{value:%H:%M}"


def _status_cell(record) -> str:
    cell = f"<b>{html.escape(record.status_label)}</b>"
    if record.status == RESOLVED:
        cell += f"<br>{_when(record.resolved_at)}<br>{text_html(record.resolved_by)}"
    elif record.status == CANCELLED:
        cell += f"<br>{_when(record.cancelled_at)}<br>{text_html(record.cancelled_by)}"
    return cell


def _description_cell(record) -> str:
    cell = text_html(record.description)
    if record.status == RESOLVED and record.resolution_note:
        cell += f"<br><span class='closed'>Poznámka k řešení: {text_html(record.resolution_note)}</span>"
    elif record.status == CANCELLED:
        cell += f"<br><span class='closed'>Důvod storna: {text_html(record.cancel_reason)}</span>"
    return cell


def _row(record) -> str:
    cells = (str(record.log_id), _when(record.event_at), html.escape(record.category_label),
             text_html(location_text(record)), _description_cell(record), _status_cell(record),
             text_html(record.created_by))
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def site_header(site) -> str:
    """SITE-CONFIG-01: "<organization> – <site name>", the organization on
    one line; no lone dash when a part is empty."""
    return " – ".join(part for part in (" ".join(site.organization_lines), site.name) if part)


def build_logbook_html(report: LogbookReport, site) -> str:
    """The whole printable logbook: site header, the scope, who/when, the
    records table (its header repeats on every page) or EMPTY_TEXT."""
    info = (
        "<table width='100%' cellpadding='2'><tr>"
        f"<td width='55%'><span class='label'>Rozsah</span><br>{html.escape(report.scope.period_text())}</td>"
        f"<td width='15%'><span class='label'>Vytvořeno</span><br>{format_datetime(report.generated_at)}</td>"
        f"<td width='15%'><span class='label'>Vytvořil</span><br>{text_html(report.generated_by)}</td>"
        f"<td width='15%'><span class='label'>Počet záznamů</span><br>{len(report.records)} "
        f"(otevřených {report.open_count})</td>"
        "</tr></table>"
    )
    if report.records:
        body = (
            "<br><table class='list' width='100%' cellspacing='0' cellpadding='3'>"
            "<thead><tr>" + "".join(f"<th width='{width}%'>{name}</th>" for name, width in _COLUMNS)
            + "</tr></thead><tbody>" + "".join(_row(r) for r in report.records) + "</tbody></table>"
        )
    else:
        body = f"<p>{EMPTY_TEXT}</p>"
    return (
        "<html><head><meta charset='utf-8'>" + _STYLE + f"<title>{TITLE}</title></head><body>"
        f"<p class='org'>{html.escape(site_header(site))}</p><h1>{TITLE}</h1>" + info + body + "</body></html>"
    )
