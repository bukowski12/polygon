"""HW-IO: QUIDO network I/O off the GUI thread.

One long-lived daemon thread per QUIDO module - "quido-in" and "quido-out".
Each reads its module periodically (POLL_INTERVAL, RETRY_INTERVAL after a
failed read - no hammering of a dead module) and hands the result to a
callback. quido-out also runs Output jobs (manual toggle, the emergency
sequence) one at a time between its reads, so a read and a SET never talk
to QUIDO Output at the same time.

A running socket call is never interrupted - it ends by itself, bounded by
pyspinel.socket_timeout. After a job quido-out waits `after_job_delay`
(HW-READ-04: the real QUIDO Output refuses a connection opened right after
the previous one closed), reads the outputs and only then reports the job
done - the GUI gets the fresh states with the result.

No Qt here: callbacks run in the worker thread (MainWindow passes Qt
signals, delivered queued in the GUI thread). Nothing is called back after
stop().
"""
import atexit
import threading
import time
import weakref

from logger_config import logger

POLL_INTERVAL = 0.6    # s - as the former GUI QTimer
RETRY_INTERVAL = 2.5   # s - next read after a failed one
STOP_TIMEOUT = 4.0     # s - > pyspinel.socket_timeout: a call in progress may finish
EXIT_JOIN_TIMEOUT = 0.5  # s - per worker still running at interpreter exit

_live_workers = weakref.WeakSet()


def request_stop_all(workers):
    """Stop requests for `workers` (non-blocking) - e.g. when their owner is destroyed."""
    for worker in list(workers):
        worker.request_stop()


@atexit.register
def _stop_live_workers():
    """Interpreter exit: no worker may still report into a Qt object while
    Qt is being torn down (a daemon thread would otherwise keep running)."""
    workers = list(_live_workers)
    request_stop_all(workers)
    for worker in workers:
        worker.join(EXIT_JOIN_TIMEOUT)


def read_result(read):
    """(True, value) or (False, error) of one read() call."""
    try:
        return True, read()
    except Exception as e:
        return False, e


class OutputJob:
    """One Output operation for quido-out: `fn` runs in the worker thread,
    its return value / exception end up in `result` / `error`."""

    def __init__(self, name, fn):
        self.name = name
        self.fn = fn
        self.result = None
        self.error = None
        self._done = threading.Event()

    def wait(self, timeout_ms=None):
        """True once the job finished and was reported (QThread.wait-like)."""
        return self._done.wait(None if timeout_ms is None else timeout_ms / 1000)

    @property
    def done(self):
        return self._done.is_set()


class QuidoWorker:
    """Periodic read of one QUIDO module + serial Output jobs, in one thread."""

    def __init__(self, name, read, on_read, on_job_done=None, interval=POLL_INTERVAL,
                 retry_interval=RETRY_INTERVAL, after_job_delay=0.0, sleep=time.sleep):
        self.name = name
        self._read = read
        self._on_read = on_read
        self._on_job_done = on_job_done
        self.interval = interval
        self.retry_interval = retry_interval
        self.after_job_delay = after_job_delay
        self._sleep = sleep
        self._cond = threading.Condition()
        self._jobs = []
        self._stopping = False
        self._thread = None
        self._last_ok = None  # log only OK <-> error transitions

    def start(self):
        _live_workers.add(self)
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def submit(self, job):
        """Queue an Output job; False once stopped (the job never runs)."""
        with self._cond:
            if self._stopping:
                return False
            self._jobs.append(job)
            self._cond.notify()
            return True

    def request_stop(self):
        """No new read or job starts; returns at once."""
        with self._cond:
            self._stopping = True
            self._cond.notify()

    def join(self, timeout=STOP_TIMEOUT):
        """True if the thread has ended within timeout (it is a daemon: a
        call stuck past it never keeps the process alive)."""
        if self._thread is not None:
            self._thread.join(timeout)
            return not self._thread.is_alive()
        return True

    def stop(self, timeout=STOP_TIMEOUT):
        self.request_stop()
        return self.join(timeout)

    @property
    def stopping(self):
        return self._stopping

    def _run(self):
        next_read = 0.0
        while True:
            with self._cond:
                while not self._stopping and not self._jobs:
                    wait = next_read - time.monotonic()
                    if wait <= 0:
                        break
                    self._cond.wait(wait)
                if self._stopping:
                    return
                job = self._jobs.pop(0) if self._jobs else None
            if job is not None:
                self._run_job(job)
            ok = self._poll() if not self._stopping else None
            if job is not None:
                self._report(self._on_job_done, job)
                job._done.set()
            next_read = time.monotonic() + (self.interval if ok else self.retry_interval)

    def _run_job(self, job):
        try:
            job.result = job.fn()
        except Exception as e:
            job.error = e
            logger.error(f"QUIDO {self.name}: {job.name} failed: {e!r}")
        if self.after_job_delay and not self._stopping:
            self._sleep(self.after_job_delay)

    def _poll(self):
        ok, value = read_result(self._read)
        if ok != self._last_ok:
            if ok:
                logger.info(f"QUIDO {self.name}: read OK")
            else:
                logger.error(f"QUIDO {self.name}: read failed: {value!r} - next try in {self.retry_interval:g} s")
            self._last_ok = ok
        self._report(self._on_read, (ok, value))
        return ok

    def _report(self, callback, value):
        if callback is None or self._stopping:
            return
        try:
            callback(value)
        except Exception as e:  # e.g. the receiver is gone - never kill the worker
            logger.warning(f"QUIDO {self.name}: result not delivered: {e!r}")
