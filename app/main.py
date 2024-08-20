import sys
import os
import configparser
from model import personModel, memberModel, trainingModel, finishedTrainingModel
from ui_mainwindow import Ui_MainWindow, PersonForm, MemberForm
from ui_loginForm import Ui_Login_Dialog
from protocol import createProtocol
from quido import Device as kvido
from camera import Camera
from ldap_auth import LdapAuth
from PyQt5 import QtCore, QtGui, QtSql
from PyQt5.QtWidgets import QMainWindow, QAbstractItemView, QMessageBox, QDialog, QApplication, QHeaderView, QPushButton, QLabel
import time
from audio import Audio
import requests

__APP_DIR__ = os.path.dirname(__file__)
__version__ = "1.0.1"
__appname__ = "polygon"
__conffile__ = os.path.join(__APP_DIR__, "../config/polygon.conf")
__log_filename__ = os.path.join(__APP_DIR__, "../log/polygon.log")
__VIDEO_FOLDER__ = os.path.join(__APP_DIR__, "../video")


class MainWindow(QMainWindow, Ui_MainWindow):
	def __init__(self):
		#super(MainWindow, self).__init__()
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.personmodel = personModel()
		self.trainingmodel = trainingModel()
		self.membermodel = memberModel()
		self.finishedtrainingmodel = finishedTrainingModel()
		self.qin_status = QLabel(f" QUIDO Input {conf['QUIDO']['din']} - status: Error")
		self.qout_status = QLabel(f" QUIDO Output {conf['QUIDO']['dout']} - status: Error")
		self.query = QtSql.QSqlQuery()
		self.assignWidgets()
		self.reader = QtCore.QTimer()
		self.reader.setInterval(600)
		self.reader.timeout.connect(self.readInput)
		self.reader.start()
		self.runningTraining = False
		self.show()
		#cams = [conf['CAMERA']['cam1'], conf['CAMERA']['cam2'],conf['CAMERA']['cam3'],conf['CAMERA']['cam10'],conf['CAMERA']['cam11']]
		cams = [conf['CAMERA']['cam1'], conf['CAMERA']['cam2'],conf['CAMERA']['cam3'],conf['CAMERA']['cam4'],conf['CAMERA']['cam5'],conf['CAMERA']['cam6'],conf['CAMERA']['cam7'],conf['CAMERA']['cam8'],conf['CAMERA']['cam9'],conf['CAMERA']['cam10'],conf['CAMERA']['cam11']]
		if conf['CAMERA']['disable'] is not True:
			self.cam = Camera(cams, int(conf['CAMERA']['width']), int(conf['CAMERA']['height']), conf['CAMERA']['user'], conf['CAMERA']['password'], self)
			self.cam.setWindowIcon(QtGui.QIcon(os.path.join(__APP_DIR__, '../files/video.png')))
		self.audio = Audio(os.path.join(__APP_DIR__, conf['AUDIO']['file']),self)
		self.sound = False

	def test_Quido(self, ip):
		try:
			r = requests.get('http://' + ip, timeout = 0.5)
		except Exception as e:
			print (e)
			return(False)
		return(True)
		
	def readInput(self):
		self.readRelays()
		if self.test_Quido(conf['QUIDO']['din']):
			self.qin_status.setText (f" QUIDO Input {conf['QUIDO']['din']} - status: OK ")
			self.qin_status.setStyleSheet("background-color: green;")
			qin = kvido(conf['QUIDO']['din'])
			states = qin.get_inputs_state()
			for floor in conf['QUIDO_IN']:
				relay = int(conf['QUIDO_IN'][floor])
				state = states[relay]
				name = floor
				label = self.tabPolygon.findChild(QLabel,name)
				if state == True:
						label.setStyleSheet("background-color: rgb(255, 255, 255); color: rgb(0, 0, 0); border: 1px solid gray;")
				else:
					if self.runningTraining:
						label.setStyleSheet("background-color: rgb(92, 184, 92); color: rgb(255, 255, 255); border: 1px solid gray;")
						if relay == 1:
							self.enterCage()
					else:
						label.setStyleSheet("background-color: rgb(255, 0, 0); color: rgb(255, 255, 255); border: 1px solid gray;")
			qin.disconnect()
		else:
			self.qin_status.setText (f" QUIDO Input {conf['QUIDO']['din']} - status: Error ")
			self.qin_status.setStyleSheet("background-color: red;")
			
	def readRelays(self):
		if self.test_Quido(conf['QUIDO']['dout']):
			self.qout_status.setText (f" QUIDO Output {conf['QUIDO']['dout']} - status: OK ")
			self.qout_status.setStyleSheet("background-color: green;")
			qout = kvido(conf['QUIDO']['dout'])
			states = qout.get_outputs_state()
			for butt in conf['QUIDO_OUT']:
				relay = int(conf['QUIDO_OUT'][butt])
				state = states[relay-1]
				name = (butt + "Button")
				button = self.tabPolygon.findChild(QPushButton,name)
				if state:
					button.setStyleSheet("background-color: rgb(92, 184, 92); color: rgb(255, 255, 255)")
				else:
					button.setStyleSheet("background-color: rgb(255, 255, 255); color: rgb(0, 0, 0)")
			qout.disconnect()
		else:
			self.qout_status.setText (f" QUIDO Output {conf['QUIDO']['dout']} - status: Error ")
			self.qout_status.setStyleSheet("background-color: red;")
		
	def assignWidgets(self):
		self.statusbar.addPermanentWidget(self.qin_status)
		self.statusbar.addPermanentWidget(self.qout_status)
		self.statusbar.showMessage(u"Version: %s       Přihlášený uživatel: %s"% (__version__, LA.getDisplayName()))
		self.proxy = QtCore.QSortFilterProxyModel(self)
		self.proxy.setSourceModel(self.personmodel)
		self.personTableView.setModel(self.proxy)
		self.personTableView.hideColumn(0)
		self.personTableView.hideColumn(6)
		self.personTableView.resizeColumnsToContents()
		self.personTableView.setAlternatingRowColors(True)
		self.personTableView.setStyleSheet("color:Black; alternate-background-color: #DDD; background-color: #EEE; selection-color: black; selection-background-color:#add4fb");
		self.personTableView.setShowGrid(False)
		self.personTableView.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.personTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.personTableView.setSortingEnabled(True)
		self.personTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
		self.memberTableView.setModel(self.membermodel)
		self.memberTableView.hideColumn(0)
		self.memberTableView.resizeColumnsToContents()
		self.memberTableView.setAlternatingRowColors(True)
		self.memberTableView.setStyleSheet("color:Black; alternate-background-color: #DDD; background-color: #EEE; selection-color: black; selection-background-color:#add4fb");
		self.memberTableView.setShowGrid(False)
		self.memberTableView.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.memberTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
		self.trainingTableView.setModel(self.finishedtrainingmodel)
		self.trainingTableView.resizeColumnsToContents()
		self.trainingTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.trainingTableView.hideColumn(0)
		self.trainingTableView.hideColumn(5)
		self.trainingTableView.setAlternatingRowColors(True)
		self.trainingTableView.setStyleSheet("color:Black; alternate-background-color: #DDD; background-color: #EEE; selection-color: black; selection-background-color:#add4fb");
		self.trainingTableView.setShowGrid(False)
		self.trainingTableView.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.trainingTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
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
		self.pushButton_19.setIcon(QtGui.QIcon(os.path.join(__APP_DIR__, '../files/play-icon.png')))
		self.volumeSlider.setRange(0, 100)
		#self.volumeSlider.setFixedWidth(100)
		self.volumeSlider.setValue(80)
		#self.connect(self.volumeSlider, QtCore.SIGNAL("valueChanged(int)"), self.setVolume)
		self.volumeSlider.valueChanged.connect(self.setVolume)

		self.startButton.clicked.connect(self.startStopwatch)
		self.stopButton.clicked.connect(self.stopStopwatch)
		self.emergencyButton.clicked.connect(self.emergency)

		self.searchPersonLineEdit.textChanged.connect(self.on_lineEdit_textChanged)
		self.delPersonButton.clicked.connect(self.delPerson)
		self.addPersonButton.clicked.connect(self.addPerson)
		self.editPersonButton.clicked.connect(self.editPerson)
		self.addMemberButton.clicked.connect(self.addMember)
		self.delMemberButton.clicked.connect(self.delMember)
		self.updateMemberButton.clicked.connect(self.updateMember)
		self.saveTrainingButton.clicked.connect(self.saveTraining)
		self.delTrainingButton.clicked.connect(self.delTraining)
		self.printTrainingButton.clicked.connect(self.printTrainingProtocol)

	def emergency(self):
		qout = kvido(conf['QUIDO']['dout'])
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
		qout.disconnect()
		time.sleep(0.3)
		self.readRelays()

	def enterCage(self):
		self.query.exec_("UPDATE training SET time_cage=IF(time_cage = '00:00:00' OR time_cage IS NULL, '%s', time_cage) WHERE status=1" % (self.racetime))

	def stopStopwatch(self):
		self.stopButton.setEnabled(False)
		self.stopButton.setEnabled(False)
		self.query.exec_("UPDATE training SET time_end='%s' WHERE status=1" % (self.racetime))
		#print query.lastQuery()
		#print self.trainingmodel.lastError().text()
		self.query.exec_("UPDATE training SET status=2 WHERE status=1")
		self.timer.stop()
		self.runningTraining = False
		self.cam.stopRecord()
		self.cam.setWindowIcon(QtGui.QIcon(os.path.join(__APP_DIR__, '../files/video.png')))

	def startStopwatch(self):
		self.runningTraining = True
		self.cam.startRecord(__VIDEO_FOLDER__)
		self.cam.setWindowIcon(QtGui.QIcon(os.path.join(__APP_DIR__, '../files/video-recording.png')))
		self.startButton.setEnabled(False)
		self.stopButton.setEnabled(True)
		self.timer = QtCore.QTimer()
		self.timer.setInterval(1000)
		self.timer.timeout.connect(self.displayTime)
		self.time = QtCore.QElapsedTimer()
		self.time.start()
		self.timer.start()

	def displayTime(self):
		msec = self.time.elapsed()
		s = int(msec / 1000 % 60)
		m = int(msec / 1000 / 60 % 60)
		#h = msec / 1000 / 3600 % 24
		#self.racetime = QtCore.QString("%1:%2:%3").arg(h, 2, 10, QtCore.QChar('0')).arg(m, 2, 10, QtCore.QChar('0')).arg(s, 2, 10, QtCore.QChar('0'))
		self.racetime = f"{m:02.0f}:{s:02.0f}"
		self.lcdNumber.display(self.racetime)

	def playSound(self):
		if self.sound:
			self.audio.stop()
			self.sound = False
			self.pushButton_19.setIcon(QtGui.QIcon(os.path.join(__APP_DIR__, '../files/play-icon.png')))
		else:
			self.sound = True
			self.audio.play()
			self.pushButton_19.setIcon(QtGui.QIcon(os.path.join(__APP_DIR__, '../files/pause-icon.png')))

	def setVolume(self, volume):
		self.audio.changeVolume(volume)

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
		trainingid = self.query.value(0)
		message = []
		if trainingid:
			self.query.exec_("SELECT member.volume, member.press_start, member.press_end, CONCAT(person.name,' ', person.surname) AS name "
							"FROM member LEFT JOIN person ON member.person_id = person.idPerson WHERE training_id=%d" % trainingid)
			while self.query.next():
				if int(self.query.value(0))==0 or int(self.query.value(1))==0 or int(self.query.value(2))==0:
					message.append (u'Nejsou vyplněné všechny hodnoty u cvičících')
				if int(self.query.value(1))<=int(self.query.value(2)):
					message.append (u'%s nemá počáteční tlak větší než koncový' % self.query.value(3))
		else:
			message.append (u'Není dokončený žádný trénink')
		if not message:
			self.query.exec_("UPDATE training SET status=10 WHERE status=2")
			self.membermodel.refresh(trainingid)
			self.finishedtrainingmodel.refresh()
			self.lcdNumber.display("00:00")
		else:
			message = set(message)
			text = "\n".join(message)
			QMessageBox.warning(self, u'Varování',text, QMessageBox.Ok)

	def delTraining(self):
		self.query.exec_("SELECT idTraining FROM training WHERE status<>10 LIMIT 1")
		if self.query.first():
			trainingid = self.query.value(0)
			if trainingid != 0:
				self.query.exec_("DELETE FROM training WHERE status<>10")
				self.query.exec_("DELETE FROM member WHERE training_id=%d" % (trainingid))
				self.membermodel.refresh(trainingid)
				self.startButton.setEnabled(False)


	def delMember(self):
		trainingid = self.getTraining()
		if trainingid is None:
			QMessageBox.warning(self, u'Varování', u'Nelze odebrat člena z proběhlého cvičení', QMessageBox.Ok)
			return
		row = self.memberTableView.selectionModel().currentIndex().row()
		idMember = self.membermodel.record(row).value("idMember")
		if idMember is not None:
			self.query.exec_("DELETE FROM member WHERE idMember=%d" % (idMember))
			self.membermodel.view()
			count = self.countMember(trainingid)
			if count == 1:
				self.query.exec_("UPDATE training SET status=0 WHERE idTraining=%d" % (trainingid))
				self.startButton.setEnabled(False)
			elif count == 0:
				self.query.exec_("DELETE FROM training WHERE training_id=%d" % (trainingid))
		else:
			QMessageBox.warning(self, u'Varování',u"Není vybrána žádná osoba", QMessageBox.Ok)

	def addMember(self, personId):
		index = self.personTableView.selectionModel().currentIndex()
		row = self.proxy.mapToSource(index).row()
		if not personId:
			personId = self.personmodel.record(row).value("idPerson")
		if row>=0:
			trainingid = self.getTraining()
			if trainingid is None:
				QMessageBox.warning(self, u'Varování', u'Nelze přidat člena do proběhlého cvičení', QMessageBox.Ok)
				return
			if self.countMember(trainingid) < 4:
				self.query.exec_("SELECT COUNT(idmember) FROM member WHERE training_id=%d AND person_id=%d" % (trainingid,personId))
				self.query.first()
				checkperson = self.query.value(0)
				if checkperson == 0:
					self.query.exec_("INSERT INTO member (training_id,person_id) VALUES (%d,%d)" % (trainingid,personId))
					self.membermodel.refresh(trainingid)
					self.memberTableView.hideColumn(0)
					if self.countMember(trainingid) >= 2:
						self.query.exec_("UPDATE training SET status=1 WHERE idTraining=%d" % (trainingid))
						self.startButton.setEnabled(True)
		else:
			QMessageBox.warning(self, u'Varování',u"Není vybrána žádná osoba", QMessageBox.Ok)


	def countMember(self, trainingid):
		self.query.exec_("SELECT COUNT(idmember) FROM member WHERE training_id=%d" % (trainingid))
		self.query.first()
		return self.query.value(0)

	def getTraining(self):
		self.trainingmodel.select()
		openstatus = self.trainingmodel.rowCount()
		if openstatus == 0:
			self.query.exec_("INSERT INTO training (time_start) VALUES (NOW())")
			trainingid = self.query.lastInsertId()
		else:
			trainingid = self.trainingmodel.record(0).value("idTraining")
			status = self.trainingmodel.record(0).value("status")
			if status == 2:
				return None
		return trainingid


	def on_lineEdit_textChanged(self, text):
		search = QtCore.QRegExp(text, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.RegExp)
		self.proxy.setFilterKeyColumn(-1);
		self.proxy.setFilterRegExp(search)

	def delPerson(self):
		index = self.personTableView.selectionModel().currentIndex()
		row = self.proxy.mapToSource(index).row()
		if row>=0:
			reply = QMessageBox.question(self, u'Smazat',u"Opravdu chcete smazat osobu?", QMessageBox.Yes, QMessageBox.No)
			if reply == QMessageBox.Yes:
				record = self.personmodel.record(row)
				record.setValue("valid",0)
				self.personmodel.setRecord(row, record);
				self.personmodel.submitAll()
		else:
			QMessageBox.warning(self, u'Varování',u"Není vybrána žádná osoba", QMessageBox.Ok)

	def addPerson(self):
		personform = PersonForm(self.personmodel)
		personform.exec_()
		self.query.exec_("SELECT LAST_INSERT_ID()")
		self.query.first()
		lastPerson = self.query.value(0)
		#self.personTableView.selectRow(personform.row)
		if personform.addMember == True:
			self.addMember (lastPerson)

	def editPerson(self):
		index = self.personTableView.selectionModel().currentIndex()
		row = self.proxy.mapToSource(index).row()
		if row>=0:
			personform = PersonForm(self.personmodel, row)
			personform.exec_()
		else:
			QMessageBox.warning(self, u'Varování',u"Není vybrána žádná osoba", QMessageBox.Ok)

	def updateMember(self):
		row = self.memberTableView.selectionModel().currentIndex().row()
		if row>=0:
			memberform = MemberForm(self.membermodel, row)
			memberform.exec_()
		else:
			QMessageBox.warning(self, u'Varování',u"Není vybrána žádná osoba", QMessageBox.Ok)

	def printTrainingProtocol(self):
		#trainingid = self.trainingTableView.selectionModel().currentIndex().row()
		row = self.trainingTableView.selectionModel().currentIndex().row()
		trainingid = self.finishedtrainingmodel.record(row).value("idTraining")
		if trainingid > 0:
			doc = createProtocol(self.query, trainingid, LA.getDisplayName())
			del doc
		else:
			QMessageBox.warning(self, u'Varování', u"Není vybráno žádné cvičení", QMessageBox.Ok)

	def closeEvent(self, event):
		quit_msg = u"Opravdu chcete ukončit program?"
		reply = QMessageBox.question(self, 'Zavřít', quit_msg, QMessageBox.Yes, QMessageBox.No)
		if reply == QMessageBox.Yes:
			self.delTraining()
			event.accept()
		else:
			event.ignore()

class Login(QDialog,Ui_Login_Dialog):
	def __init__(self):
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.buttonBox.accepted.connect(self.handleLogin)
		self.buttonBox.rejected.connect(self.handleCancel)

	def handleLogin(self):
		username = self.userLineEdit.text()
		password = self.passwordLineEdit.text()
		if not username:
			QMessageBox.warning(self, 'Chyba', u'Není zadáno uživatelské jméno!')
		elif not password:
			QMessageBox.warning(self, 'Chyba', u'Není zadáno heslo!')
		else:
			self.AttemptLogin(username, password)

	def AttemptLogin(self, username, password):
		if LA.userExist(username):
			if LA.checkPassword(str(password)):
				if LA.checkRights():
					self.accept()
				else:
					QMessageBox.warning(self, 'Chyba', u'Uživatel nemá dostatečná opravnění')
			else:
				QMessageBox.warning(self, 'Chyba', u'Špatné heslo!')
		else:
			QMessageBox.warning(self, 'Chyba', u'Uživatel neexistuje!')

	def handleCancel(self):
		self.close()


def read_config():
	config = configparser.ConfigParser()
	config.optionxform = str
	config.read(__conffile__)
	for section in config.sections():
		conf[section] = {}
		for option in config.options(section):
			conf[section][option] = config.get(section, option)
			if (conf[section][option] == "True") or (conf[section][option] == "False"):
				conf[section][option] = config.getboolean(section, option)


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
		print ("Chyba pripojeni DB")
	#qin = kvido(conf['din'])
	#qout = kvido("192.168.16.232",10001)
	#print qout.get_output_state(1)
	#qout.invertState(1)
	#print qout.get_output_state(1)
	LA = LdapAuth(host=conf['LDAP']['host'], username=conf['LDAP']['username'], password=conf['LDAP']['password'], base=conf['LDAP']['base'], group=conf['LDAP']['group'])
	app = QApplication(sys.argv)
	login = Login()
	if login.exec_() == QDialog.Accepted:
		mainWin = MainWindow()
		ret = app.exec_()
		#qout.disconnect()
		LA.unbind()
		sys.exit (ret)
