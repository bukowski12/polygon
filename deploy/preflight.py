"""DEPLOY-01: read-only runtime preflight of a Polygon checkout.

Run by bin/polygon-preflight (and by bin/polygon-update right after a
fast-forward - a failing new version is rolled back). It only checks that
the code can start on this PC: the system Python modules from APT, the Qt
QMYSQL driver, the config file. It never connects to the DB, LDAP, QUIDO or
a camera and writes nothing - the config is loaded with the app log
pointed at a temporary directory (removed again).

Exit code: 0 = PASS, 1 = PASS with WARNINGs, 2 = HARD FAIL.
"""

import argparse
import importlib
import logging
import os
import shutil
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DIR = os.path.join(REPO, "app")

PASS, WARNING, HARD_FAIL = "PASS", "WARNING", "HARD FAIL"
EXIT_CODES = {PASS: 0, WARNING: 1, HARD_FAIL: 2}

# (module, level when missing, why)
MODULES = (
    ("PyQt5.QtCore", HARD_FAIL, "python3-pyqt5"),
    ("PyQt5.QtWidgets", HARD_FAIL, "python3-pyqt5"),
    ("PyQt5.QtPrintSupport", HARD_FAIL, "python3-pyqt5 - tisk/PDF"),
    ("PyQt5.QtSql", HARD_FAIL, "python3-pyqt5.qtsql"),
    # the app plays sound through pw-play/paplay/aplay (QProcess) and does not
    # import QtMultimedia today - kept as a warning for the documented package set
    ("PyQt5.QtMultimedia", WARNING, "python3-pyqt5.qtmultimedia (aplikace ho nyní neimportuje)"),
    ("cv2", HARD_FAIL, "python3-opencv - kamery"),
    ("numpy", HARD_FAIL, "python3-numpy (s python3-opencv)"),
    ("ldap3", HARD_FAIL, "python3-ldap3 - přihlášení"),
)
VOLUME_BACKENDS = ("wpctl", "pactl")       # app/system_volume.py
AUDIO_PLAYERS = ("pw-play", "paplay", "aplay")  # app/audio.py


def _module(name):
    try:
        importlib.import_module(name)
        return True, ""
    except Exception as e:  # ImportError, or a broken binary module
        return False, f"{type(e).__name__}: {e}"


def _qmysql():
    try:
        from PyQt5 import QtCore, QtSql
        app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])  # plugin paths need one
        available = QtSql.QSqlDatabase.isDriverAvailable("QMYSQL")
        del app
        return available, "" if available else "QMYSQL není mezi Qt SQL drivery (libqt5sql5-mysql)"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _config(path):
    """Load the config through the app's ConfigManager - its log goes to a
    temporary directory, never log/polygon.log."""
    if not os.path.isfile(path):
        return False, f"{path} neexistuje"
    log_dir = tempfile.mkdtemp(prefix="polygon-preflight-")
    previous = os.environ.get("POLYGON_LOG_DIR")
    os.environ["POLYGON_LOG_DIR"] = log_dir
    try:
        if APP_DIR not in sys.path:
            sys.path.insert(0, APP_DIR)
        from config_manager import ConfigManager, ConfigurationError
        try:
            ConfigManager(path).load_config()
            return True, ""
        except ConfigurationError as e:
            return False, str(e)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        logging.shutdown()
        if previous is None:
            os.environ.pop("POLYGON_LOG_DIR", None)
        else:
            os.environ["POLYGON_LOG_DIR"] = previous
        shutil.rmtree(log_dir, ignore_errors=True)


def run(config_path, which=shutil.which):
    """[(level, name, detail)] of every check."""
    results = []
    for name, level, why in MODULES:
        ok, error = _module(name)
        results.append((PASS if ok else level, name, why if ok else f"{why}: {error}"))
    ok, detail = _qmysql()
    results.append((PASS if ok else HARD_FAIL, "Qt SQL driver QMYSQL", detail or "libqt5sql5-mysql"))
    ok, detail = _config(config_path)
    results.append((PASS if ok else HARD_FAIL, "config/polygon.conf", detail or config_path))
    volume = [name for name in VOLUME_BACKENDS if which(name)]
    results.append((PASS if volume else WARNING, "hlasitost (wpctl / pactl)",
                    ", ".join(volume) if volume else "ani wpctl (wireplumber), ani pactl (pulseaudio-utils) – "
                                                     "ovládání hlasitosti bude vypnuté"))
    players = [name for name in AUDIO_PLAYERS if which(name)]
    results.append((PASS if players else WARNING, "přehrávač zvuku (pw-play / paplay / aplay)",
                    ", ".join(players) if players else "žádný (pipewire-bin / pulseaudio-utils / alsa-utils) – "
                                                       "zvukové efekty budou vypnuté"))
    return results


def overall(results):
    levels = {level for level, _, _ in results}
    return HARD_FAIL if HARD_FAIL in levels else WARNING if WARNING in levels else PASS


def main(argv=None):
    parser = argparse.ArgumentParser(description="Polygon preflight (jen čtení)")
    parser.add_argument("--config", default=os.path.join(REPO, "config", "polygon.conf"))
    parser.add_argument("--quiet", action="store_true", help="vypsat jen problémy a výsledek")
    args = parser.parse_args(argv)
    results = run(args.config)
    for level, name, detail in results:
        if not args.quiet or level != PASS:
            print(f"{level:<9} {name} – {detail}")
    result = overall(results)
    print(f"PREFLIGHT: {result}")
    return EXIT_CODES[result]


if __name__ == "__main__":
    sys.exit(main())
