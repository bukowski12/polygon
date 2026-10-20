"""Kniha provozu (LOGBOOK-01) service - every logbook category, plus the
faulty floor sensors of MAP-02.

A record moves only OPEN -> RESOLVED (really dealt with) or
OPEN -> CANCELLED (written by mistake, reason mandatory). Nothing is ever
deleted or edited, so the history stays complete.

A faulty sensor is an OPEN record with category SENSOR_FAULT,
component_type FLOOR_SENSOR, component_id floor_XX - at most one per
sensor (also enforced by the DB). A SENSOR_FAULT created from the logbook
tab goes through create_sensor_fault() like one from the map.

Reads raise OperationLogError when the log can't be read (no DB
connection, failed query) - a caller must then treat the log as
unavailable, never as empty. Writes return a result with an outcome.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Dict, List, Optional

from operation_log_repository import CANCELLED, OPEN, RESOLVED, OperationLogRepositoryError

TECH_FAULT = "TECH_FAULT"
SENSOR_FAULT = "SENSOR_FAULT"
DAMAGE = "DAMAGE"
MAINTENANCE = "MAINTENANCE"
INJURY = "INJURY"
NOTE = "NOTE"
# Logbook categories in GUI order: code -> Czech label
CATEGORY_LABELS = {
    TECH_FAULT: "Technická závada",
    SENSOR_FAULT: "Nefunkční čidlo",
    DAMAGE: "Poškození majetku",
    MAINTENANCE: "Údržba / oprava",
    INJURY: "Úraz / zdravotní událost",
    NOTE: "Provozní poznámka",
}
STATUS_LABELS = {OPEN: "OTEVŘENO", RESOLVED: "VYŘEŠENO", CANCELLED: "STORNOVÁNO"}

FLOOR_SENSOR = "FLOOR_SENSOR"
DEFAULT_FAULT_DESCRIPTION = "Čidlo označeno obsluhou jako nefunkční."
LOCATION_MAX_LENGTH = 255    # operation_log.location_text VARCHAR(255)
USER_MAX_LENGTH = 100        # operation_log.*_by VARCHAR(100)
FUTURE_TOLERANCE = timedelta(minutes=1)   # event_at may not lie in the future


class OperationLogError(Exception):
    """The operation log is not available (no DB / failed query)."""


@dataclass
class OperationLogRecord:
    log_id: int
    event_at: datetime
    created_at: Optional[datetime]
    created_by: str
    category: str
    description: str
    status: str
    component_type: Optional[str] = None
    component_id: Optional[str] = None
    location_text: Optional[str] = None
    training_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancel_reason: Optional[str] = None

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def floor_name(self) -> Optional[str]:
        """floor_XX of a floor-sensor record, else None."""
        return self.component_id if self.component_type == FLOOR_SENSOR else None

    @property
    def is_open(self) -> bool:
        return self.status == OPEN


@dataclass
class SensorFault:
    log_id: int
    floor_name: str
    event_at: datetime
    created_at: Optional[datetime]
    created_by: str
    description: str


class FaultOutcome(Enum):
    OK = "ok"
    ALREADY_OPEN = "already_open"   # create: the floor already has an OPEN fault
    NOT_OPEN = "not_open"           # resolve/cancel: no OPEN record (anymore)
    INVALID = "invalid"             # unknown category/floor, roura, missing text/user, future time
    DB_ERROR = "db_error"


RecordOutcome = FaultOutcome  # the logbook uses the same outcomes


@dataclass
class FaultResult:
    outcome: FaultOutcome
    fault: Optional[SensorFault] = None


@dataclass
class RecordResult:
    outcome: FaultOutcome
    record: Optional[OperationLogRecord] = None


def _record(row) -> OperationLogRecord:
    return OperationLogRecord(
        row["idLog"], row["event_at"], row["created_at"], row["created_by"], row["category"],
        row["description"], row["status"], row.get("component_type"), row.get("component_id"),
        row.get("location_text"), row.get("training_id"), row.get("resolved_at"), row.get("resolved_by"),
        row.get("resolution_note"), row.get("cancelled_at"), row.get("cancelled_by"), row.get("cancel_reason"))


def _fault(row) -> SensorFault:
    return SensorFault(row["idLog"], row["component_id"], row["event_at"],
                       row["created_at"], row["created_by"], row["description"])


def _text(value) -> str:
    return (value or "").strip()


def _user(value) -> str:
    return _text(value)[:USER_MAX_LENGTH]


class OperationLogService:
    def __init__(self, repository, valid_floors=(), now=datetime.now):
        """repository None = no DB connection: reads raise, writes DB_ERROR.
        valid_floors: the floor names a sensor fault may be recorded for (the
        map's floor_XX - never roura)."""
        self.repository = repository
        self.valid_floors = frozenset(valid_floors)
        self.now = now

    def _repo(self):
        if self.repository is None:
            raise OperationLogError("operation log has no database connection")
        return self.repository

    def _read(self, call):
        try:
            return call(self._repo())
        except OperationLogRepositoryError as e:
            raise OperationLogError(str(e)) from e

    # --- logbook: reads ------------------------------------------------------

    def list_records(self, status=None, category=None, event_from=None, event_to=None,
                     oldest_first=False) -> List[OperationLogRecord]:
        """Records by status / category / event_at in [event_from, event_to)
        (None = all), newest event first unless oldest_first."""
        return [_record(r) for r in self._read(lambda repo: repo.list_records(
            status, category, event_from, event_to, oldest_first))]

    def list_today_and_open(self, today: date) -> List[OperationLogRecord]:
        """LOGBOOK-02 shift handover: records whose event_at falls on `today`
        plus every OPEN record of any date, oldest event first."""
        start = datetime.combine(today, time())
        return [_record(r) for r in self._read(
            lambda repo: repo.list_between_or_open(start, start + timedelta(days=1)))]

    def get_record(self, log_id) -> Optional[OperationLogRecord]:
        row = self._read(lambda repo: repo.get_record(log_id))
        return _record(row) if row else None

    def count_open(self) -> int:
        return self._read(lambda repo: repo.count_open())

    # --- REPORT-01: e-mail report on exit (reads only) -----------------------

    def max_log_id(self) -> int:
        return self._read(lambda repo: repo.max_log_id())

    def list_changed_or_open(self, after_id, open_ids) -> List[OperationLogRecord]:
        """Records with log_id > after_id, every OPEN record and the records
        open_ids - each once, oldest event first."""
        return [_record(r) for r in self._read(lambda repo: repo.list_changed_or_open(after_id, open_ids))]

    # --- logbook: writes -----------------------------------------------------

    def create_record(self, category, description, created_by, event_at=None,
                      location_text=None, floor_name=None) -> RecordResult:
        """New OPEN record. SENSOR_FAULT needs floor_name (location_text is
        not used) and follows the MAP-02 rules - one OPEN fault per sensor."""
        event_at = event_at or self.now()
        location = _text(location_text) or None
        if (category not in CATEGORY_LABELS or not _text(description) or not _user(created_by)
                or event_at > self.now() + FUTURE_TOLERANCE
                or (location and len(location) > LOCATION_MAX_LENGTH)):
            return RecordResult(FaultOutcome.INVALID)
        if category == SENSOR_FAULT:
            result = self.create_sensor_fault(floor_name, created_by, description, event_at=event_at)
            return self._as_record_result(result)
        try:
            log_id = self._repo().insert(event_at, _user(created_by), category, _text(description),
                                         location_text=location)
            return RecordResult(FaultOutcome.OK, self.get_record(log_id))
        except (OperationLogError, OperationLogRepositoryError):
            return RecordResult(FaultOutcome.DB_ERROR)

    def _as_record_result(self, result: FaultResult) -> RecordResult:
        if result.fault is None:
            return RecordResult(result.outcome)
        try:
            return RecordResult(result.outcome, self.get_record(result.fault.log_id))
        except OperationLogError:
            return RecordResult(result.outcome)

    def resolve_record(self, log_id, resolved_by, note=None) -> RecordResult:
        """OPEN -> RESOLVED (atomic: the UPDATE only matches an OPEN record)."""
        if not _user(resolved_by):
            return RecordResult(FaultOutcome.INVALID)
        return self._close_record(log_id, lambda repo: repo.resolve(
            log_id, self.now(), _user(resolved_by), _text(note) or None))

    def cancel_record(self, log_id, cancelled_by, reason) -> RecordResult:
        """OPEN -> CANCELLED - a mistaken record; reason is mandatory."""
        if not _user(cancelled_by) or not _text(reason):
            return RecordResult(FaultOutcome.INVALID)
        return self._close_record(log_id, lambda repo: repo.cancel(
            log_id, self.now(), _user(cancelled_by), _text(reason)))

    def _close_record(self, log_id, update) -> RecordResult:
        try:
            if not update(self._repo()):
                return RecordResult(FaultOutcome.NOT_OPEN)  # not OPEN (anymore) / no such record
            return RecordResult(FaultOutcome.OK, self.get_record(log_id))
        except (OperationLogError, OperationLogRepositoryError):
            return RecordResult(FaultOutcome.DB_ERROR)

    # --- MAP-02: faulty floor sensors -----------------------------------------

    def get_open_sensor_faults(self) -> Dict[str, SensorFault]:
        """{floor_name: SensorFault} of every OPEN sensor fault."""
        records = self._read(lambda repo: repo.find_open(SENSOR_FAULT, FLOOR_SENSOR))
        return {r["component_id"]: _fault(r) for r in records}

    def get_open_sensor_fault(self, floor_name) -> Optional[SensorFault]:
        row = self._read(lambda repo: repo.find_open_for_component(SENSOR_FAULT, FLOOR_SENSOR, floor_name))
        return _fault(row) if row else None

    def create_sensor_fault(self, floor_name, created_by, note=None, event_at=None) -> FaultResult:
        """Open a fault for floor_name. An empty note gets the standard text
        (description is never empty). event_at defaults to now."""
        if floor_name not in self.valid_floors or not _user(created_by):
            return FaultResult(FaultOutcome.INVALID)
        try:
            existing = self.get_open_sensor_fault(floor_name)
            if existing:
                return FaultResult(FaultOutcome.ALREADY_OPEN, existing)
            self._repo().insert(event_at or self.now(), _user(created_by), SENSOR_FAULT,
                                _text(note) or DEFAULT_FAULT_DESCRIPTION,
                                component_type=FLOOR_SENSOR, component_id=floor_name)
        except (OperationLogError, OperationLogRepositoryError):
            # The UNIQUE key on open faults refuses a concurrent second one
            return self._after_failed_write(floor_name)
        try:
            return FaultResult(FaultOutcome.OK, self.get_open_sensor_fault(floor_name))
        except OperationLogError:
            return FaultResult(FaultOutcome.DB_ERROR)

    def _after_failed_write(self, floor_name) -> FaultResult:
        try:
            existing = self.get_open_sensor_fault(floor_name)
        except OperationLogError:
            return FaultResult(FaultOutcome.DB_ERROR)
        return FaultResult(FaultOutcome.ALREADY_OPEN, existing) if existing else FaultResult(FaultOutcome.DB_ERROR)

    def resolve_sensor_fault(self, floor_name, resolved_by, note=None) -> FaultResult:
        """The sensor was really faulty and is fixed: OPEN -> RESOLVED."""
        return self._close_sensor_fault(floor_name, lambda fault: self.resolve_record(fault.log_id, resolved_by, note))

    def cancel_sensor_fault(self, floor_name, cancelled_by, reason) -> FaultResult:
        """The fault was recorded by mistake: OPEN -> CANCELLED. reason is mandatory."""
        return self._close_sensor_fault(floor_name, lambda fault: self.cancel_record(fault.log_id, cancelled_by, reason))

    def _close_sensor_fault(self, floor_name, close) -> FaultResult:
        try:
            fault = self.get_open_sensor_fault(floor_name)
        except OperationLogError:
            return FaultResult(FaultOutcome.DB_ERROR)
        if fault is None:
            return FaultResult(FaultOutcome.NOT_OPEN)
        result = close(fault)
        return FaultResult(result.outcome, fault)
