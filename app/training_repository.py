"""SQL access layer for the training/member tables (Etapa 6).

Owns every raw SQL statement TrainingService used to run directly. No
PyQt5 import here at all: `query` is duck-typed, same as
training_service.py's own precedent - only .exec_()/.first()/.next()/
.value()/.lastInsertId()/.lastError() are called on it.

The real point of this split, not just moving code: QSqlQuery.exec_()
returns False on a SQL error instead of raising a Python exception (see
the FK-order bug found in TrainingService.cancel_open_training(), fixed
in a prior corrective commit with two manual checks). Every method here
routes through _exec(), which raises TrainingRepositoryError on a False
return - closing that gap once, systematically, for every statement,
instead of ad hoc per call site.
"""
from typing import List, Optional


class TrainingRepositoryError(Exception):
    """A SQL statement's QSqlQuery.exec_() returned False."""


class TrainingRepository:
    def __init__(self, query):
        self.query = query

    def _exec(self, sql):
        if not self.query.exec_(sql):
            raise TrainingRepositoryError(f"{self.query.lastError().text()} (SQL: {sql})")
        return self.query

    def insert_training(self) -> int:
        self._exec("INSERT INTO training (time_start) VALUES (NOW())")
        return self.query.lastInsertId()

    def count_members(self, training_id) -> int:
        self._exec("SELECT COUNT(idmember) FROM member WHERE training_id=%d" % (training_id))
        self.query.first()
        return self.query.value(0)

    def is_member(self, training_id, person_id) -> bool:
        self._exec("SELECT COUNT(idmember) FROM member WHERE training_id=%d AND person_id=%d" % (training_id, person_id))
        self.query.first()
        return self.query.value(0) != 0

    def insert_member(self, training_id, person_id) -> None:
        self._exec("INSERT INTO member (training_id,person_id) VALUES (%d,%d)" % (training_id, person_id))

    def set_status(self, training_id, status) -> None:
        self._exec("UPDATE training SET status=%d WHERE idTraining=%d" % (status, training_id))

    def delete_member(self, member_id) -> None:
        self._exec("DELETE FROM member WHERE idMember=%d" % (member_id))

    def delete_training(self, training_id) -> None:
        self._exec("DELETE FROM training WHERE idTraining=%d" % (training_id))

    def find_training_id_not_status(self, status) -> Optional[int]:
        self._exec("SELECT idTraining FROM training WHERE status<>%d LIMIT 1" % status)
        if self.query.first():
            return self.query.value(0)
        return None

    def delete_members_of_training(self, training_id) -> None:
        self._exec("DELETE FROM member WHERE training_id=%d" % (training_id))

    def find_training_id_with_status(self, status) -> Optional[int]:
        self._exec("SELECT idTraining FROM training WHERE status=%d LIMIT 1" % status)
        if self.query.first():
            return self.query.value(0)
        return None

    def get_member_summaries(self, training_id) -> List[tuple]:
        """(volume, press_start, press_end, display_name) per member, original column order.
        press_end is None for SQL NULL (PRESS-END-NULL: not entered yet) -
        QMYSQL would hand NULL over as 0, a real 0 bar."""
        self._exec(
            "SELECT member.volume, member.press_start, member.press_end, CONCAT(person.name,' ', person.surname) AS name "
            "FROM member LEFT JOIN person ON member.person_id = person.idPerson WHERE training_id=%d" % training_id
        )
        rows = []
        while self.query.next():
            press_end = None if self.query.isNull(2) else self.query.value(2)
            rows.append((self.query.value(0), self.query.value(1), press_end, self.query.value(3)))
        return rows
