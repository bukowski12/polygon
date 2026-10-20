"""
CAMERA-MOCK-01: synthetic camera sources for home development - no RTSP,
VPN, production IPs, credentials or internet. Accepted by CamMatrix only
with [DEV] mock_camera = true.

MockCapture has the part of the cv2.VideoCapture interface camera.py uses
(open / isOpened / read / release). CamMatrix reuses one MockCapture per
camera across reconnects, so a scenario keeps its state like a physical
camera would.

Scenarios (URL query values are integers; anything invalid -> default):

    mock://online[?w=640&h=360]
        Always online; moving bar, CAM name, ONLINE, time and frame counter.
    mock://nosignal
        Never opens -> CamMatrix shows its own "NO SIGNAL - CAM n".
    mock://flaky[?up=60&down=30]
        `up` frames are read, then the stream drops (read fails); the next
        `down` open() attempts fail (CamMatrix makes one per loop), then the
        camera opens again and the cycle repeats.
    mock://slow[?read_ms=500&open_ms=0]
        Online, but every read() (and open()) blocks for the given time.
"""
import datetime
import time
from urllib.parse import parse_qs, urlsplit

MOCK_SCHEME = "mock"
SCENARIOS = ("online", "nosignal", "flaky", "slow")

DEFAULT_SIZE = (640, 360)
FLAKY_UP_FRAMES = 60
FLAKY_DOWN_OPENS = 30
SLOW_READ_MS = 500


def is_mock_url(url) -> bool:
    return isinstance(url, str) and url.strip().lower().startswith(MOCK_SCHEME + "://")


def is_valid_mock_url(url) -> bool:
    """mock:// with a known scenario."""
    return is_mock_url(url) and urlsplit(url.strip()).netloc.lower() in SCENARIOS


def _int_param(query, name, default, minimum=0):
    try:
        value = int(query[name][0])
    except (KeyError, IndexError, ValueError):
        return default
    return value if value >= minimum else default


class MockCapture:
    """One synthetic camera. `sleep` is injectable so tests of the slow
    scenario don't wait for real time."""

    def __init__(self, url, cam_id=0, sleep=time.sleep):
        parts = urlsplit(url.strip())
        query = parse_qs(parts.query)
        self.scenario = parts.netloc.lower()
        if self.scenario not in SCENARIOS:
            raise ValueError(f"unknown mock camera scenario: {self.scenario!r}")
        self.name = f"CAM {cam_id + 1}"
        self.width = _int_param(query, "w", DEFAULT_SIZE[0], minimum=16)
        self.height = _int_param(query, "h", DEFAULT_SIZE[1], minimum=16)
        self.up_frames = _int_param(query, "up", FLAKY_UP_FRAMES, minimum=1)
        self.down_opens = _int_param(query, "down", FLAKY_DOWN_OPENS)
        self.read_ms = _int_param(query, "read_ms", SLOW_READ_MS)
        self.open_ms = _int_param(query, "open_ms", 0)
        self._sleep = sleep
        self._opened = False
        self.frame_count = 0          # frames produced since creation
        self._frames_left = self.up_frames
        self._failed_opens = 0

    def open(self, url=None, apiPreference=None, params=None):
        if self.scenario == "slow" and self.open_ms:
            self._sleep(self.open_ms / 1000)
        if self.scenario == "nosignal":
            self._opened = False
        elif self.scenario == "flaky" and self._frames_left == 0:
            if self._failed_opens < self.down_opens:
                self._failed_opens += 1
                self._opened = False
            else:
                self._failed_opens = 0
                self._frames_left = self.up_frames
                self._opened = True
        else:
            self._opened = True
        return self._opened

    def isOpened(self):
        return self._opened

    def read(self):
        if not self._opened:
            return False, None
        if self.scenario == "slow" and self.read_ms:
            self._sleep(self.read_ms / 1000)
        if self.scenario == "flaky":
            if self._frames_left == 0:
                self._opened = False  # the stream dropped
                return False, None
            self._frames_left -= 1
        self.frame_count += 1
        return True, self._render()

    def release(self):
        self._opened = False

    def _render(self):
        import cv2  # only here: is_mock_url() must work without OpenCV
        import numpy as np
        w, h = self.width, self.height
        frame = np.full((h, w, 3), (60, 45, 30), dtype=np.uint8)
        bar_w = max(w // 12, 4)
        x = (self.frame_count * 8) % (w + bar_w) - bar_w
        frame[:, max(x, 0):max(x + bar_w, 0)] = (0, 200, 255)
        now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        lines = (
            (f"{self.name} MOCK {self.scenario.upper()}", (255, 255, 255)),
            ("ONLINE", (0, 220, 0)),
            (now, (255, 255, 255)),
            (f"frame {self.frame_count}", (255, 255, 255)),
        )
        for row, (text, color) in enumerate(lines):
            cv2.putText(frame, text, (10, 30 + row * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        return frame
