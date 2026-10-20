#!/usr/bin/env python3
"""
Main application entry point - Secure version.
"""
import sys
import os
import signal
import socket
import time
from datetime import date, datetime
from enum import Enum
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QAbstractItemView, QHeaderView, QMenu
from PyQt5 import QtCore, QtGui

# Import secure modules
from config_manager import ConfigManager, ConfigurationError, site_from_config
from logger_config import enable_crash_log, logger

# Constants
__APP_DIR__ = os.path.dirname(__file__)
__VIDEO_FOLDER__ = os.path.join(__APP_DIR__, "../video")
os.makedirs(__VIDEO_FOLDER__, exist_ok=True)

# Import existing modules (with fixed imports)
from model import personModel, personFilterProxyModel, memberModel, trainingModel, finishedTrainingModel, exerciseSessionModel, trainingDetailModel, personHistoryModel
from ui_mainwindow import Ui_MainWindow, PersonForm, MemberForm, PersonHistoryDialog, PassageTimeDialog, DeletedPersonsDialog, SensorFaultDialog
from ui_loginForm import Ui_Login_Dialog
import protocol
from protocol_data import build_person_html, build_summary_html, load_protocol_data, pdf_filename
from hardware_service import OUTPUT_RECONNECT_WAIT, HardwareService
import quido_io
from training_service import (
    AddMemberOutcome, DeleteMemberOutcome, SaveOutcome,
    CancelTrainingOutcome, FinishTrainingOutcome, TrainingService, TrainingStatus,
)
from session_repository import SessionRepository
from operation_log_repository import OPEN, OperationLogRepository
from operation_log_service import FaultOutcome, OperationLogError, OperationLogService
from logbook import PRINT_PREVIEW, LogbookPrintDialog, LogRecordDialog, LogRecordDetailDialog
from logbook_print import SCOPE_OPEN, SCOPE_SHIFT, LogbookReport, build_logbook_html
from session_service import EntryOutcome, ExitOutcome, SessionService, SessionStatus, TimeCorrectionOutcome
from audio import Audio
import emergency
import exit_report
import theme
import polygon_map
from about_dialog import AboutDialog, make_version_button
from splash import start_boot_splash
from system_volume import SystemVolume
from version import APP_VERSION

# Import camera module
try:
    from camera import Camera
except ImportError:
    logger.warning("Camera module not available")
    Camera = None

from PyQt5 import QtCore, QtGui, QtSql
from PyQt5.QtWidgets import (QMainWindow, QAbstractItemView, QMessageBox,
                           QDialog, QApplication, QHeaderView, QPushButton, QLabel, QFileDialog)
import ldap3


# [DEV] skip_login (home GUI testing without LDAP/AD) - see dev_login_bypass_enabled().
DEV_USER = "DEV"
DEV_MODE_BANNER = "DEV MODE – PŘIHLÁŠENÍ VYPNUTO"

LOCAL_DB_HOSTS = ("127.0.0.1", "localhost", "::1")


def db_indicator(mysql_conf, dev_mode):
    """Status bar text + kind for the connected database, so it is always
    visible whether the app writes into a local DB or the live one.

    kind: "local" (host is loopback), "live" (any other host - normal
    operation), "live-dev" (other host while a [DEV] mode is active -
    test data would go into real data)."""
    host = str(mysql_conf.get('host', '')).strip()
    database = mysql_conf.get('database', '')
    if host.lower() in LOCAL_DB_HOSTS:
        return f"LOKÁLNÍ DB: {database} @ {host}", "local"
    if dev_mode:
        return f"POZOR: OSTRÁ DB: {database} @ {host}", "live-dev"
    return f"DB: {database} @ {host}", "live"


def dev_login_bypass_enabled(config) -> bool:
    """True only if [DEV] skip_login = true AND [DEV] mock_quido = true
    (both real booleans - anything else, e.g. "yes"/"1", doesn't count).
    Lets the GUI be tested at home without LDAP/AD; tied to mock_quido so it
    can't be left on by mistake on a machine driving real QUIDO hardware.
    Default (key or [DEV] missing): False -> normal LDAP login."""
    dev = config.get('DEV') or {}
    skip_login = dev.get('skip_login', False)
    if skip_login is not True:
        if skip_login is not False:
            logger.warning(f"[DEV] skip_login={skip_login!r} is not true/false - ignored, normal login")
        return False
    if dev.get('mock_quido', False) is not True:
        logger.warning("[DEV] skip_login=true IGNORED: it requires mock_quido=true - using normal LDAP login")
        return False
    logger.warning("DEV MODE: login skipped ([DEV] skip_login=true, mock_quido=true) - no LDAP authentication")
    return True


def mock_camera_enabled(config) -> bool:
    """CAMERA-MOCK-01: True only if [DEV] mock_camera = true (a real
    boolean). Only then are mock:// cameras accepted - home development
    without RTSP cameras; never in production. Default: False."""
    value = (config.get('DEV') or {}).get('mock_camera', False)
    if value is not True:
        if value is not False:
            logger.warning(f"[DEV] mock_camera={value!r} is not true/false - ignored, mock cameras off")
        return False
    logger.warning("DEV MODE: mock cameras allowed ([DEV] mock_camera=true)")
    return True


def run_login(config):
    """Login step of main(): (display_name, dev_login_bypass), or None if the
    user cancelled. The DEV bypass skips the dialog entirely - LDAP is never
    contacted; it is not an "LDAP always succeeds" shortcut."""
    if dev_login_bypass_enabled(config):
        return DEV_USER, True
    login_dialog = LoginDialog(config['LDAP'])
    if login_dialog.exec_() != QDialog.Accepted:
        return None
    # Display name from the login dialog (for protocol printing)
    return getattr(login_dialog, 'display_name', 'Unknown User'), False


class CameraState(Enum):
    """Confirmed camera outcome shown on the Provoz tab - what the camera
    actually did, not what was requested (_camera_record_requested)."""
    DISABLED = "VYPNUTA"      # [CAMERA] disable = true, or switched off at runtime
    STARTING = "SPOUŠTÍ SE"   # enabled, Camera not created yet (deferred start)
    READY = "PŘIPRAVENA"      # initialized, not recording
    RECORDING = "NAHRÁVÁ"     # startRecord() confirmed success
    ERROR = "CHYBA"           # unavailable, or start/stop failed
    STOPPING = "VYPÍNÁ SE"    # runtime switch-off in progress


# SPLASH-01: after the main window is built, wait for the first QUIDO reads
# (HW-IO workers, results queued) so the boot lines show real states.
BOOT_FIRST_READ_MS = 1000
_BOOT_HW_STATUS = {"ok": "ok", "error": "failed", "mock": "sim"}
_BOOT_DB_STATUS = {"local": "ok", "live": "ok", "live-dev": "warn"}


def boot_status_lines(window):
    """SPLASH-01: closing boot lines [(text, status)] - camera, then DB, QUIDO
    and run mode last (the console shows the last 3). Read from the status
    bar / Provoz widgets of the main window, so they can't disagree."""
    lines = []
    camera = getattr(window, "_camera_state", None)
    if camera is not None:
        status = {CameraState.ERROR: "failed", CameraState.DISABLED: "info",
                  CameraState.STARTING: "info", CameraState.STOPPING: "info"}.get(camera, "ok")
        lines.append((f"Kamera: {camera.value}", status))

    lines.append((window.dbLabel.text().strip(), _BOOT_DB_STATUS.get(window.dbLabel.property("db"), "warn")))

    states = [window.qin_status.property("hw"), window.qout_status.property("hw")]
    if window.mock_quido:
        lines.append(("QUIDO Input/Output: SIMULACE – bez HW", "sim"))
    else:
        word = {"ok": "OK", "error": "CHYBA"}
        quido = window.conf.get('QUIDO', {})
        lines.append((f"QUIDO Input {quido.get('din')}: {word.get(states[0], '?')}, "
                      f"Output {quido.get('dout')}: {word.get(states[1], '?')}",
                      "ok" if states == ["ok", "ok"] else "failed"))

    if window.dev_login_bypass:
        lines.append(("Režim: DEV – přihlášení vypnuto, QUIDO simulace", "dev"))
    elif window.mock_quido:
        lines.append(("Režim: DEV – QUIDO simulace", "dev"))
    else:
        lines.append(("Režim: provoz", "ok"))
    return lines


_CAMERA_STATE_STYLE = {state: theme.CAMERA_STATE_STYLE[state.name] for state in CameraState}


# UX-04: double-click/right-click quick actions on personTableView and
# memberTableView. No new business logic - these only select a row and
# invoke the existing addMember()/editPerson()/updateMember()/delMember()
# handlers, so the current validation/DB/active-session protections are
# unchanged. Kept as free functions (not MainWindow methods) so they can
# be unit-tested directly against a bare QTableView, without a real
# MainWindow/DB/QMenu.exec_().

def select_row_under_cursor(view, index) -> bool:
    """Make index's row the view's current selection and return True, or
    return False without touching the selection if index is invalid (e.g.
    a right-click on empty space) - a context menu or double-click must
    always act on the row under the cursor, never a stale previous
    selection."""
    if not index.isValid():
        return False
    view.selectionModel().setCurrentIndex(
        index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
    return True


def build_person_context_menu(parent, add_to_training, edit_person, person_history) -> QMenu:
    menu = QMenu(parent)
    menu.addAction("Přidat do cvičení", add_to_training)
    menu.addAction("Upravit osobu", edit_person)
    menu.addAction("Historie cvičence", person_history)  # HISTORY-02
    return menu


def build_session_context_menu(parent, edit_passage_time, can_edit) -> QMenu:
    """UX-02: Provoz table menu. can_edit False (PŘIPRAVEN - nothing
    recorded yet) keeps the action visible but disabled."""
    menu = QMenu(parent)
    action = menu.addAction("Upravit čas průchodu…", edit_passage_time)
    action.setEnabled(can_edit)
    return menu


def build_member_context_menu(parent, update_values, remove_member) -> QMenu:
    menu = QMenu(parent)
    menu.addAction("Upravit hodnoty", update_values)
    menu.addAction("Odebrat cvičence", remove_member)
    return menu


# MAP-02: right click on a floor of the Polygon map
FLOOR_FAULT_MARK_TEXT = "Označit čidlo jako nefunkční…"
FLOOR_FAULT_RESOLVE_TEXT = "Označit čidlo jako funkční…"
FLOOR_FAULT_CANCEL_TEXT = "Stornovat chybné označení…"
FAULT_REGISTER_UNAVAILABLE_TEXT = "Evidence závad nedostupná – stav nefunkčních čidel nelze ověřit"


def build_floor_context_menu(parent, faulty, available, mark, resolve, cancel) -> QMenu:
    """MAP-02: a working sensor offers "nefunkční", a faulty one "funkční"
    and "stornovat". available False (the operation log can't be read):
    the actions stay visible but disabled under a disabled warning line."""
    menu = QMenu(parent)
    if not available:
        menu.addAction(FAULT_REGISTER_UNAVAILABLE_TEXT).setEnabled(False)
        menu.addSeparator()
    if faulty:
        actions = [menu.addAction(FLOOR_FAULT_RESOLVE_TEXT, resolve),
                   menu.addAction(FLOOR_FAULT_CANCEL_TEXT, cancel)]
    else:
        actions = [menu.addAction(FLOOR_FAULT_MARK_TEXT, mark)]
    for action in actions:
        action.setEnabled(available)
    return menu


_QUIDO_SIGNALS_ALIVE = []  # HW-IO: see MainWindow._ensure_quido_signals()


class QuidoSignals(QtCore.QObject):
    """HW-IO: results of the quido-in / quido-out workers (quido_io), emitted
    in their threads and delivered queued in the GUI thread."""
    inputRead = QtCore.pyqtSignal(object)   # (ok, [all Input states] | error)
    outputRead = QtCore.pyqtSignal(object)  # (ok, [all Output states] | error)
    jobDone = QtCore.pyqtSignal(object)     # quido_io.OutputJob


class MainWindow(QMainWindow, Ui_MainWindow):

    # Fail-closed text for the Provoz tab's "N UVNITŘ" counter.
    INSIDE_COUNT_UNKNOWN_TEXT = "Stav nelze načíst"
    # closeEvent() prompt when has_active_sessions() can't read the DB.
    CLOSE_STATE_UNKNOWN_TEXT = "Stav cvičenců nelze ověřit kvůli chybě databáze. Opravdu chcete aplikaci ukončit?"
    # Retry interval after a failed camera startRecord() while recording is wanted.
    CAMERA_RETRY_INTERVAL_MS = 10000

    def __init__(self, config: dict, display_name: str = None, dev_login_bypass: bool = False,
                 show: bool = True, dev_tab: bool = False):
        super().__init__()
        self.setupUi(self)

        # Store configuration and user info
        self.conf = config
        self.site = site_from_config(config)  # SITE-CONFIG-01
        self.setWindowTitle(self.site.name)   # DEV/DB banners append to it below
        self.current_user = display_name or "Unknown User"
        self.dev_login_bypass = dev_login_bypass
        # REPORT-01: set only by a confirmed closeEvent (+ UVNITŘ at that moment)
        self.exit_confirmed = False
        self.exit_inside = None
        self._last_pdf_dir = None  # Uložit PDF: last directory, this run only (PRINT-01c)
        # Temporary status bar message -> cleared again, which shows the
        # version and user widgets back. Owned by the window (not
        # QTimer.singleShot) so it dies with it.
        self._temporary_status = None
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._restore_default_status)

        # Initialize models (database should be connected globally)
        self.personmodel = personModel()
        self.trainingmodel = trainingModel()
        self.membermodel = memberModel()
        self.finishedtrainingmodel = finishedTrainingModel()
        self.trainingdetailmodel = trainingDetailModel()
        self.sessionmodel = exerciseSessionModel()

        # Initialize components
        self._init_quido_mode()
        # MAP-01: floors outside [QUIDO_IN] UNMAPPED, the rest UNKNOWN until the first read
        self.polygonMap.set_mapped_floors(self.conf.get('QUIDO_IN', {}))
        self._init_database_reference()
        self._init_training_service()
        self._init_operation_log()
        self._init_logbook()
        self._init_status_labels()
        self._init_widgets()
        self._init_dev_mode_banner()
        self._init_db_indicator()
        if dev_tab:  # DEV-QUIDO-01: only with ./bin/polygon --dev, never from the config
            self._init_dev_quido_tab()
        self._init_quido_io()
        self._init_camera()
        self._init_audio()
        self._init_volume_control()
        self._init_quido_simulator()

        # Restart recovery: re-populate the member/session tables and the
        # "Dokončit cvičení" button from whatever's already in the DB -
        # read-only, must never create a training (see _restore_open_training_ui).
        self._restore_open_training_ui()
        self._update_lifecycle_buttons()

        # Camera record request follows the active-session count; a
        # restart with pre-existing INSIDE sessions must be recognized here,
        # not just on the next live entry/exit event. If the count can't be
        # read at startup, this fails safe by requesting recording.
        self._camera_record_requested = False
        self._sync_camera_record_request(self.session.count_all_active())

        if show:  # main() shows it only after the boot splash (SPLASH-01)
            self.show()

    def _init_quido_mode(self):
        """Set up the QUIDO hardware access layer (real or mock, per [DEV] mock_quido)."""
        self.hardware = HardwareService(self.conf)
        self.mock_quido = self.hardware.mock_mode
        logger.info(f"QUIDO mode: {'MOCK' if self.mock_quido else 'REAL'}")
        if self.mock_quido:
            logger.warning("Development QUIDO simulator enabled - no physical QUIDO communication will be used.")

    def _init_database_reference(self):
        """Get reference to the global database connection."""
        try:
            # Get the default database connection (should be already established)
            self.db = QtSql.QSqlDatabase.database()

            if self.db.isOpen():
                logger.info("Using existing database connection")
                self.query = QtSql.QSqlQuery()
            else:
                logger.error("Database connection not available")
                QMessageBox.critical(self, 'Chyba databáze', 'Databáze není připojena.')
                self.query = None
        except Exception as e:
            logger.error(f"Database reference error: {e}")
            self.query = None

    def _init_training_service(self):
        """Set up the training lifecycle (TrainingService) and individual
        polygon-pass (SessionService) services. Both share self.query for
        their repositories; TrainingService also gets the raw db handle for
        its transaction-wrapped delete cascades."""
        self.session_repository = SessionRepository(self.query)
        self.session = SessionService(self.session_repository)
        self.training = TrainingService(
            self.query, self.trainingmodel,
            session_repository=self.session_repository, db=self.db,
        )

    def _init_operation_log(self):
        """MAP-02: faulty sensors = OPEN SENSOR_FAULT records of the
        operation log (LOGBOOK-01), loaded onto the map at start-up."""
        repository = OperationLogRepository(self.query) if self.query is not None else None
        self.operation_log = OperationLogService(repository, valid_floors=polygon_map.FLOOR_NAMES)
        self.polygonMap.floorContextRequested.connect(self._show_floor_context_menu)
        self._load_sensor_faults()

    def _init_logbook(self):
        """LOGBOOK-01: the Kniha provozu tab - refreshed on entering the tab,
        by Obnovit / a filter change and after every write. No polling."""
        tab = self.tabLogbook
        tab.refreshRequested.connect(self._refresh_logbook)
        tab.newRequested.connect(self._new_log_record)
        tab.detailRequested.connect(self._show_log_record_detail)
        tab.resolveRequested.connect(self._resolve_log_record)
        tab.cancelRequested.connect(self._cancel_log_record)
        tab.printRequested.connect(self._print_logbook)
        self.ptabWidget.currentChanged.connect(self._on_main_tab_changed)
        self._refresh_logbook()

    def _on_main_tab_changed(self, index):
        if self.ptabWidget.widget(index) is self.tabLogbook:
            self._refresh_logbook()

    def _refresh_logbook(self) -> bool:
        """Reload the logbook table. On a read error the last table stays and
        the tab shows the "not available" banner with writes disabled."""
        tab = self.tabLogbook
        try:
            records = self.operation_log.list_records(tab.status_filter(), tab.category_filter())
            open_count = self.operation_log.count_open()
        except OperationLogError as e:
            logger.warning(f"Operation log unavailable - logbook not refreshed: {e}")
            tab.set_available(False)
            return False
        tab.show_records(records, open_count)
        tab.set_available(True)
        return True

    # --- LOGBOOK-01: actions (dialogs are separate methods, tests replace them)

    def _ask_log_record(self):
        """Values of a new record from LogRecordDialog, None when cancelled."""
        dialog = LogRecordDialog(datetime.now(), self)
        return dialog.values() if dialog.exec_() == QDialog.Accepted else None

    def _ask_record_text(self, title, record, field_label, required=False):
        """(accepted, text) about one logbook record."""
        dialog = SensorFaultDialog(title, f"#{record.log_id} – {record.category_label}", field_label,
                                   required, self, subject_label="Záznam:")
        accepted = dialog.exec_() == QDialog.Accepted
        return accepted, dialog.text()

    def _show_detail_dialog(self, record, hw_state_text):
        LogRecordDetailDialog(record, hw_state_text, self).exec_()

    def _logbook_writable(self, action) -> bool:
        """No writes while the tab says the logbook is unavailable - not only
        disabled buttons (a signal/handler can still be invoked)."""
        if self.tabLogbook.is_available():
            return True
        logger.warning(f"Logbook: {action} refused - operation log unavailable")
        return False

    def _logbook_record(self, log_id):
        """A fresh copy of record log_id, None (with a message) when it can't be read."""
        try:
            record = self.operation_log.get_record(log_id)
        except OperationLogError as e:
            logger.error(f"Logbook: record {log_id} can't be read: {e}")
            self.tabLogbook.set_available(False)
            QMessageBox.warning(self, "Kniha provozu", "Záznam nelze načíst – databáze není dostupná.")
            return None
        if record is None:
            QMessageBox.information(self, "Kniha provozu", f"Záznam #{log_id} nebyl nalezen.")
        return record

    def _new_log_record(self):
        if not self._logbook_writable("new record"):
            return
        values = self._ask_log_record()
        if values is None:
            return
        result = self.operation_log.create_record(created_by=self.current_user, **values)
        self._after_log_record_change(result, "uložit záznam", values.get("floor_name"))

    def _resolve_log_record(self, log_id):
        if not self._logbook_writable("resolve"):
            return
        record = self._logbook_record(log_id)
        if record is None:
            return
        accepted, note = self._ask_record_text("Označit jako vyřešené", record, "Poznámka k řešení:")
        if accepted:
            result = self.operation_log.resolve_record(log_id, self.current_user, note)
            self._after_log_record_change(result, "označit záznam jako vyřešený", record.floor_name)

    def _cancel_log_record(self, log_id):
        if not self._logbook_writable("cancel"):
            return
        record = self._logbook_record(log_id)
        if record is None:
            return
        accepted, reason = self._ask_record_text("Stornovat záznam", record, "Důvod storna *", required=True)
        if accepted:
            result = self.operation_log.cancel_record(log_id, self.current_user, reason)
            self._after_log_record_change(result, "stornovat záznam", record.floor_name)

    def _show_log_record_detail(self, log_id):
        record = self._logbook_record(log_id)
        if record is None:
            return
        hw = None
        if record.floor_name:
            hw = polygon_map.HW_STATE_TEXT.get(self.polygonMap.floor_state(record.floor_name))
        self._show_detail_dialog(record, hw)

    def _after_log_record_change(self, result, action, floor_name=None):
        """Explain anything but success, then reload from the DB - the map
        too for a sensor record (operation_log is the only source of truth:
        a SENSOR_FAULT created / resolved / cancelled here shows on the map
        at once)."""
        if result.outcome == FaultOutcome.OK:
            logger.info(f"Logbook: {action} #{result.record.log_id if result.record else '?'} ({self.current_user})")
        elif result.outcome == FaultOutcome.ALREADY_OPEN:
            number = polygon_map.segment_text(floor_name) if floor_name else "?"
            QMessageBox.information(self, "Kniha provozu",
                                    f"Čidlo {number} už má otevřenou závadu – nový záznam se nevytvořil.")
        elif result.outcome == FaultOutcome.NOT_OPEN:
            QMessageBox.information(self, "Kniha provozu", "Záznam už není otevřený (vyřešen nebo stornován).")
        elif result.outcome == FaultOutcome.INVALID:
            QMessageBox.warning(self, "Kniha provozu", f"Nelze {action} – neplatné nebo chybějící údaje.")
        else:
            logger.error(f"Logbook: {action} failed - operation log unavailable")
            QMessageBox.warning(self, "Kniha provozu", f"Nelze {action} – databáze není dostupná. Nic se neuložilo.")
        if floor_name:
            self._load_sensor_faults()
        self._refresh_logbook()
        if result.record is not None and result.outcome in (FaultOutcome.OK, FaultOutcome.ALREADY_OPEN):
            self.tabLogbook.select_record(result.record.log_id)

    # --- LOGBOOK-02: Tisk / PDF (independent of [PROTOCOL] disable) ----------

    def _ask_logbook_print(self):
        """(LogbookScope, action) from LogbookPrintDialog, None when closed."""
        dialog = LogbookPrintDialog(date.today(), self)
        return (dialog.scope(), dialog.action) if dialog.exec_() == QDialog.Accepted else None

    def _logbook_report(self, scope):
        """The scope's records fresh from the DB, oldest event first - read
        only. None (with a message) when the log can't be read: a failed
        read must never print as an empty logbook."""
        try:
            if scope.kind == SCOPE_SHIFT:
                records = self.operation_log.list_today_and_open(scope.today)
            else:
                event_from, event_to = scope.event_bounds()
                records = self.operation_log.list_records(
                    status=OPEN if scope.kind == SCOPE_OPEN else None,
                    event_from=event_from, event_to=event_to, oldest_first=True)
        except OperationLogError as e:
            logger.error(f"Logbook print: operation log unavailable: {e}")
            self.tabLogbook.set_available(False)
            QMessageBox.warning(self, "Kniha provozu", "Knihu provozu nelze vytisknout – databáze není dostupná.")
            return None
        return LogbookReport(scope, datetime.now(), self.current_user, records)

    def _print_logbook(self):
        choice = self._ask_logbook_print()
        if choice is None:
            return
        scope, action = choice
        if not scope.is_valid():
            QMessageBox.warning(self, "Kniha provozu", "Neplatný rozsah – datum OD je po datu DO.")
            return
        report = self._logbook_report(scope)
        if report is None:
            return
        html = build_logbook_html(report, self.site)
        logger.info(f"Logbook print: {scope.kind}, {len(report.records)} records, {action} ({self.current_user})")
        if action == PRINT_PREVIEW:
            try:
                protocol.show_preview(html, self, logo_path=protocol.site_logo_path(self.site),
                                      orientation=protocol.SUMMARY_ORIENTATION)
            except Exception as e:
                logger.error(f"Error printing logbook: {e}")
                QMessageBox.warning(self, "Chyba", f"Chyba při tisku: {e}", QMessageBox.Ok)
        else:
            self._save_pdf(html, scope.filename(), protocol.SUMMARY_ORIENTATION, "logbook")

    def _load_sensor_faults(self) -> bool:
        """Open sensor faults from the DB onto the map. If the log can't be
        read, the map keeps the faults it knows and shows that the fault
        state can't be verified - it never shows "no faults" instead."""
        try:
            faults = self.operation_log.get_open_sensor_faults()
        except OperationLogError as e:
            logger.warning(f"Operation log unavailable - sensor faults can't be verified: {e}")
            self.polygonMap.set_fault_register_available(False)
            return False
        self.polygonMap.set_floor_faults({name: self._sensor_fault_detail(f) for name, f in faults.items()})
        self.polygonMap.set_fault_register_available(True)
        return True

    @staticmethod
    def _sensor_fault_detail(fault) -> str:
        """Tooltip lines of an open fault (the map adds the HW state)."""
        when = fault.event_at
        return (f"Nahlášeno: {when.day}. {when.month}. {when.year} {when:%H:%M}\n"
                f"Zapsal: {fault.created_by}\nPoznámka: {fault.description}")

    def _show_floor_context_menu(self, floor_name, global_pos):
        self._floor_context_menu(floor_name).exec_(global_pos)

    def _floor_context_menu(self, floor_name) -> QMenu:
        self._load_sensor_faults()  # fresh state, also re-checks an unavailable DB
        return build_floor_context_menu(
            self.polygonMap, self.polygonMap.is_floor_faulty(floor_name),
            self.polygonMap.fault_register_available(),
            lambda: self._mark_floor_faulty(floor_name),
            lambda: self._resolve_floor_fault(floor_name),
            lambda: self._cancel_floor_fault(floor_name))

    def _ask_fault_text(self, title, floor_name, field_label, required=False):
        """(accepted, text) from SensorFaultDialog."""
        dialog = SensorFaultDialog(title, polygon_map.segment_text(floor_name), field_label, required, self)
        accepted = dialog.exec_() == QDialog.Accepted
        return accepted, dialog.text()

    def _fault_register_writable(self, floor_name, action) -> bool:
        """Never write while the map says the fault register is unavailable -
        not only a disabled menu action (QAction.trigger() runs a disabled
        action too)."""
        if self.polygonMap.fault_register_available():
            return True
        logger.warning(f"Sensor fault {floor_name}: {action} refused - fault register unavailable")
        return False

    def _mark_floor_faulty(self, floor_name):
        if not self._fault_register_writable(floor_name, "mark faulty"):
            return
        accepted, note = self._ask_fault_text("Označit čidlo jako nefunkční", floor_name, "Poznámka k závadě:")
        if accepted:
            result = self.operation_log.create_sensor_fault(floor_name, self.current_user, note)
            self._after_sensor_fault_change(result, floor_name, "označit čidlo jako nefunkční")

    def _resolve_floor_fault(self, floor_name):
        if not self._fault_register_writable(floor_name, "resolve"):
            return
        accepted, note = self._ask_fault_text("Označit čidlo jako funkční", floor_name, "Poznámka k opravě:")
        if accepted:
            result = self.operation_log.resolve_sensor_fault(floor_name, self.current_user, note)
            self._after_sensor_fault_change(result, floor_name, "označit čidlo jako funkční")

    def _cancel_floor_fault(self, floor_name):
        if not self._fault_register_writable(floor_name, "cancel"):
            return
        accepted, reason = self._ask_fault_text("Stornovat chybné označení", floor_name,
                                                "Důvod storna:", required=True)
        if accepted:
            result = self.operation_log.cancel_sensor_fault(floor_name, self.current_user, reason)
            self._after_sensor_fault_change(result, floor_name, "stornovat označení")

    def _after_sensor_fault_change(self, result, floor_name, action):
        """Reload the map from the DB (the only source of truth) and explain
        anything but success; the logbook table follows (LOGBOOK-01)."""
        number = polygon_map.segment_text(floor_name)
        if result.outcome == FaultOutcome.OK:
            logger.info(f"Sensor fault {floor_name}: {action} ({self.current_user})")
        elif result.outcome == FaultOutcome.ALREADY_OPEN:
            QMessageBox.information(self, "Nefunkční čidlo", f"Čidlo {number} už je označené jako nefunkční.")
        elif result.outcome == FaultOutcome.NOT_OPEN:
            QMessageBox.information(self, "Nefunkční čidlo", f"Čidlo {number} už nemá otevřenou závadu.")
        elif result.outcome == FaultOutcome.INVALID:
            QMessageBox.warning(self, "Nefunkční čidlo", f"Nelze {action} – neplatné údaje.")
        else:
            logger.error(f"Sensor fault {floor_name}: {action} failed - operation log unavailable")
            QMessageBox.warning(self, "Nefunkční čidlo",
                                f"Nelze {action} – evidence závad není dostupná (DB). Nic se neuložilo.")
        self._load_sensor_faults()
        self._refresh_logbook()

    def _restore_open_training_ui(self):
        """Read-only restart recovery: if an open training already exists,
        repopulate the member/session tables and the "Dokončit cvičení"
        button state from it. Deliberately uses find_open_training(), not
        get_or_create_training() - a restart against an empty DB must not
        create a new training row."""
        try:
            found = self.training.find_open_training()
            if found is None:
                # find_open_training() returns None both for "no open
                # training" and for a DB error - trainingmodel.load_failed()
                # tells the two apart.
                if self.trainingmodel.load_failed():
                    self._show_inside_count_unknown()
                else:
                    self._update_inside_count_label(None)
                return
            training_id, status = found
            self.membermodel.refresh(training_id)
            self.sessionmodel.refresh(training_id)
            self._update_inside_count_label(training_id)
        except Exception as e:
            logger.error(f"Error restoring training state: {e}")
            self._show_inside_count_unknown()

    def _update_inside_count_label(self, training_id):
        """Keep the "N UVNITŘ" counter on the Provoz tab in sync with the
        rows sessionmodel just loaded - call right after
        sessionmodel.refresh(training_id). training_id=None means "no
        open training right now" (fresh app, or after save/delete).
        Fails closed: a failed query shows INSIDE_COUNT_UNKNOWN_TEXT,
        never "Nikdo není uvnitř"."""
        try:
            if training_id is None:
                self.insideCountLabel.setText("Žádné probíhající cvičení")
                theme.set_state(self.insideCountLabel, "idle")
                return
            count = self.sessionmodel.inside_count()
            if count is None:
                logger.error(f"Inside count unavailable: {self.sessionmodel.lastError().text()}")
                self._show_inside_count_unknown()
                return
            self.insideCountLabel.setText(f"{count} UVNITŘ" if count else "Nikdo není uvnitř")
            theme.set_state(self.insideCountLabel, "inside" if count else "idle")
        except Exception as e:
            logger.error(f"Error updating inside-count label: {e}")
            self._show_inside_count_unknown()

    def _show_inside_count_unknown(self):
        self.insideCountLabel.setText(self.INSIDE_COUNT_UNKNOWN_TEXT)
        theme.set_state(self.insideCountLabel, "unknown")

    def _hide_member_internal_columns(self):
        self.memberTableView.hideColumn(0)  # idMember
        self.memberTableView.hideColumn(self.membermodel.STAV_CODE_COLUMN)  # stav_code (internal)
        # PRINT-02 corrective: entry_at/exit_at - needed only to compute
        # the visible "Spotřeba (l/min)" column, never shown themselves.
        self.memberTableView.hideColumn(self.membermodel.ENTRY_AT_COLUMN)
        self.memberTableView.hideColumn(self.membermodel.EXIT_AT_COLUMN)

    def _hide_training_detail_internal_columns(self):
        self.trainingDetailTableView.hideColumn(self.trainingdetailmodel.ID_COLUMN)  # idMember

    def _hide_session_internal_columns(self):
        self.sessionTableView.hideColumn(0)  # idMember
        self.sessionTableView.hideColumn(self.sessionmodel.STAV_CODE_COLUMN)  # stav_code (internal)

    def _update_lifecycle_buttons(self):
        """Enable Dokončit/Uložit/Smazat cvičení from the real training
        lifecycle (Etapa 8.5) - a guard against operator mistakes only; the
        service layer's own checks (finish_training(), save(),
        cancel_open_training()) stay the authority.

            READY    Dokončit only if nobody is UVNITŘ, Uložit disabled
            STOPPED  Dokončit disabled, Uložit enabled
            none     all disabled

        Smazat mirrors cancel_open_training()'s guard: an open training
        with nobody UVNITŘ. Fails closed: if the training or the active
        count can't be read (DB error -> load_failed()/None), everything
        is disabled."""
        finish = save = delete = False
        try:
            found = self.training.find_open_training()
            if found is None:
                if self.trainingmodel.load_failed():
                    logger.error("Training state unavailable - lifecycle buttons disabled (fail closed)")
            else:
                training_id, status = found
                nobody_inside = self.session.count_active_for_training(training_id) == 0  # None -> False
                finish = status == TrainingStatus.READY and nobody_inside
                save = status == TrainingStatus.STOPPED
                delete = nobody_inside
        except Exception as e:
            logger.error(f"Error updating lifecycle buttons: {e}")
            finish = save = delete = False
        self._set_lifecycle_buttons(finish, save, delete)

    def _set_lifecycle_buttons(self, finish, save, delete):
        self.stopButton.setEnabled(finish)
        self.saveTrainingButton.setEnabled(save)
        self.delTrainingButton.setEnabled(delete)

    def _init_status_labels(self):
        """Initialize status labels."""
        try:
            din_ip = self.conf['QUIDO']['din']
            dout_ip = self.conf['QUIDO']['dout']

            self.qin_status = QLabel()
            self.qout_status = QLabel()
            self._set_quido_status(self.qin_status, "Input", din_ip, False)
            self._set_quido_status(self.qout_status, "Output", dout_ip, False)
        except KeyError as e:
            logger.error(f"Configuration error: {e}")
            self.qin_status = QLabel(" QUIDO Input - status: Config Error")
            self.qout_status = QLabel(" QUIDO Output - status: Config Error")

    def _set_quido_status(self, label, name, ip, ok):
        """QUIDO status bar label. In mock mode it never looks like real
        hardware: orange "SIMULACE", no IP, regardless of ok."""
        if self.mock_quido:
            label.setText(f" QUIDO {name}: SIMULACE – bez HW ")
            theme.set_hw_state(label, ok, mock=True)
            return
        label.setText(f" QUIDO {name} {ip} - status: {'OK' if ok else 'Error'} ")
        theme.set_hw_state(label, ok)

    def _init_dev_mode_banner(self):
        """With the DEV login bypass active, make it impossible to miss:
        window title + a permanent (never hidden by showMessage()) status
        bar label."""
        if not self.dev_login_bypass:
            return
        self.setWindowTitle(f"{self.windowTitle()} – {DEV_MODE_BANNER}")
        self.devModeLabel = QLabel(f" {DEV_MODE_BANNER} ")
        self.devModeLabel.setObjectName("devModeLabel")
        self.statusbar.addPermanentWidget(self.devModeLabel)

    def _init_db_indicator(self):
        """Permanent status bar label naming the DB of the open default
        QSqlDatabase connection (local vs live) - not the config, so the
        label can't disagree with the connection actually in use. An
        invalid connection has no host and is never shown as local."""
        db = QtSql.QSqlDatabase.database(open=False)
        text, kind = db_indicator({'host': db.hostName(), 'database': db.databaseName()},
                                  self.dev_login_bypass or self.mock_quido)
        logger.info(f"Database indicator: {text}")
        self.dbLabel = QLabel(f" {text} ")
        self.dbLabel.setObjectName("dbLabel")
        self.dbLabel.setProperty("db", kind)
        self.statusbar.addPermanentWidget(self.dbLabel)
        if kind == "live-dev":
            self.setWindowTitle(f"{self.windowTitle()} – {text}")

    def _init_widgets(self):
        """Initialize UI widgets."""
        try:
            self.assign_widgets()
        except Exception as e:
            logger.error(f"Widget initialization failed: {e}")

    # HW-IO state (class defaults: tests build MainWindow without __init__)
    QUIDO_POLL_INTERVAL = quido_io.POLL_INTERVAL
    QUIDO_RETRY_INTERVAL = quido_io.RETRY_INTERVAL
    QUIDO_STOP_TIMEOUT = quido_io.STOP_TIMEOUT
    # a running emergency sequence may need several bounded reconnects (HW-READ-04)
    QUIDO_EMERGENCY_STOP_TIMEOUT = 20.0
    RELAY_UNKNOWN_TOOLTIP = "Stav neznámý – QUIDO Output nedostupné"
    _quido_signals = None
    _quido_in = None
    _quido_out = None
    _quido_stopped = False
    _output_known = False  # last QUIDO Output read succeeded
    _output_states = None  # HW-OUT-TOGGLE-01: raw relay states of that read (index 0 = relay 1), else None
    _output_job = None     # manual relay write in progress (quido_io.OutputJob)

    devQuidoTab = None  # DEV-QUIDO-01, only with --dev
    devQuidoLog = None  # DEV-LOG-01, only with --dev

    def _init_dev_quido_tab(self):
        """DEV-QUIDO-01: read-only QUIDO diagnostics as the last tab. It gets
        the reads of the quido-in / quido-out workers - no QUIDO I/O of its own."""
        import dev_quido_tab
        from dev_quido_log import DevQuidoLog
        quido_in, quido_out = self.conf.get('QUIDO_IN', {}), self.conf.get('QUIDO_OUT', {})
        # DEV-LOG-01: the same reads (+ relay clicks) into log/dev_quido_*.log
        self.devQuidoLog = DevQuidoLog(dev_quido_tab.input_names(quido_in), dev_quido_tab.input_labels(quido_in),
                                       dev_quido_tab.output_names(quido_out), dev_quido_tab.INPUT_COUNT,
                                       dev_quido_tab.OUTPUT_COUNT)
        quido = self.conf.get('QUIDO', {})
        self.devQuidoLog.start(quido.get('din', '?'), quido.get('dout', '?'))
        self.devQuidoLog.config(self.conf, self._dev_log_runtime())
        self.devQuidoTab = dev_quido_tab.DevQuidoTab(quido_in, quido_out, log=self.devQuidoLog)
        self.ptabWidget.addTab(self.devQuidoTab, "DEV")
        logger.warning(f"DEV tab enabled (--dev): read-only QUIDO diagnostics, log {self.devQuidoLog.path}")

    def _init_quido_io(self):
        """HW-IO: QUIDO is read by two long-lived workers, never in the GUI
        thread - a silent QUIDO can't freeze the window. Map and relay
        buttons stay UNKNOWN until their first successful read."""
        self._ensure_quido_signals()
        self._quido_in = quido_io.QuidoWorker(
            "quido-in", self.hardware.read_input_states, self._quido_signals.inputRead.emit,
            interval=self.QUIDO_POLL_INTERVAL, retry_interval=self.QUIDO_RETRY_INTERVAL)
        self._quido_workers.append(self._quido_in)
        self._quido_in.start()
        self._ensure_output_worker()

    def _ensure_quido_signals(self):
        """The signal object has no parent and stays in _QUIDO_SIGNALS_ALIVE
        while a worker may still emit: a worker never emits into a deleted
        object (Qt drops queued results of a destroyed window). The workers
        are stopped by shutdown_quido_io() only - every lifecycle path calls
        it (closeEvent, Ctrl+C in main()); nothing hooks QObject.destroyed
        (TEST-SEGV-01: such a callback never ran for a window freed by the
        cyclic GC and would run mid-destruction otherwise)."""
        if self._quido_signals is None:
            self._quido_signals = QuidoSignals()
            _QUIDO_SIGNALS_ALIVE.append(self._quido_signals)
            self._quido_signals.inputRead.connect(self._on_input_read)
            self._quido_signals.outputRead.connect(self._on_output_read)
            self._quido_signals.jobDone.connect(self._on_output_job_done)
            self._quido_workers = []

    def _ensure_output_worker(self):
        """quido-out: the only place that talks to QUIDO Output - reads,
        manual relay writes and the emergency sequence, one after another."""
        if self._quido_out is None:
            self._ensure_quido_signals()
            hardware = self.hardware  # the worker must not keep the window alive
            self._quido_out = quido_io.QuidoWorker(
                "quido-out", self.hardware.read_output_states, self._quido_signals.outputRead.emit,
                on_job_done=self._quido_signals.jobDone.emit,
                interval=self.QUIDO_POLL_INTERVAL, retry_interval=self.QUIDO_RETRY_INTERVAL,
                after_job_delay=OUTPUT_RECONNECT_WAIT,
                sleep=lambda seconds: hardware.sleep(seconds))
            self._quido_workers.append(self._quido_out)
            self._quido_out.start()
        return self._quido_out

    def shutdown_quido_io(self):
        """Stop both workers: no new QUIDO call starts, a call in progress
        gets a bounded wait (longer for a running emergency sequence); no
        result is shown afterwards. Idempotent."""
        self._quido_stopped = True
        workers = [w for w in (self._quido_in, self._quido_out) if w is not None]
        for worker in workers:
            worker.request_stop()
        timeout = (self.QUIDO_EMERGENCY_STOP_TIMEOUT if self._emergency_worker is not None
                   else self.QUIDO_STOP_TIMEOUT)
        deadline = time.monotonic() + timeout
        stuck = [worker for worker in workers if not worker.join(max(deadline - time.monotonic(), 0))]
        for worker in stuck:
            logger.warning(f"QUIDO {worker.name}: call still running at shutdown - left to its socket timeout")
        if not stuck:
            self._release_quido_signals()
        if self.devQuidoLog is not None:
            self.devQuidoLog.finish()  # DEV-LOG-01: summary - no QUIDO result is shown any more

    def _dev_log_runtime(self):
        """DEV-LOG-01 KONFIG: what really runs - no credentials (the config
        keys go through the whitelist in dev_quido_log). Never fails: an
        attribute not set up yet is just "?"."""
        db_label = getattr(self, "dbLabel", None)
        bypass = getattr(self, "dev_login_bypass", None)
        mock = getattr(self, "mock_quido", None)
        return (
            ("verze", f"Polygon {APP_VERSION}"),
            ("QUIDO", "?" if mock is None else ("MOCK (simulace)" if mock else "REAL")),
            ("přihlášení", "?" if bypass is None else ("VYPNUTO (DEV skip_login)" if bypass else "LDAP")),
            ("uživatel", getattr(self, "current_user", "?")),
            ("databáze", db_label.text().strip() if db_label is not None else "?"),
            ("spuštění", "--dev"),
        )

    def _dev_log_ignored(self, relay, reason):
        if self.devQuidoLog is not None:
            self.devQuidoLog.click_ignored(relay, reason)

    def _release_quido_signals(self):
        """TEST-SEGV-01: once every worker has ended, nothing can emit any
        more - disconnect the window's slots and drop the signal object from
        _QUIDO_SIGNALS_ALIVE (one per window, it never shrank before). With
        a worker still running (stuck call) it stays there on purpose."""
        signals, self._quido_signals = self._quido_signals, None
        if signals is None:
            return
        for signal in (signals.inputRead, signals.outputRead, signals.jobDone):
            try:
                signal.disconnect()
            except TypeError:
                pass  # nothing connected
        if signals in _QUIDO_SIGNALS_ALIVE:
            _QUIDO_SIGNALS_ALIVE.remove(signals)

    def _init_camera(self):
        """Camera indicator and lifecycle bookkeeping - never the Camera
        itself (CAMERA-LIFECYCLE-01): that is created only after the main
        window is shown (_schedule_camera_start). Disabled by config ->
        VYPNUTA (not an error); enabled but unusable (no camera module/
        OpenCV, no URLs) -> CHYBA; otherwise SPOUŠTÍ SE until the start."""
        self.cam = None
        # One retry timer for a failed startRecord() - see _camera_record().
        self._camera_start_in_progress = False
        self._camera_start_request = None  # id of the pending requestRecordStart()
        self._camera_retry_timer = QtCore.QTimer(self)
        self._camera_retry_timer.setInterval(self.CAMERA_RETRY_INTERVAL_MS)
        self._camera_retry_timer.timeout.connect(self._retry_camera_start)
        # Deferred start: a member timer (not QTimer.singleShot) so that
        # closing the window first can cancel it.
        self._camera_start_timer = QtCore.QTimer(self)
        self._camera_start_timer.setSingleShot(True)
        self._camera_start_timer.setInterval(0)
        self._camera_start_timer.timeout.connect(self._start_camera_system)
        self._camera_start_scheduled = False
        self._retiring_cams = []          # switched off, kept alive until `stopped`
        self._camera_restart_pending = False
        self.cameraToggleButton.clicked.connect(self._toggle_camera_system)
        self.showCamerasButton.clicked.connect(self._show_camera_viewer)
        self.openRecordingsButton.clicked.connect(self._open_recordings_folder)
        if not theme.apply_camera_icons((self.showCamerasButton, self.cameraToggleButton), self.openRecordingsButton):
            logger.warning(f"Camera button icon not loaded: {theme.CAMERA_ICON}")
        try:
            if self.conf['CAMERA'].get('disable', True):
                logger.info("Camera system disabled")
                self._set_camera_state(CameraState.DISABLED)
                return
            if self._camera_urls() is not None:
                self._set_camera_state(CameraState.STARTING)
        except Exception as e:
            logger.error(f"Camera initialization failed: {e}")
            self._set_camera_state(CameraState.ERROR, f"Inicializace kamer selhala: {e}")

    def _camera_urls(self):
        """cam1..cam11 from self.conf (the in-memory config, never re-read
        from disk), or None after setting CHYBA when cameras can't run."""
        if not Camera:
            self._set_camera_state(CameraState.ERROR, "Modul kamery není dostupný")
            return None
        cam_urls = [self.conf['CAMERA'][f'cam{i}'] for i in range(1, 12) if f'cam{i}' in self.conf['CAMERA']]
        if not cam_urls:
            logger.error("Camera enabled but no cam1..cam11 URLs configured")
            self._set_camera_state(CameraState.ERROR, "Nejsou nastavené adresy kamer")
            return None
        return cam_urls

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_camera_start()

    def _schedule_camera_start(self):
        """CAMERA-LIFECYCLE-01: the first show of the main window queues the
        camera start on the event loop - once; the GUI is up before any
        camera is touched. Covers MainWindow(show=True) and main()'s
        showMaximized() alike."""
        if self._camera_start_scheduled or self._camera_state is not CameraState.STARTING:
            return
        self._camera_start_scheduled = True
        self._camera_start_timer.start()

    def _start_camera_system(self):
        """Create a NEW Camera (and with it a new CamMatrix + CameraWorkers -
        a stopped one is never restarted) from self.conf['CAMERA'], then
        resync recording with the people INSIDE. Any failure -> CHYBA, the
        rest of the application goes on."""
        if self.cam is not None or self._retiring_cams:
            return  # running, or the previous one is still stopping
        self._set_camera_state(CameraState.STARTING)
        try:
            cam_urls = self._camera_urls()
            if cam_urls is None:
                return
            cam = Camera(
                cam_urls,
                int(self.conf['CAMERA']['width']),
                int(self.conf['CAMERA']['height']),
                self.conf['CAMERA'].get('user'),
                self.conf['CAMERA'].get('password'),
                self,
                allow_mock=mock_camera_enabled(self.conf),
                display_mode=self.conf['CAMERA'].get('display_mode'),
                recording_fps=self.conf['CAMERA'].get('recording_fps'),
            )
            if getattr(cam, 'cam_thread', None) is None:
                cam.deleteLater()  # no thread was started - nothing to wait for
                self._set_camera_state(CameraState.ERROR, "Kamery se nepodařilo inicializovat (OpenCV?)")
                return
            # Queued: the slot never runs inside requestRecordStart() itself
            cam.recordingStartFinished.connect(self._on_camera_record_started, QtCore.Qt.QueuedConnection)

            # Set icon
            icon_path = os.path.join(os.path.dirname(__file__), '../files/video.png')
            if os.path.exists(icon_path):
                cam.setWindowIcon(QtGui.QIcon(icon_path))
            self.cam = cam
            self._set_camera_state(CameraState.READY)
        except Exception as e:
            logger.error(f"Camera initialization failed: {e}")
            self._set_camera_state(CameraState.ERROR, f"Inicializace kamer selhala: {e}")
            return
        self._resync_camera_recording()

    def _resync_camera_recording(self):
        """After a camera start: what the DB says NOW, not the old request -
        recording starts (async) if anyone is INSIDE; unknown count = fail
        safe, record."""
        active_count = self.session.count_all_active()
        if active_count is None:
            logger.warning("Active-session count unavailable - camera recording requested (fail safe)")
        self._camera_record_requested = active_count is None or active_count > 0
        if self._camera_record_requested:
            self._camera_record(True)
        self._refresh_recording_label()

    def _toggle_camera_system(self):
        """Provoz tab button: Vypnout kamery in PŘIPRAVENA/NAHRÁVÁ, Zapnout
        kamery in VYPNUTA/CHYBA (from CHYBA a whole new camera lifecycle)."""
        state = self._camera_state
        if state in (CameraState.READY, CameraState.RECORDING):
            self._stop_camera_system()
        elif state is CameraState.DISABLED:
            self._start_camera_system()
        elif state is CameraState.ERROR:
            if self.cam is None:
                self._start_camera_system()
            else:  # running camera in CHYBA (recording failed): replace it
                self._camera_restart_pending = True
                self._stop_camera_system(confirm=False)

    CAMERA_OFF_CONFIRM_TEXT = ("Uvnitř jsou cvičenci. Vypnutím kamer se zastaví nahrávání.\n"
                               "Opravdu chcete kamery vypnout?")

    def _stop_camera_system(self, confirm=True):
        """Runtime switch-off (never written to polygon.conf). Returns at
        once: VYPÍNÁ SE while Camera.requestShutdown() winds everything down
        in the background; the old Camera is kept referenced until its
        `stopped`, only then deleted -> VYPNUTA. With people INSIDE (or an
        unknown count) it asks first; No changes nothing."""
        if self.cam is None:
            return
        if confirm and self.session.count_all_active() != 0:
            reply = QMessageBox.question(self, 'Vypnout kamery', self.CAMERA_OFF_CONFIRM_TEXT,
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        cam, self.cam = self.cam, None
        self._camera_retry_timer.stop()
        self._camera_start_in_progress = False
        self._camera_start_request = None  # a late start result is ignored
        self._retiring_cams.append(cam)
        self._set_camera_state(CameraState.STOPPING)
        cam.recordingStartFinished.disconnect(self._on_camera_record_started)
        cam.stopped.connect(lambda: self._on_camera_stopped(cam), QtCore.Qt.QueuedConnection)
        cam.hide()  # not close(): Camera.closeEvent would block in shutdown()
        cam.requestShutdown()

    def _on_camera_stopped(self, cam):
        """The switched-off Camera is completely down - now it may go."""
        if cam in self._retiring_cams:
            self._retiring_cams.remove(cam)
        cam.deleteLater()
        if self._retiring_cams or self.cam is not None:
            return
        if self._camera_restart_pending:
            self._camera_restart_pending = False
            self._start_camera_system()
        else:
            self._set_camera_state(CameraState.DISABLED)

    def _set_camera_state(self, state, detail=None):
        """Record the confirmed camera state and show it on the Provoz tab."""
        if state is CameraState.DISABLED and detail is None and getattr(self, "_camera_record_requested", False):
            detail = "Nahrávání požadováno – kamery jsou vypnuté"
        self._camera_state = state
        self.cameraStateLabel.setText(f"KAMERA: {state.value}")
        self.cameraStateLabel.setStyleSheet(_CAMERA_STATE_STYLE[state])
        self.cameraStateLabel.setToolTip(detail or "")
        self._refresh_recording_label()
        on = state in (CameraState.DISABLED, CameraState.ERROR)
        self.cameraToggleButton.setText("Zapnout kamery" if on else "Vypnout kamery")
        self.cameraToggleButton.setEnabled(state not in (CameraState.STARTING, CameraState.STOPPING))
        viewer = state in (CameraState.READY, CameraState.RECORDING) or (
            state is CameraState.ERROR and getattr(self, "cam", None) is not None)
        self.showCamerasButton.setEnabled(viewer)

    def _refresh_recording_label(self):
        """ZÁZNAM line of the Kamery block, from the camera state and the
        record request: recording is automatic while anyone is INSIDE."""
        requested = getattr(self, "_camera_record_requested", False)
        if self._camera_state is CameraState.RECORDING:
            text, style = "NAHRÁVÁ", CameraState.RECORDING
        elif requested and getattr(self, "_camera_start_in_progress", False):
            text, style = "SPOUŠTÍ SE", CameraState.STARTING
        elif requested:  # people INSIDE and nothing records: say so loudly
            text, style = "NENAHRÁVÁ – uvnitř jsou cvičenci", CameraState.ERROR
        else:
            text, style = "ČEKÁ NA VSTUP", CameraState.DISABLED
        self.recordingStateLabel.setText(f"ZÁZNAM: {text}")
        self.recordingStateLabel.setStyleSheet(_CAMERA_STATE_STYLE[style])

    def _show_camera_viewer(self):
        """Zobrazit kamery: the viewer hidden by its X comes back as it was."""
        if self.cam is not None:
            self.cam.showViewer()

    RECORDINGS_OPEN_ERROR_TEXT = "Složku se záznamy se nepodařilo otevřít."

    def _open_recordings_folder(self):
        """Otevřít záznamy: the video/ folder in the desktop's file manager."""
        folder = os.path.abspath(__VIDEO_FOLDER__)
        try:
            os.makedirs(folder, exist_ok=True)
            ok = QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))
        except Exception as e:
            logger.error(f"Opening the recordings folder failed: {e}")
            ok = False
        if not ok:
            logger.error(f"Could not open the recordings folder {folder}")
            QMessageBox.warning(self, 'Záznamy', self.RECORDINGS_OPEN_ERROR_TEXT, QMessageBox.Ok)

    # AUDIO-02: "Zvukové efekty" (pushButton_19) toggles the looped sound.
    DEFAULT_AUDIO_FILE = "../files/audio/fire.wav"  # relative to app/, like [AUDIO] file
    SOUND_DISABLED_CONFIG_TIP = "Zvuk je vypnutý v konfiguraci ([AUDIO] disable = true)."
    SOUND_NO_PLAYER_TIP = "Zvuk nelze přehrát – chybí přehrávač (pw-play, paplay nebo aplay)."
    SOUND_TIP = "Zapnout / vypnout zvukový efekt (hraje dokola, hlasitost = posuvník)"

    def _init_audio(self, audio_factory=Audio):
        """Sound effect button: checkable, speaker icon, green while playing.
        Disabled with a tooltip when [AUDIO] disable = true, the file is
        missing or no player is installed - the app keeps running."""
        self.audio = None
        button = self.pushButton_19
        button.setCheckable(True)
        for filename in theme.apply_relay_icons(self.groupBox, icons=theme.SOUND_ICONS):
            logger.warning(f"Sound button icon not loaded: {os.path.join(theme.ICON_DIR, filename)}")
        theme.set_relay_state(button, False)
        try:
            audio_conf = self.conf.get('AUDIO') or {}
            if audio_conf.get('disable', False):
                logger.info("Audio system disabled")
                self._disable_sound_button(self.SOUND_DISABLED_CONFIG_TIP)
                return
            audio_file = audio_conf.get('file') or self.DEFAULT_AUDIO_FILE
            audio_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), audio_file))
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found: {audio_path}")
                self._disable_sound_button(f"Zvukový soubor nenalezen: {audio_path}")
                return
            audio = audio_factory(audio_path, self)
            if not audio.available:
                self._disable_sound_button(self.SOUND_NO_PLAYER_TIP)
                return
        except Exception as e:
            logger.error(f"Audio initialization failed: {e}")
            self._disable_sound_button(self.SOUND_NO_PLAYER_TIP)
            return
        self.audio = audio
        button.setToolTip(self.SOUND_TIP)
        audio.playingChanged.connect(self._on_sound_playing_changed)
        button.clicked.connect(self._toggle_sound)
        QApplication.instance().aboutToQuit.connect(audio.stop)  # never leave the player running

    def _disable_sound_button(self, tooltip):
        self.pushButton_19.setEnabled(False)
        self.pushButton_19.setToolTip(tooltip)

    def _toggle_sound(self):
        if self._emergency_controls_locked("sound button"):
            return
        if self.audio.is_playing:
            self.audio.stop()
        elif not self.audio.play():
            self._on_sound_playing_changed(False)  # could not start
            self._show_temporary_status("Zvuk se nepodařilo spustit – viz log.")

    def _on_sound_playing_changed(self, playing):
        self.pushButton_19.setChecked(playing)
        theme.set_relay_state(self.pushButton_19, playing)

    # AUDIO-01: volumeSlider -> system output volume (wpctl / pactl)
    VOLUME_APPLY_DELAY_MS = 150  # apply after the slider rests, not on every drag step
    VOLUME_DISABLED_CONFIG_TIP = "Zvuk je vypnutý v konfiguraci ([AUDIO] disable = true)."
    VOLUME_UNAVAILABLE_TIP = ("Ovládání hlasitosti není dostupné – chybí wpctl/pactl "
                              "nebo hlasitost systému nelze načíst.")

    def _init_volume_control(self, system_volume_factory=SystemVolume):
        """volumeSlider (0-100 %) shows and sets the PC's output volume. Disabled
        with a tooltip when [AUDIO] disable = true or no backend works."""
        self.system_volume = None
        self.volumeSlider.setRange(0, 100)
        self._volume_timer = QtCore.QTimer(self)
        self._volume_timer.setSingleShot(True)
        self._volume_timer.setInterval(self.VOLUME_APPLY_DELAY_MS)
        self._volume_timer.timeout.connect(self._apply_volume)
        try:
            if (self.conf.get('AUDIO') or {}).get('disable', False):
                logger.info("Volume control disabled ([AUDIO] disable = true)")
                self._disable_volume_control(self.VOLUME_DISABLED_CONFIG_TIP)
                return
            volume = system_volume_factory()
            current = volume.get() if volume.available else None
            if current is None:
                logger.warning("Volume control disabled: system volume not available")
                self._disable_volume_control(self.VOLUME_UNAVAILABLE_TIP)
                return
        except Exception as e:
            logger.warning(f"Volume control disabled: {e}")
            self._disable_volume_control(self.VOLUME_UNAVAILABLE_TIP)
            return
        self.system_volume = volume
        logger.info(f"Volume control: {volume.backend}, current {current} %")
        self.volumeSlider.blockSignals(True)
        self.volumeSlider.setValue(current)
        self.volumeSlider.blockSignals(False)
        self.volumeSlider.setEnabled(True)
        self.volumeSlider.setToolTip(f"Hlasitost výstupu PC (zesilovač) – {volume.backend}")
        self.volumeLabel.setText(f"{current} %")
        self.volumeSlider.valueChanged.connect(self._on_volume_changed)

    def _disable_volume_control(self, tooltip):
        self.volumeSlider.setEnabled(False)
        self.volumeSlider.setToolTip(tooltip)
        self.volumeLabel.setText("–")
        self.volumeLabel.setToolTip(tooltip)

    def _on_volume_changed(self, value):
        self.volumeLabel.setText(f"{value} %")
        self._volume_timer.start()  # restarts while the slider moves

    def _apply_volume(self):
        if self.system_volume and not self.system_volume.set(self.volumeSlider.value()):
            logger.warning(f"Setting system volume to {self.volumeSlider.value()} % failed")

    def _init_quido_simulator(self):
        """Open the DEV QUIDO simulator window when mock mode is active (also
        with --dev: its changes reach the DEV tab through the normal reads)."""
        if not self.mock_quido:
            self.quido_simulator = None
            return
        try:
            from quido_simulator import QuidoSimulatorDialog
            din_ip = self.conf['QUIDO']['din']
            dout_ip = self.conf['QUIDO']['dout']
            self.quido_simulator = QuidoSimulatorDialog(
                din_ip, dout_ip,
                self.conf.get('QUIDO_IN', {}),
                self.conf.get('QUIDO_OUT', {}),
                self,
            )
            self.quido_simulator.show()
        except Exception as e:
            logger.error(f"Error opening QUIDO simulator: {e}")
            self.quido_simulator = None

    def _on_input_read(self, result):
        """quido-in result (GUI thread); nothing after shutdown."""
        if not self._quido_stopped:
            self._apply_input_read(result)

    def _apply_input_read(self, result):
        """Show one QUIDO Input read (ok, [all Input states] | error) - the
        worker logs the errors. HW-READ-01: the read itself is the
        availability test (no TCP preflight): the status turns OK only after
        it succeeded. The DEV tab gets the same read (DEV-QUIDO-01)."""
        try:
            ok, states = result
            din_ip = self.conf['QUIDO']['din']
            self._set_quido_status(self.qin_status, "Input", din_ip, ok)
            self.polygonMap.set_input_available(ok)  # MAP-01: failed read -> UNKNOWN, no stale states
            if ok:
                for floor, state in self.hardware.map_inputs(states).items():
                    self._update_floor_indicator(floor, state)
            if self.devQuidoTab is not None:
                self.devQuidoTab.show_inputs(states if ok else None)
        except Exception as e:
            logger.error(f"Error showing QUIDO inputs: {e}")

    def _update_floor_indicator(self, floor_name: str, state: bool):
        """Show one QUIDO_IN input on the polygon map (MAP-01)."""
        try:
            # Inverted polarity: QUIDO True (input high) = no step = IDLE,
            # QUIDO False (input low) = step on the segment = ACTIVE.
            self.polygonMap.set_floor_state(floor_name, polygon_map.IDLE if state else polygon_map.ACTIVE)
        except Exception as e:
            logger.warning(f"Error updating floor indicator {floor_name}: {e}")

    def _on_output_read(self, result):
        """quido-out result (GUI thread); nothing after shutdown."""
        if not self._quido_stopped:
            self._apply_output_read(result)

    def _apply_output_read(self, result):
        """Show one QUIDO Output read: ON/OFF per relay button, or UNKNOWN
        (grey, disabled) for all of them when the read failed - never the
        last known state."""
        try:
            ok, states = result
            outputs = self.hardware.map_outputs(states) if ok else {}
            self._set_quido_status(self.qout_status, "Output", self.conf['QUIDO']['dout'], ok)
            self._output_known = ok
            self._output_states = list(states) if ok else None
            for name, button in self._relay_buttons().items():
                state = outputs.get(name) if ok else None
                theme.set_relay_state(button, state)
                button.setToolTip(self.RELAY_UNKNOWN_TOOLTIP if state is None else "")
            self._update_relay_buttons_enabled()
            if self.devQuidoTab is not None:
                self.devQuidoTab.show_outputs(states if ok else None)
        except Exception as e:
            logger.error(f"Error showing QUIDO outputs: {e}")

    def _relay_buttons(self):
        """{QUIDO_OUT name: its button on the Polygon tab}."""
        buttons = {}
        for name in self.conf.get('QUIDO_OUT', {}):
            button = self.tabPolygon.findChild(QPushButton, name + "Button")
            if button:
                buttons[name] = button
        return buttons

    def _update_relay_buttons_enabled(self):
        """A relay button is clickable only with a known Output state and no
        Output operation running. Buttons locked by the emergency mode are
        left alone - unlocking recomputes them."""
        locked = self._emergency_saved_enabled or {}
        enabled = self._output_known and self._output_job is None
        for button in self._relay_buttons().values():
            if button not in locked:
                button.setEnabled(enabled)

    def _relay_name(self, relay):
        """(QUIDO_OUT name, None) of a 1-based relay, or (None, reason) when
        the relay has no name or more than one."""
        names = []
        for name, value in self.conf.get('QUIDO_OUT', {}).items():
            try:
                if int(value) == relay:
                    names.append(name)
            except (TypeError, ValueError):
                continue
        if not names:
            return None, "relé nemá název v [QUIDO_OUT]"
        if len(names) > 1:
            return None, f"relé má v [QUIDO_OUT] více názvů ({', '.join(sorted(names))})"
        return names[0], None

    def click_button(self, relay):
        """HW-IO: hand the write to quido-out and return at once. The relay
        buttons stay disabled until it is done (a click meanwhile is not
        queued); the fresh Output read then shows the result.

        HW-OUT-TOGGLE-01: no GET + invert any more - the wanted state is the
        opposite of the last successful Output read (what the button shows)
        and is written by an explicit SET (HardwareService.set_output_reliable:
        a refused connect is retried, the SET itself never)."""
        if self._emergency_controls_locked(f"relay {relay} click"):
            self._dev_log_ignored(relay, "nouzový režim")
            return
        if self._output_job is not None:
            logger.info(f"Relay {relay} click ignored - an Output operation is running")
            self._dev_log_ignored(relay, "probíhá jiná operace Output")
            return
        states = self._output_states
        if not self._output_known or states is None:
            logger.info(f"Relay {relay} click ignored - QUIDO Output state unknown")
            self._dev_log_ignored(relay, "stav Output neznámý")
            return
        if not 1 <= relay <= len(states):
            logger.error(f"Relay {relay} click ignored - not in the QUIDO Output read ({len(states)} relays)")
            self._dev_log_ignored(relay, "relé mimo poslední čtení Output")
            return
        name, problem = self._relay_name(relay)
        if name is None:
            logger.error(f"Relay {relay} click ignored - {problem}")
            self._dev_log_ignored(relay, problem)
            return
        wanted = not bool(states[relay - 1])
        if self.devQuidoLog is not None:
            self.devQuidoLog.click(relay)
        job = quido_io.OutputJob(f"set relay {relay} {name} {'ON' if wanted else 'OFF'}",
                                 lambda: self.hardware.set_output_reliable(name, wanted))
        job.relay = relay  # DEV-LOG-01: the write result in the DEV log
        if not self._ensure_output_worker().submit(job):
            return
        self._output_job = job
        self._update_relay_buttons_enabled()

    def _on_output_job_done(self, job):
        """A quido-out job finished (GUI thread) - its Output read came first."""
        if self._quido_stopped:
            return
        if job is self._emergency_worker:
            self._on_emergency_done(job.result)
        elif job is self._output_job:
            self._output_job = None
            if self.devQuidoLog is not None:
                self.devQuidoLog.write_done(job.relay, job.error)
            self._update_relay_buttons_enabled()

    # EMERGENCY-01: texts of the emergency button itself (yellow -> red, no separate banner)
    EMERGENCY_BUTTON_TEXT = "Nouzové tlačítko"
    EMERGENCY_BANNER = "NOUZOVÝ REŽIM AKTIVNÍ"
    EMERGENCY_PENDING_BANNER = "NOUZE – AKTIVUJI BEZPEČNÝ STAV…"
    EMERGENCY_ERRORS_TEXT = "S CHYBAMI – STISKNĚTE PRO OPAKOVÁNÍ"
    EMERGENCY_UNREACHABLE_TEXT = "QUIDO OUTPUT NEDOSTUPNÉ"
    EMERGENCY_FAILED_TEXT = "VÝSTUPY QUIDO NENASTAVENY"
    EMERGENCY_UNCONFIRMED = "BEZPEČNÝ STAV NELZE POTVRDIT"
    # Status bar: short texts only - a long permanent label widens the window
    EMERGENCY_STATUS_PENDING = "NOUZE – AKTIVUJI…"
    EMERGENCY_STATUS_ERRORS = "NOUZE – S CHYBAMI"
    EMERGENCY_STATUS_UNREACHABLE = "NOUZE – QUIDO NEDOSTUPNÉ"
    EMERGENCY_STATUS_FAILED = "NOUZE – VÝSTUPY NENASTAVENY"
    EMERGENCY_RETRY_HINT = "Stiskněte nouzové tlačítko znovu pro nový pokus."
    EMERGENCY_EXIT_QUESTION = "Ukončit nouzový režim?"
    EMERGENCY_EXIT_INFO = ("Technologie zůstanou v aktuálním bezpečném stavu.\n"
                           "Běžné ovládání polygonu bude znovu povoleno.")

    # EMERGENCY-01 state (class defaults: tests build MainWindow without __init__)
    emergency_active = False  # declared by the operator (any result), normal controls locked
    emergency_status = None  # last result: emergency.ACTIVE / ACTIVE_WITH_ERRORS / FAILED
    _emergency_worker = None  # quido_io.OutputJob while the emergency sequence is queued/running
    _emergency_audio_step = None
    _emergency_saved_enabled = None  # {control: was enabled} while locked

    def activate_emergency(self):
        """EMERGENCY-01: lock the normal controls, stop the sound (here - the
        player is a QProcess) and queue the fixed output matrix as the next
        quido-out job (HW-IO: after an Output call already running, never
        interrupting it); the result arrives in _on_emergency_done().
        Pressing again re-applies the same state - it never ends the
        emergency mode or restores the old states."""
        if self._emergency_worker is not None:
            logger.info("EMERGENCY: sequence already running - press ignored")
            return
        # The press itself declares the emergency - whatever QUIDO does next.
        # Only "Ukončit nouzový režim" ends it; a repeated press is a retry.
        self.emergency_active = True
        self._lock_normal_controls()
        self.emergencyHelpButton.show()  # stays disabled until EMERGENCY-02
        self.emergencyExitButton.show()
        self.emergencyExitButton.setEnabled(False)  # until this run is finished
        self._show_emergency_banner(self.EMERGENCY_PENDING_BANNER, self.EMERGENCY_STATUS_PENDING, "")
        self._emergency_audio_step = emergency.stop_audio_step(self.audio.stop if self.audio else None)
        self._emergency_worker = quido_io.OutputJob("emergency", self._run_emergency_outputs)
        if not self._ensure_output_worker().submit(self._emergency_worker):
            self._on_emergency_done(None)  # shutting down - never lose the press silently

    def _run_emergency_outputs(self):
        """quido-out thread: the emergency writes; None on a crash."""
        try:
            return emergency.set_emergency_outputs(self.hardware, self.conf)
        except Exception as e:  # never lose the press silently
            logger.error(f"EMERGENCY: sequence crashed: {e!r}")
            return None

    def _on_emergency_done(self, steps):
        """The relay buttons already show the Output read made right after
        the sequence (quido-out reads before it reports a job done)."""
        self._emergency_worker = None
        result = None if steps is None else emergency.EmergencyResult([self._emergency_audio_step] + steps)
        self.emergency_status = emergency.FAILED if result is None else result.status
        logger.warning(f"EMERGENCY: state {self.emergency_status}")
        self._show_emergency_state(result)

    def _show_emergency_state(self, result):
        """Result on the red emergency button (short) + the status bar label
        (visible on every tab); the per-output detail goes to both tooltips."""
        failed = result.failed if result else []
        names = [self._emergency_step_label(step.name) for step in failed]
        tooltip = "\n".join(f"{name}: {step.detail}" for name, step in zip(names, failed))
        # The status bar text stays short (a long permanent label widens the
        # whole window); the details are in the tooltips and the log.
        if self.emergency_status == emergency.ACTIVE:
            text = title = self.EMERGENCY_BANNER
        elif self.emergency_status == emergency.ACTIVE_WITH_ERRORS:
            text = f"{self.EMERGENCY_BANNER}\n{self.EMERGENCY_ERRORS_TEXT}"
            title = self.EMERGENCY_STATUS_ERRORS
            tooltip = f"Nenastaveno:\n{tooltip}\n\n{self.EMERGENCY_RETRY_HINT}"
        else:  # FAILED - still declared, controls stay locked
            problem = (self.EMERGENCY_UNREACHABLE_TEXT if result is not None and result.unreachable
                       else self.EMERGENCY_FAILED_TEXT)
            text = f"{self.EMERGENCY_BANNER}\n{problem}"
            title = (self.EMERGENCY_STATUS_UNREACHABLE if problem == self.EMERGENCY_UNREACHABLE_TEXT
                     else self.EMERGENCY_STATUS_FAILED)
            if result is None:
                detail = "Chyba nouzové sekvence – viz log.\n"
            elif result.unreachable:
                detail = ""  # the whole module - no per-output list of the same reason
            else:
                detail = f"{tooltip}\n"
            tooltip = f"{problem} – {self.EMERGENCY_UNCONFIRMED}.\n{detail}\n{self.EMERGENCY_RETRY_HINT}"
        self._show_emergency_banner(text, title, tooltip)
        self.emergencyExitButton.show()
        self.emergencyExitButton.setEnabled(True)

    def _show_emergency_banner(self, text, title, tooltip):
        """The emergency button turns red with `text`; the status bar shows `title`."""
        self.emergencyButton.setText(text)
        self.emergencyButton.setToolTip(tooltip)
        theme.set_variant(self.emergencyButton, "danger")
        if getattr(self, "emergencyStatusLabel", None) is None:
            self.emergencyStatusLabel = QLabel()
            self.emergencyStatusLabel.setObjectName("emergencyStatusLabel")
            self.statusbar.addPermanentWidget(self.emergencyStatusLabel)
            # The DEV status bar is nearly full (QUIDO x2, DEV MODE, local DB):
            # the grip is useless on the maximized window, its room is not.
            self.statusbar.setSizeGripEnabled(False)
        self.emergencyStatusLabel.setText(f" {title} ")
        self.emergencyStatusLabel.setToolTip(tooltip)
        self.emergencyStatusLabel.show()

    def exit_emergency(self):
        """EMERGENCY-01: after a confirmation only leave the emergency mode -
        hide the banner and unlock the normal controls. No QUIDO write: the
        outputs stay exactly as the emergency sequence set them."""
        if not self.emergency_active or self._emergency_worker is not None:
            return
        reply = QMessageBox.question(self, "Ukončit nouzový režim",
                                     f"{self.EMERGENCY_EXIT_QUESTION}\n\n{self.EMERGENCY_EXIT_INFO}",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        logger.warning("EMERGENCY: emergency mode ended by the operator - outputs left as they are")
        self.emergency_active = False
        self.emergency_status = None
        self.emergencyButton.setText(self.EMERGENCY_BUTTON_TEXT)  # back to the yellow button
        self.emergencyButton.setToolTip("")
        theme.set_variant(self.emergencyButton, "warning")
        self.emergencyHelpButton.hide()
        if getattr(self, "emergencyStatusLabel", None) is not None:
            self.emergencyStatusLabel.hide()
        self.emergencyExitButton.hide()
        self._unlock_normal_controls()

    def _normal_controls(self):
        """Relay buttons of the emergency matrix + Zvukové efekty."""
        buttons = [self.tabPolygon.findChild(QPushButton, name + "Button")
                   for name, _ in emergency.EMERGENCY_OUTPUTS]
        return [button for button in buttons if button] + [self.pushButton_19]

    def _lock_normal_controls(self):
        if self._emergency_saved_enabled is not None:
            return  # already locked
        controls = self._normal_controls()
        self._emergency_saved_enabled = {control: control.isEnabled() for control in controls}
        for control in controls:
            control.setEnabled(False)
            theme.set_emergency_locked(control, True)

    def _unlock_normal_controls(self):
        """Back to exactly the enabled state before the lock (a sound button
        disabled by config stays disabled)."""
        saved, self._emergency_saved_enabled = self._emergency_saved_enabled, None
        for control, enabled in (saved or {}).items():
            control.setEnabled(enabled)
            theme.set_emergency_locked(control, False)
        if self._quido_out is not None:  # HW-IO: relay buttons follow the current Output state
            self._update_relay_buttons_enabled()

    def _emergency_controls_locked(self, what):
        if self._emergency_saved_enabled is None:
            return False
        logger.warning(f"EMERGENCY: {what} ignored - normal controls are locked")
        return True

    def _emergency_step_label(self, name):
        """Operator-facing name: the relay button's text, "Zvuk" for audio."""
        if name == emergency.AUDIO:
            return "Zvuk"
        button = self.tabPolygon.findChild(QPushButton, name + "Button")
        text = " ".join(button.text().split()) if button else ""  # texts have line breaks
        return text or name

    STATUS_MESSAGE_MS = 5000  # how long a temporary status bar message stays

    def _show_temporary_status(self, text):
        """Show text for STATUS_MESSAGE_MS (it covers the version and user
        widgets meanwhile), then clear it again."""
        self._temporary_status = text
        self.statusbar.showMessage(text)
        self._status_timer.start(self.STATUS_MESSAGE_MS)  # restarts on a repeated message

    def _restore_default_status(self):
        # Only if our message is still shown - never overwrite a newer one.
        if self.statusbar.currentMessage() == self._temporary_status:
            self.statusbar.clearMessage()
        self._temporary_status = None

    def show_about(self):
        """UI-ABOUT-01: read-only "O aplikaci" dialog with the changelog."""
        AboutDialog(self).exec_()

    def assign_widgets(self):
        """Assign widgets with error handling."""
        try:
            self.statusbar.addPermanentWidget(self.qin_status)
            self.statusbar.addPermanentWidget(self.qout_status)
            # Left: clickable version (UI-ABOUT-01) and the logged in user.
            # Widgets, not showMessage(): a message would hide the button.
            self.versionButton = make_version_button(self, self.show_about)
            self.statusbar.addWidget(self.versionButton)
            self.userLabel = QLabel(f"|  Přihlášen: {self.current_user}")
            self.userLabel.setObjectName("userLabel")
            self.statusbar.addWidget(self.userLabel)
            # Setup table models
            self._setup_table_models()
            # Connect button signals
            self._connect_buttons()

        except Exception as e:
            logger.error(f"Error assigning widgets: {e}")

    def _setup_table_models(self):
        """Setup table models and views."""
        try:
            # Setup person table with proxy model for filtering
            self.proxy = personFilterProxyModel(self)
            self.proxy.setSourceModel(self.personmodel)
            self.personTableView.setModel(self.proxy)
            self.personTableView.hideColumn(personModel.ID_COLUMN)
            self.personTableView.hideColumn(personModel.VALID_COLUMN)
            theme.style_table(self.personTableView)
            self.personTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.personTableView.setSortingEnabled(True)
            self.personTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            # UX-04: double-click / right-click quick actions - same
            # addMember()/editPerson() the buttons already call.
            self.personTableView.doubleClicked.connect(self._on_person_double_clicked)
            self.personTableView.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.personTableView.customContextMenuRequested.connect(self._on_person_context_menu)

            # Setup member table (Osoby tab: roster administration only -
            # add/remove/update member. No longer the entry/exit selection
            # source; that role moved to sessionTableView, see below.)
            self.memberTableView.setModel(self.membermodel)
            self._hide_member_internal_columns()
            # Same reason as sessionTableView below: columns missing from the
            # model at setModel() time come back visible after setQuery().
            self.membermodel.modelReset.connect(self._hide_member_internal_columns)
            theme.style_table(self.memberTableView)
            self.memberTableView.setItemDelegateForColumn(
                self.membermodel.STAV_COLUMN,
                theme.StavBadgeDelegate(self.membermodel.STAV_CODE_COLUMN, self.memberTableView))
            self.memberTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            # UX-04: double-click / right-click quick actions - same
            # updateMember()/delMember() the buttons already call.
            self.memberTableView.doubleClicked.connect(self._on_member_double_clicked)
            self.memberTableView.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.memberTableView.customContextMenuRequested.connect(self._on_member_context_menu)

            # Setup "who's where" table (Provoz tab): every member of the
            # current training (LEFT JOIN, so PŘIPRAVEN members with no
            # session row yet are included too) - the single selection
            # source for entry/exit actions, replacing memberTableView's
            # former dual role (see doc's own "no second independent list"
            # principle: this isn't a second list, it's a relocation).
            self.sessionTableView.setModel(self.sessionmodel)
            self._hide_session_internal_columns()
            # The empty-state query has 1 column, a real one 9 - the header
            # sections for columns that didn't exist yet come back visible
            # after setQuery(), so re-hide on every model reset.
            self.sessionmodel.modelReset.connect(self._hide_session_internal_columns)
            theme.style_table(self.sessionTableView)
            self.sessionTableView.setItemDelegateForColumn(
                self.sessionmodel.STAV_COLUMN,
                theme.StavBadgeDelegate(self.sessionmodel.STAV_CODE_COLUMN, self.sessionTableView))
            self.sessionTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.sessionTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.sessionTableView.selectionModel().currentRowChanged.connect(self.onMemberSelectionChanged)
            # UX-02: right-click -> Upravit čas průchodu… (secondary; the
            # normal workflow stays Zapsat vstup/výstup = click time).
            self.sessionTableView.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.sessionTableView.customContextMenuRequested.connect(self._on_session_context_menu)

            # Setup training table
            self.trainingTableView.setModel(self.finishedtrainingmodel)
            self.trainingTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.trainingTableView.hideColumn(0)  # Hide idTraining
            theme.style_table(self.trainingTableView)
            self.trainingTableView.setSelectionMode(QAbstractItemView.SingleSelection)
            self.trainingTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            # selectionChanged, not currentRowChanged: Ctrl+click deselects
            # the row without moving the current index (PRINT-01c).
            self.trainingTableView.selectionModel().selectionChanged.connect(self.onTrainingSelectionChanged)

            # Setup training detail table (Balík B): participants of the
            # training selected above, read-only.
            self.trainingDetailTableView.setModel(self.trainingdetailmodel)
            self._hide_training_detail_internal_columns()
            self.trainingdetailmodel.modelReset.connect(self._hide_training_detail_internal_columns)
            self.trainingDetailTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
            theme.style_table(self.trainingDetailTableView)
            self.trainingDetailTableView.setSelectionMode(QAbstractItemView.SingleSelection)
            self.trainingDetailTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.trainingDetailTableView.selectionModel().selectionChanged.connect(self._update_print_buttons)

        except Exception as e:
            logger.error(f"Error setting up table models: {e}")

    def _connect_buttons(self):
        """Connect button signals to their handlers."""
        try:
            # Person management buttons
            self.addPersonButton.clicked.connect(self.addPerson)
            self.editPersonButton.clicked.connect(self.editPerson)
            self.delPersonButton.clicked.connect(self.delPerson)
            self.deletedPersonsButton.clicked.connect(self.showDeletedPersons)  # DATA-02

            # Member management buttons
            self.addMemberButton.clicked.connect(self.addMember)
            self.delMemberButton.clicked.connect(self.delMember)
            self.updateMemberButton.clicked.connect(self.updateMember)

            # Training management buttons
            self.saveTrainingButton.clicked.connect(self.saveTraining)
            self.delTrainingButton.clicked.connect(self.delTraining)

            # PRINT-01c: Zpráva (selected training) / Potvrzení (selected person)
            self.summaryPreviewButton.clicked.connect(self.previewSummary)
            self.summaryPdfButton.clicked.connect(self.exportSummaryPdf)
            self.personPreviewButton.clicked.connect(self.previewPerson)
            self.personPdfButton.clicked.connect(self.exportPersonPdf)
            self._update_print_buttons()  # nothing selected yet -> all four disabled

            # Technology/relay buttons (fans, lights, smoke, etc.)
            for filename in theme.apply_relay_icons(self.tabPolygon):  # GUI-ICONS-01
                logger.warning(f"Relay button icon not loaded: {os.path.join(theme.ICON_DIR, filename)}")
            for name, relay_str in self.conf.get('QUIDO_OUT', {}).items():
                relay = int(relay_str)
                button = self.tabPolygon.findChild(QPushButton, name + "Button")
                if button:
                    theme.set_relay_state(button, None)  # HW-IO: UNKNOWN until the first QUIDO read
                    button.setToolTip(self.RELAY_UNKNOWN_TOOLTIP)
                    button.setEnabled(False)
                    button.clicked.connect(lambda checked, r=relay: self.click_button(r))

            # EMERGENCY-01: not a toggle, every press (re)applies the safe state
            self.emergencyButton.clicked.connect(self.activate_emergency)
            self.emergencyExitButton.clicked.connect(self.exit_emergency)

            # Finish-training button (was the global stopwatch's Stop button)
            self.stopButton.clicked.connect(self.finishTraining)
            self._set_lifecycle_buttons(finish=False, save=False, delete=False)  # until the first real read

            # Individual entry/exit buttons
            self.recordEntryButton.clicked.connect(self.recordEntry)
            self.recordExitButton.clicked.connect(self.recordExit)
            self.onMemberSelectionChanged()  # start with nothing selected -> buttons disabled

            # Search functionality
            self.searchPersonLineEdit.textChanged.connect(self.on_lineEdit_textChanged)

        except Exception as e:
            logger.error(f"Error connecting buttons: {e}")

    # Person management methods
    def addPerson(self):
        """Add new person."""
        try:
            personform = PersonForm(self.personmodel)
            if personform.exec_() == QDialog.Accepted:
                # PERSON-ADD-01: personId is the form's own INSERT id (None
                # if it couldn't be trusted) - never SELECT LAST_INSERT_ID().
                if personform.addMember and personform.personId is not None:
                    self.addMember(personform.personId)

                # Refresh model to show the new person
                self.personmodel.select()
        except Exception as e:
            logger.error(f"Error adding person: {e}")

    def editPerson(self):
        """Edit selected person."""
        try:
            index = self.personTableView.selectionModel().currentIndex()
            if index.isValid():
                row = self.proxy.mapToSource(index).row()
                personform = PersonForm(self.personmodel, row)
                personform.exec_()
            else:
                QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error editing person: {e}")

    def _selected_person(self):
        """(idPerson, "Jméno Příjmení") of the person list's current row,
        or None. The proxy (filter/sort) index is mapped to the source row
        first, so a filtered or re-sorted list always yields the person
        actually shown on that row."""
        index = self.personTableView.selectionModel().currentIndex()
        if not index.isValid():
            return None
        record = self.personmodel.record(self.proxy.mapToSource(index).row())
        return int(record.value("idPerson")), f"{record.value('name')} {record.value('surname')}"

    def person_history_dialog(self):
        """HISTORY-02: the read-only Historie cvičence dialog for the
        selected person, or None if no person is selected."""
        person = self._selected_person()
        if person is None:
            return None
        person_id, name = person
        return PersonHistoryDialog(personHistoryModel(person_id), name, self)

    def showPersonHistory(self):
        """Historie cvičence (person list context menu)."""
        try:
            dialog = self.person_history_dialog()
            if dialog is None:
                QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba', QMessageBox.Ok)
                return
            dialog.exec_()
        except Exception as e:
            logger.error(f"Error showing person history: {e}")

    def delPerson(self):
        """Delete selected person."""
        try:
            index = self.personTableView.selectionModel().currentIndex()
            if index.isValid():
                row = self.proxy.mapToSource(index).row()
                reply = QMessageBox.question(self, 'Smazat', 'Opravdu chcete smazat osobu?',
                                           QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    record = self.personmodel.record(row)
                    record.setValue("valid", 0)
                    self.personmodel.setRecord(row, record)
                    self.personmodel.submitAll()
            else:
                QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba.', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error deleting person: {e}")

    def deleted_persons_dialog(self):
        """DATA-02: the Smazané osoby dialog over a fresh valid=0 person model."""
        deleted_model = personModel(valid=0)
        return DeletedPersonsDialog(
            deleted_model, lambda person_id, name: self.restore_deleted_person(deleted_model, person_id, name), self)

    def showDeletedPersons(self):
        """Smazané osoby… (Osoby tab)."""
        try:
            self.deleted_persons_dialog().exec_()
        except Exception as e:
            logger.error(f"Error showing deleted persons: {e}")

    def restore_deleted_person(self, deleted_model, person_id, name):
        """DATA-02: after a confirmation (default No) set valid 0 -> 1 for
        exactly this idPerson (personModel.restore) and reload the main
        person list. No merging with a same-named active person - the
        schema has no rule for what a duplicate is."""
        reply = QMessageBox.question(self, 'Obnovit osobu', f'Obnovit osobu {name}?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return False
        if not deleted_model.restore(person_id):
            logger.error(f"Restoring person {person_id} failed (DB error or no longer soft-deleted)")
            QMessageBox.warning(self, 'Varování', 'Osobu se nepodařilo obnovit.', QMessageBox.Ok)
            return False
        self.personmodel.select()
        self._show_temporary_status(f"Osoba {name} obnovena.")
        return True

    def on_lineEdit_textChanged(self, text):
        """Filter the person list by the typed text - literal text, not a
        regex (UX-01: "(", ".", "*", "SDH (Město)" are plain characters),
        only in the user-visible columns (personFilterProxyModel)."""
        try:
            self.proxy.setSearchText(text)
        except Exception as e:
            logger.error(f"Error filtering: {e}")

    # Member management methods
    def addMember(self, personId=None):
        """Add member to training."""
        try:
            # If personId is not provided, get it from selected row
            if not personId:
                index = self.personTableView.selectionModel().currentIndex()
                if not index.isValid():
                    QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba', QMessageBox.Ok)
                    return
                row = self.proxy.mapToSource(index).row()
                personId = self.personmodel.record(row).value("idPerson")

            selected_member_id = self._selected_member_id()
            result = self.training.add_member(personId)
            if result.outcome == AddMemberOutcome.ADDED:
                self._refresh_member_roster(result.training_id)
                self.sessionmodel.refresh(result.training_id)
                if selected_member_id is not None:
                    self._reselect_member_row(selected_member_id)
                self._update_inside_count_label(result.training_id)
                self._update_lifecycle_buttons()
            elif result.outcome == AddMemberOutcome.NO_OPEN_TRAINING:
                QMessageBox.warning(self, 'Varování', 'Nelze přidat člena do proběhlého cvičení', QMessageBox.Ok)
            elif result.outcome == AddMemberOutcome.ALREADY_MEMBER:
                QMessageBox.information(self, 'Info', 'Osoba je již v tréninku', QMessageBox.Ok)
            elif result.outcome == AddMemberOutcome.INVALID_PERSON:
                QMessageBox.warning(self, 'Varování', 'Neplatné ID osoby', QMessageBox.Ok)
            # ERROR: already logged inside the service, no further UI action.
        except Exception as e:
            logger.error(f"Error adding member: {e}")

    def delMember(self):
        """Delete member from training."""
        try:
            trainingid = self.training.get_or_create_training()
            if trainingid is None:
                QMessageBox.warning(self, 'Varování', 'Nelze odebrat člena z proběhlého cvičení', QMessageBox.Ok)
                return
            row = self.memberTableView.selectionModel().currentIndex().row()
            idMember = self.membermodel.record(row).value("idMember")
            if idMember is None:
                QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba', QMessageBox.Ok)
                return
            selected_member_id = self._selected_member_id()  # sessionTableView's own selection, may differ from idMember above
            result = self.training.delete_member(trainingid, idMember)
            if result.outcome == DeleteMemberOutcome.BLOCKED_ACTIVE_SESSION:
                QMessageBox.warning(self, 'Varování', 'Nelze odebrat cvičence, dokud je evidován jako uvnitř polygonu.', QMessageBox.Ok)
            elif result.outcome != DeleteMemberOutcome.ERROR:
                self._refresh_member_roster()
                self.sessionmodel.refresh(trainingid)
                if selected_member_id is not None and selected_member_id != idMember:
                    self._reselect_member_row(selected_member_id)
                self._update_inside_count_label(trainingid)
                self._update_lifecycle_buttons()
        except Exception as e:
            logger.error(f"Error deleting member: {e}")

    def updateMember(self):
        """Update member values."""
        try:
            row = self.memberTableView.selectionModel().currentIndex().row()
            if row >= 0:
                member_id = self._selected_roster_member_id()
                memberform = MemberForm(self.membermodel, row)
                memberform.exec_()  # MemberForm reloads membermodel itself on OK
                self._reselect_roster_row(member_id)
            else:
                QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error updating member: {e}")

    # UX-04: double-click / right-click quick actions (personTableView,
    # memberTableView). Only ever call the existing handlers above - no
    # new business logic, same validation/DB/active-session protections.
    def _on_person_double_clicked(self, index):
        """Double-click a row in Osoby's person list -> Přidat cvičence."""
        if select_row_under_cursor(self.personTableView, index):
            self.addMember()

    def _on_member_double_clicked(self, index):
        """Double-click a row in "Osoby v aktuálním cvičení" -> Upravit hodnoty."""
        if select_row_under_cursor(self.memberTableView, index):
            self.updateMember()

    def _on_person_context_menu(self, pos):
        """Right-click in the person list: select the row under the
        cursor first (never a stale previous selection), then offer
        "Přidat do cvičení" / "Upravit osobu" / "Historie cvičence".
        Empty space -> no menu."""
        index = self.personTableView.indexAt(pos)
        if not select_row_under_cursor(self.personTableView, index):
            return
        menu = build_person_context_menu(self.personTableView, self.addMember, self.editPerson,
                                         self.showPersonHistory)
        menu.exec_(self.personTableView.viewport().mapToGlobal(pos))

    def _on_member_context_menu(self, pos):
        """Right-click in the member roster: select the row under the
        cursor first, then offer "Upravit hodnoty" / "Odebrat cvičence"."""
        index = self.memberTableView.indexAt(pos)
        if not select_row_under_cursor(self.memberTableView, index):
            return
        menu = build_member_context_menu(self.memberTableView, self.updateMember, self.delMember)
        menu.exec_(self.memberTableView.viewport().mapToGlobal(pos))

    # Training management methods
    @staticmethod
    def zero_end_pressure_confirm_text(names):
        """PRESS-END-NULL: question before saving a real 0 bar end pressure."""
        if len(names) == 1:
            return (f"{names[0]} má koncový tlak 0 bar.\n\n"
                    "Potvrzujete, že jde o skutečně naměřenou hodnotu?")
        return ("Tito cvičenci mají koncový tlak 0 bar:\n\n" + "\n".join(f"• {n}" for n in names)
                + "\n\nPotvrzujete, že jde o skutečně naměřené hodnoty?")

    def saveTraining(self):
        """Save training. A real 0 bar end pressure is saved only after the
        operator confirms it (default: Ne - the training stays STOPPED and
        the value can still be corrected)."""
        try:
            result = self.training.save()
            if result.outcome == SaveOutcome.CONFIRM_ZERO_END_PRESSURE:
                reply = QMessageBox.question(self, 'Koncový tlak 0 bar',
                                             self.zero_end_pressure_confirm_text(result.zero_end_pressure_names),
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return
                result = self.training.save(confirm_zero_end_pressure=True)
            if result.outcome == SaveOutcome.SAVED:
                self.membermodel.refresh(result.training_id)
                self.finishedtrainingmodel.refresh()
                self._show_training_detail(None)  # the refresh dropped the history selection
                self.sessionmodel.idtraining = None
                self.sessionmodel.view()
                self._update_inside_count_label(None)
                self._update_lifecycle_buttons()
            elif result.outcome in (SaveOutcome.NO_STOPPED_TRAINING, SaveOutcome.VALIDATION_FAILED):
                QMessageBox.warning(self, 'Varování', "\n".join(result.messages), QMessageBox.Ok)
            # ERROR: already logged inside the service, no further UI action.
        except Exception as e:
            logger.error(f"Error saving training: {e}")

    # Confirmation for the destructive Smazat cvičení (default: No).
    DELETE_TRAINING_CONFIRM_TEXT = (
        "Opravdu chcete smazat aktuální cvičení?\n\n"
        "Budou odstraněna data tohoto rozpracovaného cvičení včetně jeho členů a průchodů.\n"
        "Tuto akci nelze vrátit zpět."
    )

    def delTraining(self):
        """Delete training - only after an explicit Ano; Ne (the default)
        touches nothing."""
        try:
            reply = QMessageBox.question(self, 'Smazat cvičení', self.DELETE_TRAINING_CONFIRM_TEXT,
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
            result = self.training.cancel_open_training()
            if result.outcome == CancelTrainingOutcome.CANCELLED:
                self.membermodel.refresh(result.training_id)
                self.sessionmodel.idtraining = None
                self.sessionmodel.view()
                self._update_inside_count_label(None)
                self._update_lifecycle_buttons()
            elif result.outcome == CancelTrainingOutcome.BLOCKED_ACTIVE_SESSIONS:
                QMessageBox.warning(self, 'Varování', 'Nelze smazat cvičení, v polygonu jsou stále evidováni cvičenci.', QMessageBox.Ok)
            # NOTHING_TO_CANCEL / ERROR: no UI action, same as today's silent behavior.
        except Exception as e:
            logger.error(f"Error deleting training: {e}")

    @staticmethod
    def _single_selected_row(view):
        """Row of the one selected row of view, or None (nothing or, should
        SingleSelection ever be bypassed, more than one row selected)."""
        rows = view.selectionModel().selectedRows()
        return rows[0].row() if len(rows) == 1 else None

    def _selected_training_id(self):
        """idTraining (hidden column 0) of the selected Cvičení summary row, or None."""
        row = self._single_selected_row(self.trainingTableView)
        if row is None:
            return None
        return self.finishedtrainingmodel.record(row).value(0)

    def _selected_detail_member_id(self):
        """idMember (hidden column 0) of the selected person in the detail
        table, or None - also None when the detail doesn't belong to the
        currently selected training, so a person of a previously selected
        training can never be printed."""
        training_id = self._selected_training_id()
        if training_id is None or self.trainingdetailmodel.idtraining != training_id:
            return None
        row = self._single_selected_row(self.trainingDetailTableView)
        if row is None:
            return None
        return self.trainingdetailmodel.record(row).value(self.trainingdetailmodel.ID_COLUMN)

    def _show_training_detail(self, training_id):
        self.trainingDetailTableView.clearSelection()
        self.trainingdetailmodel.refresh(training_id)
        self._update_print_buttons()

    def onTrainingSelectionChanged(self, *args):
        """Load the selected saved training's participants below."""
        try:
            self._show_training_detail(self._selected_training_id())
        except Exception as e:
            logger.error(f"Error loading training detail: {e}")

    # -- PRINT-01c: Zpráva / Potvrzení - preview/print and PDF ---------------

    PROTOCOL_DISABLED_TEXT = "Tisk a PDF jsou vypnuté v konfiguraci"

    def _protocol_disabled(self):
        return bool(self.conf.get('PROTOCOL', {}).get('disable', False))

    def _update_print_buttons(self, *args):
        """Zpráva needs one selected training, Potvrzení one selected person
        of that training's detail; [PROTOCOL] disable turns all four off."""
        disabled = self._protocol_disabled()
        summary = not disabled and self._selected_training_id() is not None
        person = not disabled and self._selected_detail_member_id() is not None
        tooltip = self.PROTOCOL_DISABLED_TEXT if disabled else ""
        for button, enabled in ((self.summaryPreviewButton, summary), (self.summaryPdfButton, summary),
                                (self.personPreviewButton, person), (self.personPdfButton, person)):
            button.setEnabled(enabled)
            button.setToolTip(tooltip)

    def _protocol_document(self, person):
        """(ProtocolData, html, member_id) for the current selection, or
        None after telling the operator why nothing can be printed. Same
        checks as _update_print_buttons() - the handlers may be called
        with the buttons disabled (programmatically)."""
        if self._protocol_disabled():
            QMessageBox.information(self, 'Info', self.PROTOCOL_DISABLED_TEXT, QMessageBox.Ok)
            return None
        training_id = self._selected_training_id()
        if training_id is None:
            QMessageBox.warning(self, 'Varování', 'Není vybráno žádné cvičení', QMessageBox.Ok)
            return None
        member_id = None
        if person:
            member_id = self._selected_detail_member_id()
            if member_id is None:
                QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba vybraného cvičení', QMessageBox.Ok)
                return None
        # Own query per action - self.query is shared with the services.
        data = load_protocol_data(QtSql.QSqlQuery(), training_id)
        if data is None:
            raise ValueError(f"Cvičení {training_id} nebylo nalezeno")
        if person:
            html = build_person_html(data, member_id, self.current_user, date.today(), self.site)
        else:
            html = build_summary_html(data, self.current_user, date.today(), self.site)
        return data, html, member_id

    def _protocol_orientation(self, person):
        """PRINT-02 corrective: the summary table is too wide for A4
        portrait; the individual confirmation isn't. Same orientation for
        preview, PDF export and physical printing (all go through protocol.py)."""
        return protocol.PERSON_ORIENTATION if person else protocol.SUMMARY_ORIENTATION

    def _preview_protocol(self, person):
        try:
            document = self._protocol_document(person)
            if document is not None:
                protocol.show_preview(document[1], self, logo_path=protocol.site_logo_path(self.site),
                                      orientation=self._protocol_orientation(person))
        except Exception as e:
            logger.error(f"Error printing protocol: {e}")
            QMessageBox.warning(self, 'Chyba', f'Chyba při tisku: {e}', QMessageBox.Ok)

    def _export_protocol_pdf(self, person):
        try:
            document = self._protocol_document(person)
            if document is None:
                return
            data, html, member_id = document
            name = data.participant(member_id).name if person else None
        except Exception as e:
            logger.error(f"Error exporting protocol PDF: {e}")
            QMessageBox.warning(self, 'Chyba', f'PDF se nepodařilo uložit: {e}', QMessageBox.Ok)
            return
        self._save_pdf(html, pdf_filename(data.training_id, data.date, name), self._protocol_orientation(person),
                       "protocol")

    def _save_pdf(self, html, filename, orientation, what):
        """Uložit PDF for the protocols and the logbook (LOGBOOK-02): ask
        where (last directory of this run), then export via protocol.py."""
        try:
            directory = self._last_pdf_dir or os.path.expanduser("~")
            path, _ = QFileDialog.getSaveFileName(self, 'Uložit PDF', os.path.join(directory, filename),
                                                  'PDF (*.pdf)')
            if not path:
                return  # dialog cancelled
            if not path.lower().endswith('.pdf'):
                path += '.pdf'
            protocol.export_pdf(html, path, logo_path=protocol.site_logo_path(self.site), orientation=orientation)
            self._last_pdf_dir = os.path.dirname(path)  # remembered for this run only
            self._show_temporary_status(f"PDF uloženo: {path}")
        except Exception as e:
            logger.error(f"Error exporting {what} PDF: {e}")
            QMessageBox.warning(self, 'Chyba', f'PDF se nepodařilo uložit: {e}', QMessageBox.Ok)

    def previewSummary(self):
        self._preview_protocol(person=False)

    def exportSummaryPdf(self):
        self._export_protocol_pdf(person=False)

    def previewPerson(self):
        self._preview_protocol(person=True)

    def exportPersonPdf(self):
        self._export_protocol_pdf(person=True)

    def closeEvent(self, event):
        """Handle application close event. Closing the app and deleting a
        training are separate operations now - this never deletes anything;
        get_or_create_training() correctly resumes the same open training/
        members/sessions on next launch."""
        try:
            active = self.training.has_active_sessions()
            if active is None:
                msg = self.CLOSE_STATE_UNKNOWN_TEXT
            elif active:
                msg = "Existují cvičenci evidovaní jako UVNITŘ. Opravdu chcete aplikaci ukončit?"
            else:
                msg = "Opravdu chcete ukončit program?"
            reply = QMessageBox.question(self, 'Zavřít', msg, QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._camera_start_timer.stop()  # closed before the deferred start: no Camera at all
                self.shutdown_quido_io()
                self.hardware.close()
                # REPORT-01: the one correct exit - confirmed, shut down cleanly
                self.exit_inside = active
                self.exit_confirmed = True
                event.accept()
            else:
                event.ignore()
        except Exception as e:
            logger.error(f"Error in close event: {e}")
            self.exit_confirmed = False  # REPORT-01: no report after a failed close
            self._camera_start_timer.stop()
            event.accept()  # Close anyway if there's an error

    # Training completion
    def finishTraining(self):
        """Mark the open training as STOPPED (awaiting per-member pressure/
        volume entry + save)."""
        try:
            result = self.training.finish_training()
            if result.outcome == FinishTrainingOutcome.FINISHED:
                self._update_lifecycle_buttons()
            elif result.outcome == FinishTrainingOutcome.BLOCKED_ACTIVE_SESSIONS:
                QMessageBox.warning(self, 'Varování', 'Nelze dokončit cvičení, v polygonu jsou stále evidováni cvičenci.', QMessageBox.Ok)
            elif result.outcome == FinishTrainingOutcome.NOT_READY:
                QMessageBox.warning(self, 'Varování', 'Cvičení není připraveno k dokončení.', QMessageBox.Ok)
            # ERROR: already logged inside the service, no further UI action.
        except Exception as e:
            logger.error(f"Error finishing training: {e}")

    # Individual polygon-pass (exercise_session) methods
    def _selected_member_id(self):
        """idMember of the currently selected sessionTableView ("who's
        where") row, or None. sessionTableView is the entry/exit selection
        source since Etapa 8.2 - it covers every member of the training
        (PŘIPRAVEN/UVNITŘ/DOKONČEN alike), unlike memberTableView which
        stays admin-only on the Osoby tab."""
        row = self.sessionTableView.selectionModel().currentIndex().row()
        if row < 0:
            return None
        return self.sessionmodel.record(row).value("idMember")

    def onMemberSelectionChanged(self, *args):
        """Refresh the entry/exit controls for the current sessionTableView
        selection: show who is selected and enable only the action that's
        valid for the member's real session status."""
        try:
            member_id = self._selected_member_id()
            if member_id is not None:
                row = self.sessionTableView.selectionModel().currentIndex().row()
                name = self.sessionmodel.record(row).value("name")
                self.selectedMemberLabel.setText(str(name))
                self._update_entry_exit_button_states(member_id)
            else:
                self.selectedMemberLabel.setText("Vyberte cvičence v tabulce výše")
                self.recordEntryButton.setEnabled(False)
                self.recordExitButton.setEnabled(False)
        except Exception as e:
            logger.error(f"Error updating member selection: {e}")

    def _update_entry_exit_button_states(self, member_id):
        """Enable only the entry/exit action that's actually valid for the
        member's current session status (READY/INSIDE/DONE), instead of
        leaving both always clickable and relying solely on SessionService's
        rejection outcomes to tell the operator afterwards."""
        try:
            existing = self.session_repository.find_latest_session_for_member(member_id)
            status = existing[3] if existing is not None else SessionStatus.READY
        except Exception as e:
            logger.error(f"Error reading session status: {e}")
            # DB state unknown - fail closed (disable both) rather than
            # guessing READY, which would let the operator attempt an
            # entry the app has no actual read on.
            self.recordEntryButton.setEnabled(False)
            self.recordExitButton.setEnabled(False)
            return
        self.recordEntryButton.setEnabled(status == SessionStatus.READY)
        self.recordExitButton.setEnabled(status == SessionStatus.INSIDE)

    def _reselect_member_row(self, member_id):
        """sessionmodel.refresh() calls QSqlQueryModel.setQuery(), which
        rebuilds the model and drops whatever row was selected in
        sessionTableView. Re-find and re-select member_id's row afterward,
        with selection signals blocked so this doesn't re-trigger a full
        onMemberSelectionChanged() - callers refresh the button states
        themselves."""
        for row in range(self.sessionmodel.rowCount()):
            if self.sessionmodel.record(row).value("idMember") == member_id:
                selection_model = self.sessionTableView.selectionModel()
                selection_model.blockSignals(True)
                try:
                    self.sessionTableView.selectRow(row)
                finally:
                    selection_model.blockSignals(False)
                return

    def _selected_roster_member_id(self):
        """idMember of the selected memberTableView (Osoby) row, or None."""
        row = self.memberTableView.selectionModel().currentIndex().row()
        if row < 0:
            return None
        return self.membermodel.record(row).value("idMember")

    def _reselect_roster_row(self, member_id):
        """memberTableView counterpart of _reselect_member_row(): a
        membermodel reload drops the selection and may reorder rows (they
        are sorted by stav), so re-find the member by id."""
        if member_id is None:
            return
        for row in range(self.membermodel.rowCount()):
            if self.membermodel.record(row).value("idMember") == member_id:
                self.memberTableView.selectRow(row)
                return

    def _refresh_member_roster(self, training_id=None):
        """Reload the Osoby roster (stav included), keeping its selection.
        training_id=None reloads the training membermodel already shows."""
        member_id = self._selected_roster_member_id()
        if training_id is None:
            self.membermodel.view()
        else:
            self.membermodel.refresh(training_id)
        self._reselect_roster_row(member_id)

    def _refresh_after_session_change(self):
        member_id = self._selected_member_id()  # capture before refresh() drops the selection
        trainingid = self.training.get_or_create_training()
        if trainingid is not None:
            self._refresh_member_roster(trainingid)  # Osoby Stav column
            self.sessionmodel.refresh(trainingid)
            if member_id is not None:
                self._reselect_member_row(member_id)
            self._update_inside_count_label(trainingid)
        elif self.trainingmodel.load_failed():
            # None here is either a STOPPED training (table isn't
            # refreshed then either - label stays as is) or a DB error,
            # in which case the label must not keep showing a
            # now-unverified count.
            self._show_inside_count_unknown()
        if member_id is not None:
            self._update_entry_exit_button_states(member_id)
        self._sync_camera_record_request(self.session.count_all_active())
        self._update_lifecycle_buttons()

    def _sync_camera_record_request(self, active_count):
        """Request recording while anyone is INSIDE, stop when nobody is -
        commanded only on a change, so one member's exit doesn't stop
        recording while someone else is still inside.

        active_count=None (DB error) means unknown, not 0: never stops
        recording, and requests it if not already requested (fail safe -
        an unneeded recording is cheaper than a missing one). The next
        successful read settles it to the real count.

        _camera_record_requested tracks what was commanded, not a
        confirmed camera state - _camera_record() doesn't report whether
        startRecord() actually succeeded (that's Etapa 8.4)."""
        if active_count is None:
            logger.warning("Active-session count unavailable - camera recording kept/requested (fail safe)")
            wanted = True
        else:
            wanted = active_count > 0
        if wanted != self._camera_record_requested:
            self._camera_record(wanted)
            self._camera_record_requested = wanted
            if self._camera_state is CameraState.DISABLED:
                self._set_camera_state(CameraState.DISABLED)  # tooltip follows the request
            self._refresh_recording_label()

    def recordEntry(self):
        """Record polygon entry for the selected member at the time of the
        click (WAVE2-02: SessionService's own now(), no GUI time field)."""
        try:
            member_id = self._selected_member_id()
            if member_id is None:
                QMessageBox.warning(self, 'Varování', 'Není vybrán žádný cvičenec', QMessageBox.Ok)
                return
            result = self.session.record_entry(member_id, source='MANUAL')
            if result.outcome == EntryOutcome.RECORDED:
                self._refresh_after_session_change()
            elif result.outcome == EntryOutcome.ALREADY_INSIDE:
                QMessageBox.information(self, 'Info', 'Cvičenec je již evidován jako uvnitř polygonu.', QMessageBox.Ok)
            elif result.outcome == EntryOutcome.ALREADY_DONE:
                QMessageBox.information(self, 'Info', 'Cvičenec již průchod polygonem dokončil.', QMessageBox.Ok)
            elif result.outcome == EntryOutcome.ERROR:
                QMessageBox.critical(self, 'Chyba', 'Nepodařilo se zaznamenat vstup. Zkontrolujte databázi / log.', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error recording entry: {e}")
            QMessageBox.critical(self, 'Chyba', 'Nepodařilo se zaznamenat vstup. Zkontrolujte databázi / log.', QMessageBox.Ok)

    def recordExit(self):
        """Record polygon exit for the selected member at the time of the
        click (WAVE2-02: SessionService's own now(), no GUI time field)."""
        try:
            member_id = self._selected_member_id()
            if member_id is None:
                QMessageBox.warning(self, 'Varování', 'Není vybrán žádný cvičenec', QMessageBox.Ok)
                return
            result = self.session.record_exit(member_id)
            if result.outcome == ExitOutcome.RECORDED:
                self._refresh_after_session_change()
            elif result.outcome == ExitOutcome.NO_ENTRY:
                QMessageBox.warning(self, 'Varování', 'Cvičenec ještě nemá zaznamenaný vstup.', QMessageBox.Ok)
            elif result.outcome == ExitOutcome.ALREADY_DONE:
                QMessageBox.information(self, 'Info', 'Cvičenec již průchod polygonem dokončil.', QMessageBox.Ok)
            elif result.outcome == ExitOutcome.EXIT_BEFORE_ENTRY:
                QMessageBox.warning(self, 'Varování', 'Čas výstupu nemůže být dříve než čas vstupu.', QMessageBox.Ok)
            elif result.outcome == ExitOutcome.ERROR:
                QMessageBox.critical(self, 'Chyba', 'Nepodařilo se zaznamenat výstup. Zkontrolujte databázi / log.', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error recording exit: {e}")
            QMessageBox.critical(self, 'Chyba', 'Nepodařilo se zaznamenat výstup. Zkontrolujte databázi / log.', QMessageBox.Ok)

    # UX-02: manual correction of a recorded passage time ----------------

    TIME_CORRECTION_MESSAGES = {
        TimeCorrectionOutcome.NO_SESSION: "Cvičenec ještě nemá zapsaný vstup – není co opravovat.",
        TimeCorrectionOutcome.NOT_STARTED: "Cvičenec ještě nemá zapsaný vstup – není co opravovat.",
        TimeCorrectionOutcome.TRAINING_SAVED: "Cvičení je už uložené – čas průchodu nelze upravit.",
        TimeCorrectionOutcome.MISSING_TIME: "Vyplňte čas vstupu i výstupu.",
        TimeCorrectionOutcome.EXIT_NOT_RECORDED: "Cvičenec je uvnitř – výstup zatím nelze upravit.",
        TimeCorrectionOutcome.INVALID_TIME_ORDER: "Čas výstupu nemůže být dříve než čas vstupu.",
    }
    TIME_CORRECTION_ERROR = "Čas průchodu se nepodařilo upravit. Zkontrolujte databázi / log."

    def _on_session_context_menu(self, pos):
        """Right-click in the Provoz table: select the row under the cursor
        first (never a stale selection), then offer Upravit čas průchodu…
        - disabled for PŘIPRAVEN. Empty space -> no menu."""
        index = self.sessionTableView.indexAt(pos)
        if not select_row_under_cursor(self.sessionTableView, index):
            return
        can_edit = self.sessionmodel.data(
            self.sessionmodel.index(index.row(), self.sessionmodel.STAV_CODE_COLUMN)) in (
            SessionStatus.INSIDE, SessionStatus.DONE)
        menu = build_session_context_menu(self.sessionTableView, self.editPassageTime, can_edit)
        menu.exec_(self.sessionTableView.viewport().mapToGlobal(pos))

    def passage_time_dialog(self):
        """UX-02: the correction dialog for the selected Provoz row, or None
        (nothing selected / PŘIPRAVEN - there is nothing to correct)."""
        member_id = self._selected_member_id()
        if member_id is None:
            return None
        existing = self.session_repository.find_latest_session_for_member(member_id)
        if existing is None or existing[3] == SessionStatus.READY or existing[1] is None:
            return None
        _, entry_at, exit_at, status = existing
        row = self.sessionTableView.selectionModel().currentIndex().row()
        name = self.sessionmodel.record(row).value("name")
        return PassageTimeDialog(name, entry_at, exit_at if status == SessionStatus.DONE else None,
                                 lambda entry, exit_: self._save_passage_time(member_id, entry, exit_), self)

    def _save_passage_time(self, member_id, entry_at, exit_at):
        """PassageTimeDialog save callback: True = saved (dialog closes)."""
        result = self.session.correct_times(member_id, entry_at, exit_at)
        if result.outcome == TimeCorrectionOutcome.UPDATED:
            self._refresh_after_time_correction(member_id)
            return True
        if result.outcome == TimeCorrectionOutcome.ERROR:
            QMessageBox.critical(self, 'Chyba', self.TIME_CORRECTION_ERROR, QMessageBox.Ok)
        else:
            QMessageBox.warning(self, 'Varování', self.TIME_CORRECTION_MESSAGES[result.outcome], QMessageBox.Ok)
        return False

    def editPassageTime(self):
        """Upravit čas průchodu… (Provoz context menu)."""
        try:
            if self._selected_member_id() is None:
                QMessageBox.warning(self, 'Varování', 'Není vybrán žádný cvičenec', QMessageBox.Ok)
                return
            dialog = self.passage_time_dialog()
            if dialog is None:
                QMessageBox.information(self, 'Info', self.TIME_CORRECTION_MESSAGES[TimeCorrectionOutcome.NOT_STARTED],
                                        QMessageBox.Ok)
                return
            dialog.exec_()
        except Exception as e:
            logger.error(f"Error editing passage time: {e}")
            QMessageBox.critical(self, 'Chyba', self.TIME_CORRECTION_ERROR, QMessageBox.Ok)

    def _refresh_after_time_correction(self, member_id):
        """Reload only what shows the corrected times: Provoz (Vstup/Výstup/
        Doba) and the Osoby roster (Spotřeba). Unlike
        _refresh_after_session_change() it never touches the stav-driven
        parts (inside count, camera, QUIDO, lifecycle buttons) - a time
        correction changes no status - and it also works after Dokončit
        cvičení (STOPPED), where get_or_create_training() returns None."""
        self.sessionmodel.refresh()          # keeps its current idtraining
        self._reselect_member_row(member_id)
        self._refresh_member_roster()        # membermodel.view(): same training
        self._update_entry_exit_button_states(member_id)

    def _camera_record(self, start: bool):
        """Start/stop camera recording, called by _sync_camera_record_request()
        only when the requested state changes. Records the *confirmed*
        outcome in _camera_state (the Provoz indicator): only a start that
        reports success counts as NAHRÁVÁ - anything else (failure, an
        exception) is CHYBA. No camera (disabled or failed init) ->
        nothing to command, state stays as set by _init_camera(), and no
        retry.

        CAMERA-START-01: a start never waits for the VideoWriter to open -
        requestRecordStart() returns at once and the outcome comes to
        _on_camera_record_started(). While one is pending no second start
        is made; a stop cancels it (its late result is ignored).

        A failed start arms _camera_retry_timer (the one timer, never a
        second): _retry_camera_start() tries again every
        CAMERA_RETRY_INTERVAL_MS until a start succeeds or recording is
        no longer wanted. A stop command disarms it immediately."""
        if not start:
            self._camera_retry_timer.stop()
            self._camera_start_in_progress = False
            self._camera_start_request = None
        if self.cam is None:
            return
        if start:
            if self._camera_start_in_progress:
                return  # never overlap start attempts
            self._camera_start_in_progress = True
            self._refresh_recording_label()
            try:
                self._camera_start_request = self.cam.requestRecordStart(__VIDEO_FOLDER__)
            except Exception as e:
                logger.error(f"Error controlling camera recording: {e}")
                self._camera_start_in_progress = False
                self._camera_start_request = None
                self._camera_record_result(True, False)
            return
        try:
            ok = self.cam.stopRecord() is True
        except Exception as e:
            logger.error(f"Error controlling camera recording: {e}")
            ok = False
        self._camera_record_result(False, ok)

    def _on_camera_record_started(self, request, ok):
        """Camera.recordingStartFinished slot - the outcome of the pending
        start. A result for anything but the current request (a stop or
        shutdown came in between) changes nothing."""
        if request != self._camera_start_request or not self._camera_start_in_progress:
            return
        self._camera_start_in_progress = False
        self._camera_start_request = None
        if not self._camera_record_requested or self.cam is None:
            return
        self._camera_record_result(True, ok)

    def _camera_record_result(self, start, ok):
        """Confirmed outcome of a start/stop -> indicator, retry, icon."""
        if not ok:
            if start:
                if not self._camera_retry_timer.isActive():
                    self._camera_retry_timer.start()
                detail = (f"Nahrávání se nepodařilo spustit - další pokus za "
                          f"{self.CAMERA_RETRY_INTERVAL_MS // 1000} s")
            else:
                detail = "Nahrávání se nepodařilo zastavit"
            logger.error(detail)
            self._set_camera_state(CameraState.ERROR, detail)
            return
        if start:
            self._camera_retry_timer.stop()
        self._set_camera_state(CameraState.RECORDING if start else CameraState.READY)
        try:
            icon = '../files/video-recording.png' if start else '../files/video.png'
            self.cam.setWindowIcon(QtGui.QIcon(os.path.join(__APP_DIR__, icon)))
        except Exception as e:
            logger.error(f"Error updating camera window icon: {e}")

    def _retry_camera_start(self):
        """_camera_retry_timer slot: retry a failed start while recording is
        still wanted; disarm otherwise."""
        if not self._camera_record_requested or self.cam is None or self._camera_state is CameraState.RECORDING:
            self._camera_retry_timer.stop()
            return
        logger.info("Retrying camera recording start")
        self._camera_record(True)


class LoginDialog(QDialog, Ui_Login_Dialog):
    """Login dialog with LDAP authentication."""

    def __init__(self, ldap_config: dict):
        super().__init__()
        self.setupUi(self)
        self.ldap_config = ldap_config
        self.username = None  # Store username for later use
        self.display_name = None  # Store display name for later use

        # Connect signals
        self.buttonBox.accepted.connect(self.handle_login)
        self.buttonBox.rejected.connect(self.handle_cancel)

        # Set password field
        self.passwordLineEdit.setEchoMode(self.passwordLineEdit.Password)
        self.passwordLineEdit.clear()

    def handle_login(self):
        """Handle login attempt."""
        try:
            username = self.userLineEdit.text().strip()
            password = self.passwordLineEdit.text()

            # Clear password field immediately
            self.passwordLineEdit.clear()

            if not username or not password:
                QMessageBox.warning(self, 'Chyba přihlášení', 'Zadejte uživatelské jméno a heslo.')
                return

            # Attempt LDAP authentication
            if self._authenticate_ldap(username, password):
                logger.info(f"Successful login for user: {username}")
                self.username = username  # Store username for later use
                self.accept()
            else:
                QMessageBox.warning(self, 'Chyba přihlášení', 'Nesprávné přihlašovací údaje nebo nedostatečná oprávnění.')

        except Exception as e:
            logger.error(f"Login error: {e}")
            QMessageBox.warning(self, 'Chyba přihlášení', 'Došlo k chybě při přihlašování.')

    def _authenticate_ldap(self, username: str, password: str) -> bool:
        """Authenticate user against LDAP."""
        try:
            # Create LDAP connection
            server = ldap3.Server(self.ldap_config['host'])
            conn = ldap3.Connection(
                server,
                self.ldap_config['username'],
                self.ldap_config['password'],
                auto_bind=True
            )

            # Search for user
            search_filter = f'(&(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2))(!(objectClass=computer))(sAMAccountName={username}))'

            conn.search(
                self.ldap_config['base'],
                search_filter,
                ldap3.SUBTREE,
                attributes=['displayName']
            )

            if not conn.entries:
                return False

            user_dn = conn.entries[0].entry_dn

            # Get display name if available
            if hasattr(conn.entries[0], 'displayName') and conn.entries[0].displayName.value:
                self.display_name = conn.entries[0].displayName.value
            else:
                self.display_name = username  # Fallback to username

            # Test user password
            user_conn = ldap3.Connection(server, user_dn, password)
            if not user_conn.bind():
                return False

            # Check group membership
            conn.search(
                self.ldap_config['group'],
                '(objectClass=group)',
                ldap3.SUBTREE,
                attributes=['member']
            )

            if conn.entries and hasattr(conn.entries[0], 'member'):
                for member in conn.entries[0].member.values:
                    if user_dn.lower() == member.lower():
                        return True

            return False

        except Exception as e:
            logger.error(f"LDAP authentication error: {e}")
            return False

    def handle_cancel(self):
        """Handle login cancellation."""
        self.passwordLineEdit.clear()
        self.userLineEdit.clear()
        self.reject()


NORMAL_WINDOW_FRACTION = 0.85


def normal_window_geometry(available, minimum):
    """WINDOW-RESPONSIVE-01: restore geometry of the main window - about
    85 % of the work area, centered in it, never below the layout minimum
    (a minimum larger than the work area is left visible, not masked)."""
    size = QtCore.QSize(max(int(available.width() * NORMAL_WINDOW_FRACTION), minimum.width()),
                        max(int(available.height() * NORMAL_WINDOW_FRACTION), minimum.height()))
    rect = QtCore.QRect(QtCore.QPoint(0, 0), size)
    rect.moveCenter(available.center())
    return rect


def _install_qt_translations(app):
    """Czech texts for Qt's own widgets (Uložit/Zrušit, Ano/Ne in message
    boxes). Missing translation files just leave them in English."""
    translator = QtCore.QTranslator(app)
    path = QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.TranslationsPath)
    if translator.load("qtbase_cs", path):
        app.installTranslator(translator)
    else:
        logger.info(f"Qt Czech translation (qtbase_cs) not found in {path}")


class CtrlCQuit:
    """Ctrl+C in the terminal ends the application (Linux habit). Without
    this, Python turns SIGINT into a KeyboardInterrupt inside the next slot
    (e.g. a QUIDO result slot), PyQt just prints it and the app keeps running.
    quit() leaves every running event loop - main loop, the boot splash's
    waits, the login dialog; main() checks requested and finishes. A short
    timer lets the interpreter run the handler even while Qt is idle."""

    WAKE_MS = 250

    def __init__(self, app):
        self.requested = False
        self._app = app
        self._wake = QtCore.QTimer()
        self._wake.timeout.connect(lambda: None)
        self._wake.start(self.WAKE_MS)
        signal.signal(signal.SIGINT, self._handle)

    def _handle(self, signum, frame):
        logger.info("Ctrl+C - quitting the application")
        self.requested = True
        self._app.quit()


# DEV-QUIDO-01: ./bin/polygon --dev adds the read-only DEV tab (QUIDO
# diagnostics). Only this explicit argument - [DEV] in the config never does.
DEV_TAB_ARG = "--dev"


def dev_tab_requested(argv) -> bool:
    return DEV_TAB_ARG in argv[1:]


def start_exit_report(config, main_window):
    """REPORT-01 for this run (None = off): its first-run baseline is made
    now. Never raises - the report must never stop the application."""
    try:
        report = exit_report.create(config, QtSql.QSqlDatabase.database(open=False),
                                    main_window.operation_log, APP_VERSION)
        if report is not None:
            report.start()
        return report
    except Exception as e:
        logger.error(f"REPORT-01: e-mail report not started ({type(e).__name__})")
        return None


def run_exit_report(report, main_window, ctrl_c, config, started_at):
    """After the main loop: only after a confirmed closeEvent, never after
    Ctrl+C (closeEvent did not run). Returns the outcome (None = not run);
    never raises, so the exit code stays as it was."""
    if report is None or ctrl_c.requested or not main_window.exit_confirmed:
        return None
    try:
        info = exit_report.ExitInfo(
            started_at, datetime.now(), main_window.current_user, socket.gethostname(), APP_VERSION,
            main_window.dbLabel.text().strip(), main_window.dbLabel.property("db") == "local",
            exit_report.is_dev_mode(config), main_window.exit_inside)
        return report.run(info)
    except Exception as e:
        logger.error(f"REPORT-01: report failed ({type(e).__name__})")
        return exit_report.FAILED


def main():
    """Main entry point."""
    enable_crash_log()  # native crashes (e.g. inside Qt) -> log/crash.log
    started_at = datetime.now()  # REPORT-01: "Spuštění aplikace"
    boot = None  # SPLASH-01 boot splash, closed before any error dialog
    try:
        # Initialize Qt application; --dev is ours, Qt never sees it
        dev_tab = dev_tab_requested(sys.argv)
        app = QApplication([arg for arg in sys.argv if arg != DEV_TAB_ARG])
        app.setApplicationName("Polygon Control System")
        app.setApplicationVersion(APP_VERSION)
        theme.apply_theme(app)
        _install_qt_translations(app)
        ctrl_c = CtrlCQuit(app)

        # Load configuration
        try:
            app_dir = os.path.dirname(__file__)
            config_file = os.path.join(app_dir, "../config/polygon.conf")

            config_manager = ConfigManager(config_file)
            config = config_manager.load_config()

        except ConfigurationError as e:
            QMessageBox.critical(None, 'Chyba konfigurace', str(e))
            return 1

        # Login (LDAP), or the [DEV] skip_login bypass - see run_login()
        login = run_login(config)
        if login is None or ctrl_c.requested:
            logger.info("User cancelled login")
            return 0
        display_name, dev_login_bypass = login

        # SPLASH-01: boot-log splash over the rest of the start-up
        boot = start_boot_splash()
        boot.log(f"Polygon {APP_VERSION} – spouštění programu")
        boot.log("Konfigurace načtena", "ok")
        if dev_login_bypass:
            boot.log("Přihlášení vypnuto – uživatel DEV", "dev")
        else:
            boot.log(f"Přihlášen uživatel {display_name} (LDAP)", "ok")

        # Initialize database connection globally (like in original version)
        boot.log("Připojování k databázi…")
        try:
            db = QtSql.QSqlDatabase.addDatabase("QMYSQL")
            db.setHostName(config['MYSQL']['host'])
            db.setUserName(config['MYSQL']['user'])
            db.setPassword(config['MYSQL']['password'])
            db.setDatabaseName(config['MYSQL']['database'])

            if not db.open():
                error = db.lastError()
                logger.error(f"Database connection failed: {error.text()}")
                boot.log("Připojení k databázi selhalo", "failed")
                boot.close()
                QMessageBox.critical(None, 'Chyba databáze', f'Nepodařilo se připojit k databázi: {error.text()}')
                return 1
            else:
                logger.info("Database connection established")

        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            boot.close()
            QMessageBox.critical(None, 'Chyba databáze', f'Chyba při připojování k databázi: {e}')
            return 1

        # Create and show main window
        boot.log("Inicializace hlavního okna…")
        # Built hidden: a window manager may stack it over the splash
        # (WindowStaysOnTopHint is not honored everywhere, e.g. GNOME/Wayland).
        main_window = MainWindow(config, display_name, dev_login_bypass=dev_login_bypass, show=False,
                                 dev_tab=dev_tab)
        boot.log("Hlavní okno připraveno", "ok")
        report = start_exit_report(config, main_window)
        boot.wait(BOOT_FIRST_READ_MS)  # first QUIDO poll -> real status bar states
        for text, status in boot_status_lines(main_window):
            boot.log(text, status)
        boot.finish_boot()
        if ctrl_c.requested:  # Ctrl+C during the start-up
            main_window.shutdown_quido_io()
            main_window.hardware.close()
            return 0
        # Maximized on the primary monitor; the camera view has its own
        # display_mode. The normal (restore) geometry is set first so that
        # restore really shrinks the window. Native Wayland ignores the
        # position - the compositor places it.
        available = app.primaryScreen().availableGeometry()
        main_window.setGeometry(normal_window_geometry(available, main_window.minimumSizeHint()))
        main_window.showMaximized()

        # Run application
        result = app.exec_()
        if ctrl_c.requested:  # closeEvent() did not run
            main_window.shutdown_quido_io()
            main_window.hardware.close()
        run_exit_report(report, main_window, ctrl_c, config, started_at)  # REPORT-01
        return result

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if boot is not None:
            boot.close()
        QMessageBox.critical(None, 'Kritická chyba', f'Došlo k kritické chybě: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())