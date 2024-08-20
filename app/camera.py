from PyQt5 import QtCore, QtWidgets
import cv2
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import pyqtSignal
import numpy as np
import os
import datetime
import math

try:
	_fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
	def _fromUtf8(s):
		return s

try:
	_encoding = QtWidgets.QApplication.UnicodeUTF8
	def _translate(context, text, disambig):
		return QtWidgets.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
	def _translate(context, text, disambig):
		return QtWidgets.QApplication.translate(context, text, disambig)

class Ui_Kamery(object):
	def setupUi(self, Kamery, grid, width, height):
		#self.setWindowFlags(QtCore.Qt.Window)
		Kamery.setObjectName(_fromUtf8("Kamery"))
		#Kamery.resize(grid*width, 3*height)
		Kamery.resize(1920, 1200)
		Kamery.setWindowFlags(QtCore.Qt.Window)
		# disable (but not hide) close button
		Kamery.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowCloseButtonHint)
		self.camWindow = QtWidgets.QLabel(Kamery)
		#self.camWindow.setGeometry(QtCore.QRect(0, 0, 3*352, 3*290))
		self.camWindow.setGeometry(QtCore.QRect(0, 0, grid*width, grid*height))
		self.camWindow.setObjectName(_fromUtf8("camWindow"))
		self.retranslateUi(Kamery)
		QtCore.QMetaObject.connectSlotsByName(Kamery)
                                                                                                                                                                                                                                                             
	def retranslateUi(self, Kamery):                                                                                                                                                                                                                         
		Kamery.setWindowTitle(_translate("Kamery", "Kamera", None))


class CamMatrix(QtCore.QThread):

	trigger = pyqtSignal(np.ndarray)

	def __init__(self, urls, width, height, user=None, password=None, parent = None):
		QtCore.QThread.__init__(self, parent)
		self.urls = urls
		self.user = user
		self.password = password
		self.width = width
		self.height = height
		self.start()
	
	def run(self):
		self.camLoop()

	def camLoop(self):
		self.countCam = len(self.urls)
		self.img = self.createArray()
		self.device = [None]*self.countCam
		self.init_device()
		while (True):
			for i,url in enumerate(self.urls):
				if not self.device[i].isOpened():
					self.init_device(i)
				frame= self.getFrame(i)
				(height, width) = frame.shape[:2]
				if not (height == self.height and width == self.width):
					frame = self.resize_image(frame, self.height, self.width)
				self.insertImage(i, frame)
				camGrid = self.combineImages(self.img, self.countCam)
				self.trigger.emit(camGrid)

	def init_device(self, cam=None):
			for i,url in enumerate(self.urls):
				if cam==i or cam is None:
					try:
						self.device[i] = cv2.VideoCapture()
						self.device[i].open(url, apiPreference=cv2.CAP_FFMPEG, params=[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000],)
						if not self.device[i].isOpened():
							raise ConnectionError
					except ConnectionError:
						print ("Error cam - ", i+1)
		
	def resize_image (self, image, height, width):
		if height > width:
			ratio = self.height / float(height)
			new_width = int(width * ratio)
			new_height = height
		else:
			ratio = self.width / float(width)
			new_height = int(height * ratio)
			new_width = width
		return(cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA))

	def insertImage (self, idcam, frame):
		self.img[idcam] = np.array(frame)

	def getFrame(self,cam):
		ret,frame = self.device[cam].read()
		if ret==False:
			frame = self.blueDeath(cam)
			self.device[cam].release()
		return frame
	
	def blueDeath(self, idcam):
		frame = np.full((self.height,self.width,3),(255,123,0),dtype=np.uint8)
		time = str(datetime.datetime.now().strftime("%H:%M:%S"))
		cv2.putText(frame, f'NO SIGNAL - CAM {idcam+1} {time}', (10,50), cv2.FONT_HERSHEY_PLAIN, 2,(7,193,255),4)
		return frame

	def createArray(self):
		imgArray = []
		for i in range(self.countCam):
			img = self.blueDeath(i)
			imgArray.append(img)
		return (imgArray)

	def combineImages(self, imageArray, numImages):
		# Square-root of the number of images will tell us how big the
		# sides of the square need to be. Ceiled to ensure they always all fit.
		grid = int(math.ceil(math.sqrt(numImages)))
		combinedImage = np.full((self.height*grid, self.width*grid, 3), (0,0,153), np.uint8)
		for index, img in enumerate(imageArray):
			# Which grid square are we up to?
			row = int(math.floor(index / grid))
			column = index % grid
			height, width  = img.shape[:2]
			combinedImage[row*self.height:row*self.height + height, column*self.width:column*self.width + width] = img
			date = str(datetime.datetime.now().strftime("%d-%m-%Y"))
			time = str(datetime.datetime.now().strftime("%H:%M:%S"))
			cv2.putText(combinedImage, date, (3*self.width+120,2*self.height+120), cv2.FONT_HERSHEY_PLAIN, 2,(7,193,255),4)
			cv2.putText(combinedImage, time, (3*self.width+150,2*self.height+170), cv2.FONT_HERSHEY_PLAIN, 2,(7,193,255),4)
		return combinedImage


class Camera(QtWidgets.QWidget, Ui_Kamery):
    	
	def __init__(self, urls, width, height, user=None, password=None, parent = None):
		super(Camera, self).__init__(parent)
		grid = int(math.ceil(math.sqrt(len(urls))))
		self.dWidth = grid*width
		self.dHeight = grid*height
		self.setupUi(self, grid, width, height)
		self.camWindow.setGeometry(QtCore.QRect(0, 0, grid*width, grid*height))
		self.worker = CamMatrix(urls, width, height, user, password)
		self.show()
		self.is_recording = False
		self.worker.trigger.connect(self.display)
    
	def display(self, camGrid):
		height, width, bytes_per_component = camGrid.shape
		bytes_per_line = bytes_per_component * width
		image = QImage(camGrid.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
		self.camWindow.setPixmap(QPixmap.fromImage(image))
		if self.is_recording is True:
			self.record.write(camGrid)
    
	def startRecord(self, folder):
		filename = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '.avi'
		filepath = os.path.join(folder, filename)
		try:
			self.record = cv2.VideoWriter(filepath,cv2.VideoWriter_fourcc(*'XVID'),1,(self.dWidth, self.dHeight))
			print('start recording...')
			self.setWindowTitle("Nahrávám kamery")
			self.is_recording = True
		except Exception as e:
			print (e)
			print ("chyba record")

	def stopRecord(self):
		print('stop record')
		self.setWindowTitle("Kamery")
		self.is_recording = False
		self.record.release()