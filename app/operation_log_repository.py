"""SQL access layer for operation_log - Kniha provozu (LOGBOOK-01): the
logbook tab (every category) and MAP-02 (faulty floor sensors).

Same rules as session_repository.py: no PyQt5 import (`query` is
duck-typed), prepared statements only, a failed prepare()/exec_() raises
OperationLogRepositoryError, DATETIME values are formatted on the way in
and converted to plain Python datetime on the way out.

Records are never deleted - there is deliberately no DELETE here. A
record only moves OPEN -> RESOLVED or OPEN -> CANCELLED, and the UPDATEs
carry `status = 'OPEN'` in their WHERE, so a closed record never changes.
REPORT-01 (exit_report.py) relies on exactly this to find the changes since
its last report from idLog and status alone - any new kind of edit would
need its own change marker (an updated_at column, i.e. a migration).
"""
from typing import List, Optional

from session_repository import _from_sql_datetime, _to_sql_value

OPEN = "OPEN"
RESOLVED = "RESOLVED"
CANCELLED = "CANCELLED"

_RECORD_COLUMNS = (
    "idLog, event_at, created_at, created_by, category, description, status, "
    "component_type, component_id, location_text, training_id, resolved_at, resolved_by, "
    "resolution_note, cancelled_at, cancelled_by, cancel_reason"
)
_DATETIME_FIELDS = {"event_at", "created_at", "resolved_at", "cancelled_at"}


class OperationLogRepositoryError(Exception):
    """A SQL statement's prepare() or exec_() returned False."""


class OperationLogRepository:
    def __init__(self, query):
        self.query = query

    def _execute(self, sql, bindings=None):
        if not self.query.prepare(sql):
            raise OperationLogRepositoryError(f"{self.query.lastError().text()} (prepare: {sql})")
        for name, value in (bindings or {}).items():
            self.query.bindValue(name, value)
        if not self.query.exec_():
            raise OperationLogRepositoryError(f"{self.query.lastError().text()} (SQL: {sql})")
        return self.query

    def _record(self):
        """The current row of a _RECORD_COLUMNS select as a dict."""
        names = [name.strip() for name in _RECORD_COLUMNS.split(",")]
        record = {}
        for index, name in enumerate(names):
            value = None if self.query.isNull(index) else self.query.value(index)
            record[name] = _from_sql_datetime(value) if name in _DATETIME_FIELDS else value
        return record

    def insert(self, event_at, created_by, category, description,
               component_type=None, component_id=None, location_text=None, training_id=None) -> int:
        self._execute(
            "INSERT INTO operation_log (event_at, created_by, category, description, status, "
            "component_type, component_id, location_text, training_id) "
            "VALUES (:event_at, :created_by, :category, :description, 'OPEN', "
            ":component_type, :component_id, :location_text, :training_id)",
            {":event_at": _to_sql_value(event_at), ":created_by": created_by, ":category": category,
             ":description": description, ":component_type": component_type,
             ":component_id": component_id, ":location_text": location_text, ":training_id": training_id},
        )
        return self.query.lastInsertId()

    def list_records(self, status=None, category=None, event_from=None, event_to=None,
                     oldest_first=False) -> List[dict]:
        """Records filtered by status / category / event_at in
        [event_from, event_to) (None = any), newest event first - or oldest
        first for the printed logbook (LOGBOOK-02)."""
        where, bindings = [], {}
        if status is not None:
            where.append("status = :status")
            bindings[":status"] = status
        if category is not None:
            where.append("category = :category")
            bindings[":category"] = category
        if event_from is not None:
            where.append("event_at >= :event_from")
            bindings[":event_from"] = _to_sql_value(event_from)
        if event_to is not None:
            where.append("event_at < :event_to")
            bindings[":event_to"] = _to_sql_value(event_to)
        condition = f"WHERE {' AND '.join(where)} " if where else ""
        order = "ORDER BY event_at, idLog" if oldest_first else "ORDER BY event_at DESC, idLog DESC"
        self._execute(f"SELECT {_RECORD_COLUMNS} FROM operation_log {condition}{order}", bindings)
        return self._records()

    def list_between_or_open(self, event_from, event_to) -> List[dict]:
        """LOGBOOK-02 shift handover: every record with event_at in
        [event_from, event_to) plus every OPEN record of any date - one
        SELECT (one snapshot, no duplicates), oldest event first."""
        self._execute(
            f"SELECT {_RECORD_COLUMNS} FROM operation_log "
            "WHERE (event_at >= :event_from AND event_at < :event_to) OR status = 'OPEN' "
            "ORDER BY event_at, idLog",
            {":event_from": _to_sql_value(event_from), ":event_to": _to_sql_value(event_to)},
        )
        return self._records()

    def max_log_id(self) -> int:
        """REPORT-01: the highest idLog (0 for an empty log)."""
        self._execute("SELECT MAX(idLog) FROM operation_log")
        return int(self.query.value(0)) if self.query.first() and not self.query.isNull(0) else 0

    def list_changed_or_open(self, after_id, open_ids) -> List[dict]:
        """REPORT-01: every record with idLog > after_id, every OPEN record
        and the records open_ids (OPEN at the last report) - one SELECT (one
        snapshot, each record once), oldest event first. The ids are bound,
        never put into the SQL text."""
        bindings = {":after_id": int(after_id)}
        condition = "idLog > :after_id OR status = 'OPEN'"
        ids = sorted({int(log_id) for log_id in open_ids})
        if ids:
            names = [f":open{index}" for index in range(len(ids))]
            bindings.update(zip(names, ids))
            condition += f" OR idLog IN ({', '.join(names)})"
        self._execute(f"SELECT {_RECORD_COLUMNS} FROM operation_log WHERE {condition} ORDER BY event_at, idLog",
                      bindings)
        return self._records()

    def _records(self) -> List[dict]:
        records = []
        while self.query.next():
            records.append(self._record())
        return records

    def get_record(self, log_id) -> Optional[dict]:
        self._execute(f"SELECT {_RECORD_COLUMNS} FROM operation_log WHERE idLog = :id", {":id": log_id})
        return self._record() if self.query.first() else None

    def count_open(self) -> int:
        self._execute("SELECT COUNT(*) FROM operation_log WHERE status = 'OPEN'")
        return int(self.query.value(0)) if self.query.first() else 0

    def find_open(self, category, component_type) -> List[dict]:
        """Every OPEN record of category/component_type, oldest event first."""
        self._execute(
            f"SELECT {_RECORD_COLUMNS} FROM operation_log WHERE status = 'OPEN' "
            "AND category = :category AND component_type = :component_type ORDER BY event_at, idLog",
            {":category": category, ":component_type": component_type},
        )
        return self._records()

    def find_open_for_component(self, category, component_type, component_id) -> Optional[dict]:
        self._execute(
            f"SELECT {_RECORD_COLUMNS} FROM operation_log WHERE status = 'OPEN' AND category = :category "
            "AND component_type = :component_type AND component_id = :component_id "
            "ORDER BY idLog DESC LIMIT 1",
            {":category": category, ":component_type": component_type, ":component_id": component_id},
        )
        return self._record() if self.query.first() else None

    def history_for_component(self, category, component_type, component_id) -> List[dict]:
        """All records of a component, any status, oldest first."""
        self._execute(
            f"SELECT {_RECORD_COLUMNS} FROM operation_log WHERE category = :category "
            "AND component_type = :component_type AND component_id = :component_id ORDER BY idLog",
            {":category": category, ":component_type": component_type, ":component_id": component_id},
        )
        return self._records()

    def resolve(self, log_id, resolved_at, resolved_by, resolution_note=None) -> bool:
        """OPEN -> RESOLVED. False when the record is no longer OPEN."""
        self._execute(
            "UPDATE operation_log SET status = 'RESOLVED', resolved_at = :resolved_at, "
            "resolved_by = :resolved_by, resolution_note = :note WHERE idLog = :id AND status = 'OPEN'",
            {":resolved_at": _to_sql_value(resolved_at), ":resolved_by": resolved_by,
             ":note": resolution_note, ":id": log_id},
        )
        return self.query.numRowsAffected() == 1

    def cancel(self, log_id, cancelled_at, cancelled_by, cancel_reason) -> bool:
        """OPEN -> CANCELLED (a mistaken record). False when no longer OPEN."""
        self._execute(
            "UPDATE operation_log SET status = 'CANCELLED', cancelled_at = :cancelled_at, "
            "cancelled_by = :cancelled_by, cancel_reason = :reason WHERE idLog = :id AND status = 'OPEN'",
            {":cancelled_at": _to_sql_value(cancelled_at), ":cancelled_by": cancelled_by,
             ":reason": cancel_reason, ":id": log_id},
        )
        return self.query.numRowsAffected() == 1
