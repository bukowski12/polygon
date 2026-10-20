"""SQL access layer for exercise_session (Etapa 7).

Owns every raw SQL statement dealing with individual polygon passes.
No PyQt5 import here at all: `query` is duck-typed (only .prepare()/
.bindValue()/.exec_()/.first()/.next()/.value()/.lastInsertId()/
.lastError() are called on it), mirroring training_repository.py's
own precedent.

Unlike TrainingRepository (which still uses "%d"-interpolated SQL for
plain integer ids/statuses), this repository uses prepared statements
throughout: it handles real DATETIME values that are meant to become
operator-editable later, a materially higher-risk category than
anything "%d" interpolation has ever touched in this codebase.

QSqlQuery can fail at two separate points - prepare() and exec_() -
and neither raises a Python exception on its own; both are checked
here and turned into a SessionRepositoryError, so a caller's ordinary
try/except catches a failed SQL statement the same way it already
catches everything else (see the FK-order corrective fix in
training_service.py for why this discipline exists).

DATETIME values cross a real type boundary here (verified against a
live MariaDB connection, not assumed): binding a plain Python
`datetime.datetime` via bindValue() does not work with the QMYSQL
driver (it silently binds as an empty string and the write fails) -
it must be formatted as "YYYY-MM-DD HH:MM:SS" first. Reading a
DATETIME column back returns a PyQt5 QDateTime, not a Python
datetime. Both conversions are handled at this module's boundary
(_to_sql_value/_from_sql_datetime below), duck-typed on
strftime()/toPyDateTime() so no PyQt5 import is needed here and the
plain-Python fakes used in unit tests keep working unchanged -
SessionService only ever sees plain Python datetime objects.
"""
from typing import Optional


class SessionRepositoryError(Exception):
    """A SQL statement's prepare() or exec_() returned False."""


def _to_sql_value(value):
    """Format a datetime-like value for binding. Duck-typed: a real
    datetime.datetime gets formatted; anything else (e.g. a plain string
    already, as used by the test fakes) passes through unchanged."""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def _from_sql_datetime(value):
    """Normalize a value read back from the DB to a plain Python datetime
    (or None). Duck-typed: a real QDateTime gets converted; anything else
    (e.g. the test fakes' plain stored values, or None) passes through
    unchanged.

    A NULL DATETIME column comes back from QSqlQuery.value() as a *null*
    QDateTime (year 0, .isNull() True), not as None - confirmed against a
    live MariaDB connection. Calling toPyDateTime() on that raises
    ValueError instead of producing anything usable, so it must be caught
    here before conversion, not left to surprise every caller."""
    if hasattr(value, "toPyDateTime"):
        if hasattr(value, "isNull") and value.isNull():
            return None
        return value.toPyDateTime()
    return value


class SessionRepository:
    def __init__(self, query):
        self.query = query

    def _execute(self, sql, bindings=None):
        if not self.query.prepare(sql):
            raise SessionRepositoryError(f"{self.query.lastError().text()} (prepare: {sql})")
        for name, value in (bindings or {}).items():
            self.query.bindValue(name, value)
        if not self.query.exec_():
            raise SessionRepositoryError(f"{self.query.lastError().text()} (SQL: {sql})")
        return self.query

    def create_session(self, member_id, source='MANUAL') -> int:
        self._execute(
            "INSERT INTO exercise_session (member_id, status, source) VALUES (:member_id, 0, :source)",
            {":member_id": member_id, ":source": source},
        )
        return self.query.lastInsertId()

    def find_latest_session_for_member(self, member_id) -> Optional[tuple]:
        """(idSession, entry_at, exit_at, status) for member_id's most recent
        session, or None if it has never had one. entry_at/exit_at are
        always plain Python datetime (or None), never QDateTime."""
        self._execute(
            "SELECT idSession, entry_at, exit_at, status FROM exercise_session "
            "WHERE member_id=:member_id ORDER BY idSession DESC LIMIT 1",
            {":member_id": member_id},
        )
        if self.query.first():
            return (
                self.query.value(0),
                _from_sql_datetime(self.query.value(1)),
                _from_sql_datetime(self.query.value(2)),
                self.query.value(3),
            )
        return None

    def record_entry(self, session_id, entry_at) -> None:
        self._execute(
            "UPDATE exercise_session SET entry_at=:entry_at, status=1 WHERE idSession=:id",
            {":entry_at": _to_sql_value(entry_at), ":id": session_id},
        )

    def record_exit(self, session_id, exit_at) -> None:
        self._execute(
            "UPDATE exercise_session SET exit_at=:exit_at, status=2 WHERE idSession=:id",
            {":exit_at": _to_sql_value(exit_at), ":id": session_id},
        )

    def correct_times(self, session_id, entry_at, exit_at=None) -> None:
        """UX-02: fix an existing pass's recorded time(s) - one UPDATE, so a
        DONE pass never ends up half-corrected. exit_at None = an INSIDE
        pass, only entry_at changes. Never touches status or source, never
        creates a session; the status in WHERE is a last guard that the
        pass is still in the state the caller validated."""
        if exit_at is None:
            self._execute(
                "UPDATE exercise_session SET entry_at=:entry_at WHERE idSession=:id AND status=1",
                {":entry_at": _to_sql_value(entry_at), ":id": session_id},
            )
        else:
            self._execute(
                "UPDATE exercise_session SET entry_at=:entry_at, exit_at=:exit_at "
                "WHERE idSession=:id AND status=2",
                {":entry_at": _to_sql_value(entry_at), ":exit_at": _to_sql_value(exit_at), ":id": session_id},
            )

    def find_training_status_for_member(self, member_id) -> Optional[int]:
        """training.status of member_id's training, or None if the member doesn't exist."""
        self._execute(
            "SELECT t.status FROM member m JOIN training t ON t.idTraining = m.training_id "
            "WHERE m.idMember=:member_id",
            {":member_id": member_id},
        )
        return self.query.value(0) if self.query.first() else None

    def count_active_for_training(self, training_id) -> int:
        self._execute(
            "SELECT COUNT(*) FROM exercise_session s JOIN member m ON m.idMember = s.member_id "
            "WHERE m.training_id=:training_id AND s.status=1",
            {":training_id": training_id},
        )
        self.query.first()
        return self.query.value(0)

    def has_active_session(self, member_id) -> bool:
        self._execute(
            "SELECT COUNT(*) FROM exercise_session WHERE member_id=:member_id AND status=1",
            {":member_id": member_id},
        )
        self.query.first()
        return self.query.value(0) != 0

    def count_all_active(self) -> int:
        self._execute("SELECT COUNT(*) FROM exercise_session WHERE status=1")
        self.query.first()
        return self.query.value(0)

    def delete_sessions_of_member(self, member_id) -> None:
        self._execute(
            "DELETE FROM exercise_session WHERE member_id=:member_id",
            {":member_id": member_id},
        )

    def delete_sessions_for_training(self, training_id) -> None:
        self._execute(
            "DELETE FROM exercise_session WHERE member_id IN "
            "(SELECT idMember FROM member WHERE training_id=:training_id)",
            {":training_id": training_id},
        )
