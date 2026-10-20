"""Training lifecycle logic, extracted from MainWindow (Etapa 5).

Owns the training/member state machine, validation, and the exercise
clock, so it's testable without Qt. All SQL lives in TrainingRepository
(Etapa 6) - this class only decides what should happen (validation,
thresholds, status transitions), never how it's persisted.

No PyQt5 import here at all: `training_model` is duck-typed (only
.select()/.rowCount()/.record() are called on it - Qt model plumbing,
deliberately left out of the repository, see get_or_create_training()).
"""
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import List, Optional

from logger_config import logger
from training_repository import TrainingRepository
from session_repository import SessionRepository


class TrainingStatus(IntEnum):
    """Mirrors config/polygon.sql's `training.status` comment exactly -
    these are the only 4 values ever written to that column."""
    NEW = 0      # just created, no members yet
    READY = 1    # 1+ members, operationally usable (entries/exits, Dokončit)
                 # - WORKFLOW-03: no longer "2+ members" (old squad model)
    STOPPED = 2  # finished, awaiting per-member volume/pressure check + save
    SAVED = 10   # confirmed and printable


class AddMemberOutcome(Enum):
    ADDED = "added"
    NO_OPEN_TRAINING = "no_open_training"
    ALREADY_MEMBER = "already_member"
    INVALID_PERSON = "invalid_person"
    ERROR = "error"


@dataclass
class AddMemberResult:
    outcome: AddMemberOutcome
    training_id: Optional[int] = None
    ready: bool = False  # ADDED and the training is now READY (always true once a member is added)


class DeleteMemberOutcome(Enum):
    DELETED = "deleted"                            # 1+ members remain, status untouched
    TRAINING_REMOVED = "training_removed"          # 0 remain -> training row deleted (no startButton change - existing quirk)
    BLOCKED_ACTIVE_SESSION = "blocked_active_session"  # member is currently INSIDE - can't be deleted mid-pass
    ERROR = "error"


@dataclass
class DeleteMemberResult:
    outcome: DeleteMemberOutcome


class SaveOutcome(Enum):
    SAVED = "saved"
    NO_STOPPED_TRAINING = "no_stopped_training"
    VALIDATION_FAILED = "validation_failed"
    CONFIRM_ZERO_END_PRESSURE = "confirm_zero_end_pressure"  # nothing saved - ask, then save(confirm...=True)
    ERROR = "error"


@dataclass
class SaveResult:
    outcome: SaveOutcome
    training_id: Optional[int] = None
    messages: List[str] = field(default_factory=list)
    zero_end_pressure_names: List[str] = field(default_factory=list)  # CONFIRM_ZERO_END_PRESSURE only


class CancelTrainingOutcome(Enum):
    CANCELLED = "cancelled"
    NOTHING_TO_CANCEL = "nothing_to_cancel"
    BLOCKED_ACTIVE_SESSIONS = "blocked_active_sessions"
    ERROR = "error"


@dataclass
class CancelTrainingResult:
    outcome: CancelTrainingOutcome
    training_id: Optional[int] = None


class FinishTrainingOutcome(Enum):
    FINISHED = "finished"
    NOT_READY = "not_ready"  # no open training, or it's not in READY status
    BLOCKED_ACTIVE_SESSIONS = "blocked_active_sessions"
    ERROR = "error"


@dataclass
class FinishTrainingResult:
    outcome: FinishTrainingOutcome
    training_id: Optional[int] = None


class TrainingService:
    def __init__(self, query, training_model, repository=None,
                 session_repository=None, db=None):
        self.training_model = training_model
        self.repository = repository or TrainingRepository(query)
        self.session_repository = session_repository or SessionRepository(query)
        # Duck-typed: needs .transaction()/.commit()/.rollback(), e.g. a real
        # QtSql.QSqlDatabase handle. None (the default, and what every unit
        # test uses) runs the same code path non-transactionally.
        self.db = db

    # -- minimal transaction helpers, scoped to the two destructive cascades
    # below (exercise_session -> member -> training) - not a generic
    # framework. A False return from transaction()/commit() is a real
    # failure and must not be treated as success. _commit() is called
    # *inside* each cascade's own try/except, not after it - a failed
    # commit must trigger the same rollback as a failed DELETE, otherwise
    # a half-applied cascade could be left uncommitted and unrolled-back.

    def _begin(self):
        if self.db is not None and not self.db.transaction():
            raise RuntimeError(f"Could not start transaction: {self.db.lastError().text()}")

    def _commit(self):
        if self.db is not None and not self.db.commit():
            raise RuntimeError(f"Could not commit transaction: {self.db.lastError().text()}")

    def _rollback(self):
        # Already inside an except block reacting to the real failure - log
        # rather than raise, so a failed rollback doesn't replace/mask the
        # original exception that triggered it.
        if self.db is not None and not self.db.rollback():
            logger.error(f"Rollback itself failed: {self.db.lastError().text()}")

    # -- membership / lifecycle -------------------------------------------------

    def get_or_create_training(self) -> Optional[int]:
        """Find the one open (status NEW/READY/STOPPED) training, or create one."""
        try:
            self.training_model.select()
            if self.training_model.rowCount() == 0:
                return self.repository.insert_training()
            record = self.training_model.record(0)
            if record.value("status") == TrainingStatus.STOPPED:
                return None
            return record.value("idTraining")
        except Exception as e:
            logger.error(f"Error getting training: {e}")
            return None

    def count_members(self, training_id) -> int:
        try:
            return self.repository.count_members(training_id)
        except Exception as e:
            logger.error(f"Error counting members: {e}")
            return 0

    def add_member(self, person_id) -> AddMemberResult:
        try:
            if not (person_id and person_id > 0):
                return AddMemberResult(AddMemberOutcome.INVALID_PERSON)

            training_id = self.get_or_create_training()
            if training_id is None:
                return AddMemberResult(AddMemberOutcome.NO_OPEN_TRAINING)

            if self.repository.is_member(training_id, person_id):
                return AddMemberResult(AddMemberOutcome.ALREADY_MEMBER, training_id=training_id)

            self.repository.insert_member(training_id, person_id)
            # WORKFLOW-03: a single participant is a valid training too.
            self.repository.set_status(training_id, TrainingStatus.READY)

            return AddMemberResult(AddMemberOutcome.ADDED, training_id=training_id, ready=True)
        except Exception as e:
            logger.error(f"Error adding member: {e}")
            return AddMemberResult(AddMemberOutcome.ERROR)

    def delete_member(self, training_id, member_id) -> DeleteMemberResult:
        try:
            if self.session_repository.has_active_session(member_id):
                return DeleteMemberResult(DeleteMemberOutcome.BLOCKED_ACTIVE_SESSION)
            self._begin()
            try:
                self.session_repository.delete_sessions_of_member(member_id)
                self.repository.delete_member(member_id)
                # self.repository.count_members(), not self.count_members():
                # the latter swallows a DB error and returns 0, which is
                # fine for the non-destructive callers elsewhere but
                # dangerous here - a masked error misread as "0 members
                # left" would delete the whole training. Inside this
                # transaction, a failure must raise so it rolls back
                # instead of being silently treated as "nobody's left."
                count = self.repository.count_members(training_id)
                if count == 0:
                    self.repository.delete_training(training_id)
                    outcome = DeleteMemberOutcome.TRAINING_REMOVED
                else:
                    outcome = DeleteMemberOutcome.DELETED
                self._commit()
            except Exception:
                self._rollback()
                raise
            return DeleteMemberResult(outcome)
        except Exception as e:
            logger.error(f"Error deleting member: {e}")
            return DeleteMemberResult(DeleteMemberOutcome.ERROR)

    def cancel_open_training(self) -> CancelTrainingResult:
        """Delete whatever training is not yet SAVED (used by the explicit
        Delete-training action; no longer called from closeEvent() - closing
        the app and deleting a training are separate operations).

        Blocked entirely if anyone is currently INSIDE (checked before any
        delete is attempted). Deletes sessions, then members, then the
        training row itself, all by explicit id (no bulk by-status delete
        anymore). exercise_session.member_id has an FK with no ON DELETE
        CASCADE, and member.training_id is CASCADE only in production /
        config/polygon.sql (RESTRICT in the test schema, SCHEMA-01) - so
        children always go first; deleting a parent before them would be
        rejected by the DB (see the FK-order corrective fix; the
        repositories' _exec() raises on that failure instead of it passing
        unnoticed)."""
        try:
            training_id = self.repository.find_training_id_not_status(TrainingStatus.SAVED)
            if not training_id:
                return CancelTrainingResult(CancelTrainingOutcome.NOTHING_TO_CANCEL)
            if self.session_repository.count_active_for_training(training_id) > 0:
                return CancelTrainingResult(CancelTrainingOutcome.BLOCKED_ACTIVE_SESSIONS, training_id=training_id)
            self._begin()
            try:
                self.session_repository.delete_sessions_for_training(training_id)
                self.repository.delete_members_of_training(training_id)
                self.repository.delete_training(training_id)
                self._commit()
            except Exception:
                self._rollback()
                raise
            return CancelTrainingResult(CancelTrainingOutcome.CANCELLED, training_id=training_id)
        except Exception as e:
            logger.error(f"Error deleting training: {e}")
            return CancelTrainingResult(CancelTrainingOutcome.ERROR)

    def save(self, confirm_zero_end_pressure=False) -> SaveResult:
        """Uložit cvičení (STOPPED -> SAVED) after VALIDATION-01.

        PRESS-END-NULL: press_end None = not entered yet -> blocks the save;
        0 = a real, measured 0 bar - valid, but unusual enough to need the
        operator's confirmation: without confirm_zero_end_pressure the
        result is CONFIRM_ZERO_END_PRESSURE with the affected names and
        nothing changes (the training stays STOPPED); the GUI asks and calls
        save(confirm_zero_end_pressure=True). Still required: volume > 0,
        press_start > 0, press_end >= 0, press_start > press_end. Real
        errors are reported before any zero confirmation is asked for."""
        try:
            training_id = self.repository.find_training_id_with_status(TrainingStatus.STOPPED)
            messages = []
            zero_end_names = []
            if training_id:
                for volume, press_start, press_end, name in self.repository.get_member_summaries(training_id):
                    if float(volume or 0) <= 0 or int(press_start or 0) <= 0 or press_end is None:
                        messages.append('Nejsou vyplněné všechny hodnoty u cvičících')
                    elif int(press_end) < 0:
                        messages.append('%s nemá platný koncový tlak' % name)
                    elif int(press_start) <= int(press_end):
                        messages.append('%s nemá počáteční tlak větší než koncový' % name)
                    elif int(press_end) == 0:
                        zero_end_names.append(name)
            else:
                messages.append('Není dokončený žádný trénink')

            if messages:
                outcome = SaveOutcome.VALIDATION_FAILED if training_id else SaveOutcome.NO_STOPPED_TRAINING
                return SaveResult(outcome, training_id=training_id or None, messages=list(set(messages)))
            if zero_end_names and not confirm_zero_end_pressure:
                return SaveResult(SaveOutcome.CONFIRM_ZERO_END_PRESSURE, training_id=training_id,
                                  zero_end_pressure_names=zero_end_names)

            self.repository.set_status(training_id, TrainingStatus.SAVED)
            return SaveResult(SaveOutcome.SAVED, training_id=training_id)
        except Exception as e:
            logger.error(f"Error saving training: {e}")
            return SaveResult(SaveOutcome.ERROR)

    def find_open_training(self) -> Optional[tuple]:
        """Read-only: (idTraining, status) of the one open (NEW/READY/STOPPED)
        training, or None if none exists. Unlike get_or_create_training(),
        never creates one - for operations (like finish_training()) that
        only make sense on a training that already exists."""
        try:
            self.training_model.select()
            if self.training_model.rowCount() == 0:
                return None
            record = self.training_model.record(0)
            return record.value("idTraining"), record.value("status")
        except Exception as e:
            logger.error(f"Error finding training: {e}")
            return None

    def finish_training(self) -> FinishTrainingResult:
        """Mark the open training as STOPPED (awaiting per-member pressure/
        volume entry + save) - replaces the "close out the training" half
        of the old global stopwatch. Blocked if the training isn't READY
        (this used to be enforced only implicitly by startButton/stopButton
        enable-state) or if anyone is still INSIDE. Does not write
        training.time_end - the old value was an elapsed-since-start
        string, not a real timestamp, and there's no single meaningful
        elapsed time left once the global clock is gone."""
        try:
            found = self.find_open_training()
            if found is None or found[1] != TrainingStatus.READY:
                return FinishTrainingResult(FinishTrainingOutcome.NOT_READY, training_id=found[0] if found else None)
            training_id, _ = found
            if self.session_repository.count_active_for_training(training_id) > 0:
                return FinishTrainingResult(FinishTrainingOutcome.BLOCKED_ACTIVE_SESSIONS, training_id=training_id)
            self.repository.set_status(training_id, TrainingStatus.STOPPED)
            return FinishTrainingResult(FinishTrainingOutcome.FINISHED, training_id=training_id)
        except Exception as e:
            logger.error(f"Error finishing training: {e}")
            return FinishTrainingResult(FinishTrainingOutcome.ERROR)

    def has_active_sessions(self) -> Optional[bool]:
        """Training-agnostic "is anyone inside the polygon right now" -
        unlike count_active_for_training(), needs no training id, so it
        has no create-a-training side effect. Used by closeEvent().
        Tri-state: True/False, or None if the DB can't be read - never
        guesses either way on an error."""
        try:
            return self.session_repository.count_all_active() > 0
        except Exception as e:
            logger.error(f"Error checking active sessions: {e}")
            return None
