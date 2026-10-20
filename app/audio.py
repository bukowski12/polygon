"""AUDIO-02: sound effect playback (button "Zvukové efekty").

Plays one WAV file in a loop until stopped, through the system's own
command line player in a QProcess - pw-play (PipeWire), paplay (PulseAudio)
or aplay (ALSA), whichever is installed. Qt's QMediaPlayer needs the
libqt5multimedia5-plugins package, which the target machines don't have.

The stream plays at full stream volume; the loudness is the system output
volume (volumeSlider, AUDIO-01). Never raises - failures are logged and
reported through the playingChanged signal / is_playing.
"""

import shutil

from PyQt5 import QtCore

from logger_config import logger

PLAYERS = ("pw-play", "paplay", "aplay")


class Audio(QtCore.QObject):
    playingChanged = QtCore.pyqtSignal(bool)

    def __init__(self, audiofile, parent=None, which=shutil.which, process_factory=QtCore.QProcess):
        super().__init__(parent)
        self.audiofile = audiofile
        self.player = next((name for name in PLAYERS if which(name)), None)
        if self.player is None:
            logger.warning("Audio: no player found (pw-play, paplay, aplay) - sound effects disabled")
        self._process_factory = process_factory
        self._process = None
        self._wanted = False

    @property
    def available(self):
        return self.player is not None

    @property
    def is_playing(self):
        return self._wanted

    def play(self):
        """Start the looped playback (no-op if already playing). True on start."""
        if self._wanted:
            return True
        if not self.available:
            return False
        self._wanted = True
        if not self._start_process():
            self._wanted = False
            return False
        logger.info(f"Audio: playing {self.audiofile} ({self.player}, loop)")
        self.playingChanged.emit(True)
        return True

    def stop(self):
        """Stop the playback (no-op if not playing)."""
        if not self._wanted:
            return
        self._wanted = False
        process, self._process = self._process, None
        if process is not None:
            process.finished.disconnect(self._on_finished)
            process.kill()
            process.waitForFinished(1000)
        logger.info("Audio: stopped")
        self.playingChanged.emit(False)

    def _start_process(self):
        process = self._process_factory(self)
        process.finished.connect(self._on_finished)
        process.start(self.player, [self.audiofile])
        if not process.waitForStarted(2000):
            logger.warning(f"Audio: {self.player} did not start: {process.errorString()}")
            process.finished.disconnect(self._on_finished)
            return False
        self._process = process
        return True

    def _on_finished(self, exit_code, exit_status):
        """End of the file -> loop; a player error -> stop."""
        if not self._wanted:
            return
        if exit_status != QtCore.QProcess.NormalExit or exit_code != 0:
            logger.warning(f"Audio: {self.player} ended with code {exit_code} - playback stopped")
            self._wanted = False
            self._process = None
            self.playingChanged.emit(False)
            return
        if not self._start_process():  # play the file again
            self._wanted = False
            self._process = None
            self.playingChanged.emit(False)
