# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'camera1.ui'
#
# Created: Wed Jun  3 10:07:02 2015
#      by: PyQt4 UI code generator 4.11.2
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui
import cv2
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QTimer
from PyQt4.QtGui import QImage, QPixmap
import cv2
#import os
#from time import sleep
import datetime

try:
	_fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
	def _fromUtf8(s):
		return s

try:
	_encoding = QtGui.QApplication.UnicodeUTF8
	def _translate(context, text, disambig):
		return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
	def _translate(context, text, disambig):
		return QtGui.QApplication.translate(context, text, disambig)

class Ui_Kamery(object):
	def setupUi(self, Kamery):
		#self.setWindowFlags(QtCore.Qt.Window)
		Kamery.setObjectName(_fromUtf8("Kamery"))
		Kamery.resize(642, 481)
		Kamery.setWindowFlags(QtCore.Qt.Window)
		self.camWindow = QtGui.QLabel(Kamery)
		self.camWindow.setGeometry(QtCore.QRect(0, 0, 640, 480))
		#self.camWindow.setFrameShape(QtGui.QFrame.StyledPanel)
		#self.camWindow.setFrameShadow(QtGui.QFrame.Raised)
		self.camWindow.setObjectName(_fromUtf8("camWindow"))

		self.retranslateUi(Kamery)
		QtCore.QMetaObject.connectSlotsByName(Kamery)
                                                                                                                                                                                                                                                             
	def retranslateUi(self, Kamery):                                                                                                                                                                                                                         
		Kamery.setWindowTitle(_translate("Kamery", "Kamera", None))


class Camera(QtGui.QWidget, Ui_Kamery):
	def __init__(self, url, parent = None):
		#super(Camera, self).__init__(self, parent)
		QtGui.QWidget.__init__(self, parent)
		#self.setWindowFlags(QtCore.Qt.Window)
		self.setupUi(self)
		#camWidget = QtGui.QWidget(parent)
		#ui = Ui_Kamery()
		#ui.setupUi(camWidget)
		#camWidget.setWindowFlags(QtCore.Qt.Window)
		#camWidget.show()
		self.show()
		self.url = url
		self.is_recording = False
		self.timer = QtCore.QTimer()
		self.timer.setInterval(500)
		self.timer.timeout.connect(self.display)
        
		self.openDevice()
    
	def display(self):
		#try:
			print "display"
			self.device.open(self.url)
			#if self.device.isOpened():
			#	print "open"
			ret,frame = self.device.read()
			print ret,frame
			if ret:
				height, width, bytes_per_component = frame.shape
				bytes_per_line = bytes_per_component * width
				self.image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
				self.camWindow.setPixmap(QPixmap.fromImage(self.image))
				if self.is_recording:
					self.video.write(frame)
		#except:
		#	self.camWindow.setText("<span style='font-size:64pt; font-weight:700; color:#ffffff;'>NO SIGNAL</span>")
		#	self.camWindow.setStyleSheet("background-color: blue")
		#	self.camWindow.setAlignment(QtCore.Qt.AlignCenter)
		#	print "chyba display"

	def openDevice(self):
		try:
			self.device = cv2.VideoCapture()
			#print self.device
			if self.device:
				self.timer.start()
		except:
			print "chyba open device"
    
	def startRecord(self):
		filename = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '.avi'
		filepath = os.path.join(VIDEO_FOLDER, filename)
		if not os.path.exists(VIDEO_FOLDER):
			os.makedirs(VIDEO_FOLDER)
		try:
			self.device.open(self.url)
			dWidth = int(self.came.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH))
			dHeight = int(self.came.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT))
			fourcc = cv2.cv.CV_FOURCC('X','V','I','D')
			self.video = cv2.VideoWriter(filepath,fourcc,1,(dWidth,dHeight))
			print('start recording...')
			print('saving to %s' % filepath)
			self.is_recording = True
		except:
			print "chyba record"

        #ui.record.setText('Nahravam')
        #ui.record.clicked.disconnect()
        #ui.record.clicked.connect(self.stopRecord)
    
	def stopRecord(self):
		print('stop record')
		self.is_recording = False
		self.video.release()

        #ui.record.setText('Record')
        #ui.record.clicked.disconnect()
        #ui.record.clicked.connect(self.startRecord)

	def changeUrl(self,url):
		self.url = url

	def closeDevice(self):
		self.device.release()