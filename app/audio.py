# -*- coding: utf-8 -*-

import pyaudio
import wave
import sys
from PyQt4 import QtCore

CHUNK = 2048

class Audio(QtCore.QThread):
    def __init__(self, audiofile, parent):
        super(Audio, self).__init__(parent)
        self.player = pyaudio.PyAudio()
        self.wf = wave.open(audiofile, 'rb')
        self.stream = self.player.open(format=self.player.get_format_from_width(self.wf.getsampwidth()),
                channels=self.wf.getnchannels(),
                rate=self.wf.getframerate(),
                output=True)
                #output_device_index=1)
        self.wf = wave.open(audiofile, 'rb')
    
    def run(self):
        self.loop = True
        data = self.wf.readframes(CHUNK)
        while self.loop :
            self.stream.write(data)
            data = self.wf.readframes(CHUNK)
            if data == '' : # If file is over then rewind.
                self.wf.rewind()
                data = self.wf.readframes(CHUNK)

    def play(self):
        self.start()

    def stop(self):
        self.loop = False
  
    def changeVolume(self, value):
        #self.volume = value
        pass

    def __del__(self):
        self.stream.close()
        self.p.terminate()