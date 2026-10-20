"""REPORT-01: e-mail report of the Kniha provozu on a correct exit.

Sent only when the operator closed the application and confirmed it
(closeEvent -> Ano) - main() calls ExitReport.run() after the main loop.
Never on Ctrl+C, a closeEvent error, a start-up error, SIGTERM or a crash.

A report goes out only when the logbook changed since the last report that
was SENT successfully: a new record, OPEN -> RESOLVED or OPEN -> CANCELLED.
Records that merely stay OPEN never trigger one. No timestamps are used -
records are never deleted and change at most once (OPEN -> closed, see
operation_log_repository.py), so the checkpoint {max_log_id, open_log_ids}
fully describes what was reported:

    new        idLog > max_log_id
    resolved   idLog in open_log_ids, now RESOLVED
    cancelled  idLog in open_log_ids, now CANCELLED

The PDF holds changed UNION current OPEN, each record once, oldest event
first. The checkpoint lives outside the DB, in
$XDG_STATE_HOME/polygon/report_email.json (~/.local/state/... without it),
one entry per source <mode>|<host>|<port>|<database> taken from the open
DB connection - polygon_dev / polygon_test and DEV runs never touch the
production entry. It moves only after a successful SMTP send; a failed DB
read, PDF or send leaves it as it was and the next correct exit tries
again (the PDF is made from the DB again - no outbox). The only other write
is the first-run baseline (baseline_pending = true).

Nothing here may stop the application from ending or change its exit
code: run() never raises. The SMTP password is never logged.
"""

import json
import os
import smtplib
import ssl
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Callable, Optional, Tuple

from config_manager import SiteConfig, site_from_config
from logger_config import logger
from logbook_print import LogbookReport, build_logbook_html, format_datetime, location_text
from operation_log_repository import CANCELLED, OPEN, RESOLVED

SECTION = "REPORT_EMAIL"
STATE_FILE = os.path.join("polygon", "report_email.json")
STATE_VERSION = 1
SECURITY_PORTS = {"starttls": 587, "ssl": 465, "none": 25}
DEFAULT_TIMEOUT = 10.0
DEFAULT_MYSQL_PORT = 3306
MODE_DEV = "dev"
MODE_PROD = "prod"

SENT = "sent"
SKIPPED = "skipped"
FAILED = "failed"
ALREADY_RUN = "already_run"


class CheckpointError(Exception):
    """The checkpoint file exists but can't be read (not: is corrupt)."""


class PdfError(Exception):
    """The report PDF could not be created."""


# -- configuration --------------------------------------------------------------

@dataclass(frozen=True)
class ReportSettings:
    smtp_host: str
    smtp_port: int
    security: str
    username: str
    password: str = field(repr=False)   # never in a repr / log line
    sender: str = ""
    recipients: Tuple[str, ...] = ()
    timeout: float = DEFAULT_TIMEOUT
    subject_prefix: str = SiteConfig.name
    allow_dev: bool = False
    site: SiteConfig = SiteConfig()   # SITE-CONFIG-01: body heading, PDF header


def _text(value) -> str:
    return "" if value is None or isinstance(value, bool) else str(value).strip()


def load_settings(config) -> Optional[ReportSettings]:
    """[REPORT_EMAIL] as ReportSettings; None when the section is missing,
    enabled is not true, or it is incomplete/invalid (a warning, never an
    error - the application runs exactly as without the report)."""
    section = config.get(SECTION)
    if not section:
        return None
    if section.get("enabled", False) is not True:
        logger.info("REPORT-01: e-mail report disabled ([REPORT_EMAIL] enabled is not true)")
        return None
    security = _text(section.get("security")).lower() or "starttls"
    if security not in SECURITY_PORTS:
        logger.warning(f"REPORT-01: e-mail report off - [REPORT_EMAIL] security={security!r} "
                       f"is not one of {', '.join(SECURITY_PORTS)}")
        return None
    host, sender = _text(section.get("smtp_host")), _text(section.get("from"))
    recipients = tuple(address.strip() for address in _text(section.get("to")).split(",") if address.strip())
    missing = [name for name, value in (("smtp_host", host), ("from", sender), ("to", recipients)) if not value]
    if missing:
        logger.warning(f"REPORT-01: e-mail report off - [REPORT_EMAIL] missing {', '.join(missing)}")
        return None
    try:
        port = int(_text(section.get("smtp_port")) or SECURITY_PORTS[security])
        timeout = float(_text(section.get("timeout")) or DEFAULT_TIMEOUT)
        if not 0 < port < 65536 or timeout <= 0:
            raise ValueError
    except ValueError:
        logger.warning("REPORT-01: e-mail report off - [REPORT_EMAIL] smtp_port/timeout invalid")
        return None
    site = site_from_config(config)
    return ReportSettings(host, port, security, _text(section.get("username")),
                          "" if section.get("password") is None else str(section.get("password")),
                          sender, recipients, timeout,
                          _text(section.get("subject_prefix")) or site.name,  # empty = [SITE] name
                          section.get("allow_dev", False) is True, site)


def is_dev_mode(config) -> bool:
    """REPORT-01's DEV: [DEV] mock_quido or skip_login true (--dev and
    mock_camera don't count)."""
    dev = config.get("DEV") or {}
    return dev.get("mock_quido", False) is True or dev.get("skip_login", False) is True


def source_key(dev_mode, db) -> str:
    """<mode>|<host>|<port>|<database> of the open QSqlDatabase `db`."""
    port = db.port() if db.port() > 0 else DEFAULT_MYSQL_PORT
    mode = MODE_DEV if dev_mode else MODE_PROD
    return f"{mode}|{db.hostName().strip().lower()}|{port}|{db.databaseName().strip()}"


def state_path(environ=None) -> str:
    """$XDG_STATE_HOME/polygon/report_email.json (an absolute
    XDG_STATE_HOME only, as the spec says), else ~/.local/state/..."""
    environ = os.environ if environ is None else environ
    base = environ.get("XDG_STATE_HOME", "")
    if not os.path.isabs(base):
        base = os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, STATE_FILE)


# -- checkpoint -----------------------------------------------------------------

def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat(timespec="seconds") if value is not None else None


def _from_iso(value) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value is not None else None


@dataclass(frozen=True)
class Checkpoint:
    max_log_id: int
    open_log_ids: Tuple[int, ...]
    baseline_pending: bool
    last_success_at: Optional[datetime]
    initialized_at: datetime
    app_version: str

    def to_dict(self) -> dict:
        return {"max_log_id": self.max_log_id, "open_log_ids": list(self.open_log_ids),
                "baseline_pending": self.baseline_pending, "last_success_at": _iso(self.last_success_at),
                "initialized_at": _iso(self.initialized_at), "app_version": self.app_version}

    @classmethod
    def from_dict(cls, data) -> "Checkpoint":
        """ValueError/TypeError/KeyError for anything malformed."""
        max_log_id = data["max_log_id"]
        open_ids = data["open_log_ids"]
        if (not isinstance(max_log_id, int) or isinstance(max_log_id, bool) or max_log_id < 0
                or not isinstance(open_ids, list)
                or not all(isinstance(i, int) and not isinstance(i, bool) for i in open_ids)
                or not isinstance(data["baseline_pending"], bool)):
            raise ValueError("malformed checkpoint")
        return cls(max_log_id, tuple(sorted(set(open_ids))), data["baseline_pending"],
                   _from_iso(data["last_success_at"]), _from_iso(data["initialized_at"]),
                   str(data.get("app_version", "")))


class CheckpointStore:
    """report_email.json: {"version": 1, "sources": {key: checkpoint}}.
    put() rewrites the file atomically and keeps every other source."""

    def __init__(self, path, now=datetime.now):
        self.path = path
        self.now = now

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as file:
                text = file.read()
        except FileNotFoundError:
            return {}
        except OSError as e:
            raise CheckpointError(f"{self.path}: {e}") from e
        try:
            data = json.loads(text)
            if not isinstance(data, dict) or not isinstance(data.get("sources"), dict):
                raise ValueError("no sources")
            return data["sources"]
        except ValueError:
            corrupt = f"{self.path}.corrupt-{self.now():%Y%m%d-%H%M%S}"
            os.replace(self.path, corrupt)
            logger.warning(f"REPORT-01: checkpoint {self.path} is corrupt - moved to {corrupt}, "
                           "continuing as the first run")
            return {}

    def get(self, key) -> Optional[Checkpoint]:
        entry = self._load().get(key)
        if entry is None:
            return None
        try:
            return Checkpoint.from_dict(entry)
        except (ValueError, TypeError, KeyError):
            logger.warning(f"REPORT-01: checkpoint of {key} is malformed - continuing as the first run")
            return None

    def put(self, key, checkpoint: Checkpoint) -> None:
        sources = self._load()
        sources[key] = checkpoint.to_dict()
        _write_atomic(self.path, {"version": STATE_VERSION, "sources": sources})


def _write_atomic(path, data) -> None:
    """Temp file in the same directory -> json.dump, flush, fsync ->
    chmod 0600 -> os.replace: the file is always either the old or the new
    content, never half written."""
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".report_email.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


# -- what to report -------------------------------------------------------------

@dataclass
class ReportPlan:
    checkpoint: Checkpoint              # the one the plan was made against
    records: list                       # changed UNION open, oldest event first
    new: list
    resolved: list
    cancelled: list
    open: list
    max_log_id: int                     # of the snapshot - the next checkpoint
    open_log_ids: Tuple[int, ...]

    @property
    def changed(self) -> bool:
        return bool(self.new or self.resolved or self.cancelled)

    @property
    def send(self) -> bool:
        """A change - or the first report, while anything is OPEN."""
        return self.changed or (self.checkpoint.baseline_pending and bool(self.open))

    def next_checkpoint(self, last_success_at, app_version) -> Checkpoint:
        return Checkpoint(self.max_log_id, self.open_log_ids, False, last_success_at,
                          self.checkpoint.initialized_at, app_version)


def plan_report(checkpoint: Checkpoint, records) -> ReportPlan:
    """records: one list_changed_or_open(checkpoint.max_log_id,
    checkpoint.open_log_ids) snapshot."""
    reported_open = set(checkpoint.open_log_ids)
    unique = {}
    for record in records:
        unique.setdefault(record.log_id, record)
    snapshot = sorted(unique.values(), key=lambda r: (r.event_at, r.log_id))
    new = [r for r in snapshot if r.log_id > checkpoint.max_log_id]
    resolved = [r for r in snapshot if r.log_id in reported_open and r.status == RESOLVED]
    cancelled = [r for r in snapshot if r.log_id in reported_open and r.status == CANCELLED]
    current_open = [r for r in snapshot if r.status == OPEN]
    changed_ids = {r.log_id for r in new + resolved + cancelled}
    missing = reported_open - set(unique)
    if missing:  # only a manual DB intervention can remove a record
        logger.warning(f"REPORT-01: records {sorted(missing)} of the last report no longer exist")
    return ReportPlan(
        checkpoint, [r for r in snapshot if r.log_id in changed_ids or r.status == OPEN],
        new, resolved, cancelled, current_open,
        max([checkpoint.max_log_id] + list(unique)), tuple(sorted(r.log_id for r in current_open)))


# -- e-mail ---------------------------------------------------------------------

@dataclass(frozen=True)
class ExitInfo:
    started_at: datetime
    finished_at: datetime
    user: str
    hostname: str
    app_version: str
    db_text: str
    local_db: bool
    dev_mode: bool
    inside: Optional[bool]   # trainees UVNITŘ at the exit: True / False / None = unknown


def pdf_filename(finished_at: datetime) -> str:
    return f"kniha_provozu_report_{finished_at:%Y-%m-%d_%H%M}.pdf"


def _since(plan: ReportPlan) -> datetime:
    return plan.checkpoint.last_success_at or plan.checkpoint.initialized_at


class _ReportScope:
    """What build_logbook_html() needs of a scope - REPORT-01's own range,
    LOGBOOK-02's scopes stay as they are."""

    def __init__(self, plan: ReportPlan):
        self._plan = plan

    def period_text(self) -> str:
        text = f"Změny od {format_datetime(_since(self._plan))} + všechny otevřené záznamy"
        if self._plan.checkpoint.last_success_at is None:
            text += " (první report)"
        return text


def build_html(plan: ReportPlan, info: ExitInfo, site) -> str:
    return build_logbook_html(LogbookReport(_ReportScope(plan), info.finished_at, info.user, plan.records), site)


def build_subject(plan: ReportPlan, info: ExitInfo, prefix) -> str:
    tags = [f"[{prefix}]"] + (["[DEV]"] if info.dev_mode else []) + (["[LOKÁLNÍ DB]"] if info.local_db else [])
    counts = f"nové {len(plan.new)} / vyřešené {len(plan.resolved)}"
    if plan.cancelled:
        counts += f" / stornované {len(plan.cancelled)}"
    return f"{' '.join(tags)} Provozní report – {counts} / otevřené {len(plan.open)}"


_INSIDE_TEXT = {True: "ANO", False: "NE", None: "NEZNÁMO"}


def build_body(plan: ReportPlan, info: ExitInfo, attachment, site) -> str:
    """Plain text - counts and the OPEN records' ID/date/type/place, never a
    description (an Úraz record may hold health details): those are in the PDF."""
    first = plan.checkpoint.last_success_at is None
    lines = [
        f"{site.name} – provozní report", "",
        f"Ukončení aplikace:   {format_datetime(info.finished_at)}",
        f"Spuštění aplikace:   {format_datetime(info.started_at)}",
        f"Uživatel:            {info.user}",
        f"Verze:               Polygon {info.app_version}",
        f"Počítač:             {info.hostname}",
        f"Databáze:            {info.db_text}",
    ]
    if info.dev_mode:
        lines.append("Režim:               DEV")
    lines += [
        "",
        f"Kniha provozu – změny od {format_datetime(_since(plan))}" + (" (první report)" if first else "") + ":",
        f"  nové:                         {len(plan.new)}",
        f"  vyřešené:                     {len(plan.resolved)}",
        f"  stornované:                   {len(plan.cancelled)}",
        f"  aktuálně otevřené:            {len(plan.open)}",
        f"  cvičenci UVNITŘ při ukončení: {_INSIDE_TEXT[info.inside]}",
        "", "Otevřené záznamy:",
    ]
    lines += [f"  ID {r.log_id} | {format_datetime(r.event_at)} | {r.category_label} | {location_text(r)}"
              for r in plan.open] or ["  žádné"]
    lines += ["", f"Podrobnosti (popisy, řešení, storna) jsou v příloze {attachment}.", "",
              "Automaticky odesláno programem Polygon při ukončení aplikace."]
    return "\n".join(lines) + "\n"


def build_message(settings: ReportSettings, subject, body, pdf_name, pdf_bytes) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.sender
    message["To"] = ", ".join(settings.recipients)
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=settings.sender.rpartition("@")[2] or None)
    message.set_content(body)
    message.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_name)
    return message


def connect_smtp(settings: ReportSettings):
    """smtplib connection with the settings' timeout (ssl = SMTP_SSL)."""
    if settings.security == "ssl":
        return smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.timeout,
                                context=ssl.create_default_context())
    return smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.timeout)


def send_message(settings: ReportSettings, message, connect=connect_smtp) -> None:
    """One attempt, no retry; raises on any failure."""
    with connect(settings) as smtp:
        if settings.security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if settings.username:
            smtp.login(settings.username, settings.password)
        smtp.send_message(message)


def write_pdf(html, path) -> None:
    """The logbook renderer of LOGBOOK-02, landscape A4 - no dialog."""
    import protocol  # Qt printing - only when a report is really made
    protocol.export_pdf(html, path, orientation=protocol.SUMMARY_ORIENTATION)


def _failure(e) -> str:
    """Exception type (+ SMTP code) - never its text, which might quote
    the server's reply to the login."""
    code = getattr(e, "smtp_code", None)
    return f"{type(e).__name__}" + (f" {code}" if code is not None else "")


# -- orchestration ----------------------------------------------------------------

class ExitReport:
    def __init__(self, settings: ReportSettings, key, operation_log, store: CheckpointStore, app_version,
                 connect: Callable = connect_smtp, pdf_writer: Callable = write_pdf, now=datetime.now):
        self.settings = settings
        self.key = key
        self.operation_log = operation_log
        self.store = store
        self.app_version = app_version
        self.connect = connect
        self.pdf_writer = pdf_writer
        self.now = now
        self._done = False

    def _ensure_checkpoint(self) -> Checkpoint:
        """The checkpoint of this source - created as the first-run baseline
        (MAX(idLog) + OPEN ids, baseline_pending) when there is none or the
        DB holds less than it (another / restored DB). Raises
        OperationLogError / CheckpointError / OSError."""
        current_max = self.operation_log.max_log_id()
        checkpoint = self.store.get(self.key)
        if checkpoint is not None and current_max >= checkpoint.max_log_id:
            return checkpoint
        if checkpoint is not None:
            logger.warning(f"REPORT-01: DB {self.key} has MAX(idLog) {current_max} < checkpoint "
                           f"{checkpoint.max_log_id} - another or restored DB, checkpoint reinitialized")
        open_ids = tuple(sorted(r.log_id for r in self.operation_log.list_records(status=OPEN)))
        checkpoint = Checkpoint(current_max, open_ids, True, None, self.now(), self.app_version)
        self.store.put(self.key, checkpoint)
        logger.info(f"REPORT-01: baseline checkpoint for {self.key}: max idLog {current_max}, "
                    f"{len(open_ids)} OPEN")
        return checkpoint

    def start(self) -> None:
        """At start-up: the first-run baseline, so changes of this run count
        even if the start of the next one fails. Never raises - without it
        run() makes the baseline itself."""
        try:
            self._ensure_checkpoint()
        except Exception as e:
            logger.warning(f"REPORT-01: checkpoint not prepared at start-up ({_failure(e)})")

    def run(self, info: ExitInfo) -> str:
        """Once per process. SENT / SKIPPED / FAILED; never raises."""
        if self._done:
            return ALREADY_RUN
        self._done = True
        try:
            return self._run(info)
        except Exception as e:
            logger.error(f"REPORT-01: report failed ({_failure(e)}) - checkpoint unchanged")
            return FAILED

    def _run(self, info: ExitInfo) -> str:
        try:
            checkpoint = self._ensure_checkpoint()
            plan = plan_report(checkpoint, self.operation_log.list_changed_or_open(
                checkpoint.max_log_id, checkpoint.open_log_ids))
        except Exception as e:
            logger.warning(f"REPORT-01: logbook not readable ({_failure(e)}) - no report, checkpoint unchanged")
            return FAILED
        if not plan.send:
            if checkpoint.baseline_pending:
                self.store.put(self.key, plan.next_checkpoint(None, self.app_version))
                logger.info("REPORT-01: first run, nothing to report - checkpoint initialized, no e-mail")
            else:
                logger.info("REPORT-01: no logbook change since the last report - no e-mail")
            return SKIPPED
        name = pdf_filename(info.finished_at)
        with tempfile.TemporaryDirectory(prefix="polygon-report-") as directory:
            path = os.path.join(directory, name)
            try:
                self.pdf_writer(build_html(plan, info, self.settings.site), path)
                with open(path, "rb") as file:
                    pdf = file.read()
                if not pdf.startswith(b"%PDF"):
                    raise PdfError("not a PDF")
            except Exception as e:
                logger.error(f"REPORT-01: PDF not created ({_failure(e)}) - no report, checkpoint unchanged")
                return FAILED
        message = build_message(self.settings, build_subject(plan, info, self.settings.subject_prefix),
                                build_body(plan, info, name, self.settings.site), name, pdf)
        try:
            send_message(self.settings, message, self.connect)
        except Exception as e:
            logger.warning(f"REPORT-01: e-mail not sent via {self.settings.smtp_host}:{self.settings.smtp_port} "
                           f"({_failure(e)}) - checkpoint unchanged, the next correct exit retries")
            return FAILED
        logger.info(f"REPORT-01: report sent to {len(self.settings.recipients)} recipient(s): "
                    f"new {len(plan.new)}, resolved {len(plan.resolved)}, cancelled {len(plan.cancelled)}, "
                    f"open {len(plan.open)}")
        try:
            self.store.put(self.key, plan.next_checkpoint(self.now(), self.app_version))
        except Exception as e:
            logger.error(f"REPORT-01: report sent but checkpoint not saved ({_failure(e)}) - "
                         "the next correct exit sends it again")
        return SENT


def create(config, db, operation_log, app_version, path=None) -> Optional[ExitReport]:
    """The ExitReport for this run, or None: report off / incomplete, or a
    DEV run without allow_dev (then the checkpoint is never touched)."""
    settings = load_settings(config)
    if settings is None:
        return None
    dev_mode = is_dev_mode(config)
    if dev_mode and not settings.allow_dev:
        logger.info("REPORT-01: DEV mode - e-mail report off ([REPORT_EMAIL] allow_dev is not true)")
        return None
    key = source_key(dev_mode, db)
    logger.info(f"REPORT-01: e-mail report on, source {key}")
    return ExitReport(settings, key, operation_log, CheckpointStore(path or state_path()), app_version)
