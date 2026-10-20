"""
Camera module
"""
import datetime
import itertools
import math
import os
import threading
import time
from collections import namedtuple
from urllib.parse import urlsplit

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import pyqtSignal
from logger_config import logger
import theme

# CAMERA-SEC-02: -8 = AV_LOG_QUIET. Raw FFmpeg logging is disabled because it
# may contain credentialed RTSP URLs (user:password@); application camera state
# is logged separately through sanitized application logging (CAMERA-SEC-01).
# Assigned, not setdefault: an inherited verbose level must not switch the
# protection off. Must precede import cv2.
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    logger.warning("OpenCV not available - camera functionality disabled")
    CV2_AVAILABLE = False
    np = None


INVALID_CAMERA_URL = "<invalid URL>"


def safe_camera_location(url) -> str:
    """CAMERA-SEC-01: "host[:port]/path" of a camera URL for logs - never
    the user/password, query or fragment. Anything it can't parse safely
    (no scheme/host, an '@' outside the credentials, bad port, not a
    string) gives INVALID_CAMERA_URL, never the original text. A path
    with '=' (cameras taking user=/password= in the path) is redacted."""
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
        if not parts.scheme or not host:
            return INVALID_CAMERA_URL
        # An unencoded '/', '?' or '#' in a password moves the rest of the
        # credentials out of netloc - urlsplit would then mistake them for
        # the host or the path.
        if "@" in url and "@" not in parts.netloc:
            return INVALID_CAMERA_URL
        if ":" in host:
            host = f"[{host}]"  # IPv6
        if parts.port is not None:
            host = f"{host}:{parts.port}"
        path = parts.path
        if "=" in path or "@" in path:
            path = "/<path redacted>"
        return host + path
    except Exception:
        return INVALID_CAMERA_URL


def safe_camera_label(cam_id: int, url) -> str:
    """CAMERA-SEC-01: e.g. "CAM 1 (192.0.2.20/Streaming/Channels/2)"."""
    return f"CAM {cam_id} ({safe_camera_location(url)})"


def create_capture(url, cam_id, previous=None):
    """CAMERA-MOCK-01: capture object for camera cam_id (0-based) - a new
    cv2.VideoCapture for a real URL; for mock:// a MockCapture, reusing
    `previous` across reconnects so the scenario keeps its state. Only
    called for URLs CamMatrix accepted (mock:// needs allow_mock)."""
    import mock_camera
    if mock_camera.is_mock_url(url):
        if isinstance(previous, mock_camera.MockCapture):
            return previous
        return mock_camera.MockCapture(url, cam_id)
    return cv2.VideoCapture()


# CAMERA-UI-01: [CAMERA] display_mode
DISPLAY_WINDOWED = "windowed"
DISPLAY_SECONDARY_FULLSCREEN = "secondary_fullscreen"
DISPLAY_MODES = (DISPLAY_WINDOWED, DISPLAY_SECONDARY_FULLSCREEN)


def normalize_display_mode(value) -> str:
    """[CAMERA] display_mode -> one of DISPLAY_MODES. Missing/empty means
    windowed (the original behaviour); anything unknown falls back to
    windowed with a warning."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return DISPLAY_WINDOWED
    mode = str(value).strip().lower()
    if mode not in DISPLAY_MODES:
        logger.warning(f"[CAMERA] display_mode={value!r} is not one of {', '.join(DISPLAY_MODES)} - using windowed")
        return DISPLAY_WINDOWED
    return mode


def select_secondary_screen(screens, primary):
    """First screen that isn't the primary one, None with a single screen.
    Doesn't rely on the order of screens[] or on screen names."""
    return next((screen for screen in screens if screen is not primary), None)


def show_camera_window(window, mode, screens=None, primary=None):
    """Show the camera window per display mode. secondary_fullscreen puts
    it fullscreen on a non-primary screen through Qt's own API
    (QWindow.setScreen + showFullScreen - no move(), no X11 coordinates,
    works on Wayland); with a single screen it falls back to windowed."""
    if mode == DISPLAY_SECONDARY_FULLSCREEN:
        if screens is None:
            app = QtWidgets.QApplication.instance()
            screens, primary = app.screens(), app.primaryScreen()
        target = select_secondary_screen(screens, primary)
        if target is None:
            logger.warning("Camera display_mode=secondary_fullscreen but only one screen - showing windowed")
        else:
            window.winId()  # creates the native QWindow behind windowHandle()
            window.windowHandle().setScreen(target)
            window.showFullScreen()
            logger.info(f"Camera view fullscreen on secondary screen {target.name()}")
            return
    window.show()


class CameraView(QtWidgets.QWidget):
    """CAMERA-UI-01: shows the matrix frame from CamMatrix.trigger scaled
    to the widget, keeping its aspect ratio (black around). Presentation
    only - no capture, no thread of its own."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QtCore.Qt.black)
        self.setPalette(palette)
        self.label = QtWidgets.QLabel(self)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self._pixmap = None
        self.frames_shown = 0

    def set_frame(self, frame):
        """frame: BGR numpy image (height, width, 3)."""
        height, width, channels = frame.shape
        image = QImage(frame.data, width, height, channels * width, QImage.Format_RGB888).rgbSwapped()
        self._pixmap = QPixmap.fromImage(image)
        self.frames_shown += 1
        self._rescale()

    def clear(self):
        """Drop the shown frame (an offline camera's last image isn't live)."""
        self._pixmap = None
        self.label.clear()

    def _rescale(self):
        if self._pixmap is None or self.width() <= 0 or self.height() <= 0:
            return
        self.label.setPixmap(self._pixmap.scaled(self.size(), QtCore.Qt.KeepAspectRatio,
                                                 QtCore.Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


def choose_grid(count, width, height, aspect, header=0):
    """CAMERA-UI-02: (rows, columns) for `count` camera tiles in a
    width x height area - the shape that shows the most video at the
    cameras' aspect ratio (each tile loses `header` px of height to its
    title bar). Within 1 % of the best, fewer empty cells win."""
    if count <= 0:
        return 0, 0
    if width <= 0 or height <= 0:
        cols = math.ceil(math.sqrt(count))
        return math.ceil(count / cols), cols
    options = []
    for cols in range(1, count + 1):
        rows = math.ceil(count / cols)
        cell_w, cell_h = width / cols, height / rows - header
        if cell_h <= 0:
            continue
        video_w = min(cell_w, cell_h * aspect)
        options.append((video_w * video_w / aspect, rows * cols - count, rows, cols))
    if not options:  # area too low for even one row of title bars
        return count, 1
    best_area = max(area for area, _, _, _ in options)
    _, _, rows, cols = min((o for o in options if o[0] >= best_area * 0.99), key=lambda o: (o[1], -o[0]))
    return rows, cols


class CameraFeed(QtWidgets.QWidget):
    """Common part of CameraTile and CameraDetailView: ONLINE/OFFLINE label,
    the live image (CameraView, aspect ratio kept) or NO SIGNAL instead of
    the last frozen image, and a frame converted to a pixmap only when its
    generation changes. Presentation of the worker state only - it never
    opens or reads a camera. Subclasses lay out the header."""

    STATUS_STYLE = theme.CAMERA_TILE_STATUS_STYLE

    def _build(self, cam_id, no_signal_style):
        self.statusLabel = QtWidgets.QLabel()
        self.view = CameraView()
        self.view.setStyleSheet(theme.CAMERA_VIEW_STYLE)  # black around the image, not the header colour
        self.noSignalLabel = QtWidgets.QLabel()
        self.noSignalLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.noSignalLabel.setStyleSheet(no_signal_style)
        self.noSignalLabel.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.body = QtWidgets.QStackedWidget()
        self.body.addWidget(self.view)
        self.body.addWidget(self.noSignalLabel)
        self.nameLabel = QtWidgets.QLabel()
        self.set_camera(cam_id)

    def set_camera(self, cam_id):
        """Show camera cam_id, OFFLINE until its first snapshot."""
        self.cam_id = cam_id
        self.title = f"KAMERA {cam_id + 1}"
        self.nameLabel.setText(self.title)
        self.noSignalLabel.setText(f"NO SIGNAL\n{self.title}")
        self.online = None
        self.generation = None  # generation of the frame on screen, None = none
        self.view.clear()
        self.set_state(False, None, None)

    def set_state(self, online, frame, generation):
        live = bool(online) and frame is not None
        if live:
            if generation != self.generation:
                self.view.set_frame(frame)
                self.generation = generation
            self.body.setCurrentWidget(self.view)
        else:
            self.body.setCurrentWidget(self.noSignalLabel)
            if self.generation is not None:
                self.view.clear()
                self.generation = None
        if live != self.online:
            self.online = live
            self.statusLabel.setText("● ONLINE" if live else "● OFFLINE")
            self.statusLabel.setStyleSheet(self.STATUS_STYLE[live])


class CameraTile(CameraFeed):
    """CAMERA-UI-02: one camera in the grid - "KAMERA n" and ONLINE/OFFLINE
    in a title bar, its live image below. CAMERA-UI-03: a left click
    anywhere on the tile emits activated(cam_id) (online or offline)."""

    activated = pyqtSignal(int)

    def __init__(self, cam_id, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.setAutoFillBackground(True)
        self.setStyleSheet(theme.CAMERA_TILE_STYLE)
        self._build(cam_id, theme.CAMERA_TILE_NO_SIGNAL_STYLE)
        self.nameLabel.setStyleSheet(theme.CAMERA_TILE_NAME_STYLE)
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(4, 2, 4, 2)
        header.addWidget(self.nameLabel)
        header.addStretch(1)
        header.addWidget(self.statusLabel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self.body, 1)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.activated.emit(self.cam_id)
            event.accept()
        else:
            super().mousePressEvent(event)


class CameraDetailView(CameraFeed):
    """CAMERA-UI-03: one camera focused over the whole camera window - the
    same published frame as its tile (the worker's [CAMERA] width x height
    frame) shown larger, not a high-resolution stream. "← ZPĚT", a left
    click on the view (and Esc, handled by Camera) emit backRequested.
    Created once and re-pointed with set_camera()."""

    backRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # a plain QWidget subclass paints a stylesheet background only with this
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(theme.CAMERA_DETAIL_STYLE)
        self._build(0, theme.CAMERA_DETAIL_NO_SIGNAL_STYLE)
        self.nameLabel.setStyleSheet(theme.CAMERA_DETAIL_NAME_STYLE)
        self.nameLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.backButton = QtWidgets.QPushButton("← ZPĚT")
        self.backButton.setStyleSheet(theme.CAMERA_DETAIL_BACK_STYLE)
        self.backButton.setFocusPolicy(QtCore.Qt.NoFocus)  # keep Esc for the window
        self.backButton.clicked.connect(self.backRequested.emit)
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(6, 4, 6, 4)
        header.addWidget(self.backButton)
        header.addStretch(1)
        header.addWidget(self.nameLabel)
        header.addStretch(1)
        header.addWidget(self.statusLabel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self.body, 1)
        self.updates = 0

    def update_camera(self, snapshot):
        self.set_state(snapshot.online, snapshot.frame, snapshot.generation)
        self.updates += 1

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.backRequested.emit()
            event.accept()
        else:
            super().mousePressEvent(event)


class CameraGridView(QtWidgets.QWidget):
    """CAMERA-UI-02: N CameraTiles in a grid re-shaped on resize by
    choose_grid(). Fed by CamMatrix.cameras_updated snapshots - no
    capture of its own."""

    HEADER_PX = 28  # tile title bar, for choose_grid()
    cameraActivated = pyqtSignal(int)  # CAMERA-UI-03: a tile was clicked

    def __init__(self, count, aspect, parent=None):
        super().__init__(parent)
        self.aspect = aspect
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QtCore.Qt.black)
        self.setPalette(palette)
        self.tiles = [CameraTile(i, self) for i in range(count)]
        for tile in self.tiles:
            tile.activated.connect(self.cameraActivated.emit)
        self.grid = QtWidgets.QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.grid_shape = None
        self.updates = 0
        self._relayout()

    def update_cameras(self, snapshots):
        for snap in snapshots:
            if 0 <= snap.cam_id < len(self.tiles):
                self.tiles[snap.cam_id].set_state(snap.online, snap.frame, snap.generation)
        self.updates += 1

    def _relayout(self):
        shape = choose_grid(len(self.tiles), self.width(), self.height(), self.aspect, self.HEADER_PX)
        if shape == self.grid_shape:
            return
        old_rows, old_cols = self.grid_shape or (0, 0)
        self.grid_shape = shape
        rows, cols = shape
        for tile in self.tiles:
            self.grid.removeWidget(tile)
        for i, tile in enumerate(self.tiles):
            self.grid.addWidget(tile, i // cols, i % cols)
        for r in range(max(rows, old_rows)):
            self.grid.setRowStretch(r, 1 if r < rows else 0)
        for c in range(max(cols, old_cols)):
            self.grid.setColumnStretch(c, 1 if c < cols else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()


class Ui_Kamery(object):
    """Camera UI setup."""

    def setupUi(self, Kamery):
        Kamery.setObjectName("Kamery")
        Kamery.resize(1920, 1200)
        Kamery.setWindowFlags(QtCore.Qt.Window)
        # Disable close button
        Kamery.setWindowFlags(Kamery.windowFlags() & ~QtCore.Qt.WindowCloseButtonHint)

        # CAMERA-UI-02: the CameraGridView goes in here once the number of
        # (validated) cameras is known - see Camera.__init__.
        self.cameraLayout = QtWidgets.QVBoxLayout(Kamery)
        self.cameraLayout.setContentsMargins(0, 0, 0, 0)

        self.retranslateUi(Kamery)
        QtCore.QMetaObject.connectSlotsByName(Kamery)

    def retranslateUi(self, Kamery):
        Kamery.setWindowTitle("Kamera")


# CAMERA-UI-04: per-camera capture workers.
OPEN_TIMEOUT_MS = 3000
READ_TIMEOUT_MS = 3000
# Seconds to wait before reconnect attempt n (the last value repeats);
# a successful frame resets it.
REAL_RETRY_SCHEDULE = (2, 5, 15, 30)
MOCK_RETRY_SCHEDULE = (0.25, 0.5, 1)
# A mock read returns at once - cap it to a camera-like frame rate.
MOCK_FRAME_INTERVAL = 1 / 28
# Shared deadline for all workers on shutdown (they stop in parallel).
WORKER_STOP_TIMEOUT = READ_TIMEOUT_MS / 1000 + 2
MATRIX_INTERVAL_MS = 33  # ~30 FPS matrix
# Shutdown waits this long for a writer still opening (CAMERA-START-01).
START_THREAD_JOIN_TIMEOUT = 2.0
# CAMERA-LIFECYCLE-01: a runtime stop (requestShutdown) runs in its own
# thread, so it may wait longer than the quit path - long enough for the
# ~17 s writer open seen in production - before it reports stopped anyway.
RUNTIME_STOP_WORKER_TIMEOUT = 10.0
RUNTIME_STOP_OPENER_TIMEOUT = 20.0
RUNTIME_STOP_MATRIX_TIMEOUT_MS = 10000

# Request ids unique across Camera instances: a late result of a camera
# that was switched off can never match a request of its successor.
_record_request_ids = itertools.count(1)

_read_timeout_warned = False


def capture_open_params():
    """OpenCV open params for a real capture: open timeout, and the read
    timeout when this OpenCV build has it (warned once if not)."""
    global _read_timeout_warned
    params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, OPEN_TIMEOUT_MS]
    read_timeout = getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", None)
    if read_timeout is not None:
        params += [read_timeout, READ_TIMEOUT_MS]
    elif not _read_timeout_warned:
        _read_timeout_warned = True
        logger.warning("OpenCV has no CAP_PROP_READ_TIMEOUT_MSEC - camera reads without a timeout")
    return params


# CAMERA-UI-02: one camera's state in a CamMatrix.cameras_updated snapshot;
# generation grows with every new good frame.
CameraSnapshot = namedtuple("CameraSnapshot", "cam_id online frame generation")


class CameraWorker:
    """CAMERA-UI-04: one camera in its own thread. Owns its capture object
    (open/read/reconnect/release happen only in this thread) and publishes
    the latest frame + ONLINE state under a lock - no frame queue. Offline
    cameras are retried on a bounded backoff (retry_schedule), reset by a
    successful frame. Online/offline changes are logged once, never the
    raw URL (CAMERA-SEC-01).

    capture_factory / clock / retry_schedule / frame_interval are injectable
    for tests; step() is one iteration and returns how long to wait."""

    def __init__(self, cam_id, url, width, height, capture_factory=None, clock=time.monotonic,
                 retry_schedule=None, frame_interval=None):
        import mock_camera
        self.cam_id = cam_id
        self.url = url
        self.width = width
        self.height = height
        self.is_mock = mock_camera.is_mock_url(url)
        self._capture_factory = capture_factory or create_capture
        self._clock = clock
        self.retry_schedule = retry_schedule or (MOCK_RETRY_SCHEDULE if self.is_mock else REAL_RETRY_SCHEDULE)
        self.frame_interval = (frame_interval if frame_interval is not None
                               else (MOCK_FRAME_INTERVAL if self.is_mock else 0))
        self._lock = threading.Lock()
        self._frame = None
        self._online = False
        self._generation = 0        # +1 per new good frame (CAMERA-UI-02)
        self._logged_online = None
        self._capture = None
        self._failures = 0          # consecutive failures -> backoff step
        self._next_attempt = 0.0
        self._stop = threading.Event()
        self._thread = None
        self.frames_read = 0

    # -- thread control -------------------------------------------------
    def start(self):
        # daemon: a stream stuck past its read timeout can't block the
        # interpreter exit; it is never terminated/killed.
        self._thread = threading.Thread(target=self.run, name=f"camera-{self.cam_id + 1}", daemon=True)
        self._thread.start()

    def request_stop(self):
        self._stop.set()

    def join(self, timeout):
        if self._thread is not None:
            self._thread.join(max(timeout, 0))
        return not self.is_alive()

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()

    def run(self):
        try:
            while not self._stop.is_set():
                try:
                    delay = self.step()
                except Exception as e:
                    logger.error(f"Camera {self.cam_id + 1} worker error: {type(e).__name__}")
                    self._went_offline()
                    delay = self._schedule_retry()
                if delay > 0:
                    self._stop.wait(delay)
        finally:
            self._release()

    # -- shared state -----------------------------------------------------
    def latest(self):
        """(online, frame) - frame is the last good one, None if never."""
        with self._lock:
            return self._online, self._frame

    def snapshot(self):
        """CameraSnapshot of the published state - never reads the camera."""
        with self._lock:
            return CameraSnapshot(self.cam_id, self._online, self._frame, self._generation)

    # -- one iteration --------------------------------------------------
    def step(self):
        started = self._clock()
        if self._capture is None or not self._capture.isOpened():
            if started < self._next_attempt:
                return self._next_attempt - started
            if not self._open():
                self._went_offline()
                return self._schedule_retry()
        ok, frame = self._capture.read()
        if not ok or frame is None:
            self._release()
            self._went_offline()
            return self._schedule_retry()
        h, w = frame.shape[:2]
        if h != self.height or w != self.width:
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
        self._failures = 0
        self.frames_read += 1
        with self._lock:
            self._frame = frame
            self._online = True
            self._generation += 1
        self._log_state(True)
        return max(self.frame_interval - (self._clock() - started), 0)

    def _open(self):
        try:
            self._capture = self._capture_factory(self.url, self.cam_id, self._capture)
            params = [] if self.is_mock else capture_open_params()
            self._capture.open(self.url, apiPreference=cv2.CAP_FFMPEG, params=params)
            return self._capture.isOpened()
        except Exception:
            return False

    def _release(self):
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass

    def _went_offline(self):
        with self._lock:
            self._online = False
        self._log_state(False)

    def _schedule_retry(self):
        delay = self.retry_schedule[min(self._failures, len(self.retry_schedule) - 1)]
        self._failures += 1
        self._next_attempt = self._clock() + delay
        return delay

    def _log_state(self, online):
        if self._logged_online == online:
            return
        self._logged_online = online
        location = safe_camera_location(self.url)
        if online:
            logger.info(f"Camera {self.cam_id + 1} online ({location})")
        else:
            logger.warning(f"Camera {self.cam_id + 1} offline ({location})")


# CAMERA-UI-05: recording
RECORDING_FPS_DEFAULT = 10
RECORDING_FPS_MIN, RECORDING_FPS_MAX = 1, 30


def normalize_recording_fps(value) -> int:
    """[CAMERA] recording_fps -> int in RECORDING_FPS_MIN..MAX; missing or
    empty = RECORDING_FPS_DEFAULT, anything else invalid -> default + warning."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return RECORDING_FPS_DEFAULT
    try:
        if isinstance(value, bool):
            raise ValueError
        fps = int(str(value).strip())
    except ValueError:
        fps = None
    if fps is None or not RECORDING_FPS_MIN <= fps <= RECORDING_FPS_MAX:
        logger.warning(f"[CAMERA] recording_fps={value!r} is not {RECORDING_FPS_MIN}-{RECORDING_FPS_MAX} - "
                       f"using {RECORDING_FPS_DEFAULT}")
        return RECORDING_FPS_DEFAULT
    return fps


def recording_path(folder, now=None, taken=()):
    """folder/YYYYMMDD_HHMMSS_mmm.avi - with _1, _2... if that file exists
    or is in `taken` (paths already used, e.g. starts within the same
    millisecond whose file isn't on disk yet)."""
    now = now or datetime.datetime.now()
    base = now.strftime("%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}"
    path, n = os.path.join(folder, base + ".avi"), 0
    while os.path.exists(path) or path in taken:
        n += 1
        path = os.path.join(folder, f"{base}_{n}.avi")
    return path


def _open_video_writer(path, fps, size):
    return cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'XVID'), fps, size)


class RecordingController:
    """CAMERA-UI-05: the one owner of the VideoWriter. start / write / stop
    all run under one lock, so a write() can never overlap the release().

    The AVI has a fixed frame rate, so frames are written on a monotonic
    cadence, not per matrix tick: at time t after start() the video must
    hold floor(t * fps) + 1 frames - a faster matrix is thinned out, a
    slower one is padded with its current frame, and stop() pads the tail
    with the last frame - so video duration follows wall time.

    CAMERA-START-01: the writer is opened OUTSIDE the lock (a VideoWriter
    open can block for seconds), so write() never waits for it. Open
    attempts are serialized by _open_lock; each one captures _generation,
    which stop() and close() bump, and installs its writer only if the
    generation is unchanged and the controller isn't closed - otherwise
    the fresh writer is released. stop() ends one recording (a later
    start() works again); close() is final (the Camera is going away)."""

    def __init__(self, fps=RECORDING_FPS_DEFAULT, clock=time.monotonic, writer_factory=None):
        self.fps = fps
        self._clock = clock
        self._writer_factory = writer_factory or _open_video_writer
        self._lock = threading.Lock()
        self._open_lock = threading.Lock()  # one open attempt at a time
        self._generation = 0                # bumped by stop()/close(): cancels a pending open
        self._closed = False
        self._writer = None
        self._started = 0.0
        self._last_frame = None
        self.path = None
        self.frames_written = 0

    @property
    def active(self):
        with self._lock:
            return self._writer is not None

    def _slots_due(self):
        """Whole frame intervals since start() (tiny epsilon: 0.7 s at
        10 FPS must be 7 slots, not 6.999...)."""
        return int((self._clock() - self._started) * self.fps + 1e-6)

    def start(self, path, size):
        """Open a writer for path/size. True when recording (also if it
        already was - no second writer), False if the writer didn't open,
        None if stop()/close() cancelled the attempt while it was opening
        (its writer is released, never installed)."""
        with self._lock:
            if self._closed:
                return None
            if self._writer is not None:
                return True
            generation = self._generation
        with self._open_lock:
            with self._lock:  # a stop()/close() or another start while waiting here?
                if self._closed or generation != self._generation:
                    return None
                if self._writer is not None:
                    return True
            writer = self._writer_factory(path, self.fps, size)  # may block - no _lock held
            if not writer.isOpened():
                writer.release()
                return False
            with self._lock:
                if not self._closed and generation == self._generation:
                    self._writer = writer
                    self._started = self._clock()
                    self._last_frame = None
                    self.path = path
                    self.frames_written = 0
                    return True
            writer.release()  # cancelled during the open
            logger.info("Recording start cancelled while the writer was opening")
            return None

    def write(self, frame):
        """Write frame into every cadence slot due by now (0, 1 or more);
        nothing when not recording. Returns the number of frames written."""
        with self._lock:
            if self._writer is None:
                return 0
            due = self._slots_due() + 1
            count = max(due - self.frames_written, 0)
            for _ in range(count):
                self._writer.write(frame)
            self.frames_written += count
            self._last_frame = frame
            return count

    def stop(self):
        """Pad the tail to wall time, release the writer exactly once, and
        cancel an open in progress. True when not recording afterwards
        (also if it wasn't). A later start() records again."""
        with self._lock:
            self._generation += 1
            return self._finish_locked()

    def close(self):
        """Final stop(): no start() succeeds afterwards, not even one that
        is opening its writer right now. Idempotent."""
        with self._lock:
            self._closed = True
            self._generation += 1
            return self._finish_locked()

    def _finish_locked(self):
        """stop()/close() body, under _lock: pad the tail, release once."""
        writer, self._writer = self._writer, None
        if writer is None:
            return True
        try:
            if self._last_frame is not None:
                due = self._slots_due()
                for _ in range(max(due - self.frames_written, 0)):
                    writer.write(self._last_frame)
                    self.frames_written += 1
            writer.release()
            return True
        except Exception as e:
            logger.error(f"Failed to finish recording: {e}")
            return False
        finally:
            self._last_frame = None


class CamMatrix(QtCore.QThread):
    """Builds the camera matrix from the CameraWorkers' latest frames
    (NO SIGNAL for offline cameras), emits it and feeds the one recording
    pipeline. Never reads a capture itself (CAMERA-UI-04)."""

    trigger = pyqtSignal(np.ndarray) if CV2_AVAILABLE else pyqtSignal(object)
    # CAMERA-UI-02: [CameraSnapshot] of all cameras, once per tick - for the tiles
    cameras_updated = pyqtSignal(object)

    def __init__(self, urls, width, height, user=None, password=None, parent=None, allow_mock=False,
                 worker_factory=None, recording_fps=None):
        QtCore.QThread.__init__(self, parent)

        if not CV2_AVAILABLE:
            logger.error("Cannot initialize camera - OpenCV not available")
            return

        self.urls = urls or []
        self.width = width
        self.height = height
        self.user = user
        self.password = password
        self.running = False
        # CAMERA-UI-05: the single recording pipeline (owns the VideoWriter)
        self.recorder = RecordingController(normalize_recording_fps(recording_fps))
        self.allow_mock = allow_mock  # [DEV] mock_camera = true

        # Validate URLs
        self.urls = [url for url in self.urls if self._validate_url(url)]
        self.num_cameras = len(self.urls)
        factory = worker_factory or CameraWorker
        self.workers = [factory(i, url, width, height) for i, url in enumerate(self.urls)]

        logger.info(f"Initialized camera matrix with {self.num_cameras} cameras")

    def _validate_url(self, url: str) -> bool:
        """Validate camera URL format."""
        if not url or not isinstance(url, str):
            return False
        import mock_camera
        if mock_camera.is_mock_url(url):
            # CAMERA-MOCK-01: a mock camera never passes for a real one.
            if not self.allow_mock:
                logger.warning(f"Mock camera ignored ({safe_camera_location(url)}) - "
                               "requires [DEV] mock_camera = true")
                return False
            if not mock_camera.is_valid_mock_url(url):
                logger.warning(f"Mock camera ignored ({safe_camera_location(url)}) - unknown scenario")
                return False
            return True
        return url.startswith(('http://', 'https://', 'rtsp://'))

    def _create_no_signal_frame(self, cam_id: int):
        """Create blue 'NO SIGNAL' frame."""
        import datetime
        frame = np.full((self.height, self.width, 3), (255, 123, 0), dtype=np.uint8)
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        cv2.putText(frame, f'NO SIGNAL - CAM {cam_id+1} {time_str}',
                   (10, 50), cv2.FONT_HERSHEY_PLAIN, 2, (7, 193, 255), 4)
        return frame

    def snapshots(self):
        """CameraSnapshot of every worker (its latest state, no read)."""
        return [worker.snapshot() for worker in self.workers]

    def current_frames(self, snapshots=None):
        """Latest frame of each online camera, NO SIGNAL for the others."""
        frames = []
        for i, snap in enumerate(snapshots if snapshots is not None else self.snapshots()):
            frames.append(snap.frame if snap.online and snap.frame is not None
                          else self._create_no_signal_frame(i))
        return frames

    def _tick(self):
        """One tick: snapshot every camera for the tiles, then compose,
        emit and record the matrix from the same snapshot."""
        snapshots = self.snapshots()
        self.cameras_updated.emit(snapshots)
        matrix_frame = self._create_matrix(self.current_frames(snapshots))
        self.trigger.emit(matrix_frame)
        self.recorder.write(matrix_frame)  # no-op unless recording
        return matrix_frame

    def start(self, *args):
        """Set running BEFORE the thread exists: a stop() right after start()
        (quit during camera start-up) must win - set inside run() it was
        overwritten and the loop never ended."""
        self.running = True
        super().start(*args)

    def run(self):
        """Matrix thread loop - the workers do the capturing."""
        if not CV2_AVAILABLE:
            logger.warning("Camera thread cannot run - no OpenCV")
            return

        logger.info(f"Camera thread starting ({self.num_cameras} capture workers)...")
        for worker in self.workers:
            worker.start()

        try:
            while self.running:
                try:
                    self._tick()
                    self.msleep(MATRIX_INTERVAL_MS)
                except Exception as e:
                    logger.error(f"Error in camera loop: {e}")
                    self.msleep(1000)

        except Exception as e:
            logger.error(f"Fatal error in camera thread: {e}")
        finally:
            for worker in self.workers:
                worker.request_stop()
            if self.recorder.active:
                self.recorder.stop()
                logger.info("Recording stopped (camera thread stopping)")
            logger.info("Camera thread stopped")

    def _create_matrix(self, frames):
        """Create matrix layout from individual frames like in original version."""
        # Always create matrix for all cameras (never return single frame)
        num_cameras = len(frames) if frames else self.num_cameras
        grid_size = int(np.ceil(np.sqrt(num_cameras)))

        # Create matrix with blue background like original (BGR: 0,0,153 = dark blue)
        matrix_height = grid_size * self.height  # 4 * 356 = 1424
        matrix_width = grid_size * self.width    # 4 * 475 = 1900
        matrix = np.full((matrix_height, matrix_width, 3), (0, 0, 153), dtype=np.uint8)

        for i, frame in enumerate(frames):
            row = i // grid_size
            col = i % grid_size

            y_start = row * self.height
            y_end = y_start + self.height
            x_start = col * self.width
            x_end = x_start + self.width

            matrix[y_start:y_end, x_start:x_end] = frame

        # Add date and time like in original version
        import datetime
        date_str = datetime.datetime.now().strftime("%d-%m-%Y")
        time_str = datetime.datetime.now().strftime("%H:%M:%S")

        # Position text in bottom right area (like original)
        cv2.putText(matrix, date_str, (3*self.width+120, 2*self.height+120),
                   cv2.FONT_HERSHEY_PLAIN, 2, (7, 193, 255), 4)
        cv2.putText(matrix, time_str, (3*self.width+150, 2*self.height+170),
                   cv2.FONT_HERSHEY_PLAIN, 2, (7, 193, 255), 4)

        return matrix

    def stop(self, timeout=WORKER_STOP_TIMEOUT):
        """Stop everything within one shared deadline: ask every worker to
        stop first, then the matrix loop, only then wait - workers wind
        down in parallel, so shutdown takes ~the slowest one, not the sum
        of their timeouts. Threads still blocked at the deadline are left
        to finish on their own (logged), never terminated."""
        deadline = time.monotonic() + timeout
        for worker in getattr(self, "workers", []):
            worker.request_stop()
        self.running = False
        if not self.wait(max(int((deadline - time.monotonic()) * 1000), 0)):
            logger.warning("Camera matrix thread did not stop in time")
        stuck = [w.cam_id + 1 for w in getattr(self, "workers", [])
                 if not w.join(deadline - time.monotonic())]
        if stuck:
            logger.warning(f"Camera workers still stopping after {timeout:.0f} s: {stuck}")
        return not stuck


class Camera(QtWidgets.QWidget, Ui_Kamery):
    """Main camera widget."""

    # CAMERA-START-01: (request id, ok) of a requestRecordStart() - emitted
    # from its opener thread, delivered queued to GUI-thread receivers.
    recordingStartFinished = pyqtSignal(int, bool)
    # CAMERA-LIFECYCLE-01: requestShutdown() finished - matrix thread ended,
    # workers and the writer opener waited for; the Camera may be deleted.
    stopped = pyqtSignal()

    def __init__(self, urls, width, height, user=None, password=None, parent=None, allow_mock=False,
                 display_mode=None, recording_fps=None):
        super().__init__(parent)

        self.urls = urls or []
        self.frame_width = width
        self.frame_height = height

        # Calculate grid size
        num_cameras = len(self.urls)
        self.grid_size = int(np.ceil(np.sqrt(num_cameras))) if CV2_AVAILABLE else 3

        self.setupUi(self)
        self.display_mode = normalize_display_mode(display_mode)
        self._shut_down = False
        self.focused_camera_id = None  # CAMERA-UI-03: None = GRID, else DETAIL of that cam_id
        self._last_snapshots = []
        self._recording_paths = set()  # CAMERA-UI-05: every file name used
        self._paths_lock = threading.Lock()  # GUI thread + opener thread pick names
        # CAMERA-START-01: the one async start attempt (requestRecordStart)
        self._start_lock = threading.Lock()
        self._start_thread = None
        self._start_request = 0  # id of the newest request
        self._stop_thread = None  # CAMERA-LIFECYCLE-01: requestShutdown()
        self._quit_hooked = False

        # Set window icon before show()
        import os
        icon_path = os.path.join(os.path.dirname(__file__), '../files/video.png')
        if os.path.exists(icon_path):
            from PyQt5 import QtGui
            self.setWindowIcon(QtGui.QIcon(icon_path))

        if CV2_AVAILABLE and self.urls:
            self.cam_thread = CamMatrix(urls, width, height, user, password, self, allow_mock=allow_mock,
                                        recording_fps=recording_fps)
            # CAMERA-UI-02: one tile per validated camera, fed by snapshots;
            # CAMERA-UI-03: GRID / DETAIL pages of one stack, both created
            # once. Connect BEFORE show and start (like in original version)
            self.cameraGrid = CameraGridView(self.cam_thread.num_cameras, width / height, self)
            self.cameraDetail = CameraDetailView(self)
            self.cameraStack = QtWidgets.QStackedWidget(self)
            self.cameraStack.addWidget(self.cameraGrid)
            self.cameraStack.addWidget(self.cameraDetail)
            self.cameraLayout.addWidget(self.cameraStack)
            self.cameraGrid.cameraActivated.connect(self.show_detail)
            self.cameraDetail.backRequested.connect(self.show_grid)
            self.cam_thread.cameras_updated.connect(self._on_cameras_updated)
            # Show the camera window (CAMERA-UI-01: per [CAMERA] display_mode)
            show_camera_window(self, self.display_mode)
            # Start thread AFTER signal is connected
            self.cam_thread.start()
            QtWidgets.QApplication.instance().aboutToQuit.connect(self.shutdown)
            self._quit_hooked = True
            self.stopped.connect(self._unhook_quit)  # GUI thread, queued from the stop thread
        else:
            logger.warning("Camera not initialized - OpenCV unavailable or no URLs")
            self.cam_thread = None
            self.cameraGrid = None
            self.cameraDetail = None

    # -- CAMERA-UI-03: GRID / DETAIL ----------------------------------------
    def _on_cameras_updated(self, snapshots):
        """Snapshots go to the visible page only: all tiles in GRID, just
        the focused camera in DETAIL (the hidden grid converts nothing)."""
        self._last_snapshots = snapshots
        if self.focused_camera_id is None:
            self.cameraGrid.update_cameras(snapshots)
            return
        for snap in snapshots:
            if snap.cam_id == self.focused_camera_id:
                self.cameraDetail.update_camera(snap)
                break

    def show_detail(self, cam_id):
        """Focus camera cam_id (by CameraSnapshot.cam_id, never by its
        position in the grid); same window, same screen, same workers."""
        self.focused_camera_id = cam_id
        self.cameraDetail.set_camera(cam_id)
        for snap in self._last_snapshots:
            if snap.cam_id == cam_id:
                self.cameraDetail.update_camera(snap)
                break
        self.cameraStack.setCurrentWidget(self.cameraDetail)

    def show_grid(self):
        """Back to GRID; the tiles catch up with the next snapshot."""
        self.focused_camera_id = None
        self.cameraStack.setCurrentWidget(self.cameraGrid)

    def keyPressEvent(self, event):
        """Esc in DETAIL goes back to GRID - it never closes the window or
        leaves fullscreen. Anything else (Esc in GRID too) as before."""
        if event.key() == QtCore.Qt.Key_Escape and self.focused_camera_id is not None:
            self.show_grid()
            event.accept()
            return
        super().keyPressEvent(event)

    def startRecord(self, folder_path) -> bool:
        """Start recording into a new AVI in folder_path. True only if the
        writer really opened (cv2.VideoWriter doesn't raise on a bad
        codec/path, it just isn't opened) - or recording already runs.
        CAMERA-UI-05: the writer belongs to cam_thread.recorder.
        Blocks while the writer opens - the GUI uses requestRecordStart()."""
        return self._start_recording(folder_path)

    def requestRecordStart(self, folder_path):
        """CAMERA-START-01: startRecord() without blocking the caller - the
        writer opens in a daemon thread, the outcome comes as
        recordingStartFinished(request_id, ok). Returns the request id.

        Only one attempt runs at a time: a request made while one is in
        progress joins it, and if that attempt was cancelled by
        stopRecord() meanwhile, the thread tries once more for the newer
        request. Exactly one signal per thread run, carrying the newest
        id - never after shutdown()."""
        with self._start_lock:
            self._start_request = next(_record_request_ids)
            request = self._start_request
            if self._start_thread is None:
                self._start_thread = threading.Thread(target=self._run_record_start, args=(folder_path,),
                                                      name="camera-record-start", daemon=True)
                self._start_thread.start()
        return request

    def _run_record_start(self, folder_path):
        while True:
            with self._start_lock:
                request = self._start_request
            result = self._start_recording(folder_path)
            with self._start_lock:
                if result is None and request != self._start_request and not self._shut_down:
                    continue  # cancelled, but a newer request wants recording
                self._start_thread = None
                if self._shut_down:
                    return
                try:  # under the lock: shutdown() can't slip in before it
                    self.recordingStartFinished.emit(self._start_request, result is True)
                except RuntimeError:  # the QObject is already gone
                    pass
                return

    def _start_recording(self, folder_path):
        """True recording / False failed / None cancelled by stop or shutdown."""
        if not self.cam_thread or not self.cam_thread.isRunning():
            logger.error("Cannot start recording - camera thread not running")
            return False
        recorder = self.cam_thread.recorder
        if recorder.active:
            return True
        grid = self.cam_thread.num_cameras and int(np.ceil(np.sqrt(self.cam_thread.num_cameras))) or self.grid_size
        size = (grid * self.frame_width, grid * self.frame_height)
        try:
            os.makedirs(folder_path, exist_ok=True)
            with self._paths_lock:
                filepath = recording_path(folder_path, taken=self._recording_paths)
                self._recording_paths.add(filepath)
            result = recorder.start(filepath, size)
            if result is None:
                return None
            if not result:
                logger.error(f"Failed to start recording - VideoWriter could not open {filepath}")
                return False
            logger.info(f"Recording started: {filepath} ({recorder.fps} FPS)")
            return True
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False

    def stopRecord(self) -> bool:
        """Stop recording and release the VideoWriter (once). True when
        recording is stopped (also if none ran), False if there was no
        camera thread or finishing the file failed."""
        if not self.cam_thread:
            logger.error("Cannot stop recording - no camera thread")
            return False
        recorder = self.cam_thread.recorder
        was_active = recorder.active
        ok = recorder.stop()
        if was_active:
            logger.info(f"Recording stopped ({recorder.frames_written} frames)")
        return ok

    def shutdown(self):
        """Stop the camera threads (workers + matrix) - once; also on
        QApplication.aboutToQuit, so a quit path that never closes this
        window doesn't leave threads running. Blocking (bounded) - for the
        quit path; a runtime switch-off uses requestShutdown()."""
        if self._stop_thread is not None:
            # A runtime stop is already running: quitting must not leave its
            # threads behind - wait for it (bounded), it does the rest.
            self._stop_thread.join(WORKER_STOP_TIMEOUT + START_THREAD_JOIN_TIMEOUT)
            return
        if self.cam_thread and not self._shut_down:
            with self._start_lock:
                self._shut_down = True  # a pending async start won't signal
                start_thread = self._start_thread
            # CAMERA-UI-05: never leave the AVI open, even if the matrix
            # thread didn't get to it (idempotent - released only once).
            # CAMERA-START-01: close() first - final, so a writer still
            # opening is released instead of installed.
            self.cam_thread.recorder.close()
            self.cam_thread.stop()
            if start_thread is not None:
                start_thread.join(START_THREAD_JOIN_TIMEOUT)
                if start_thread.is_alive():
                    logger.warning("Recording start still opening its writer at shutdown - "
                                   "it is released when the open returns")

    def requestShutdown(self):
        """CAMERA-LIFECYCLE-01: runtime switch-off without blocking the
        caller. Everything that can block - closing the recorder, stopping
        the matrix thread, joining the workers and a writer still opening -
        runs in a daemon thread; `stopped` is emitted once all of it is
        done (not just CamMatrix.finished). Idempotent: a second call
        changes nothing. No recording start succeeds or signals afterwards."""
        if self._stop_thread is not None:
            return
        with self._start_lock:
            self._shut_down = True
            start_thread = self._start_thread
        self._stop_thread = threading.Thread(target=self._run_shutdown, args=(start_thread,),
                                             name="camera-stop", daemon=True)
        self._stop_thread.start()

    def _run_shutdown(self, start_thread):
        matrix = self.cam_thread
        if matrix is not None:
            matrix.recorder.close()  # final: a writer still opening is released
            matrix.stop()
            # The QThread must have ended before the Camera (its parent) is
            # deleted, or Qt aborts with "QThread: Destroyed while running".
            if not matrix.wait(RUNTIME_STOP_MATRIX_TIMEOUT_MS):
                logger.error("Camera matrix thread did not end - camera kept alive, not reported stopped")
                return
            deadline = time.monotonic() + RUNTIME_STOP_WORKER_TIMEOUT
            stuck = [w.cam_id + 1 for w in matrix.workers if not w.join(deadline - time.monotonic())]
            if stuck:
                logger.warning(f"Camera workers still stopping after switch-off: {stuck}")
        if start_thread is not None:
            start_thread.join(RUNTIME_STOP_OPENER_TIMEOUT)
            if start_thread.is_alive():
                logger.warning("Recording start still opening its writer after switch-off - "
                               "it is released when the open returns")
        logger.info("Camera system stopped")
        try:
            self.stopped.emit()
        except RuntimeError:  # the QObject is already gone
            pass

    def _unhook_quit(self):
        """After a runtime stop this Camera has nothing left to do on quit."""
        if self._quit_hooked:
            self._quit_hooked = False
            try:
                QtWidgets.QApplication.instance().aboutToQuit.disconnect(self.shutdown)
            except (TypeError, RuntimeError):
                pass

    def showViewer(self):
        """CAMERA-LIFECYCLE-01: bring the viewer back (Zobrazit kamery) the
        same way it first appeared - per display_mode (show_camera_window)."""
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized)
        show_camera_window(self, self.display_mode)
        self.raise_()
        if self.display_mode == DISPLAY_WINDOWED:  # fullscreen on the 2nd screen: don't steal focus
            self.activateWindow()

    def closeEvent(self, event):
        """CAMERA-LIFECYCLE-01: the window's X only hides the viewer - the
        cameras, the recording and the camera state stay exactly as they
        are (Zobrazit kamery brings it back; Vypnout kamery or quitting the
        application stops them). Once shut down, a close is just a close."""
        if self._shut_down:
            event.accept()
            return
        event.ignore()
        self.hide()
        logger.info("Camera viewer hidden - cameras keep running")