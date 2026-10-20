"""
Centralized logger configuration to avoid circular imports.
"""
import os
import logging
import faulthandler
from datetime import datetime

# Get application directory
__APP_DIR__ = os.path.dirname(__file__)
# log/ is git-ignored, so a clean checkout has none: create it before the
# log file is opened (LOG-02), or the import - and the whole app - fails.
# POLYGON_LOG_DIR moves it elsewhere - only automated tests set it (LOG-01),
# so they never write the app's own log/polygon.log.
LOG_DIR = os.path.abspath(os.environ.get("POLYGON_LOG_DIR") or os.path.join(__APP_DIR__, "..", "log"))
os.makedirs(LOG_DIR, exist_ok=True)
__log_filename__ = os.path.join(LOG_DIR, "polygon.log")

# Configure logging
logging.basicConfig(
    filename=__log_filename__,
    level=logging.INFO,  # Changed from ERROR to INFO to show info messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create logger instance
logger = logging.getLogger(__name__)


# Native crashes (SIGSEGV, SIGABRT, ... e.g. inside Qt) kill the process
# before any Python logging can run - faulthandler writes the Python and C
# stack of such a crash into this file instead.
CRASH_LOG = os.path.join(LOG_DIR, "crash.log")
_crash_file = None  # kept open for the whole process: faulthandler writes into it on a crash


def enable_crash_log(path=CRASH_LOG) -> bool:
    """Enable faulthandler into `path` (appending). Each start writes a
    timestamped marker line, since faulthandler's own output has no time.
    Returns False (and logs a warning) if the file can't be opened."""
    global _crash_file
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        crash_file = open(path, "a", encoding="utf-8")
        crash_file.write(f"=== start {datetime.now():%Y-%m-%d %H:%M:%S} pid {os.getpid()} ===\n")
        crash_file.flush()
        faulthandler.enable(crash_file, all_threads=True)
    except OSError as e:
        logger.warning(f"Crash log unavailable ({path}): {e}")
        return False
    _crash_file = crash_file
    return True
