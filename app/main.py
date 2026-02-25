#!/usr/bin/env python3
"""
Main application entry point - Secure version.
"""
import sys
import os
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QAbstractItemView, QHeaderView
from PyQt5 import QtCore, QtGui

# Import secure modules
from config_manager import ConfigManager, ConfigurationError
from logger_config import logger

# Constants
__APP_DIR__ = os.path.dirname(__file__)
__VERSION__ = "1.0.2"
__VIDEO_FOLDER__ = os.path.join(__APP_DIR__, "../video")
os.makedirs(__VIDEO_FOLDER__, exist_ok=True)

# Import existing modules (with fixed imports)
from model import personModel, memberModel, trainingModel, finishedTrainingModel
from ui_mainwindow import Ui_MainWindow, PersonForm, MemberForm
from ui_loginForm import Ui_Login_Dialog
from protocol import createProtocol
from quido import Device as kvido
from audio import Audio

# Import camera module
try:
    from camera import Camera
except ImportError:
    logger.warning("Camera module not available")
    Camera = None

from PyQt5 import QtCore, QtGui, QtSql
from PyQt5.QtWidgets import (QMainWindow, QAbstractItemView, QMessageBox,
                           QDialog, QApplication, QHeaderView, QPushButton, QLabel)
import time
import requests
import ldap3


class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self, config: dict, display_name: str = None):
        super().__init__()
        self.setupUi(self)

        # Store configuration and user info
        self.conf = config
        self.current_user = display_name or "Unknown User"

        # Initialize models (database should be connected globally)
        self.personmodel = personModel()
        self.trainingmodel = trainingModel()
        self.membermodel = memberModel()
        self.finishedtrainingmodel = finishedTrainingModel()

        # Initialize components
        self._init_database_reference()
        self._init_status_labels()
        self._init_widgets()
        self._init_timer()
        self._init_camera()
        self._init_audio()

        self.runningTraining = False
        self.show()

    def _init_database_reference(self):
        """Get reference to the global database connection."""
        try:
            # Get the default database connection (should be already established)
            self.db = QtSql.QSqlDatabase.database()

            if self.db.isOpen():
                logger.info("Using existing database connection")
                self.query = QtSql.QSqlQuery()
            else:
                logger.error("Database connection not available")
                QMessageBox.critical(self, 'Chyba databáze', 'Databáze není připojena.')
                self.query = None
        except Exception as e:
            logger.error(f"Database reference error: {e}")
            self.query = None

    def _init_status_labels(self):
        """Initialize status labels."""
        try:
            din_ip = self.conf['QUIDO']['din']
            dout_ip = self.conf['QUIDO']['dout']

            self.qin_status = QLabel(f" QUIDO Input {din_ip} - status: Error")
            self.qout_status = QLabel(f" QUIDO Output {dout_ip} - status: Error")
        except KeyError as e:
            logger.error(f"Configuration error: {e}")
            self.qin_status = QLabel(" QUIDO Input - status: Config Error")
            self.qout_status = QLabel(" QUIDO Output - status: Config Error")

    def _init_widgets(self):
        """Initialize UI widgets."""
        try:
            self.assign_widgets()
        except Exception as e:
            logger.error(f"Widget initialization failed: {e}")

    def _init_timer(self):
        """Initialize timer for device monitoring."""
        try:
            self.reader = QtCore.QTimer()
            self.reader.setInterval(600)
            self.reader.timeout.connect(self.read_input)
            self.reader.start()
        except Exception as e:
            logger.error(f"Timer initialization failed: {e}")

    def _init_camera(self):
        """Initialize camera system."""
        try:
            if Camera and not self.conf['CAMERA'].get('disable', True):
                # Build camera URLs list
                cam_urls = []
                for i in range(1, 12):
                    cam_key = f'cam{i}'
                    if cam_key in self.conf['CAMERA']:
                        cam_urls.append(self.conf['CAMERA'][cam_key])

                if cam_urls:
                    self.cam = Camera(
                        cam_urls,
                        int(self.conf['CAMERA']['width']),
                        int(self.conf['CAMERA']['height']),
                        self.conf['CAMERA'].get('user'),
                        self.conf['CAMERA'].get('password'),
                        self
                    )

                    # Set icon
                    icon_path = os.path.join(os.path.dirname(__file__), '../files/video.png')
                    if os.path.exists(icon_path):
                        self.cam.setWindowIcon(QtGui.QIcon(icon_path))
            else:
                logger.info("Camera system disabled")

        except Exception as e:
            logger.error(f"Camera initialization failed: {e}")
            self.cam = None

    def _init_audio(self):
        """Initialize audio system."""
        try:
            audio_file = self.conf['AUDIO']['file']
            audio_path = os.path.join(os.path.dirname(__file__), audio_file)

            if os.path.exists(audio_path):
                self.audio = Audio(audio_path, self)
                self.sound = False
            else:
                logger.error(f"Audio file not found: {audio_path}")
                self.audio = None
        except Exception as e:
            logger.error(f"Audio initialization failed: {e}")
            self.audio = None

    def test_quido_device(self, ip: str) -> bool:
        """Test QUIDO device connectivity with validation."""
        try:
            if not ip:
                return False
            response = requests.get(f'http://{ip}', timeout=0.5)
            return response.status_code == 200
        except (requests.exceptions.RequestException, Exception):
            return False

    def read_input(self):
        """Read device inputs with proper error handling."""
        try:
            self.read_relays()

            din_ip = self.conf['QUIDO']['din']
            if self.test_quido_device(din_ip):
                self.qin_status.setText(f" QUIDO Input {din_ip} - status: OK ")
                self.qin_status.setStyleSheet("background-color: green;")
                self._read_quido_inputs(din_ip)
            else:
                self.qin_status.setText(f" QUIDO Input {din_ip} - status: Error ")
                self.qin_status.setStyleSheet("background-color: red;")

        except Exception as e:
            logger.error(f"Error reading inputs: {e}")

    def _read_quido_inputs(self, ip: str):
        """Read QUIDO input states safely."""
        try:
            qin = kvido(ip)
            states = qin.get_inputs_state()

            # Process configured inputs
            quido_in_config = self.conf.get('QUIDO_IN', {})
            for floor, relay_str in quido_in_config.items():
                try:
                    relay = int(relay_str)
                    if 0 <= relay < len(states):
                        state = states[relay]
                        self._update_floor_indicator(floor, state)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Invalid relay configuration for {floor}: {e}")

            qin.disconnect()

        except Exception as e:
            logger.error(f"Error reading QUIDO inputs: {e}")

    def _update_floor_indicator(self, floor_name: str, state: bool):
        """Update floor indicator display."""
        try:
            label = self.tabPolygon.findChild(QLabel, floor_name)
            if label:
                if state:
                    label.setStyleSheet("background-color: rgb(255, 255, 255); color: rgb(0, 0, 0); border: 1px solid gray;")
                else:
                    label.setStyleSheet("background-color: rgb(255, 0, 0); color: rgb(255, 255, 255); border: 1px solid gray;")
        except Exception as e:
            logger.warning(f"Error updating floor indicator {floor_name}: {e}")

    def read_relays(self):
        """Read relay states and update button colors."""
        try:
            dout_ip = self.conf['QUIDO']['dout']
            if self.test_quido_device(dout_ip):
                self.qout_status.setText(f" QUIDO Output {dout_ip} - status: OK ")
                self.qout_status.setStyleSheet("background-color: green;")
                qout = kvido(dout_ip)
                states = qout.get_outputs_state()
                for name, relay_str in self.conf.get('QUIDO_OUT', {}).items():
                    relay = int(relay_str)
                    state = states[relay - 1]
                    button = self.tabPolygon.findChild(QPushButton, name + "Button")
                    if button:
                        if state:
                            button.setStyleSheet("background-color: rgb(92, 184, 92); color: rgb(255, 255, 255)")
                        else:
                            button.setStyleSheet("background-color: rgb(255, 255, 255); color: rgb(0, 0, 0)")
                qout.disconnect()
            else:
                self.qout_status.setText(f" QUIDO Output {dout_ip} - status: Error ")
                self.qout_status.setStyleSheet("background-color: red;")
        except Exception as e:
            logger.error(f"Error reading relays: {e}")

    def click_button(self, relay):
        """Toggle relay output and update button color."""
        try:
            dout_ip = self.conf['QUIDO']['dout']
            qout = kvido(dout_ip)
            button = QtCore.QObject.sender(self)
            state = qout.get_output_state(relay)
            if not state:
                qout.set_output_on(relay)
                button.setStyleSheet("background-color: rgb(92, 184, 92); color: rgb(255, 255, 255)")
            else:
                qout.set_output_off(relay)
                button.setStyleSheet("background-color: rgb(255, 255, 255); color: rgb(0, 0, 0)")
            qout.disconnect()
        except Exception as e:
            logger.error(f"Error clicking button (relay {relay}): {e}")

    def assign_widgets(self):
        """Assign widgets with error handling."""
        try:
            self.statusbar.addPermanentWidget(self.qin_status)
            self.statusbar.addPermanentWidget(self.qout_status)
            # Show version and logged in user
            self.statusbar.showMessage(f"Version: {__VERSION__} | Přihlášen: {self.current_user}")
            # Setup table models
            self._setup_table_models()
            # Connect button signals
            self._connect_buttons()

        except Exception as e:
            logger.error(f"Error assigning widgets: {e}")

    def _setup_table_models(self):
        """Setup table models and views."""
        try:
            # Setup person table with proxy model for filtering
            self.proxy = QtCore.QSortFilterProxyModel(self)
            self.proxy.setSourceModel(self.personmodel)
            self.personTableView.setModel(self.proxy)
            self.personTableView.hideColumn(0)  # Hide idPerson
            self.personTableView.hideColumn(6)  # Hide valid column
            self.personTableView.resizeColumnsToContents()
            self.personTableView.setAlternatingRowColors(True)
            self.personTableView.setStyleSheet("color:Black; alternate-background-color: #DDD; background-color: #EEE; selection-color: black; selection-background-color:#add4fb")
            self.personTableView.setShowGrid(False)
            self.personTableView.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.personTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.personTableView.setSortingEnabled(True)
            self.personTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

            # Setup member table
            self.memberTableView.setModel(self.membermodel)
            self.memberTableView.hideColumn(0)  # Hide idMember
            self.memberTableView.resizeColumnsToContents()
            self.memberTableView.setAlternatingRowColors(True)
            self.memberTableView.setStyleSheet("color:Black; alternate-background-color: #DDD; background-color: #EEE; selection-color: black; selection-background-color:#add4fb")
            self.memberTableView.setShowGrid(False)
            self.memberTableView.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.memberTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

            # Setup training table
            self.trainingTableView.setModel(self.finishedtrainingmodel)
            self.trainingTableView.resizeColumnsToContents()
            self.trainingTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.trainingTableView.hideColumn(0)  # Hide idTraining
            self.trainingTableView.hideColumn(5)  # Hide status
            self.trainingTableView.setAlternatingRowColors(True)
            self.trainingTableView.setStyleSheet("color:Black; alternate-background-color: #DDD; background-color: #EEE; selection-color: black; selection-background-color:#add4fb")
            self.trainingTableView.setShowGrid(False)
            self.trainingTableView.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.trainingTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        except Exception as e:
            logger.error(f"Error setting up table models: {e}")

    def _connect_buttons(self):
        """Connect button signals to their handlers."""
        try:
            # Person management buttons
            self.addPersonButton.clicked.connect(self.addPerson)
            self.editPersonButton.clicked.connect(self.editPerson)
            self.delPersonButton.clicked.connect(self.delPerson)

            # Member management buttons
            self.addMemberButton.clicked.connect(self.addMember)
            self.delMemberButton.clicked.connect(self.delMember)
            self.updateMemberButton.clicked.connect(self.updateMember)

            # Training management buttons
            self.saveTrainingButton.clicked.connect(self.saveTraining)
            self.delTrainingButton.clicked.connect(self.delTraining)
            self.printTrainingButton.clicked.connect(self.printTrainingProtocol)

            # Technology/relay buttons (fans, lights, smoke, etc.)
            for name, relay_str in self.conf.get('QUIDO_OUT', {}).items():
                relay = int(relay_str)
                button = self.tabPolygon.findChild(QPushButton, name + "Button")
                if button:
                    button.clicked.connect(lambda checked, r=relay: self.click_button(r))

            # Start/Stop buttons
            self.startButton.clicked.connect(self.startStopwatch)
            self.stopButton.clicked.connect(self.stopStopwatch)

            # Initialize button states
            self.startButton.setEnabled(False)
            self.stopButton.setEnabled(False)

            # Search functionality
            self.searchPersonLineEdit.textChanged.connect(self.on_lineEdit_textChanged)

        except Exception as e:
            logger.error(f"Error connecting buttons: {e}")

    # Person management methods
    def addPerson(self):
        """Add new person."""
        try:
            personform = PersonForm(self.personmodel)
            if personform.exec_() == QDialog.Accepted:
                # Get the last inserted ID using SQL query (more reliable)
                self.query.exec_("SELECT LAST_INSERT_ID()")
                if self.query.first():
                    lastPerson = self.query.value(0)
                    if hasattr(personform, 'addMember') and personform.addMember == True:
                        self.addMember(lastPerson)

                # Refresh model to show the new person
                self.personmodel.select()
        except Exception as e:
            logger.error(f"Error adding person: {e}")

    def editPerson(self):
        """Edit selected person."""
        try:
            index = self.personTableView.selectionModel().currentIndex()
            if index.isValid():
                row = self.proxy.mapToSource(index).row()
                personform = PersonForm(self.personmodel, row)
                personform.exec_()
            else:
                QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error editing person: {e}")

    def delPerson(self):
        """Delete selected person."""
        try:
            index = self.personTableView.selectionModel().currentIndex()
            if index.isValid():
                row = self.proxy.mapToSource(index).row()
                reply = QMessageBox.question(self, 'Smazat', 'Opravdu chcete smazat osobu?',
                                           QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    record = self.personmodel.record(row)
                    record.setValue("valid", 0)
                    self.personmodel.setRecord(row, record)
                    self.personmodel.submitAll()
            else:
                QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba.', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error deleting person: {e}")

    def on_lineEdit_textChanged(self, text):
        """Handle search text change."""
        try:
            from PyQt5 import QtCore
            search = QtCore.QRegExp(text, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.RegExp)
            self.proxy.setFilterKeyColumn(-1)
            self.proxy.setFilterRegExp(search)
        except Exception as e:
            logger.error(f"Error filtering: {e}")

    # Member management methods
    def addMember(self, personId=None):
        """Add member to training."""
        try:
            # If personId is not provided, get it from selected row
            if not personId:
                index = self.personTableView.selectionModel().currentIndex()
                if not index.isValid():
                    QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba', QMessageBox.Ok)
                    return
                row = self.proxy.mapToSource(index).row()
                personId = self.personmodel.record(row).value("idPerson")

            # Validate personId
            if personId and personId > 0:
                trainingid = self.getTraining()
                if trainingid is None:
                    QMessageBox.warning(self, 'Varování', 'Nelze přidat člena do proběhlého cvičení', QMessageBox.Ok)
                    return
                if self.countMember(trainingid) < 4:
                    self.query.exec_("SELECT COUNT(idmember) FROM member WHERE training_id=%d AND person_id=%d" % (trainingid, personId))
                    self.query.first()
                    checkperson = self.query.value(0)
                    if checkperson == 0:
                        self.query.exec_("INSERT INTO member (training_id,person_id) VALUES (%d,%d)" % (trainingid, personId))
                        self.membermodel.refresh(trainingid)
                        if hasattr(self, 'memberTableView'):
                            self.memberTableView.hideColumn(0)
                        if self.countMember(trainingid) >= 2:
                            self.query.exec_("UPDATE training SET status=1 WHERE idTraining=%d" % (trainingid))
                            # Enable start button if exists
                            if hasattr(self, 'startButton'):
                                self.startButton.setEnabled(True)
                    else:
                        QMessageBox.information(self, 'Info', 'Osoba je již v tréninku', QMessageBox.Ok)
                else:
                    QMessageBox.warning(self, 'Varování', 'Trénink již má maximum 4 členů', QMessageBox.Ok)
            else:
                QMessageBox.warning(self, 'Varování', 'Neplatné ID osoby', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error adding member: {e}")

    def delMember(self):
        """Delete member from training."""
        try:
            trainingid = self.getTraining()
            if trainingid is None:
                QMessageBox.warning(self, 'Varování', 'Nelze odebrat člena z proběhlého cvičení', QMessageBox.Ok)
                return
            row = self.memberTableView.selectionModel().currentIndex().row()
            idMember = self.membermodel.record(row).value("idMember")
            if idMember is not None:
                self.query.exec_("DELETE FROM member WHERE idMember=%d" % (idMember))
                self.membermodel.view()
                count = self.countMember(trainingid)
                if count == 1:
                    self.query.exec_("UPDATE training SET status=0 WHERE idTraining=%d" % (trainingid))
                    if hasattr(self, 'startButton'):
                        self.startButton.setEnabled(False)
                elif count == 0:
                    self.query.exec_("DELETE FROM training WHERE idTraining=%d" % (trainingid))
            else:
                QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error deleting member: {e}")

    def updateMember(self):
        """Update member values."""
        try:
            row = self.memberTableView.selectionModel().currentIndex().row()
            if row >= 0:
                memberform = MemberForm(self.membermodel, row)
                memberform.exec_()
            else:
                QMessageBox.warning(self, 'Varování', 'Není vybrána žádná osoba', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error updating member: {e}")

    # Training management methods
    def saveTraining(self):
        """Save training."""
        try:
            self.query.exec_("SELECT idTraining FROM training WHERE status=2 LIMIT 1")
            self.query.first()
            trainingid = self.query.value(0)
            message = []
            if trainingid:
                self.query.exec_("SELECT member.volume, member.press_start, member.press_end, CONCAT(person.name,' ', person.surname) AS name "
                               "FROM member LEFT JOIN person ON member.person_id = person.idPerson WHERE training_id=%d" % trainingid)
                while self.query.next():
                    if int(self.query.value(0)) == 0 or int(self.query.value(1)) == 0:
                        message.append('Nejsou vyplněné všechny hodnoty u cvičících')
                    if int(self.query.value(1)) <= int(self.query.value(2)):
                        message.append('%s nemá počáteční tlak větší než koncový' % self.query.value(3))
            else:
                message.append('Není dokončený žádný trénink')
            if not message:
                self.query.exec_("UPDATE training SET status=10 WHERE status=2")
                self.membermodel.refresh(trainingid)
                self.finishedtrainingmodel.refresh()
                if hasattr(self, 'lcdNumber'):
                    self.lcdNumber.display("00:00")
            else:
                message = set(message)
                text = "\n".join(message)
                QMessageBox.warning(self, 'Varování', text, QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error saving training: {e}")

    def delTraining(self):
        """Delete training."""
        try:
            self.query.exec_("SELECT idTraining FROM training WHERE status<>10 LIMIT 1")
            if self.query.first():
                trainingid = self.query.value(0)
                if trainingid != 0:
                    self.query.exec_("DELETE FROM training WHERE status<>10")
                    self.query.exec_("DELETE FROM member WHERE training_id=%d" % (trainingid))
                    self.membermodel.refresh(trainingid)
                    if hasattr(self, 'startButton'):
                        self.startButton.setEnabled(False)
        except Exception as e:
            logger.error(f"Error deleting training: {e}")

    def printTrainingProtocol(self):
        """Print training protocol."""
        try:
            row = self.trainingTableView.selectionModel().currentIndex().row()
            if row >= 0:
                trainingid = self.finishedtrainingmodel.record(row).value("idTraining")
                if trainingid > 0:
                    # Import protocol module
                    from protocol import createProtocol

                    # Create and show protocol
                    doc = createProtocol(self.query, trainingid, self.current_user)
                    del doc
                else:
                    QMessageBox.warning(self, 'Varování', 'Neplatné ID cvičení', QMessageBox.Ok)
            else:
                QMessageBox.warning(self, 'Varování', 'Není vybráno žádné cvičení', QMessageBox.Ok)
        except Exception as e:
            logger.error(f"Error printing protocol: {e}")
            QMessageBox.warning(self, 'Chyba', f'Chyba při tisku protokolu: {e}', QMessageBox.Ok)

    # Helper methods
    def countMember(self, trainingid):
        """Count members in training."""
        try:
            self.query.exec_("SELECT COUNT(idmember) FROM member WHERE training_id=%d" % (trainingid))
            self.query.first()
            return self.query.value(0)
        except Exception as e:
            logger.error(f"Error counting members: {e}")
            return 0

    def getTraining(self):
        """Get or create current training."""
        try:
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
        except Exception as e:
            logger.error(f"Error getting training: {e}")
            return None

    def closeEvent(self, event):
        """Handle application close event."""
        try:
            quit_msg = "Opravdu chcete ukončit program?"
            reply = QMessageBox.question(self, 'Zavřít', quit_msg, QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.delTraining()
                # Close Spinel 97 log file
                try:
                    import pyspinel
                    pyspinel.close_log()
                except Exception as e:
                    logger.error(f"Error closing Spinel 97 log: {e}")
                event.accept()
            else:
                event.ignore()
        except Exception as e:
            logger.error(f"Error in close event: {e}")
            event.accept()  # Close anyway if there's an error

    # Timer and stopwatch methods
    def startStopwatch(self):
        """Start training stopwatch."""
        try:
            self.runningTraining = True
            # Start camera recording if available
            if hasattr(self, 'cam'):
                self.cam.startRecord(__VIDEO_FOLDER__)
                self.cam.setWindowIcon(QtGui.QIcon(os.path.join(__APP_DIR__, '../files/video-recording.png')))

            self.startButton.setEnabled(False)
            self.stopButton.setEnabled(True)

            # Initialize timer
            self.timer = QtCore.QTimer()
            self.timer.setInterval(1000)
            self.timer.timeout.connect(self.displayTime)
            self.time = QtCore.QElapsedTimer()
            self.time.start()
            self.timer.start()
        except Exception as e:
            logger.error(f"Error starting stopwatch: {e}")

    def stopStopwatch(self):
        """Stop training stopwatch."""
        try:
            self.stopButton.setEnabled(False)
            self.startButton.setEnabled(False)

            # Update training end time
            self.query.exec_("UPDATE training SET time_end='%s' WHERE status=1" % (self.racetime))
            self.query.exec_("UPDATE training SET status=2 WHERE status=1")

            # Stop timer
            if hasattr(self, 'timer'):
                self.timer.stop()
            self.runningTraining = False

            # Stop camera recording if available
            if hasattr(self, 'cam'):
                self.cam.stopRecord()
                self.cam.setWindowIcon(QtGui.QIcon(os.path.join(__APP_DIR__, '../files/video.png')))
        except Exception as e:
            logger.error(f"Error stopping stopwatch: {e}")

    def displayTime(self):
        """Display elapsed time on LCD."""
        try:
            if hasattr(self, 'time'):
                msec = self.time.elapsed()
                s = int(msec / 1000 % 60)
                m = int(msec / 1000 / 60 % 60)
                self.racetime = f"{m:02.0f}:{s:02.0f}"
                if hasattr(self, 'lcdNumber'):
                    self.lcdNumber.display(self.racetime)
        except Exception as e:
            logger.error(f"Error displaying time: {e}")

    def enterCage(self):
        """Record cage entry time."""
        try:
            if hasattr(self, 'racetime'):
                self.query.exec_("UPDATE training SET time_cage=IF(time_cage = '00:00:00' OR time_cage IS NULL, '%s', time_cage) WHERE status=1" % (self.racetime))
        except Exception as e:
            logger.error(f"Error recording cage entry: {e}")


class LoginDialog(QDialog, Ui_Login_Dialog):
    """Login dialog with LDAP authentication."""

    def __init__(self, ldap_config: dict):
        super().__init__()
        self.setupUi(self)
        self.ldap_config = ldap_config
        self.username = None  # Store username for later use
        self.display_name = None  # Store display name for later use

        # Connect signals
        self.buttonBox.accepted.connect(self.handle_login)
        self.buttonBox.rejected.connect(self.handle_cancel)

        # Set password field
        self.passwordLineEdit.setEchoMode(self.passwordLineEdit.Password)
        self.passwordLineEdit.clear()

    def handle_login(self):
        """Handle login attempt."""
        try:
            username = self.userLineEdit.text().strip()
            password = self.passwordLineEdit.text()

            # Clear password field immediately
            self.passwordLineEdit.clear()

            if not username or not password:
                QMessageBox.warning(self, 'Chyba přihlášení', 'Zadejte uživatelské jméno a heslo.')
                return

            # Attempt LDAP authentication
            if self._authenticate_ldap(username, password):
                logger.info(f"Successful login for user: {username}")
                self.username = username  # Store username for later use
                self.accept()
            else:
                QMessageBox.warning(self, 'Chyba přihlášení', 'Nesprávné přihlašovací údaje nebo nedostatečná oprávnění.')

        except Exception as e:
            logger.error(f"Login error: {e}")
            QMessageBox.warning(self, 'Chyba přihlášení', 'Došlo k chybě při přihlašování.')

    def _authenticate_ldap(self, username: str, password: str) -> bool:
        """Authenticate user against LDAP."""
        try:
            # Create LDAP connection
            server = ldap3.Server(self.ldap_config['host'])
            conn = ldap3.Connection(
                server,
                self.ldap_config['username'],
                self.ldap_config['password'],
                auto_bind=True
            )

            # Search for user
            search_filter = f'(&(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2))(!(objectClass=computer))(sAMAccountName={username}))'

            conn.search(
                self.ldap_config['base'],
                search_filter,
                ldap3.SUBTREE,
                attributes=['displayName']
            )

            if not conn.entries:
                return False

            user_dn = conn.entries[0].entry_dn

            # Get display name if available
            if hasattr(conn.entries[0], 'displayName') and conn.entries[0].displayName.value:
                self.display_name = conn.entries[0].displayName.value
            else:
                self.display_name = username  # Fallback to username

            # Test user password
            user_conn = ldap3.Connection(server, user_dn, password)
            if not user_conn.bind():
                return False

            # Check group membership
            conn.search(
                self.ldap_config['group'],
                '(objectClass=group)',
                ldap3.SUBTREE,
                attributes=['member']
            )

            if conn.entries and hasattr(conn.entries[0], 'member'):
                for member in conn.entries[0].member.values:
                    if user_dn.lower() == member.lower():
                        return True

            return False

        except Exception as e:
            logger.error(f"LDAP authentication error: {e}")
            return False

    def handle_cancel(self):
        """Handle login cancellation."""
        self.passwordLineEdit.clear()
        self.userLineEdit.clear()
        self.reject()


def main():
    """Main entry point."""
    try:
        # Initialize Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("Polygon Control System")
        app.setApplicationVersion(__VERSION__)

        # Load configuration
        try:
            app_dir = os.path.dirname(__file__)
            config_file = os.path.join(app_dir, "../config/polygon.conf")

            config_manager = ConfigManager(config_file)
            config = config_manager.load_config()

        except ConfigurationError as e:
            QMessageBox.critical(None, 'Chyba konfigurace', str(e))
            return 1

        # Show login dialog
        login_dialog = LoginDialog(config['LDAP'])

        if login_dialog.exec_() != QDialog.Accepted:
            logger.info("User cancelled login")
            return 0

        # Get display name from login dialog (for protocol printing)
        display_name = getattr(login_dialog, 'display_name', 'Unknown User')

        # Initialize database connection globally (like in original version)
        try:
            db = QtSql.QSqlDatabase.addDatabase("QMYSQL")
            db.setHostName(config['MYSQL']['host'])
            db.setUserName(config['MYSQL']['user'])
            db.setPassword(config['MYSQL']['password'])
            db.setDatabaseName(config['MYSQL']['database'])

            if not db.open():
                error = db.lastError()
                logger.error(f"Database connection failed: {error.text()}")
                QMessageBox.critical(None, 'Chyba databáze', f'Nepodařilo se připojit k databázi: {error.text()}')
                return 1
            else:
                logger.info("Database connection established")

        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            QMessageBox.critical(None, 'Chyba databáze', f'Chyba při připojování k databázi: {e}')
            return 1

        # Create and show main window
        main_window = MainWindow(config, display_name)

        # Run application
        return app.exec_()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        QMessageBox.critical(None, 'Kritická chyba', f'Došlo k kritické chybě: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())