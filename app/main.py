# -*- coding: utf-8 -*-

import sys
import configparser
from model import personModel, memberModel, trainingModel
from ui_mainwindow import Ui_MainWindow, PersonForm, MemberForm
from quido import Device as kvido
from camera import Camera
from PyQt4 import QtCore, QtGui, QtSql, QtWebKit
import time
from audio import Audio

reload(sys)
sys.setdefaultencoding('utf-8')

__version__ = "0.0.4"
__appname__ = "polygon"
__conffile__ = "../config/polygon.conf"
__log_filename__ = "../log/polygon.log"


class MainWindow(QtGui.QMainWindow, Ui_MainWindow):
	def __init__(self):
		super(MainWindow, self).__init__()
		self.setupUi(self)
		self.personmodel = personModel()
		self.trainingmodel = trainingModel()
		self.membermodel = memberModel()
		self.finishedtrainingmodel = trainingModel(True)
		self.query = QtSql.QSqlQuery()
		self.assignWidgets()
		self.reader = QtCore.QTimer()
		self.reader.setInterval(400)
		self.reader.timeout.connect(self.readInput)
		self.reader.start()
		self.runningTraining = False
		self.show()
		cams = [conf['CAMERA']['cam1'], conf['CAMERA']['cam2'],conf['CAMERA']['cam3'],conf['CAMERA']['cam4'],conf['CAMERA']['cam5'],conf['CAMERA']['cam6'],conf['CAMERA']['cam7'],conf['CAMERA']['cam8'],conf['CAMERA']['cam9']]
		#bcams = [conf['CAMERA']['cam1'], conf['CAMERA']['cam2']]
		self.cam = Camera(cams, int(conf['CAMERA']['width']), int(conf['CAMERA']['height']), conf['CAMERA']['user'], conf['CAMERA']['password'], self)
		self.audio = Audio(conf['AUDIO']['file'],self)
		self.sound = False
		
	def readInput(self):
		self.readRelays()
		qin = kvido(conf['QUIDO']['din'])
		states = qin.get_inputs_state()
		for floor in conf['QUIDO_IN']:
			relay = int(conf['QUIDO_IN'][floor])
			state = states[relay]
			name = QtCore.QString(floor)
			label = self.tabPolygon.findChild(QtGui.QLabel,name)
			if state == True:
					label.setStyleSheet("background-color: rgb(255, 255, 255); color: rgb(0, 0, 0); border: 1px solid gray;")
			else:
				if self.runningTraining:
					label.setStyleSheet("background-color: rgb(92, 184, 92); color: rgb(255, 255, 255); border: 1px solid gray;")
				else:
					label.setStyleSheet("background-color: rgb(255, 0, 0); color: rgb(255, 255, 255); border: 1px solid gray;")
		qin.disconnect()

	def readRelays(self):
		qout = kvido(conf['QUIDO']['dout'])
		states = qout.get_outputs_state()
		for butt in conf['QUIDO_OUT']:
			relay = int(conf['QUIDO_OUT'][butt])
			state = states[relay-1]
			name = QtCore.QString("%1Button").arg(butt)
			button = self.tabPolygon.findChild(QtGui.QPushButton,name)
			if state:
				button.setStyleSheet("background-color: rgb(92, 184, 92); color: rgb(255, 255, 255)")	
			else:
				button.setStyleSheet("background-color: rgb(255, 255, 255); color: rgb(0, 0, 0)")
		qout.disconnect()

	def assignWidgets(self):
		self.statusbar.showMessage("Version: %s"%__version__)
		#self.actionExit.triggered.connect(self.close)

		self.proxy = QtGui.QSortFilterProxyModel(self)
		self.proxy.setSourceModel(self.personmodel)

		self.personTableView.setModel(self.proxy)
		self.personTableView.hideColumn(0)
		self.personTableView.hideColumn(6)
		self.memberTableView.setModel(self.membermodel)
		self.memberTableView.hideColumn(0)
		self.trainingTableView.setModel(self.finishedtrainingmodel)
		#self.trainingTableView.setVisible(False)
		#self.trainingTableView.resizeColumnsToContents()
		#self.trainingTableView.setVisible(True)
		self.trainingTableView.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
		self.trainingTableView.hideColumn(0)
		self.trainingTableView.hideColumn(4)
		#self.trainingTableView.horizontalHeader().setResizeMode(QtGui.QHeaderView.ResizeToContents)
		self.startButton.setEnabled(False)
		self.stopButton.setEnabled(False)
		self.lcdNumber.display("00:00")


		self.fan12Button.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['fan12'])))
		self.fan34Button.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['fan34'])))
		self.fanControlRoomButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['fanControlRoom'])))
		self.glowButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['glow'])))
		self.stroboButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['strobo'])))
		self.hotZoneButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['hotZone'])))
		self.louverButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['louver'])))
		self.smokeButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['smoke'])))
		self.polygonLight1Button.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['polygonLight1'])))
		self.polygonLight2Button.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['polygonLight2'])))
		self.polygonLight3Button.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['polygonLight3'])))
		self.hotZoneLightButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['hotZoneLight'])))
		self.stressRoomLightButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['stressRoomLight'])))
		self.infraLightButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['infraLight'])))
		self.controlRoomLightButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['controlRoomLight'])))
		self.helpLightButton.clicked.connect(lambda:self.clickButton(int(conf['QUIDO_OUT']['helpLight'])))

		self.pushButton_19.clicked.connect(self.playSound)
		self.pushButton_19.setIcon(QtGui.QIcon('../files/play-icon.png'))

		self.startButton.clicked.connect(self.startStopwatch)		
		self.stopButton.clicked.connect(self.stopStopwatch)
		self.emergencyButton.clicked.connect(self.emergency)

		self.searchPersonLineEdit.textChanged.connect(self.on_lineEdit_textChanged)
		self.delPersonButton.clicked.connect(self.delPerson)
		self.addPersonButton.clicked.connect(self.addPerson)
		self.addMemberButton.clicked.connect(self.addMember)
		self.delMemberButton.clicked.connect(self.delMember)
		self.updateMemberButton.clicked.connect(self.updateMember)
		self.saveTrainingButton.clicked.connect(self.saveTraining)
		self.delTrainingButton.clicked.connect(self.delTraining)
		self.printTrainingButton.clicked.connect(self.printTrainingProtocol)

	def emergency(self):
		#qout = kvido(conf['QUIDO']['dout'])
		self.qout.set_output_off(int(conf['QUIDO_OUT']['fan12']))
		self.qout.set_output_off(int(conf['QUIDO_OUT']['fan34']))
		self.qout.set_output_off(int(conf['QUIDO_OUT']['fanControlRoom']))
		self.qout.set_output_off(int(conf['QUIDO_OUT']['glow']))
		self.qout.set_output_off(int(conf['QUIDO_OUT']['strobo']))
		self.qout.set_output_off(int(conf['QUIDO_OUT']['hotZone']))
		self.qout.set_output_off(int(conf['QUIDO_OUT']['louver']))
		self.qout.set_output_off(int(conf['QUIDO_OUT']['smoke']))
		self.qout.set_output_on(int(conf['QUIDO_OUT']['polygonLight1']))
		self.qout.set_output_on(int(conf['QUIDO_OUT']['polygonLight2']))
		self.qout.set_output_on(int(conf['QUIDO_OUT']['polygonLight3']))
		self.qout.set_output_on(int(conf['QUIDO_OUT']['hotZoneLight']))
		self.qout.set_output_on(int(conf['QUIDO_OUT']['stressRoomLight']))
		self.qout.set_output_on(int(conf['QUIDO_OUT']['controlRoomLight']))
		self.qout.set_output_on(int(conf['QUIDO_OUT']['helpLight']))
		#qout.disconnect()
		time.sleep(0.3)
		self.readRelays()

	def stopStopwatch(self):
		self.stopButton.setEnabled(False)
		self.stopButton.setEnabled(False)
		self.query.exec_("UPDATE training SET time_end='%s' WHERE status=1" % (self.racetime))
		#print query.lastQuery()
		#print self.trainingmodel.lastError().text()
		self.query.exec_("UPDATE training SET status=2 WHERE status=1")
		self.timer.stop()
		self.runningTraining = False


	def startStopwatch(self):
		self.runningTraining = True
		self.startButton.setEnabled(False)
		self.stopButton.setEnabled(True)
		self.timer = QtCore.QTimer()
		self.timer.setInterval(1000)
		self.timer.timeout.connect(self.displayTime)
		self.time = QtCore.QTime()
		self.time.start()
		self.timer.start()

	def displayTime(self):
		msec = self.time.elapsed()
		s = msec / 1000 % 60
		m = msec / 1000 / 60 % 60
		self.racetime = QtCore.QString("%1:%2").arg(m, 2, 10, QtCore.QChar('0')).arg(s, 2, 10, QtCore.QChar('0'))
		self.lcdNumber.display(self.racetime)

	def playSound(self):
		if self.sound:
			self.audio.stop()
			self.sound = False
			self.pushButton_19.setIcon(QtGui.QIcon('../files/play-icon.png'))
		else:
			self.sound = True
			self.audio.play()
			self.pushButton_19.setIcon(QtGui.QIcon('../files/pause-icon.png'))

	def clickButton(self,relay):
		qout = kvido(conf['QUIDO']['dout'])
		#qout.invertState(relay)
		button = QtCore.QObject.sender(self)
		state = qout.get_output_state(relay)
		if state == False:
			qout.set_output_on(relay)
			button.setStyleSheet("background-color: rgb(92, 184, 92); color: rgb(255, 255, 255)")
		else:
			qout.set_output_off(relay)
			button.setStyleSheet("background-color: rgb(255, 255, 255); color: rgb(0, 0, 0)")
		qout.disconnect()

	def saveTraining(self):
		self.query.exec_("SELECT idTraining FROM training WHERE status=2 LIMIT 1")
		self.query.first() 
		trainingid = self.query.value(0).toInt()[0]
		message = []
		if trainingid != 0:
			self.query.exec_("SELECT member.volume, member.press_start, member.press_end, CONCAT(person.name,' ', person.surname) AS name "
							"FROM member LEFT JOIN person ON member.person_id = person.idPerson WHERE training_id=%d" % trainingid)
			while self.query.next():
				if self.query.value(0).toInt()[0]==0 or self.query.value(1).toInt()[0]==0 or self.query.value(2).toInt()[0]==0:
					message.append (u'Nejsou vyplněné všechny hodnoty u cvičících')
				if self.query.value(1).toInt()[0]<=self.query.value(2).toInt()[0]:
					message.append (u'%s nemá počáteční tlak není menší než koncový' % self.query.value(3).toString())
		else:
			message.append (u'Není dokončený žádný trénink')
		if not message:
			self.query.exec_("UPDATE training SET status=10 WHERE status=2")
			self.membermodel.refresh(trainingid)
			self.finishedtrainingmodel.select()
			self.lcdNumber.display("00:00")
		else:
			message = set(message)
			text = "\n".join(message)
			QtGui.QMessageBox.warning(self, u'Varování',text, QtGui.QMessageBox.Ok)

	def delTraining(self):
		self.query.exec_("SELECT idTraining FROM training WHERE status<>10 LIMIT 1")
		if self.query.first():
			trainingid = self.query.value(0).toInt()[0]
			if trainingid != 0:
				self.query.exec_("DELETE FROM training WHERE status<>10")
				self.query.exec_("DELETE FROM member WHERE training_id=%d" % (trainingid))
				self.membermodel.refresh(trainingid)
				self.startButton.setEnabled(False)


	def delMember(self):
		trainingid = self.getTraining()
		row = self.memberTableView.selectionModel().currentIndex().row()
		idmember = self.membermodel.record(row).value("idMember").toInt()[0]
		self.query.exec_("DELETE FROM member WHERE idMember=%d" % (idmember))
		self.membermodel.view()
		count = self.countMember(trainingid)
		if count == 1:
			self.query.exec_("UPDATE training SET status=0 WHERE idTraining=%d" % (trainingid))
			self.startButton.setEnabled(False)
		elif count == 0:
			self.query.exec_("DELETE FROM training WHERE training_id=%d" % (trainingid))

	def addMember(self):
		index = self.personTableView.selectionModel().currentIndex()
		row = self.proxy.mapToSource(index).row()
		personid = self.personmodel.record(row).value("idPerson").toInt()[0]
		if row>=0:
			trainingid = self.getTraining()
			if self.countMember(trainingid) < 5:
				self.query.exec_("SELECT COUNT(idmember) FROM member WHERE training_id=%d AND person_id=%d" % (trainingid,personid))
				self.query.first() 
				checkperson = self.query.value(0).toInt()[0]
				if checkperson == 0:
					self.query.exec_("INSERT INTO member (training_id,person_id) VALUES (%d,%d)" % (trainingid,personid))
					self.membermodel.refresh(trainingid)
					self.memberTableView.hideColumn(0)
					if self.countMember(trainingid) >= 2:
						self.query.exec_("UPDATE training SET status=1 WHERE idTraining=%d" % (trainingid))
						self.startButton.setEnabled(True)
		


	def countMember(self, trainingid):
		self.query.exec_("SELECT COUNT(idmember) FROM member WHERE training_id=%d" % (trainingid))
		self.query.first() 
		return self.query.value(0).toInt()[0]

	def getTraining(self):
		self.trainingmodel.select()
		openstatus = self.trainingmodel.rowCount()
		if openstatus == 0:
			self.query.exec_("INSERT INTO training (date) VALUES (CURDATE())")
			trainingid = self.query.lastInsertId().toInt()[0]
		else:
			trainingid = self.trainingmodel.record(0).value("idTraining").toInt()[0]
		return trainingid


	def on_lineEdit_textChanged(self, text):
		search = QtCore.QRegExp(text, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.RegExp)
		self.proxy.setFilterKeyColumn(-1);
		self.proxy.setFilterRegExp(search)

	def delPerson(self):
		index = self.personTableView.selectionModel().currentIndex()
		row = self.proxy.mapToSource(index).row()
		if row>0:
			reply = QtGui.QMessageBox.question(self, u'Smazat',"Opravdu chcete smazat osobu?", QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
			if reply == QtGui.QMessageBox.Yes:
				record = self.personmodel.record(row)
				record.setValue("valid",0)
				self.personmodel.setRecord(row, record);
				self.personmodel.submitAll()
		else:
			QtGui.QMessageBox.warning(self, u'Varování',"Není vybrána žádná osoba", QtGui.QMessageBox.Ok)

	def addPerson(self):
		personform = PersonForm(self.personmodel)
		personform.exec_()

	def updateMember(self):
		row = self.memberTableView.selectionModel().currentIndex().row()
		memberform = MemberForm(self.membermodel,row)
		memberform.exec_()

	def printTrainingProtocol(self):
		content = u"Bude obsahovat údaje o průběhu výcviku. <html lang='cs'> \
<head> \
	<meta charset='UTF-8'>\
	<title>Test css</title>\
	<style>\
		h1 {color: red;}\
		h2 {color: green;}\
		.text-center {text-align: right;}\
		.space-left {margin-left: 40px;}\
	</style>\
</head>\
<body>\
	<h1>Toto je červený nadpis</h1>\
	<h2>Toto je zelený nadpis</h2>\
	<h3 class='text-center'>Toto je vycentrovany text.</h3>\
	<p class='space-left'>Toto je odsazeny text z leva 40px.</p>\
</body>\
</html>"
		#tempFile = QtCore.QTemporaryFile()
		#if tempFile.open():
		#	tempName = tempFile.fileName()
		printer = QtGui.QPrinter()
		#printer.setOutputFileName(tempName)
		printer.setOutputFormat(QtGui.QPrinter.PdfFormat)
		printer.setPageSize(QtGui.QPrinter.A4)
		#printer.setOrientation(QtGui.QPrinter.Landscape)        
		#printer.setFullPage(True)
		
		doc = QtGui.QTextDocument()
		#doc.setDefaultStyleSheet(self.stylesheet)
		doc.setHtml(content)

		#view = QtWebKit.QWebView()
		#view.setHtml(htmlContent)
		#view.print_(printer)
		
		dialog = QtGui.QPrintPreviewDialog()
		#dialog.paintRequested.connect(self.editor.print_)
		dialog.paintRequested.connect(doc.print_)
		dialog.exec_()

	#	def print_doc(self, doc):
    #    dialog = QtGui.QPrintDialog()
    #    if dialog.exec_() == QtGui.QDialog.Accepted:
    #        doc.print_(dialog.printer())
	#    def print_preview_doc(self, doc):
    #    dialog = QtGui.QPrintPreviewDialog()
    #    dialog.paintRequested.connect(doc.print_)
    #    dialog.exec_()

	def closeEvent(self, event):
		quit_msg = u"Opravdu chcete ukončit program?"
		reply = QtGui.QMessageBox.question(self, 'Message', quit_msg, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
		if reply == QtGui.QMessageBox.Yes:
			self.delTraining()
			event.accept()
		else:
			event.ignore()


def read_config():
	config = configparser.ConfigParser()
	config.optionxform = str
	config.read(__conffile__)
	for section in config.sections():
		conf[section] = {}
		for option in config.options(section):
			conf[section][option] = config.get(section, option)


if __name__ == '__main__':
	conf = {}
	read_config()
	db = QtSql.QSqlDatabase.addDatabase("QMYSQL")
	db.setHostName ( conf['MYSQL']['host'] )
	db.setUserName ( conf['MYSQL']['user'] )
	db.setPassword ( conf['MYSQL']['password'] )
	db.setDatabaseName ( conf['MYSQL']['database'] )
	try:
		db.open()
	except:
		print "chyba"

	#qin = kvido(conf['din'])
	#qout = kvido("192.168.16.232",10001)
	#print qout.get_output_state(1)
	#qout.invertState(1)
	#print qout.get_output_state(1)

	app = QtGui.QApplication(sys.argv)
	mainWin = MainWindow()
	#camWidget = QtGui.QWidget(mainWin)
		#ui = Ui_Kamery()
		#ui.setupUi(camWidget)
	#camWidget.setWindowFlags(QtCore.Qt.Window)
	#cam = Camera(conf['CAMERA']['cam1'])
	#camWidget.show()
	ret = app.exec_()
	sys.exit( ret )
	qout.disconnect()