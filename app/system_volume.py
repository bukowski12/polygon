"""AUDIO-01: system output volume of the PC (-> external amplifier).

Reads and sets the volume of the default audio output, 0-100 %, through the
desktop sound server's command line tool - no sudo:
- wpctl (PipeWire / WirePlumber, Ubuntu default),
- pactl (PulseAudio, or pipewire-pulse) as a fallback.
Never above 100 % (no software boost). Every failure is logged and reported
as None / False - the caller disables the volume control, nothing raises.
"""

import re
import shutil
import subprocess

from logger_config import logger

COMMAND_TIMEOUT_S = 2

_WPCTL_SINK = "@DEFAULT_AUDIO_SINK@"
_PACTL_SINK = "@DEFAULT_SINK@"


def _clamp(percent):
    return max(0, min(100, int(round(percent))))


class SystemVolume:
    BACKENDS = ("wpctl", "pactl")

    def __init__(self, run=subprocess.run, which=shutil.which):
        self._run = run
        self.backend = next((name for name in self.BACKENDS if which(name)), None)
        if self.backend is None:
            logger.warning("System volume: neither wpctl nor pactl found - volume control disabled")

    @property
    def available(self):
        return self.backend is not None

    def _call(self, args):
        """stdout of the command, or None on any failure."""
        try:
            result = self._run(args, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning(f"System volume: {' '.join(args)} failed: {e}")
            return None
        if result.returncode != 0:
            logger.warning(f"System volume: {' '.join(args)} exited {result.returncode}: "
                           f"{(result.stderr or '').strip()}")
            return None
        return result.stdout

    def get(self):
        """Current output volume 0-100 (a boosted >100 % reads as 100), or None."""
        if self.backend == "wpctl":
            out = self._call(["wpctl", "get-volume", _WPCTL_SINK])
            match = re.search(r"Volume:\s*([0-9.]+)", out or "")
            value = float(match.group(1)) * 100 if match else None
        elif self.backend == "pactl":
            out = self._call(["pactl", "get-sink-volume", _PACTL_SINK])
            match = re.search(r"(\d+)%", out or "")  # first channel
            value = float(match.group(1)) if match else None
        else:
            return None
        if value is None:
            if out is not None:
                logger.warning(f"System volume: unexpected {self.backend} output: {out.strip()!r}")
            return None
        return _clamp(value)

    def set(self, percent):
        """Set the output volume to percent (clamped to 0-100). True on success."""
        percent = _clamp(percent)
        if self.backend == "wpctl":
            # -l 1.0: wpctl itself never goes above 100 %
            args = ["wpctl", "set-volume", "-l", "1.0", _WPCTL_SINK, f"{percent / 100:.2f}"]
        elif self.backend == "pactl":
            args = ["pactl", "set-sink-volume", _PACTL_SINK, f"{percent}%"]
        else:
            return False
        return self._call(args) is not None
