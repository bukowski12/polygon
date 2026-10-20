"""Individual polygon-pass lifecycle logic (Etapa 7).

Owns the entry/exit state machine for one member's pass through the
polygon - the "who's inside right now" truth that used to not exist at
all (the old app had one global stopwatch for the whole training).
Mirrors training_service.py's shape: business logic only, SQL lives in
SessionRepository. No PyQt5 import; `now` is an injectable callable
(mirrors TrainingService's `clock=time.monotonic`) so tests never
depend on real wall-clock time. Deals exclusively in plain Python
datetime objects - SessionRepository is responsible for the DB-driver
type boundary (see its own module docstring).

"One session per member" for v1 (doc's own explicit recommendation):
found via repository.find_latest_session_for_member(), created if none
exists. A second real pass by the same member in the same training is
not supported yet - extend later if needed.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntEnum
from typing import Optional

from logger_config import logger


class SessionStatus(IntEnum):
    """Own enum, unrelated to TrainingStatus despite overlapping numbers -
    never compare instances of the two across classes."""
    READY = 0
    INSIDE = 1
    DONE = 2


class EntryOutcome(Enum):
    RECORDED = "recorded"
    ALREADY_INSIDE = "already_inside"
    ALREADY_DONE = "already_done"
    ERROR = "error"


@dataclass
class EntryResult:
    outcome: EntryOutcome
    session_id: Optional[int] = None


class ExitOutcome(Enum):
    RECORDED = "recorded"
    NO_ENTRY = "no_entry"
    ALREADY_DONE = "already_done"
    EXIT_BEFORE_ENTRY = "exit_before_entry"
    ERROR = "error"


@dataclass
class ExitResult:
    outcome: ExitOutcome
    session_id: Optional[int] = None


class TimeCorrectionOutcome(Enum):
    """UX-02: result of SessionService.correct_times()."""
    UPDATED = "updated"
    NO_SESSION = "no_session"              # never entered - nothing to correct
    NOT_STARTED = "not_started"            # READY session - Zapsat vstup, not a correction
    TRAINING_SAVED = "training_saved"      # saved history is not editable here
    MISSING_TIME = "missing_time"          # a time the pass's state requires is missing
    EXIT_NOT_RECORDED = "exit_not_recorded"  # INSIDE pass: no exit to correct yet
    INVALID_TIME_ORDER = "invalid_time_order"  # exit before entry
    ERROR = "error"


@dataclass
class TimeCorrectionResult:
    outcome: TimeCorrectionOutcome
    session_id: Optional[int] = None


# training.status of a saved training - same value as TrainingStatus.SAVED
# in training_service.py (not imported: the session layer stays independent
# of the training layer, which itself builds on SessionRepository).
_TRAINING_SAVED = 10


class SessionService:
    def __init__(self, repository, now=datetime.now):
        self.repository = repository
        self._now = now

    def record_entry(self, member_id, entry_at=None, source='MANUAL') -> EntryResult:
        """entry_at defaults to now() if not given. `source` is forwarded to
        repository.create_session() only when a new session row is created -
        this parameter is what lets a future Dallas reader call this exact
        method with source='DALLAS' and nothing else different."""
        try:
            existing = self.repository.find_latest_session_for_member(member_id)
            if existing is not None:
                session_id, _, _, status = existing
                if status == SessionStatus.INSIDE:
                    return EntryResult(EntryOutcome.ALREADY_INSIDE, session_id=session_id)
                if status == SessionStatus.DONE:
                    return EntryResult(EntryOutcome.ALREADY_DONE, session_id=session_id)
                # status == READY (session created but never entered) - reuse it.
            else:
                session_id = self.repository.create_session(member_id, source=source)

            when = entry_at if entry_at is not None else self._now()
            self.repository.record_entry(session_id, when)
            return EntryResult(EntryOutcome.RECORDED, session_id=session_id)
        except Exception as e:
            logger.error(f"Error recording entry: {e}")
            return EntryResult(EntryOutcome.ERROR)

    def record_exit(self, member_id, exit_at=None) -> ExitResult:
        try:
            existing = self.repository.find_latest_session_for_member(member_id)
            if existing is None:
                return ExitResult(ExitOutcome.NO_ENTRY)
            session_id, entry_at, _, status = existing
            if status == SessionStatus.READY:
                return ExitResult(ExitOutcome.NO_ENTRY, session_id=session_id)
            if status == SessionStatus.DONE:
                return ExitResult(ExitOutcome.ALREADY_DONE, session_id=session_id)

            when = exit_at if exit_at is not None else self._now()
            if entry_at is not None and when < entry_at:
                return ExitResult(ExitOutcome.EXIT_BEFORE_ENTRY, session_id=session_id)

            self.repository.record_exit(session_id, when)
            return ExitResult(ExitOutcome.RECORDED, session_id=session_id)
        except Exception as e:
            logger.error(f"Error recording exit: {e}")
            return ExitResult(ExitOutcome.ERROR)

    def correct_times(self, member_id, entry_at, exit_at=None) -> TimeCorrectionResult:
        """UX-02: manual correction of an existing pass's time(s) when the
        operator clicked late. Only fixes entry_at (INSIDE) or entry_at and
        exit_at (DONE) of the member's existing session - never creates a
        session, never changes its status or source, so READY can't turn
        INSIDE through here (that's record_entry()). Same time order rule
        as record_exit(): exit before entry is rejected, equal is allowed.
        Allowed until the training is SAVED (also after Dokončit cvičení)."""
        try:
            existing = self.repository.find_latest_session_for_member(member_id)
            if existing is None:
                return TimeCorrectionResult(TimeCorrectionOutcome.NO_SESSION)
            session_id, _, _, status = existing
            if status == SessionStatus.READY:
                return TimeCorrectionResult(TimeCorrectionOutcome.NOT_STARTED, session_id=session_id)
            if self.repository.find_training_status_for_member(member_id) == _TRAINING_SAVED:
                return TimeCorrectionResult(TimeCorrectionOutcome.TRAINING_SAVED, session_id=session_id)
            if entry_at is None:
                return TimeCorrectionResult(TimeCorrectionOutcome.MISSING_TIME, session_id=session_id)
            if status == SessionStatus.INSIDE:
                if exit_at is not None:
                    return TimeCorrectionResult(TimeCorrectionOutcome.EXIT_NOT_RECORDED, session_id=session_id)
            else:  # DONE
                if exit_at is None:
                    return TimeCorrectionResult(TimeCorrectionOutcome.MISSING_TIME, session_id=session_id)
                if exit_at < entry_at:
                    return TimeCorrectionResult(TimeCorrectionOutcome.INVALID_TIME_ORDER, session_id=session_id)

            self.repository.correct_times(session_id, entry_at, exit_at)
            return TimeCorrectionResult(TimeCorrectionOutcome.UPDATED, session_id=session_id)
        except Exception as e:
            logger.error(f"Error correcting passage times: {e}")
            return TimeCorrectionResult(TimeCorrectionOutcome.ERROR)

    # The three reads below return None (never 0/False) when the DB can't
    # be read - "unknown" must stay distinguishable from "nobody inside",
    # callers decide how to fail closed.

    def count_active_for_training(self, training_id) -> Optional[int]:
        """Number of INSIDE sessions in training_id, or None on a DB error."""
        try:
            return self.repository.count_active_for_training(training_id)
        except Exception as e:
            logger.error(f"Error counting active sessions: {e}")
            return None

    def count_all_active(self) -> Optional[int]:
        """Number of INSIDE sessions across all trainings, or None on a DB error."""
        try:
            return self.repository.count_all_active()
        except Exception as e:
            logger.error(f"Error counting active sessions: {e}")
            return None

    def has_active_session(self, member_id) -> Optional[bool]:
        """Whether member_id is currently INSIDE, or None on a DB error."""
        try:
            return self.repository.has_active_session(member_id)
        except Exception as e:
            logger.error(f"Error checking active session: {e}")
            return None

    def duration_str(self, entry_at, exit_at) -> str:
        """'HH:MM:SS' between entry_at and exit_at, or '' if either is
        missing. Not 'MM:SS' - a pass can in principle run past an hour."""
        if entry_at is None or exit_at is None:
            return ""
        total_seconds = int((exit_at - entry_at).total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
