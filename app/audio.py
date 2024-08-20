from PyQt5.QtMultimedia import QAudioOutput, QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, QThread


class Audio(QThread):
    def __init__(self, audiofile, parent):
        super(Audio, self).__init__(parent)
        self.aOutput = QAudioOutput()
        self.player = QMediaPlayer(self)
        url = QUrl.fromLocalFile(audiofile)
        self.content = QMediaContent(url)
        self.player.setMedia(self.content)

    def run(self):
        self.player.play()

    def play(self):
        self.start()

    def stop(self):
        self.player.pause()

    def onFinished(self):
        self.player.stop()
        self.player.play()

    def changeVolume(self, value):
        self.player.setVolume(value)