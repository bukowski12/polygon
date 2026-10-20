"""PRINT-01a: data and HTML for the two printable documents.

- Souhrnná "Zpráva o absolvování výcvikového polygonu" - one document per
  training, every participant in one compact table (row per person).
- Individuální "Potvrzení o absolvování výcvikového polygonu" - one
  document for one selected participant.

Both are built from the same ProtocolData, loaded by the one SQL query in
load_protocol_data(). Qt value types are converted to plain Python here,
once, so the HTML builders are pure functions (no Qt, no DB).

Rendering (QTextDocument), printing and PDF export belong to PRINT-01b;
the builders therefore stick to simple HTML/CSS that QTextDocument
supports (tables, <thead>, no position/float).

PRINT-02 adds average air consumption for INDIVIDUAL passes, computed
from the same stored values (never persisted - always derived).
compute_consumption() is the single implementation of that formula -
model.py's memberModel and trainingDetailModel ("Spotřeba (l/min)"
columns) call it too, straight from the row's own volume/press_start/press_end/
entry_at/exit_at, rather than duplicating the arithmetic.
"""

import html
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple

from logger_config import logger

INDIVIDUAL = "INDIVIDUAL"
LEGACY = "LEGACY"

SUMMARY_TITLE = "Zpráva o absolvování výcvikového polygonu"
PERSON_TITLE = "Potvrzení o absolvování výcvikového polygonu"
# The logo's Qt document resource name (protocol.py registers the image
# under it) and the default logo file relative to the repository root.
LOGO = "files/znak-hzs.png"


def compute_consumption(volume: Decimal, press_start: int, press_end: Optional[int],
                        duration_s: Optional[int]) -> Optional[Tuple[Decimal, Decimal]]:
    """PRINT-02 formula - the single implementation, shared by Participant
    below (protocol printing) and model.py's memberModel/trainingDetailModel
    (Osoby roster and Cvičení history "Spotřeba (l/min)" columns):
    (spotřebovaný vzduch [l], průměrná spotřeba [l/min]), unrounded
    (rounding is presentation-only, see consumption_text()). None when any
    input makes the value meaningless: no bottle, no start pressure, end
    pressure not entered (None) or negative, no drop in pressure, or no
    complete/positive duration - a short real duration (a handful of
    seconds) is not such a case and produces a large, correct l/min
    figure, not None.

    PRESS-END-NULL: press_end None = not entered yet; 0 = a real, measured
    0 bar (bottle emptied - confirmed by the operator on save), so
    6.8 l, 200 -> 0 bar, 10 min is a valid 1360 l / 136 l/min."""
    if volume <= 0 or press_start <= 0:
        return None
    if press_end is None or press_end < 0 or press_start <= press_end:
        return None
    if duration_s is None or duration_s <= 0:
        return None
    air = (press_start - press_end) * volume
    return air, air * 60 / Decimal(duration_s)


@dataclass
class Participant:
    member_id: int
    name: str
    birthday: Optional[date]
    oec: Optional[str]
    unit: str
    entry_at: Optional[datetime]  # only from exercise_session
    exit_at: Optional[datetime]
    volume: Decimal
    press_start: int
    press_end: Optional[int]  # PRESS-END-NULL: None = not entered, 0 = a real 0 bar

    @property
    def duration_s(self) -> Optional[int]:
        if self.entry_at is None or self.exit_at is None:
            return None
        return max(0, int((self.exit_at - self.entry_at).total_seconds()))

    def _consumption(self) -> Optional[Tuple[Decimal, Decimal]]:
        return compute_consumption(self.volume, self.press_start, self.press_end, self.duration_s)

    @property
    def air_consumed_l(self) -> Optional[Decimal]:
        """PRINT-02: spotřebovaný vzduch = (tlak zač. - tlak kon.) x objem
        lahve, in liters, unrounded (rounding is presentation-only)."""
        consumption = self._consumption()
        return consumption[0] if consumption else None

    @property
    def average_consumption_l_min(self) -> Optional[Decimal]:
        """PRINT-02: průměrná spotřeba = spotřebovaný vzduch / doba
        průchodu, in l/min, unrounded."""
        consumption = self._consumption()
        return consumption[1] if consumption else None


@dataclass
class ProtocolData:
    training_id: int
    date: Optional[date]                 # training.time_start; 0000-00-00 -> None
    kind: str                            # INDIVIDUAL (has passes) / LEGACY (old squad model)
    legacy_cage: Optional[str] = None    # LEGACY only: shared squad times, "MM:SS"
    legacy_end: Optional[str] = None
    participants: List[Participant] = field(default_factory=list)

    @property
    def first_entry(self) -> Optional[datetime]:
        times = [p.entry_at for p in self.participants if p.entry_at is not None]
        return min(times) if times else None

    @property
    def last_exit(self) -> Optional[datetime]:
        times = [p.exit_at for p in self.participants if p.exit_at is not None]
        return max(times) if times else None

    def participant(self, member_id) -> Participant:
        for p in self.participants:
            if p.member_id == member_id:
                return p
        raise ValueError(f"member {member_id} is not a participant of training {self.training_id}")


# -- loading ------------------------------------------------------------------

# One row per member. At most one exercise_session per member is expected
# (SessionService reuses the latest one), but the schema doesn't enforce
# it: the join picks the latest session (MAX(idSession), same rule as
# SessionService.find_latest_session_for_member) so a stray duplicate can
# never duplicate the participant; session_count lets us log it.
_PROTOCOL_SQL = (
    "SELECT t.idTraining, t.time_start, t.time_cage, t.time_end, "
    "m.idMember, CONCAT(p.name,' ', p.surname) AS name, p.birthday, p.oec, p.unit, "
    "m.volume, m.press_start, m.press_end, s.entry_at, s.exit_at, "
    "(SELECT COUNT(*) FROM exercise_session x WHERE x.member_id = m.idMember) AS session_count "
    "FROM training t "
    "LEFT JOIN member m ON m.training_id = t.idTraining "
    "LEFT JOIN person p ON p.idPerson = m.person_id "
    "LEFT JOIN exercise_session s ON s.idSession = "
    "(SELECT MAX(x.idSession) FROM exercise_session x WHERE x.member_id = m.idMember) "
    "WHERE t.idTraining = %d "
    "ORDER BY s.entry_at IS NULL, s.entry_at ASC, m.idMember ASC"
)


def load_protocol_data(query, training_id) -> Optional[ProtocolData]:
    """ProtocolData for training_id, or None if that training doesn't
    exist. query is a QSqlQuery on the app's connection. Raises
    RuntimeError if the query itself fails."""
    if not query.exec_(_PROTOCOL_SQL % int(training_id)):
        raise RuntimeError(f"Protocol query failed: {query.lastError().text()}")
    data = None
    has_passes = False
    while query.next():
        value = query.value
        if data is None:
            training_date = _to_date(value(1))
            data = ProtocolData(training_id=value(0), date=training_date, kind=LEGACY,
                                legacy_cage=legacy_time_text(value(2), training_date),
                                legacy_end=legacy_time_text(value(3), training_date))
        if query.isNull(4):
            continue  # training without members: the LEFT JOIN row carries no member
                      # (QMYSQL returns 0, not None, for a NULL int - check isNull)
        if int(value(14) or 0) > 1:
            logger.warning(f"Member {value(4)} has {value(14)} exercise_session rows - "
                           f"protocol uses the latest one (training {training_id})")
        participant = Participant(
            member_id=value(4), name=value(5) or "", birthday=_to_date(value(6)),
            oec=value(7) or None, unit=value(8) or "",
            entry_at=_to_datetime(value(12)), exit_at=_to_datetime(value(13)),
            volume=to_decimal(value(9)), press_start=int(value(10) or 0),
            press_end=None if query.isNull(11) else int(value(11)))  # NULL = not entered, never 0
        has_passes = has_passes or participant.entry_at is not None
        data.participants.append(participant)
    if data is not None and has_passes:
        data.kind = INDIVIDUAL
        data.legacy_cage = data.legacy_end = None  # never mix legacy squad times into individual records
    return data


def _to_date(value) -> Optional[date]:
    """A DATE column comes from QMYSQL as QDate or as QDateTime, depending
    on the driver (home DEV: QDate, work PC: QDateTime - QDateTime has no
    toPyDate()). Invalid or unexpected values -> None."""
    if hasattr(value, "isValid"):
        if not value.isValid():
            return None
        if hasattr(value, "toPyDateTime"):  # QDateTime
            return value.toPyDateTime().date()
        if hasattr(value, "toPyDate"):      # QDate
            return value.toPyDate()
        return None
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def _to_datetime(value) -> Optional[datetime]:
    if hasattr(value, "isValid"):
        return value.toPyDateTime().replace(microsecond=0) if value.isValid() else None
    return value.replace(microsecond=0) if isinstance(value, datetime) else None


def to_decimal(value) -> Decimal:
    """QMYSQL/QSQLITE value of a DECIMAL(3,1) column (volume) as Decimal,
    e.g. keeps 6.8 as 6.8 rather than a binary float. Public: also used by
    model.py's memberModel for the "Spotřeba (l/min)" column."""
    if value is None or value == "":
        return Decimal("0.0")
    return Decimal(str(value)).quantize(Decimal("0.1"))


# DATA-04: which format the old app wrote into training.time_cage/time_end.
# "MM:SS" strings are stored by MariaDB as HH:MM:00, "H:M:S" as-is.
MMSS_ERA_UNTIL = date(2015, 12, 3)     # last repo code writing "%1:%2" (MM:SS); data: id 1
HMS_ERA = (date(2017, 10, 18), date(2023, 11, 26))   # every value H:M:S-shaped (ids 154-418)
MMSS_ERA_FROM = date(2024, 7, 18)      # first MM:SS-shaped value again (id 472); commit 1734004
AMBIGUOUS_TEXT = "nejednoznačný údaj (uloženo %s)"


def legacy_time_text(value, training_date: Optional[date] = None) -> Optional[str]:
    """Old shared squad time (training.time_cage / time_end) as "MM:SS",
    or None when unset ("00:00:00"). See DATA-04.

    Most stored values identify their format by shape alone: hours > 0
    (seconds 0) can only come from an "MM:SS" string stored as HH:MM:00,
    seconds > 0 (hours 0) only from "H:M:S". The shape 00:MM:00 is
    ambiguous ("MM minutes" in H:M:S, or "MM seconds" from an "00:MM"
    string) and is resolved by the training date's era. Outside the known
    eras (or without a date) it is not guessed: the stored value is shown
    marked as ambiguous. Hours and seconds both set never occur and are
    shown as stored."""
    if value is None:
        return None
    if hasattr(value, "toString"):  # QTime
        value = value.toString("HH:mm:ss")
    parts = str(value).strip().split(":")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    h, m, s = (int(p) for p in parts)
    stored = "%02d:%02d:%02d" % (h, m, s)
    if h == m == s == 0:
        return None
    if h > 0 and s > 0:
        return stored
    if h > 0:
        return "%02d:%02d" % (h, m)       # "MM:SS" stored as HH:MM:00
    if s > 0:
        return "%02d:%02d" % (m, s)       # "H:M:S"
    # 00:MM:00 - ambiguous shape, the era decides
    if training_date is not None:
        if training_date <= MMSS_ERA_UNTIL or training_date >= MMSS_ERA_FROM:
            return "00:%02d" % m          # written "00:MM" -> MM seconds
        if HMS_ERA[0] <= training_date <= HMS_ERA[1]:
            return "%02d:00" % m          # written "0:MM:0" -> MM minutes
    return AMBIGUOUS_TEXT % stored


# -- formatting ---------------------------------------------------------------

def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def date_text(value: Optional[date]) -> str:
    return value.strftime("%d.%m.%Y") if value else "neuvedeno"


def clock_text(value: Optional[datetime]) -> str:
    return value.strftime("%H:%M:%S") if value else "—"


def duration_text(seconds: Optional[int]) -> str:
    if seconds is None:
        return "—"
    return "%02d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)


def volume_text(value: Decimal) -> str:
    return "%.1f" % value


# PRESS-END-NULL: a not-yet-entered end pressure (member.press_end IS NULL),
# in the protocol documents and the app's tables alike.
NOT_ENTERED_TEXT = "—"


def pressure_text(value: Optional[int]) -> str:
    """Pressure in bar; None (not entered) -> '—', a real 0 -> '0'."""
    return NOT_ENTERED_TEXT if value is None else str(value)


def consumption_text(value: Optional[Decimal]) -> str:
    """PRINT-02 presentation: whole units, ROUND_HALF_UP (never the
    implicit banker's rounding), or '—' when the value wasn't computed."""
    if value is None:
        return "—"
    return str(int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


# -- HTML ---------------------------------------------------------------------

_STYLE = (
    "<style>"
    "body { font-family: Arial, sans-serif; font-size: 11pt; color: #000; }"
    "h1 { font-size: 14pt; text-transform: uppercase; }"
    ".org { font-size: 14pt; font-weight: bold; text-transform: uppercase; }"
    ".label { font-size: 8pt; text-transform: uppercase; }"
    "table.list th { font-size: 9pt; text-align: left; border-bottom: 1px solid #000; }"
    "table.list td { font-size: 10pt; }"
    ".legacy { font-size: 10pt; }"
    "</style>"
)


def _header(site) -> str:
    """SITE-CONFIG-01: organization (one line each, escaped) and the
    address - an empty one leaves no empty paragraph."""
    lines = site.organization_lines
    organization = f"<p class='org'>{'<br>'.join(esc(line) for line in lines)}</p>" if lines else ""
    address = f"<p>{esc(site.address)}</p>" if site.address else ""
    return (
        "<table width='100%'><tr>"
        f"<td width='110'><img src='{LOGO}' width='72' height='100'></td>"
        f"<td>{organization}{address}</td>"
        "</tr></table>"
    )


def _footer(site, operator, today: date) -> str:
    place = f"{esc(site.place)}, " if site.place else ""
    return (
        "<br><table width='100%'><tr>"
        f"<td width='50%'>{place}{date_text(today)}</td>"
        f"<td width='50%' align='center'>....................................<br>"
        f"<b>{esc(operator)}</b><br><span class='label'>Obsluha výcvikového polygonu</span></td>"
        "</tr></table>"
    )


def _legacy_block(data: ProtocolData) -> str:
    """Old shared squad times - always labelled as shared, never as a
    participant's own entry/exit."""
    rows = [f"<p class='legacy'><b>Starší záznam (model družstva)</b> – individuální vstupy a výstupy "
            f"nebyly v té době evidovány.</p>"]
    if data.legacy_cage:
        rows.append(f"<p class='legacy'>Společný čas družstva – vstup do klece: {esc(data.legacy_cage)}</p>")
    if data.legacy_end:
        rows.append(f"<p class='legacy'>Společný čas družstva – konec výcviku: {esc(data.legacy_end)}</p>")
    return "".join(rows)


def _document(title: str, body: str, operator, today: date, site) -> str:
    return (
        "<html><head><meta charset='utf-8'>" + _STYLE + f"<title>{esc(title)}</title></head><body>"
        + _header(site) + f"<h1>{esc(title)}</h1>" + body + _footer(site, operator, today) + "</body></html>"
    )


# Summary table layout (PRINT-01b/PRINT-02, presentation only): % widths
# so that QTextDocument never squeezes dates/times, and no wrapping inside
# the short fixed-format values. Name and unit may wrap. Rebalanced from
# PRINT-01b's 11-column set to make room for "Spotřeba (l/min)" (checked
# against the real PDF render - tests/integration/test_protocol_pdf.py).
_COLUMN_WIDTH = {"#": 3, "Jméno": 15, "Datum nar.": 8, "OEČ": 5, "Jednotka": 12, "Vstup": 8, "Výstup": 8,
                 "Doba": 7, "Objem (l)": 7, "Tlak zač. (bar)": 7, "Tlak kon. (bar)": 8, "Spotřeba (l/min)": 12}
_WRAPPING_COLUMNS = {"Jméno", "Jednotka"}


def _cell(column, content) -> str:
    if column in _WRAPPING_COLUMNS:
        return f"<td>{content}</td>"
    return f"<td style='white-space: nowrap'>{content}</td>"


# "Spotřeba (l/min)" is long enough that QTextDocument's column-width
# auto-sizing sometimes leaves it less room than its own header text,
# and it has no hyphenation: a plain word-wrap there breaks the word
# itself into unreadable fragments instead of wrapping at the space.
# Forcing it onto one line (like the nowrap data cells) avoids that;
# other short/multi-word headers keep wrapping as before.
# The inline style must repeat the stylesheet's border-bottom: QTextDocument
# drops the "table.list th" border for a cell with its own style attribute.
_NOWRAP_HEADERS = {"Spotřeba (l/min)"}


def _header_cell(column) -> str:
    style = " style='white-space: nowrap; border-bottom: 1px solid #000'" if column in _NOWRAP_HEADERS else ""
    return f"<th width='{_COLUMN_WIDTH[column]}%'{style}>{column}</th>"


def build_summary_html(data: ProtocolData, operator, today: date, site) -> str:
    """Souhrnná zpráva: whole training, one table row per participant."""
    individual = data.kind == INDIVIDUAL
    info = (
        "<table width='100%'><tr>"
        f"<td><span class='label'>Datum výcviku</span><br>{date_text(data.date)}</td>"
        f"<td><span class='label'>Počet osob</span><br>{len(data.participants)}</td>"
    )
    if individual:
        info += (f"<td><span class='label'>První vstup</span><br>{clock_text(data.first_entry)}</td>"
                 f"<td><span class='label'>Poslední výstup</span><br>{clock_text(data.last_exit)}</td>")
    info += (f"<td><span class='label'>Záznam</span><br>"
             f"{'INDIVIDUÁLNÍ' if individual else 'STARŠÍ ZÁZNAM'}</td></tr></table>")
    body = info if individual else info + _legacy_block(data)

    if not data.participants:
        return _document(SUMMARY_TITLE, body + "<p>Bez účastníků.</p>", operator, today, site)

    columns = ["#", "Jméno", "Datum nar.", "OEČ", "Jednotka"]
    if individual:
        columns += ["Vstup", "Výstup", "Doba"]  # LEGACY: omitted entirely, not left blank
    columns += ["Objem (l)", "Tlak zač. (bar)", "Tlak kon. (bar)"]
    if individual:
        columns += ["Spotřeba (l/min)"]  # PRINT-02: not a meaningful figure for LEGACY's shared squad times
    rows = []
    for number, p in enumerate(data.participants, start=1):
        cells = [str(number), esc(p.name), date_text(p.birthday), esc(p.oec), esc(p.unit)]
        if individual:
            cells += [clock_text(p.entry_at), clock_text(p.exit_at), duration_text(p.duration_s)]
        cells += [volume_text(p.volume), str(p.press_start), pressure_text(p.press_end)]
        if individual:
            cells += [consumption_text(p.average_consumption_l_min)]
        rows.append("<tr>" + "".join(_cell(column, c) for column, c in zip(columns, cells)) + "</tr>")
    table = (
        "<br><table class='list' width='100%' cellspacing='0' cellpadding='3'>"
        "<thead><tr>" + "".join(_header_cell(c) for c in columns) + "</tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )
    return _document(SUMMARY_TITLE, body + table, operator, today, site)


def build_person_html(data: ProtocolData, member_id, operator, today: date, site) -> str:
    """Individuální potvrzení: one participant only. Raises ValueError if
    member_id is not a participant of this training."""
    p = data.participant(member_id)

    def row(label, value):
        return f"<tr><td width='40%'><span class='label'>{label}</span></td><td>{value}</td></tr>"

    person = ("<table width='100%' cellpadding='3'>"
              + row("Jméno", f"<b>{esc(p.name)}</b>")
              + row("Datum narození", date_text(p.birthday))
              + row("OEČ", esc(p.oec) or "—")
              + row("Jednotka", esc(p.unit))
              + row("Datum výcviku", date_text(data.date))
              + "</table>")
    if data.kind == INDIVIDUAL:
        if p.entry_at is None:
            passage = "<p>Průchod polygonem nebyl zaznamenán.</p>"
        else:
            passage = ("<table width='100%' cellpadding='3'>"
                       + row("Vstup do polygonu", clock_text(p.entry_at))
                       + row("Výstup z polygonu", clock_text(p.exit_at))
                       + row("Doba průchodu", duration_text(p.duration_s))
                       + "</table>")
    else:
        passage = _legacy_block(data)
    apparatus_rows = (row("Objem lahve (l)", volume_text(p.volume))
                      + row("Tlak na začátku (bar)", str(p.press_start))
                      + row("Tlak na konci (bar)", pressure_text(p.press_end)))
    if data.kind == INDIVIDUAL:
        # PRINT-02: never derived from LEGACY's historical shared time - it
        # would look like an individually measured consumption, which it isn't.
        apparatus_rows += (row("Spotřebováno (l)", consumption_text(p.air_consumed_l))
                           + row("Průměrná spotřeba (l/min)", consumption_text(p.average_consumption_l_min)))
    apparatus = "<table width='100%' cellpadding='3'>" + apparatus_rows + "</table>"
    body = (person + "<h2>Průchod polygonem</h2>" + passage
            + "<h2>Dýchací přístroj</h2>" + apparatus)
    return _document(PERSON_TITLE, body, operator, today, site)


# -- PDF file names (PRINT-01c) -----------------------------------------------

def _filename_part(text) -> str:
    """ASCII-only file name fragment: diacritics dropped, whitespace ->
    "_", anything but letters/digits/"-"/"_" removed."""
    ascii_text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"\s+", "_", ascii_text.strip())
    ascii_text = re.sub(r"[^A-Za-z0-9_-]", "", ascii_text)
    return re.sub(r"_+", "_", ascii_text).strip("_")


def pdf_filename(training_id, training_date: Optional[date], person_name=None) -> str:
    """Suggested file name for Uložit PDF, e.g.
    zprava_polygon_2026-09-24_cviceni-511.pdf (summary, person_name None) or
    potvrzeni_polygon_2026-09-24_Jan_Novak_cviceni-511.pdf. The training
    id is always kept, a missing date becomes "bez-data"."""
    day = training_date.isoformat() if training_date else "bez-data"
    parts = ["potvrzeni" if person_name is not None else "zprava", "polygon", day]
    name = _filename_part(person_name) if person_name is not None else ""
    if name:
        parts.append(name)
    parts.append(f"cviceni-{int(training_id)}")
    return "_".join(parts) + ".pdf"
