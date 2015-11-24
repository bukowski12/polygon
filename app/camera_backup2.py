# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'camera1.ui'
#
# Created: Wed Jun  3 10:07:02 2015
#      by: PyQt4 UI code generator 4.11.2
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui
import cv2
from PyQt4.QtGui import QImage, QPixmap
from operator import attrgetter
import base64
import urllib2
import numpy as np
#import os
#from time import sleep
import datetime
import math
import time

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
		Kamery.resize(2000, 1500)
		Kamery.setWindowFlags(QtCore.Qt.Window)
		self.camWindow = QtGui.QLabel(Kamery)
		self.camWindow.setGeometry(QtCore.QRect(0, 0, 3*640, 3*480))
		#self.camWindow.setFrameShape(QtGui.QFrame.StyledPanel)
		#self.camWindow.setFrameShadow(QtGui.QFrame.Raised)
		self.camWindow.setObjectName(_fromUtf8("camWindow"))

		self.retranslateUi(Kamery)
		QtCore.QMetaObject.connectSlotsByName(Kamery)
                                                                                                                                                                                                                                                             
	def retranslateUi(self, Kamery):                                                                                                                                                                                                                         
		Kamery.setWindowTitle(_translate("Kamery", "Kamera", None))


class Grab(QtCore.QThread):
	def __init__(self, urls, user=None, password=None, parent = None):
		QtCore.QThread.__init__(self, parent)
		self.urls = urls
		self.user = user
		self.password = password
		self.start()
	
	def run(self):
		self.openDevice()

	def get_frame(self):
		#try:
        #urllib2.urlopen(request)
#>>> except urllib2.URLError, e:
 #       print e.reason
		response = urllib2.urlopen(self.req)
		img_array = np.asarray(bytearray(response.read()), dtype=np.uint8)
		frame = cv2.imdecode(img_array, 1)
		return frame
		#height, width, bytes_per_component = frame.shape
		#bytes_per_line = bytes_per_component * width
		#image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
		#self.emit(QtCore.SIGNAL("output(QImage)"), image)

	def openDevice(self):
		while (True):
			img = []
			for i,url in enumerate(self.urls):
				try:
					auth_encoded = base64.encodestring('%s:%s' % (self.user, self.password))[:-1]
					self.req = urllib2.Request(url)
					self.req.add_header('Authorization', 'Basic %s' % auth_encoded)
				except Exception,e: print str(e)
				a = self.get_frame()
				img.append(np.array(a))
				#img = self.get_frame()
			camGrid = self.combineImages(img, i)
			camGrid = np.asarray(camGrid[:,:])
			#cv2.imshow('cam',camGrid)
			height, width, bytes_per_component = camGrid.shape
			bytes_per_line = bytes_per_component * width
			image = QImage(camGrid.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
			self.emit(QtCore.SIGNAL("output(QImage)"), image)


	#def combineImages(*args):
	#	numImages = 0
	#	imageArray = []
	#	for img in args:
	#		if img != None and img.width > 0 and img.height > 0:
	#			imageArray.append(img)
	#			numImages += 1
	#		if numImages <= 0:
	#			return None
	def combineImages(self, imageArray, numImages):
		# Find the largest x and y dimensions out of all the images
		# The resulting grid of images will all have this size, 
		# whether or not the images fit (though they won't be scaled).
		#colWidth = max(imageArray, key=attrgetter('width')).width
		#rowHeight = max(imageArray, key=attrgetter('height')).height
		colWidth = 640
		rowHeight = 480
		# Square-root of the number of images will tell us how big the
		# sides of the square need to be. Ceiled to ensure they always
		# all fit.
		grid = int(math.ceil(math.sqrt(numImages)))
		combinedImage = cv2.cv.CreateImage((colWidth*grid, rowHeight*grid), 8, 3)
		cv2.cv.Set(combinedImage, cv2.cv.CV_RGB(50,50,50));
		for index, img in enumerate(imageArray):
			# Ensure all images are same type
			#if img.nChannels == 1:
			#	colourImg = cv.CreateImage((img.width, img.height), 8,3)
			#	cv2.CvtColor(img, colourImg, cv2.CV_GRAY2RGB)
			#	img = colourImg
		  
			# Which grid square are we up to?
			row = int(math.ceil(index / grid))
			column = index % grid
			height, width, channels  = img.shape
			img2 = cv2.cv.fromarray(img)
			cv2.cv.SetImageROI(combinedImage, (column*colWidth, row*rowHeight, width, height))
			cv2.cv.Copy(img2, combinedImage)
			cv2.cv.ResetImageROI(combinedImage)
		 
		return combinedImage


class Camera(QtGui.QWidget, Ui_Kamery):
	def __init__(self, urls, user=None, password=None, parent = None):
		super(Camera, self).__init__(parent)
		self.setupUi(self)
		#QtCore.QThread.__init__(self)
		self.worker = Grab(urls, user, password)
		#self.setWindowFlags(QtCore.Qt.Window)
		#self.setupUi(self)
		#self.camWidget = QtGui.QWidget(parent)
		#ui = Ui_Kamery()
		#ui.setupUi(self.camWidget)
		#self.camWidget = Ui_Kamery()
		#camWidget.setWindowFlags(QtCore.Qt.Window)
		#camWidget.show()
		self.show()
		self.is_recording = False
		#self.camThread = QtCore.QThread()
		#self.camThread.start()
		#self.timer = QtCore.QTimer(None)
		#print self.timer.thread()
		#self.timer.moveToThread(self.camThread)
		#print self.timer.thread()
		#self.timer.setInterval(2000)
		#self.timer.timeout.connect(self.display)
		#self.camThread.start()
		#self.start()
		#self.openDevice()
		self.connect(self.worker, QtCore.SIGNAL("output(QImage)"), self.display)
    
	def display(self, image):
		self.camWindow.setPixmap(QPixmap.fromImage(image))
			#	if self.is_recording:
			#		self.video.write(frame)
		#except:
		#	self.camWindow.setText("<span style='font-size:64pt; font-weight:700; color:#ffffff;'>NO SIGNAL</span>")
		#	self.camWindow.setStyleSheet("background-color: blue")
		#	self.camWindow.setAlignment(QtCore.Qt.AlignCenter)
		#	print "chyba display"

    
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