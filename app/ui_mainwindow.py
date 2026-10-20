from PyQt5 import QtCore, QtGui, QtSql, QtWidgets
from PyQt5.QtWidgets import QMessageBox
from logger_config import logger
from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout, QTabWidget, QHBoxLayout, QGroupBox, QLabel, QSlider, QSizePolicy, QSpacerItem, QTableView, QStatusBar, QAction, QDialog, QWidget, QLineEdit, QDialogButtonBox, QFormLayout, QDataWidgetMapper \
							, QDateEdit, QDateTimeEdit, QCheckBox, QComboBox, QSplitter

from theme import TEXT_MUTED, set_variant, style_table
from polygon_map import PolygonMapWidget
from logbook import LogbookTab
from model import personFilterProxyModel, personModel

try:
	_fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
	def _fromUtf8(s):
		return s

try:
	_encoding = QApplication.UnicodeUTF8
	def _translate(context, text, disambig):
		return QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
	def _translate(context, text, disambig):
		return QApplication.translate(context, text, disambig)

class Ui_MainWindow(object):
	def setupUi(self, MainWindow):
		MainWindow.setObjectName(_fromUtf8("MainWindow"))
		self.centralwidget = QWidget(MainWindow)
		self.centralwidget.setObjectName(_fromUtf8("centralwidget"))
		self.horizontalLayout = QHBoxLayout(self.centralwidget)
		self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
		self.verticalLayout = QVBoxLayout()
		self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
		self.ptabWidget = QTabWidget(self.centralwidget)
		palette = QtGui.QPalette()
		brush = QtGui.QBrush(QtGui.QColor(49, 54, 59))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.WindowText, brush)
		brush = QtGui.QBrush(QtGui.QColor(239, 240, 241))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Button, brush)
		brush = QtGui.QBrush(QtGui.QColor(49, 54, 59))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Text, brush)
		brush = QtGui.QBrush(QtGui.QColor(49, 54, 59))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.ButtonText, brush)
		brush = QtGui.QBrush(QtGui.QColor(252, 252, 252))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Base, brush)
		brush = QtGui.QBrush(QtGui.QColor(243, 244, 245))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Window, brush)
		brush = QtGui.QBrush(QtGui.QColor(61, 174, 233))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Highlight, brush)
		brush = QtGui.QBrush(QtGui.QColor(239, 240, 241))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.HighlightedText, brush)
		brush = QtGui.QBrush(QtGui.QColor(41, 128, 185))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Link, brush)
		brush = QtGui.QBrush(QtGui.QColor(127, 140, 141))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.LinkVisited, brush)
		brush = QtGui.QBrush(QtGui.QColor(239, 240, 241))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.AlternateBase, brush)
		brush = QtGui.QBrush(QtGui.QColor(49, 54, 59))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.WindowText, brush)
		brush = QtGui.QBrush(QtGui.QColor(239, 240, 241))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Button, brush)
		brush = QtGui.QBrush(QtGui.QColor(49, 54, 59))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Text, brush)
		brush = QtGui.QBrush(QtGui.QColor(49, 54, 59))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.ButtonText, brush)
		brush = QtGui.QBrush(QtGui.QColor(252, 252, 252))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Base, brush)
		brush = QtGui.QBrush(QtGui.QColor(243, 244, 245))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Window, brush)
		brush = QtGui.QBrush(QtGui.QColor(61, 174, 233))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Highlight, brush)
		brush = QtGui.QBrush(QtGui.QColor(239, 240, 241))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.HighlightedText, brush)
		brush = QtGui.QBrush(QtGui.QColor(41, 128, 185))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Link, brush)
		brush = QtGui.QBrush(QtGui.QColor(127, 140, 141))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.LinkVisited, brush)
		brush = QtGui.QBrush(QtGui.QColor(239, 240, 241))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.AlternateBase, brush)
		brush = QtGui.QBrush(QtGui.QColor(49, 54, 59))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, brush)
		brush = QtGui.QBrush(QtGui.QColor(239, 240, 241))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Button, brush)
		brush = QtGui.QBrush(QtGui.QColor(49, 54, 59))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Text, brush)
		brush = QtGui.QBrush(QtGui.QColor(49, 54, 59))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, brush)
		brush = QtGui.QBrush(QtGui.QColor(252, 252, 252))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Base, brush)
		brush = QtGui.QBrush(QtGui.QColor(243, 244, 245))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Window, brush)
		brush = QtGui.QBrush(QtGui.QColor(61, 174, 233))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Highlight, brush)
		brush = QtGui.QBrush(QtGui.QColor(239, 240, 241))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.HighlightedText, brush)
		brush = QtGui.QBrush(QtGui.QColor(41, 128, 185))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Link, brush)
		brush = QtGui.QBrush(QtGui.QColor(127, 140, 141))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.LinkVisited, brush)
		brush = QtGui.QBrush(QtGui.QColor(239, 240, 241))
		brush.setStyle(QtCore.Qt.SolidPattern)
		palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.AlternateBase, brush)
		self.ptabWidget.setPalette(palette)
		self.ptabWidget.setObjectName(_fromUtf8("ptabWidget"))
		self.tabProvoz = QWidget()
		self.tabProvoz.setObjectName(_fromUtf8("tabProvoz"))
		self.verticalLayout_provoz = QVBoxLayout(self.tabProvoz)
		self.verticalLayout_provoz.setObjectName(_fromUtf8("verticalLayout_provoz"))
		self.insideCountLabel = QLabel(self.tabProvoz)
		self.insideCountLabel.setObjectName(_fromUtf8("insideCountLabel"))
		font_insideCount = QtGui.QFont()
		font_insideCount.setPointSize(16)
		font_insideCount.setBold(True)
		self.insideCountLabel.setFont(font_insideCount)
		self.insideCountLabel.setMinimumWidth(360)
		self.verticalLayout_provoz.addWidget(self.insideCountLabel, 0, QtCore.Qt.AlignLeft)
		self.sessionGroupBox = QGroupBox(self.tabProvoz)
		self.sessionGroupBox.setObjectName(_fromUtf8("sessionGroupBox"))
		self.verticalLayout_23 = QVBoxLayout(self.sessionGroupBox)
		self.verticalLayout_23.setObjectName(_fromUtf8("verticalLayout_23"))
		# Etapa 8.5: order follows the operator's work - who's where first,
		# then the selected member and their entry/exit.
		self.sessionTableView = QTableView(self.sessionGroupBox)
		self.sessionTableView.setObjectName(_fromUtf8("sessionTableView"))
		self.verticalLayout_23.addWidget(self.sessionTableView)
		self.selectedMemberLabel = QLabel(self.sessionGroupBox)
		self.selectedMemberLabel.setObjectName(_fromUtf8("selectedMemberLabel"))
		self.verticalLayout_23.addWidget(self.selectedMemberLabel)
		# WAVE2-02: entry/exit record the time of the click - no time fields,
		# both buttons side by side in one row.
		self.horizontalLayout_34 = QHBoxLayout()
		self.horizontalLayout_34.setObjectName(_fromUtf8("horizontalLayout_34"))
		self.recordEntryButton = QPushButton(self.sessionGroupBox)
		self.recordEntryButton.setMinimumSize(QtCore.QSize(125, 52))
		self.recordEntryButton.setObjectName(_fromUtf8("recordEntryButton"))
		set_variant(self.recordEntryButton, "success", "lg")
		self.horizontalLayout_34.addWidget(self.recordEntryButton)
		self.recordExitButton = QPushButton(self.sessionGroupBox)
		self.recordExitButton.setMinimumSize(QtCore.QSize(125, 52))
		self.recordExitButton.setObjectName(_fromUtf8("recordExitButton"))
		set_variant(self.recordExitButton, "danger", "lg")
		self.horizontalLayout_34.addWidget(self.recordExitButton)
		self.verticalLayout_23.addLayout(self.horizontalLayout_34)
		self.verticalLayout_provoz.addWidget(self.sessionGroupBox)
		# Training lifecycle (main operational action + save), separate from
		# the destructive admin action below.
		self.lifecycleGroupBox = QGroupBox(self.tabProvoz)
		self.lifecycleGroupBox.setObjectName(_fromUtf8("lifecycleGroupBox"))
		self.horizontalLayout_provozActions = QHBoxLayout(self.lifecycleGroupBox)
		self.horizontalLayout_provozActions.setObjectName(_fromUtf8("horizontalLayout_provozActions"))
		self.stopButton = QPushButton(self.lifecycleGroupBox)
		self.stopButton.setMinimumSize(QtCore.QSize(0, 100))
		self.stopButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.stopButton.setObjectName(_fromUtf8("stopButton"))
		set_variant(self.stopButton, "primary", "xl")
		self.horizontalLayout_provozActions.addWidget(self.stopButton, 3)
		self.saveTrainingButton = QPushButton(self.lifecycleGroupBox)
		self.saveTrainingButton.setMinimumSize(QtCore.QSize(125, 100))
		self.saveTrainingButton.setObjectName(_fromUtf8("saveTrainingButton"))
		self.saveTrainingButton.setFocusPolicy(QtCore.Qt.NoFocus)
		set_variant(self.saveTrainingButton, "success", "xl")
		self.horizontalLayout_provozActions.addWidget(self.saveTrainingButton, 1)
		self.verticalLayout_provoz.addWidget(self.lifecycleGroupBox)
		# Destructive/admin action: its own group, right-aligned, small and
		# outline-only - never on par with the operational buttons.
		self.adminGroupBox = QGroupBox(self.tabProvoz)
		self.adminGroupBox.setObjectName(_fromUtf8("adminGroupBox"))
		self.horizontalLayout_provozAdmin = QHBoxLayout(self.adminGroupBox)
		self.horizontalLayout_provozAdmin.setObjectName(_fromUtf8("horizontalLayout_provozAdmin"))
		spacerItem_provozAdmin = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
		self.horizontalLayout_provozAdmin.addItem(spacerItem_provozAdmin)
		self.delTrainingButton = QPushButton(self.adminGroupBox)
		self.delTrainingButton.setMinimumSize(QtCore.QSize(125, 28))
		self.delTrainingButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.delTrainingButton.setObjectName(_fromUtf8("delTrainingButton"))
		set_variant(self.delTrainingButton, "destructive")
		self.horizontalLayout_provozAdmin.addWidget(self.delTrainingButton)
		self.verticalLayout_provoz.addWidget(self.adminGroupBox)
		self.tabPolygon = QWidget()
		self.tabPolygon.setObjectName(_fromUtf8("tabPolygon"))
		self.horizontalLayout_2 = QHBoxLayout(self.tabPolygon)
		self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
		self.verticalLayout_2 = QVBoxLayout()
		self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
		self.verticalLayout_10 = QVBoxLayout()
		self.verticalLayout_10.setObjectName(_fromUtf8("verticalLayout_10"))
		self.groupBox_5 = QGroupBox(self.tabPolygon)
		self.groupBox_5.setEnabled(True)
		self.groupBox_5.setTitle(_fromUtf8(""))
		self.groupBox_5.setObjectName(_fromUtf8("groupBox_5"))
		# MAP-01: one scalable floor-plan map instead of 59 QLabel floor_XX + roura
		self.verticalLayout_map = QVBoxLayout(self.groupBox_5)
		self.verticalLayout_map.setContentsMargins(0, 0, 0, 0)
		self.polygonMap = PolygonMapWidget(self.groupBox_5)
		self.polygonMap.setObjectName(_fromUtf8("polygonMap"))
		self.verticalLayout_map.addWidget(self.polygonMap)
		self.verticalLayout_10.addWidget(self.groupBox_5)
		self.verticalLayout_2.addLayout(self.verticalLayout_10)
		self.horizontalLayout_3 = QHBoxLayout()
		self.horizontalLayout_3.setObjectName(_fromUtf8("horizontalLayout_3"))
		self.groupBox_4 = QGroupBox(self.tabPolygon)
		self.groupBox_4.setObjectName(_fromUtf8("groupBox_4"))
		self.horizontalLayout_9 = QHBoxLayout(self.groupBox_4)
		self.horizontalLayout_9.setObjectName(_fromUtf8("horizontalLayout_9"))
		self.horizontalLayout_8 = QHBoxLayout()
		self.horizontalLayout_8.setObjectName(_fromUtf8("horizontalLayout_8"))
		self.horizontalLayout_11 = QHBoxLayout()
		self.horizontalLayout_11.setObjectName(_fromUtf8("horizontalLayout_11"))
		self.verticalLayout_5 = QVBoxLayout()
		self.verticalLayout_5.setObjectName(_fromUtf8("verticalLayout_5"))
		self.fan12Button = QPushButton(self.groupBox_4)
		self.fan12Button.setMinimumSize(QtCore.QSize(120, 60))
		self.fan12Button.setFocusPolicy(QtCore.Qt.NoFocus)
		self.fan12Button.setStyleSheet(_fromUtf8(""))
		self.fan12Button.setCheckable(True)
		self.fan12Button.setObjectName(_fromUtf8("fan12Button"))
		self.verticalLayout_5.addWidget(self.fan12Button)
		self.fan34Button = QPushButton(self.groupBox_4)
		self.fan34Button.setMinimumSize(QtCore.QSize(120, 60))
		self.fan34Button.setFocusPolicy(QtCore.Qt.NoFocus)
		self.fan34Button.setCheckable(True)
		self.fan34Button.setObjectName(_fromUtf8("fan34Button"))
		self.verticalLayout_5.addWidget(self.fan34Button)
		self.fanControlRoomButton = QPushButton(self.groupBox_4)
		self.fanControlRoomButton.setMinimumSize(QtCore.QSize(120, 60))
		self.fanControlRoomButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.fanControlRoomButton.setCheckable(True)
		self.fanControlRoomButton.setObjectName(_fromUtf8("fanControlRoomButton"))
		self.verticalLayout_5.addWidget(self.fanControlRoomButton)
		self.glowButton = QPushButton(self.groupBox_4)
		self.glowButton.setMinimumSize(QtCore.QSize(120, 60))
		self.glowButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.glowButton.setCheckable(True)
		self.glowButton.setObjectName(_fromUtf8("glowButton"))
		self.verticalLayout_5.addWidget(self.glowButton)
		self.horizontalLayout_11.addLayout(self.verticalLayout_5)
		self.horizontalLayout_8.addLayout(self.horizontalLayout_11)
		self.horizontalLayout_12 = QHBoxLayout()
		self.horizontalLayout_12.setObjectName(_fromUtf8("horizontalLayout_12"))
		self.verticalLayout_6 = QVBoxLayout()
		self.verticalLayout_6.setObjectName(_fromUtf8("verticalLayout_6"))
		self.stroboButton = QPushButton(self.groupBox_4)
		self.stroboButton.setMinimumSize(QtCore.QSize(120, 60))
		self.stroboButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.stroboButton.setCheckable(True)
		self.stroboButton.setObjectName(_fromUtf8("stroboButton"))
		self.verticalLayout_6.addWidget(self.stroboButton)
		self.hotZoneButton = QPushButton(self.groupBox_4)
		self.hotZoneButton.setMinimumSize(QtCore.QSize(120, 60))
		self.hotZoneButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.hotZoneButton.setCheckable(True)
		self.hotZoneButton.setObjectName(_fromUtf8("hotZoneButton"))
		self.verticalLayout_6.addWidget(self.hotZoneButton)
		self.louverButton = QPushButton(self.groupBox_4)
		self.louverButton.setMinimumSize(QtCore.QSize(120, 60))
		self.louverButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.louverButton.setCheckable(True)
		self.louverButton.setObjectName(_fromUtf8("louverButton"))
		self.verticalLayout_6.addWidget(self.louverButton)
		self.smokeButton = QPushButton(self.groupBox_4)
		self.smokeButton.setMinimumSize(QtCore.QSize(120, 60))
		self.smokeButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.smokeButton.setCheckable(True)
		self.smokeButton.setObjectName(_fromUtf8("smokeButton"))
		self.verticalLayout_6.addWidget(self.smokeButton)
		self.horizontalLayout_12.addLayout(self.verticalLayout_6)
		self.horizontalLayout_8.addLayout(self.horizontalLayout_12)
		self.horizontalLayout_9.addLayout(self.horizontalLayout_8)
		self.horizontalLayout_3.addWidget(self.groupBox_4)
		self.groupBox_3 = QGroupBox(self.tabPolygon)
		self.groupBox_3.setObjectName(_fromUtf8("groupBox_3"))
		self.horizontalLayout_5 = QHBoxLayout(self.groupBox_3)
		self.horizontalLayout_5.setObjectName(_fromUtf8("horizontalLayout_5"))
		self.horizontalLayout_4 = QHBoxLayout()
		self.horizontalLayout_4.setObjectName(_fromUtf8("horizontalLayout_4"))
		self.horizontalLayout_6 = QHBoxLayout()
		self.horizontalLayout_6.setObjectName(_fromUtf8("horizontalLayout_6"))
		self.verticalLayout_3 = QVBoxLayout()
		self.verticalLayout_3.setObjectName(_fromUtf8("verticalLayout_3"))
		self.polygonLight1Button = QPushButton(self.groupBox_3)
		self.polygonLight1Button.setMinimumSize(QtCore.QSize(120, 60))
		self.polygonLight1Button.setFocusPolicy(QtCore.Qt.NoFocus)
		self.polygonLight1Button.setCheckable(True)
		self.polygonLight1Button.setObjectName(_fromUtf8("polygonLight1Button"))
		self.verticalLayout_3.addWidget(self.polygonLight1Button)
		self.polygonLight2Button = QPushButton(self.groupBox_3)
		self.polygonLight2Button.setMinimumSize(QtCore.QSize(120, 60))
		self.polygonLight2Button.setFocusPolicy(QtCore.Qt.NoFocus)
		self.polygonLight2Button.setCheckable(True)
		self.polygonLight2Button.setObjectName(_fromUtf8("polygonLight2Button"))
		self.verticalLayout_3.addWidget(self.polygonLight2Button)
		self.polygonLight3Button = QPushButton(self.groupBox_3)
		self.polygonLight3Button.setMinimumSize(QtCore.QSize(120, 60))
		self.polygonLight3Button.setFocusPolicy(QtCore.Qt.NoFocus)
		self.polygonLight3Button.setCheckable(True)
		self.polygonLight3Button.setObjectName(_fromUtf8("polygonLight3Button"))
		self.verticalLayout_3.addWidget(self.polygonLight3Button)
		self.hotZoneLightButton = QPushButton(self.groupBox_3)
		self.hotZoneLightButton.setMinimumSize(QtCore.QSize(120, 60))
		self.hotZoneLightButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.hotZoneLightButton.setCheckable(True)
		self.hotZoneLightButton.setObjectName(_fromUtf8("hotZoneLightButton"))
		self.verticalLayout_3.addWidget(self.hotZoneLightButton)
		self.horizontalLayout_6.addLayout(self.verticalLayout_3)
		self.horizontalLayout_4.addLayout(self.horizontalLayout_6)
		self.horizontalLayout_7 = QHBoxLayout()
		self.horizontalLayout_7.setObjectName(_fromUtf8("horizontalLayout_7"))
		self.verticalLayout_4 = QVBoxLayout()
		self.verticalLayout_4.setObjectName(_fromUtf8("verticalLayout_4"))
		self.stressRoomLightButton = QPushButton(self.groupBox_3)
		self.stressRoomLightButton.setMinimumSize(QtCore.QSize(120, 60))
		self.stressRoomLightButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.stressRoomLightButton.setCheckable(True)
		self.stressRoomLightButton.setObjectName(_fromUtf8("stressRoomLightButton"))
		self.verticalLayout_4.addWidget(self.stressRoomLightButton)
		self.infraLightButton = QPushButton(self.groupBox_3)
		self.infraLightButton.setMinimumSize(QtCore.QSize(120, 60))
		self.infraLightButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.infraLightButton.setCheckable(True)
		self.infraLightButton.setObjectName(_fromUtf8("infraLightButton"))
		self.verticalLayout_4.addWidget(self.infraLightButton)
		self.controlRoomLightButton = QPushButton(self.groupBox_3)
		self.controlRoomLightButton.setMinimumSize(QtCore.QSize(120, 60))
		self.controlRoomLightButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.controlRoomLightButton.setCheckable(True)
		self.controlRoomLightButton.setObjectName(_fromUtf8("controlRoomLightButton"))
		self.verticalLayout_4.addWidget(self.controlRoomLightButton)
		self.helpLightButton = QPushButton(self.groupBox_3)
		self.helpLightButton.setMinimumSize(QtCore.QSize(120, 60))
		self.helpLightButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.helpLightButton.setCheckable(True)
		self.helpLightButton.setObjectName(_fromUtf8("helpLightButton"))
		self.verticalLayout_4.addWidget(self.helpLightButton)
		self.horizontalLayout_7.addLayout(self.verticalLayout_4)
		self.horizontalLayout_4.addLayout(self.horizontalLayout_7)
		self.horizontalLayout_5.addLayout(self.horizontalLayout_4)
		self.horizontalLayout_3.addWidget(self.groupBox_3)
		self.groupBox = QGroupBox(self.tabPolygon)
		self.groupBox.setObjectName(_fromUtf8("groupBox"))
		self.horizontalLayout_13 = QHBoxLayout(self.groupBox)
		self.horizontalLayout_13.setObjectName(_fromUtf8("horizontalLayout_13"))
		self.verticalLayout_8 = QVBoxLayout()
		self.verticalLayout_8.setObjectName(_fromUtf8("verticalLayout_8"))
		self.horizontalLayout_16 = QHBoxLayout()
		self.horizontalLayout_16.setObjectName(_fromUtf8("horizontalLayout_16"))
		self.volumeSlider = QSlider(self.groupBox)
		self.volumeSlider.setProperty("value", 50)
		self.volumeSlider.setOrientation(QtCore.Qt.Vertical)
		self.volumeSlider.setTickPosition(QSlider.TicksBothSides)
		self.volumeSlider.setObjectName(_fromUtf8("volumeSlider"))
		sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		sizePolicy.setHeightForWidth(self.volumeSlider.sizePolicy().hasHeightForWidth())
		self.volumeSlider.setSizePolicy(sizePolicy)
		self.horizontalLayout_16.addWidget(self.volumeSlider)
		self.volumeLabel = QLabel(self.groupBox)  # AUDIO-01: current volume in %
		self.volumeLabel.setObjectName(_fromUtf8("volumeLabel"))
		self.volumeLabel.setMinimumWidth(60)
		self.horizontalLayout_16.addWidget(self.volumeLabel)
		# AUDIO-02: volume on the left, sound buttons in a column on the right
		self.horizontalLayout_13.addLayout(self.horizontalLayout_16)
		self.pushButton_19 = QPushButton(self.groupBox)
		self.pushButton_19.setMinimumSize(QtCore.QSize(0, 60))
		self.pushButton_19.setFocusPolicy(QtCore.Qt.NoFocus)
		self.pushButton_19.setObjectName(_fromUtf8("pushButton_19"))
		set_variant(self.pushButton_19, "secondary")
		self.verticalLayout_8.addWidget(self.pushButton_19)  # more sound buttons go below
		self.horizontalLayout_15 = QHBoxLayout()
		self.horizontalLayout_15.setObjectName(_fromUtf8("horizontalLayout_15"))
		self.verticalLayout_8.addLayout(self.horizontalLayout_15)  # room for more sound buttons
		self.verticalLayout_8.addStretch(1)  # buttons stay at the top
		self.horizontalLayout_13.addLayout(self.verticalLayout_8)
		self.horizontalLayout_3.addWidget(self.groupBox)
		# CAMERA-LIFECYCLE-01: Kamery - the one place for camera state and control
		self.groupBox_cameras = QGroupBox(self.tabPolygon)
		self.groupBox_cameras.setObjectName(_fromUtf8("groupBox_cameras"))
		self.verticalLayout_cameras = QVBoxLayout(self.groupBox_cameras)
		self.verticalLayout_cameras.setObjectName(_fromUtf8("verticalLayout_cameras"))
		self.cameraStateLabel = QLabel(self.groupBox_cameras)
		self.cameraStateLabel.setObjectName(_fromUtf8("cameraStateLabel"))
		self.verticalLayout_cameras.addWidget(self.cameraStateLabel)
		self.recordingStateLabel = QLabel(self.groupBox_cameras)
		self.recordingStateLabel.setObjectName(_fromUtf8("recordingStateLabel"))
		self.verticalLayout_cameras.addWidget(self.recordingStateLabel)
		for label in (self.cameraStateLabel, self.recordingStateLabel):
			label.setAlignment(QtCore.Qt.AlignCenter)
		for name in ("showCamerasButton", "cameraToggleButton", "openRecordingsButton"):
			button = QPushButton(self.groupBox_cameras)
			button.setMinimumSize(QtCore.QSize(0, 40))
			button.setFocusPolicy(QtCore.Qt.NoFocus)
			button.setObjectName(_fromUtf8(name))
			set_variant(button, "secondary")
			setattr(self, name, button)
			self.verticalLayout_cameras.addWidget(button)
		self.verticalLayout_cameras.addStretch(1)
		self.horizontalLayout_3.addWidget(self.groupBox_cameras)
		self.groupBox_6 = QGroupBox(self.tabPolygon)
		self.groupBox_6.setObjectName(_fromUtf8("groupBox_6"))
		self.horizontalLayout_10 = QHBoxLayout(self.groupBox_6)
		self.horizontalLayout_10.setObjectName(_fromUtf8("horizontalLayout_10"))
		self.verticalLayout_9 = QVBoxLayout()
		self.verticalLayout_9.setObjectName(_fromUtf8("verticalLayout_9"))
		self.emergencyButton = QPushButton(self.groupBox_6)
		self.emergencyButton.setMinimumSize(QtCore.QSize(0, 87))
		self.emergencyButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.emergencyButton.setObjectName(_fromUtf8("emergencyButton"))
		set_variant(self.emergencyButton, "warning", "lg")
		self.verticalLayout_9.addWidget(self.emergencyButton)
		# EMERGENCY-01: the button itself turns red while the emergency is active
		self.emergencyButton.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
		self.emergencyHelpButton = QPushButton(self.groupBox_6)  # EMERGENCY-02 placeholder, only while active
		self.emergencyHelpButton.setMinimumSize(QtCore.QSize(0, 48))
		self.emergencyHelpButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.emergencyHelpButton.setObjectName(_fromUtf8("emergencyHelpButton"))
		set_variant(self.emergencyHelpButton, "secondary")
		self.emergencyHelpButton.setEnabled(False)  # not wired to SIP yet - never active
		self.emergencyHelpButton.hide()
		self.verticalLayout_9.addWidget(self.emergencyHelpButton)
		self.emergencyExitButton = QPushButton(self.groupBox_6)  # EMERGENCY-01, only while active
		self.emergencyExitButton.setMinimumSize(QtCore.QSize(0, 48))
		self.emergencyExitButton.setFocusPolicy(QtCore.Qt.NoFocus)
		self.emergencyExitButton.setObjectName(_fromUtf8("emergencyExitButton"))
		set_variant(self.emergencyExitButton, "secondary")
		self.emergencyExitButton.hide()
		self.verticalLayout_9.addWidget(self.emergencyExitButton)
		self.horizontalLayout_10.addLayout(self.verticalLayout_9)
		self.horizontalLayout_3.addWidget(self.groupBox_6)
		# Technologie and Světla are the primary blocks - Zvuky, Kamery and
		# Obsluha share the rest (CAMERA-LIFECYCLE-01 added Kamery)
		for index, stretch in enumerate((3, 3, 2, 2, 2)):
			self.horizontalLayout_3.setStretch(index, stretch)
		self.verticalLayout_2.addLayout(self.horizontalLayout_3)
		self.verticalLayout_2.setStretch(0, 2)
		self.verticalLayout_2.setStretch(1, 1)
		self.horizontalLayout_2.addLayout(self.verticalLayout_2)
		self.tabPerson = QWidget()
		self.tabPerson.setObjectName(_fromUtf8("tabPerson"))
		self.horizontalLayout_19 = QHBoxLayout(self.tabPerson)
		self.horizontalLayout_19.setObjectName(_fromUtf8("horizontalLayout_19"))
		self.verticalLayout_11 = QVBoxLayout()
		self.verticalLayout_11.setObjectName(_fromUtf8("verticalLayout_11"))
		self.verticalLayout_15 = QVBoxLayout()
		self.verticalLayout_15.setObjectName(_fromUtf8("verticalLayout_15"))
		self.horizontalLayout_25 = QHBoxLayout()
		self.horizontalLayout_25.setObjectName(_fromUtf8("horizontalLayout_25"))
		self.label_4 = QLabel(self.tabPerson)
		self.label_4.setObjectName(_fromUtf8("label_4"))
		self.horizontalLayout_25.addWidget(self.label_4)
		self.searchPersonLineEdit = QLineEdit(self.tabPerson)
		self.searchPersonLineEdit.setMinimumSize(QtCore.QSize(0, 40))
		self.searchPersonLineEdit.setObjectName(_fromUtf8("searchPersonLineEdit"))
		self.searchPersonLineEdit.setClearButtonEnabled(True)
		self.horizontalLayout_25.addWidget(self.searchPersonLineEdit)
		self.addPersonButton = QPushButton(self.tabPerson)
		self.addPersonButton.setMinimumSize(QtCore.QSize(120, 40))
		self.addPersonButton.setObjectName(_fromUtf8("addPersonButton"))
		set_variant(self.addPersonButton, "primary")
		self.horizontalLayout_25.addWidget(self.addPersonButton)
		self.delPersonButton = QPushButton(self.tabPerson)
		self.delPersonButton.setMinimumSize(QtCore.QSize(120, 40))
		self.delPersonButton.setObjectName(_fromUtf8("delPersonButton"))
		set_variant(self.delPersonButton, "destructive")
		self.horizontalLayout_25.addWidget(self.delPersonButton)
		self.editPersonButton = QPushButton(self.tabPerson)
		sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		sizePolicy.setHeightForWidth(self.editPersonButton.sizePolicy().hasHeightForWidth())
		self.editPersonButton.setSizePolicy(sizePolicy)
		self.editPersonButton.setMinimumSize(QtCore.QSize(120, 40))
		self.editPersonButton.setObjectName(_fromUtf8("editPersonButton"))
		set_variant(self.editPersonButton, "secondary")
		self.horizontalLayout_25.addWidget(self.editPersonButton)
		spacerItem = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
		self.horizontalLayout_25.addItem(spacerItem)
		# DATA-02: secondary/admin action, kept apart at the far right.
		self.deletedPersonsButton = QPushButton(self.tabPerson)
		self.deletedPersonsButton.setMinimumSize(QtCore.QSize(120, 40))
		self.deletedPersonsButton.setObjectName(_fromUtf8("deletedPersonsButton"))
		set_variant(self.deletedPersonsButton, "secondary")
		self.horizontalLayout_25.addWidget(self.deletedPersonsButton)
		self.verticalLayout_15.addLayout(self.horizontalLayout_25)
		self.personTableView = QTableView(self.tabPerson)
		sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		sizePolicy.setHeightForWidth(self.personTableView.sizePolicy().hasHeightForWidth())
		self.personTableView.setSizePolicy(sizePolicy)
		self.personTableView.setObjectName(_fromUtf8("personTableView"))
		self.verticalLayout_15.addWidget(self.personTableView)
		self.verticalLayout_11.addLayout(self.verticalLayout_15)
		self.horizontalLayout_27 = QGroupBox(self.tabPerson)
		self.horizontalLayout_27.setObjectName(_fromUtf8("horizontalLayout_27"))
		self.verticalLayout_17 = QVBoxLayout(self.horizontalLayout_27)
		self.verticalLayout_17.setObjectName(_fromUtf8("verticalLayout_17"))
		self.verticalLayout_22 = QVBoxLayout()
		self.verticalLayout_22.setObjectName(_fromUtf8("verticalLayout_22"))
		self.horizontalLayout_32 = QHBoxLayout()
		self.horizontalLayout_32.setObjectName(_fromUtf8("horizontalLayout_32"))
		self.addMemberButton = QPushButton(self.horizontalLayout_27)
		self.addMemberButton.setMinimumSize(QtCore.QSize(125, 40))
		self.addMemberButton.setObjectName(_fromUtf8("addMemberButton"))
		set_variant(self.addMemberButton, "primary")
		self.horizontalLayout_32.addWidget(self.addMemberButton)
		self.delMemberButton = QPushButton(self.horizontalLayout_27)
		self.delMemberButton.setMinimumSize(QtCore.QSize(125, 40))
		self.delMemberButton.setObjectName(_fromUtf8("delMemberButton"))
		set_variant(self.delMemberButton, "destructive")
		self.horizontalLayout_32.addWidget(self.delMemberButton)
		self.updateMemberButton = QPushButton(self.horizontalLayout_27)
		self.updateMemberButton.setMinimumSize(QtCore.QSize(125, 40))
		self.updateMemberButton.setObjectName(_fromUtf8("updateMemberButton"))
		set_variant(self.updateMemberButton, "secondary")
		self.horizontalLayout_32.addWidget(self.updateMemberButton)
		spacerItem1 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
		self.horizontalLayout_32.addItem(spacerItem1)
		self.verticalLayout_22.addLayout(self.horizontalLayout_32)
		self.memberTableView = QTableView(self.horizontalLayout_27)
		self.memberTableView.setObjectName(_fromUtf8("memberTableView"))
		self.verticalLayout_22.addWidget(self.memberTableView)
		self.verticalLayout_17.addLayout(self.verticalLayout_22)
		self.verticalLayout_11.addWidget(self.horizontalLayout_27)
		self.horizontalLayout_19.addLayout(self.verticalLayout_11)
		self.tabTraining = QWidget()
		self.tabTraining.setObjectName(_fromUtf8("tabTraining"))
		self.horizontalLayout_21 = QHBoxLayout(self.tabTraining)
		self.horizontalLayout_21.setObjectName(_fromUtf8("horizontalLayout_21"))
		self.verticalLayout_12 = QVBoxLayout()
		self.verticalLayout_12.setObjectName(_fromUtf8("verticalLayout_12"))
		self.verticalLayout_13 = QVBoxLayout()
		self.verticalLayout_13.setObjectName(_fromUtf8("verticalLayout_13"))
		self.horizontalLayout_18 = QHBoxLayout()
		self.horizontalLayout_18.setObjectName(_fromUtf8("horizontalLayout_18"))
		# PRINT-01c: Zpráva = the training selected in the table below.
		self.summaryPreviewButton = QPushButton(self.tabTraining)
		self.summaryPreviewButton.setObjectName(_fromUtf8("summaryPreviewButton"))
		self.summaryPreviewButton.setMinimumSize(QtCore.QSize(160, 40))
		set_variant(self.summaryPreviewButton, "secondary")
		self.horizontalLayout_18.addWidget(self.summaryPreviewButton)
		self.summaryPdfButton = QPushButton(self.tabTraining)
		self.summaryPdfButton.setObjectName(_fromUtf8("summaryPdfButton"))
		self.summaryPdfButton.setMinimumSize(QtCore.QSize(160, 40))
		set_variant(self.summaryPdfButton, "secondary")
		self.horizontalLayout_18.addWidget(self.summaryPdfButton)
		spacerItem3 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
		self.horizontalLayout_18.addItem(spacerItem3)
		self.verticalLayout_13.addLayout(self.horizontalLayout_18)
		# Balík B: saved-training summary on top, the selected training's
		# participants below; the operator can drag the split.
		self.trainingSplitter = QSplitter(QtCore.Qt.Vertical, self.tabTraining)
		self.trainingSplitter.setObjectName(_fromUtf8("trainingSplitter"))
		self.trainingSplitter.setChildrenCollapsible(False)
		self.trainingTableView = QTableView(self.trainingSplitter)
		self.trainingTableView.setObjectName(_fromUtf8("trainingTableView"))
		self.trainingDetailGroupBox = QGroupBox(self.trainingSplitter)
		self.trainingDetailGroupBox.setObjectName(_fromUtf8("trainingDetailGroupBox"))
		self.verticalLayout_trainingDetail = QVBoxLayout(self.trainingDetailGroupBox)
		self.verticalLayout_trainingDetail.setObjectName(_fromUtf8("verticalLayout_trainingDetail"))
		# PRINT-01c: Potvrzení = the person selected in the table below.
		self.horizontalLayout_trainingDetailButtons = QHBoxLayout()
		self.horizontalLayout_trainingDetailButtons.setObjectName(_fromUtf8("horizontalLayout_trainingDetailButtons"))
		self.personPreviewButton = QPushButton(self.trainingDetailGroupBox)
		self.personPreviewButton.setObjectName(_fromUtf8("personPreviewButton"))
		self.personPreviewButton.setMinimumSize(QtCore.QSize(160, 40))
		set_variant(self.personPreviewButton, "secondary")
		self.horizontalLayout_trainingDetailButtons.addWidget(self.personPreviewButton)
		self.personPdfButton = QPushButton(self.trainingDetailGroupBox)
		self.personPdfButton.setObjectName(_fromUtf8("personPdfButton"))
		self.personPdfButton.setMinimumSize(QtCore.QSize(160, 40))
		set_variant(self.personPdfButton, "secondary")
		self.horizontalLayout_trainingDetailButtons.addWidget(self.personPdfButton)
		self.horizontalLayout_trainingDetailButtons.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
		self.verticalLayout_trainingDetail.addLayout(self.horizontalLayout_trainingDetailButtons)
		self.trainingDetailTableView = QTableView(self.trainingDetailGroupBox)
		self.trainingDetailTableView.setObjectName(_fromUtf8("trainingDetailTableView"))
		self.verticalLayout_trainingDetail.addWidget(self.trainingDetailTableView)
		self.trainingSplitter.setStretchFactor(0, 1)
		self.trainingSplitter.setStretchFactor(1, 1)
		self.verticalLayout_13.addWidget(self.trainingSplitter)
		self.verticalLayout_12.addLayout(self.verticalLayout_13)
		self.horizontalLayout_21.addLayout(self.verticalLayout_12)
		# LOGBOOK-01: Kniha provozu (view in logbook.py, logic in MainWindow)
		self.tabLogbook = LogbookTab()
		# UI-TABS-01: Polygon first, the order is set here in one place
		for tab in (self.tabPolygon, self.tabProvoz, self.tabTraining, self.tabPerson, self.tabLogbook):
			self.ptabWidget.addTab(tab, _fromUtf8(""))
		self.verticalLayout.addWidget(self.ptabWidget)
		self.horizontalLayout.addLayout(self.verticalLayout)
		MainWindow.setCentralWidget(self.centralwidget)
		#self.menubar = QMenuBar(MainWindow)
		#self.menubar.setGeometry(QtCore.QRect(0, 0, 1248, 29))
		#self.menubar.setObjectName(_fromUtf8("menubar"))
		#self.menuMenu = QMenu(self.menubar)
		#self.menuMenu.setObjectName(_fromUtf8("menuMenu"))
		#MainWindow.setMenuBar(self.menubar)
		self.statusbar = QStatusBar(MainWindow)
		self.statusbar.setObjectName(_fromUtf8("statusbar"))
		MainWindow.setStatusBar(self.statusbar)
		self.actionItem_1 = QAction(MainWindow)
		self.actionItem_1.setObjectName(_fromUtf8("actionItem_1"))
		self.actionItem_2 = QAction(MainWindow)
		self.actionItem_2.setObjectName(_fromUtf8("actionItem_2"))
		self.actionItem_3 = QAction(MainWindow)
		self.actionItem_3.setObjectName(_fromUtf8("actionItem_3"))
		self.actionO_aplikaci = QAction(MainWindow)
		self.actionO_aplikaci.setObjectName(_fromUtf8("actionO_aplikaci"))
		#self.menuMenu.addAction(self.actionItem_1)
		#self.menuMenu.addAction(self.actionItem_2)
		#self.menuMenu.addAction(self.actionItem_3)
		#self.menuMenu.addSeparator()
		#self.menuMenu.addAction(self.actionO_aplikaci)
		#self.menubar.addAction(self.menuMenu.menuAction())

		self.retranslateUi(MainWindow)
		self.ptabWidget.setCurrentWidget(self.tabPolygon)
		QtCore.QMetaObject.connectSlotsByName(MainWindow)

	def retranslateUi(self, MainWindow):
		MainWindow.setWindowTitle(_translate("MainWindow", "Polygon", None))
		self.groupBox_4.setTitle(_translate("MainWindow", "Technologie", None))
		self.fan12Button.setText(_translate("MainWindow", "Větrání\nlevá strana", None))
		self.fan34Button.setText(_translate("MainWindow", "Větrání\npravá strana", None))
		self.fanControlRoomButton.setText(_translate("MainWindow", "Ventilace\nvelínu", None))
		self.glowButton.setText(_translate("MainWindow", "Předehřev\nzadýmení", None))
		self.stroboButton.setText(_translate("MainWindow", "Záblesky", None))
		self.hotZoneButton.setText(_translate("MainWindow", "Teplá zóna", None))
		self.louverButton.setText(_translate("MainWindow", "Zatemnění\nžaluzie", None))
		self.smokeButton.setText(_translate("MainWindow", "Zadýmení", None))
		self.groupBox_3.setTitle(_translate("MainWindow", "Světla", None))
		self.polygonLight1Button.setText(_translate("MainWindow", "Osvětlení\npolygonu 1", None))
		self.polygonLight2Button.setText(_translate("MainWindow", "Osvětlení\npolygonu 2", None))
		self.polygonLight3Button.setText(_translate("MainWindow", "Osvětlení\npolygonu 3", None))
		self.hotZoneLightButton.setText(_translate("MainWindow", "Světlo\nteplé zóny", None))
		self.stressRoomLightButton.setText(_translate("MainWindow", "Zátěžová\nmístnost", None))
		self.infraLightButton.setText(_translate("MainWindow", "IR přísvit\nkamer", None))
		self.controlRoomLightButton.setText(_translate("MainWindow", "Světlo\nvelínu", None))
		self.helpLightButton.setText(_translate("MainWindow", "Navigační\nsvětla", None))
		self.ptabWidget.setTabText(self.ptabWidget.indexOf(self.tabProvoz), _translate("MainWindow", "Provoz", None))
		self.insideCountLabel.setText(_translate("MainWindow", "Žádné probíhající cvičení", None))
		self.sessionGroupBox.setTitle(_translate("MainWindow", "Individuální průchod polygonem", None))
		self.selectedMemberLabel.setText(_translate("MainWindow", "Vyberte cvičence v tabulce výše", None))
		self.recordEntryButton.setText(_translate("MainWindow", "Zapsat vstup", None))
		self.recordExitButton.setText(_translate("MainWindow", "Zapsat výstup", None))
		self.stopButton.setText(_translate("MainWindow", "Dokončit cvičení", None))
		self.saveTrainingButton.setText(_translate("MainWindow", "Uložit cvičení", None))
		self.delTrainingButton.setText(_translate("MainWindow", "Smazat cvičení", None))
		self.lifecycleGroupBox.setTitle(_translate("MainWindow", "Průběh cvičení", None))
		self.adminGroupBox.setTitle(_translate("MainWindow", "Správa cvičení", None))
		self.groupBox.setTitle(_translate("MainWindow", "Zvuky", None))
		self.pushButton_19.setText(_translate("MainWindow", "Zvukové efekty", None))
		self.groupBox_6.setTitle(_translate("MainWindow", "Obsluha", None))
		self.groupBox_cameras.setTitle(_translate("MainWindow", "Kamery", None))
		self.showCamerasButton.setText(_translate("MainWindow", "Zobrazit kamery", None))
		self.openRecordingsButton.setText(_translate("MainWindow", "Otevřít záznamy", None))
		self.emergencyButton.setText(_translate("MainWindow", "Nouzové tlačítko", None))
		self.emergencyHelpButton.setText(_translate("MainWindow", "PŘIVOLAT POMOC ROZHLASEM", None))
		self.emergencyHelpButton.setToolTip(_translate("MainWindow", "Přivolání personálu přes SIP / rozhlas bude doplněno v EMERGENCY-02.", None))
		self.emergencyExitButton.setText(_translate("MainWindow", "Ukončit nouzový režim", None))
		self.ptabWidget.setTabText(self.ptabWidget.indexOf(self.tabPolygon), _translate("MainWindow", "Polygon", None))
		self.label_4.setText(_translate("MainWindow", "Vyhledat osobu", None))
		self.addPersonButton.setText(_translate("MainWindow", "Založit osobu", None))
		self.delPersonButton.setText(_translate("MainWindow", "Smazat osobu", None))
		self.editPersonButton.setText(_translate("MainWindow", "Upravit osobu", None))
		self.deletedPersonsButton.setText(_translate("MainWindow", "Smazané osoby…", None))
		self.horizontalLayout_27.setTitle(_translate("MainWindow", "Osoby v aktuálním cvičení", None))
		self.addMemberButton.setText(_translate("MainWindow", "Přidat cvičence", None))
		self.delMemberButton.setText(_translate("MainWindow", "Smazat cvičence", None))
		self.updateMemberButton.setText(_translate("MainWindow", "Upravit hodnoty", None))
		self.ptabWidget.setTabText(self.ptabWidget.indexOf(self.tabPerson), _translate("MainWindow", "Osoby", None))
		self.summaryPreviewButton.setText(_translate("MainWindow", "Zpráva – náhled/tisk", None))
		self.summaryPdfButton.setText(_translate("MainWindow", "Zpráva – PDF", None))
		self.personPreviewButton.setText(_translate("MainWindow", "Potvrzení – náhled/tisk", None))
		self.personPdfButton.setText(_translate("MainWindow", "Potvrzení – PDF", None))
		self.trainingDetailGroupBox.setTitle(_translate("MainWindow", "Osoby ve vybraném cvičení", None))
		self.ptabWidget.setTabText(self.ptabWidget.indexOf(self.tabTraining), _translate("MainWindow", "Cvičení", None))
		self.ptabWidget.setTabText(self.ptabWidget.indexOf(self.tabLogbook), _translate("MainWindow", "Kniha provozu", None))
		#self.menuMenu.setTitle(_translate("MainWindow", "Menu", None))
		self.actionItem_1.setText(_translate("MainWindow", "Item 1", None))
		self.actionItem_2.setText(_translate("MainWindow", "Item 2", None))
		self.actionItem_3.setText(_translate("MainWindow", "Item 3", None))
		self.actionO_aplikaci.setText(_translate("MainWindow", "O aplikaci", None))


def exec_or_warn(dialog, query, message):
	"""exec_() a prepared query; on failure log the DB error, show a
	warning over `dialog` and return False (the caller must not accept)."""
	if query.exec_():
		return True
	error = query.lastError().text()
	logger.error(f"{dialog.__class__.__name__}: {message} {error}")
	QMessageBox.warning(dialog, u'Chyba', message + u'\n\n' + error)
	return False


PRESS_END_NOT_ENTERED = u"nezadáno"


def pressure_value(text):
	"""Bottle pressure 0-999 bar as int, None for anything else - empty
	included (never silently 0). ASCII digits only: setText() bypasses
	the form's QIntValidator."""
	if text.isascii() and text.isdigit() and len(text) <= 3:
		return int(text)
	return None


class PassageTimeDialog(QDialog):
	"""UX-02: manual correction of a pass's recorded time(s), opened from
	the Provoz context menu - never part of the normal click-time workflow.
	QDateTimeEdit (date too - a pass may cross midnight). exit_at None
	(UVNITŘ) disables Výstup: there is no exit to correct yet.

	Saving goes through save_callback(entry_at, exit_at) -> bool (MainWindow
	calls SessionService.correct_times() and shows any message); the dialog
	closes only when it returns True, so an invalid time stays editable."""
	FORMAT = "dd.MM.yyyy HH:mm:ss"

	def __init__(self, name, entry_at, exit_at, save_callback, parent=None):
		QDialog.__init__(self, parent)
		self.save_callback = save_callback
		self.setWindowTitle(u"Upravit čas průchodu – %s" % name)
		layout = QFormLayout(self)
		self.entryEdit = QDateTimeEdit(entry_at, self)
		self.exitEdit = QDateTimeEdit(exit_at if exit_at is not None else entry_at, self)
		for edit in (self.entryEdit, self.exitEdit):
			edit.setDisplayFormat(self.FORMAT)
			edit.setCalendarPopup(True)
		self.has_exit = exit_at is not None
		self.exitEdit.setEnabled(self.has_exit)
		if not self.has_exit:
			self.exitEdit.setSpecialValueText(u"—")  # shown at the minimum value
			self.exitEdit.setDateTime(self.exitEdit.minimumDateTime())
		layout.addRow(u"Vstup", self.entryEdit)
		layout.addRow(u"Výstup", self.exitEdit)
		self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
		self.buttonBox.accepted.connect(self.save)
		self.buttonBox.rejected.connect(self.reject)
		layout.addRow(self.buttonBox)

	def values(self):
		"""(entry_at, exit_at or None) as plain Python datetimes."""
		entry = self.entryEdit.dateTime().toPyDateTime().replace(microsecond=0)
		exit_ = self.exitEdit.dateTime().toPyDateTime().replace(microsecond=0) if self.has_exit else None
		return entry, exit_

	def save(self):
		if self.save_callback(*self.values()):
			self.accept()


class SensorFaultDialog(QDialog):
	"""MAP-02 / LOGBOOK-01: the one text a fault / logbook action needs
	(fault note, resolution note or cancel reason), with what it is about
	shown read-only (subject_label: "Čidlo:" or "Záznam:").
	required: OK stays disabled until the text isn't blank (cancel reason)."""
	MAX_LENGTH = 500

	def __init__(self, title, floor_text, field_label, required=False, parent=None, subject_label=u"Čidlo:"):
		QDialog.__init__(self, parent)
		self.setWindowTitle(title)
		self.setMinimumWidth(420)
		layout = QFormLayout(self)
		layout.addRow(subject_label, QLabel(floor_text, self))
		self.textEdit = QLineEdit(self)
		self.textEdit.setMaxLength(self.MAX_LENGTH)
		self.textEdit.setPlaceholderText(u"povinné" if required else u"volitelné")
		layout.addRow(field_label, self.textEdit)
		self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		layout.addRow(self.buttonBox)
		if required:
			ok = self.buttonBox.button(QDialogButtonBox.Ok)
			ok.setEnabled(False)
			self.textEdit.textChanged.connect(lambda text: ok.setEnabled(bool(text.strip())))

	def text(self):
		return self.textEdit.text().strip()


class PersonHistoryDialog(QDialog):
	"""HISTORY-02: read-only Historie cvičence - one person's saved
	trainings (model.personHistoryModel), newest first. No editing,
	statistics, export or printing in this first version."""
	EMPTY_TEXT = u"Cvičenec zatím nemá uloženou historii."

	def __init__(self, history_model, person_name, parent=None):
		QDialog.__init__(self, parent)
		self.model = history_model
		self.setWindowTitle(u"Historie cvičence – %s" % person_name)
		self.resize(900, 420)
		layout = QVBoxLayout(self)
		self.tableView = QTableView(self)
		self.tableView.setModel(history_model)
		style_table(self.tableView)
		self.tableView.hideColumn(history_model.ID_COLUMN)  # idTraining
		self.tableView.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
		self.tableView.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
		self.tableView.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
		layout.addWidget(self.tableView)
		self.emptyLabel = QLabel(self.EMPTY_TEXT, self)
		self.emptyLabel.setVisible(history_model.rowCount() == 0)
		layout.addWidget(self.emptyLabel)
		self.buttonBox = QDialogButtonBox(QDialogButtonBox.Close, self)
		self.buttonBox.rejected.connect(self.reject)
		layout.addWidget(self.buttonBox)


class DeletedPersonsDialog(QDialog):
	"""DATA-02: Smazané osoby - read-only list of the soft-deleted persons
	(model.personModel(valid=0)) with the same literal search and
	chronological date sort as the main person list (the same
	personFilterProxyModel). Obnovit osobu calls restore_callback(idPerson,
	"Jméno Příjmení") -> bool; MainWindow confirms and restores. The proxy
	row is always mapped to the source row, so a filtered/sorted list
	restores exactly the person shown."""
	EMPTY_TEXT = u"Žádné smazané osoby."

	def __init__(self, deleted_model, restore_callback, parent=None):
		QDialog.__init__(self, parent)
		self.model = deleted_model
		self.restore_callback = restore_callback
		self.setWindowTitle(u"Smazané osoby")
		self.resize(800, 480)
		layout = QVBoxLayout(self)
		self.searchLineEdit = QLineEdit(self)
		self.searchLineEdit.setPlaceholderText(u"Hledat")
		self.searchLineEdit.setClearButtonEnabled(True)
		layout.addWidget(self.searchLineEdit)
		self.proxy = personFilterProxyModel(self)
		self.proxy.setSourceModel(deleted_model)
		self.tableView = QTableView(self)
		self.tableView.setModel(self.proxy)
		style_table(self.tableView)
		self.tableView.hideColumn(personModel.ID_COLUMN)
		self.tableView.hideColumn(personModel.VALID_COLUMN)
		self.tableView.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
		self.tableView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
		self.tableView.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
		self.tableView.setSortingEnabled(True)
		self.tableView.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
		layout.addWidget(self.tableView)
		self.emptyLabel = QLabel(self.EMPTY_TEXT, self)
		layout.addWidget(self.emptyLabel)
		self.buttonBox = QDialogButtonBox(QDialogButtonBox.Close, self)
		self.restoreButton = self.buttonBox.addButton(u"Obnovit osobu", QDialogButtonBox.ActionRole)
		self.buttonBox.button(QDialogButtonBox.Close).setText(u"Zavřít")
		self.buttonBox.rejected.connect(self.reject)
		self.restoreButton.clicked.connect(self.restore_selected)
		layout.addWidget(self.buttonBox)
		self.searchLineEdit.textChanged.connect(self.proxy.setSearchText)
		self.tableView.selectionModel().selectionChanged.connect(self.update_state)
		self.update_state()

	def selected_person(self):
		"""(idPerson, "Jméno Příjmení") of the selected row, or None."""
		rows = self.tableView.selectionModel().selectedRows()
		if not rows:
			return None
		record = self.model.record(self.proxy.mapToSource(rows[0]).row())
		return int(record.value("idPerson")), u"%s %s" % (record.value("name"), record.value("surname"))

	def update_state(self, *args):
		self.emptyLabel.setVisible(self.model.rowCount() == 0)
		self.restoreButton.setEnabled(self.selected_person() is not None)

	def restore_selected(self):
		person = self.selected_person()
		if person is not None:
			self.restore_callback(*person)
		self.update_state()  # a reload drops the selection without selectionChanged


class PersonForm(QDialog):
	def __init__(self, model, row = None):
		QDialog.__init__(self)
		self.row = row
		self.model = model
		self.setupUi(self)

	def setupUi(self, Dialog):
		Dialog.setObjectName(_fromUtf8("Dialog"))
		Dialog.resize(500, 360)
		self.verticalLayoutWidget = QWidget(Dialog)
		self.verticalLayoutWidget.setGeometry(QtCore.QRect(30, 30, 441, 291))
		self.verticalLayoutWidget.setObjectName(_fromUtf8("verticalLayoutWidget"))
		self.verticalLayout = QVBoxLayout(self.verticalLayoutWidget)
		self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
		self.formLayout = QFormLayout()
		self.formLayout.setObjectName(_fromUtf8("formLayout"))
		self.verticalLayout_5 = QVBoxLayout()
		self.verticalLayout_5.setSpacing(10)
		self.verticalLayout_5.setObjectName(_fromUtf8("verticalLayout_5"))
		self.nameLineEdit = QLineEdit(self.verticalLayoutWidget)
		self.nameLineEdit.setMinimumSize(QtCore.QSize(0, 25))
		self.nameLineEdit.setObjectName(_fromUtf8("nameLineEdit"))
		self.verticalLayout_5.addWidget(self.nameLineEdit)
		self.surnameLineEdit = QLineEdit(self.verticalLayoutWidget)
		self.surnameLineEdit.setMinimumSize(QtCore.QSize(0, 25))
		self.surnameLineEdit.setObjectName(_fromUtf8("surnameLineEdit"))
		self.verticalLayout_5.addWidget(self.surnameLineEdit)
		self.birthdayDateEdit = QDateEdit(self.verticalLayoutWidget)
		self.birthdayDateEdit.setMinimumSize(QtCore.QSize(0, 25))
		self.birthdayDateEdit.setCalendarPopup(True)
		self.birthdayDateEdit.setObjectName(_fromUtf8("birthdayDateEdit"))
		self.verticalLayout_5.addWidget(self.birthdayDateEdit)
		self.oecLineEdit = QLineEdit(self.verticalLayoutWidget)
		self.oecLineEdit.setMinimumSize(QtCore.QSize(0, 25))
		self.oecLineEdit.setObjectName(_fromUtf8("oecLineEdit"))
		self.verticalLayout_5.addWidget(self.oecLineEdit)
		self.unitLineEdit = QLineEdit(self.verticalLayoutWidget)
		self.unitLineEdit.setMinimumSize(QtCore.QSize(0, 25))
		self.unitLineEdit.setText(_fromUtf8(""))
		self.unitLineEdit.setObjectName(_fromUtf8("unitLineEdit"))
		self.verticalLayout_5.addWidget(self.unitLineEdit)
		self.formLayout.setLayout(0, QFormLayout.FieldRole, self.verticalLayout_5)
		self.verticalLayout_4 = QVBoxLayout()
		self.verticalLayout_4.setSpacing(10)
		self.verticalLayout_4.setObjectName(_fromUtf8("verticalLayout_4"))
		self.label = QLabel(self.verticalLayoutWidget)
		self.label.setMinimumSize(QtCore.QSize(0, 25))
		self.label.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
		self.label.setObjectName(_fromUtf8("label"))
		self.verticalLayout_4.addWidget(self.label)
		self.label_2 = QLabel(self.verticalLayoutWidget)
		self.label_2.setMinimumSize(QtCore.QSize(0, 25))
		self.label_2.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
		self.label_2.setObjectName(_fromUtf8("label_2"))
		self.verticalLayout_4.addWidget(self.label_2)
		self.label_3 = QLabel(self.verticalLayoutWidget)
		self.label_3.setMinimumSize(QtCore.QSize(0, 25))
		self.label_3.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
		self.label_3.setObjectName(_fromUtf8("label_3"))
		self.verticalLayout_4.addWidget(self.label_3)
		self.label_4 = QLabel(self.verticalLayoutWidget)
		self.label_4.setMinimumSize(QtCore.QSize(0, 25))
		self.label_4.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
		self.label_4.setObjectName(_fromUtf8("label_4"))
		self.verticalLayout_4.addWidget(self.label_4)
		self.label_5 = QLabel(self.verticalLayoutWidget)
		self.label_5.setMinimumSize(QtCore.QSize(0, 25))
		self.label_5.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
		self.label_5.setObjectName(_fromUtf8("label_5"))
		self.verticalLayout_4.addWidget(self.label_5)
		self.formLayout.setLayout(0, QFormLayout.LabelRole, self.verticalLayout_4)
		self.horizontalLayout = QHBoxLayout()
		self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
		self.formLayout.setLayout(1, QFormLayout.LabelRole, self.horizontalLayout)
		self.verticalLayout_2 = QVBoxLayout()
		self.verticalLayout_2.setObjectName(u"verticalLayout_2")
		self.addMemberCheckBox = QCheckBox(self.verticalLayoutWidget)
		self.addMemberCheckBox.setObjectName(u"addMemberCheckBox")
		self.addMemberCheckBox.setEnabled(True)
		self.addMemberCheckBox.setLayoutDirection(QtCore.Qt.RightToLeft)
		self.addMemberCheckBox.setChecked(True)
		self.verticalLayout_2.addWidget(self.addMemberCheckBox)
		self.formLayout.setLayout(1, QFormLayout.SpanningRole, self.verticalLayout_2)

		self.buttonBox = QDialogButtonBox(self.verticalLayoutWidget)
		self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
		self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Save)
		self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
		self.formLayout.setWidget(2, QFormLayout.FieldRole, self.buttonBox)
		self.verticalLayout.addLayout(self.formLayout)
		self.verticalLayoutWidget.raise_()

		self.birthdayDateEdit.setDisplayFormat("dd.MM.yyyy")
		self.oecLineEdit.setText("")
		self.unitLineEdit.setText("")
		self.addMember = False
		self.personId = None  # set by addPerson() only after a successful INSERT

		if self.row is None:
			# No model row is inserted while the dialog is open (PERSON-ADD-01):
			# a pending insertRow() left behind by Cancel made the next
			# submitAll() fail.
			self.buttonBox.accepted.connect(self.addPerson)
		else:
			self.addMemberCheckBox.setEnabled(False)
			name = self.model.record(self.row).value("name")
			surname = self.model.record(self.row).value("surname")
			birthday = self.model.record(self.row).value("birthday")
			oec = self.model.record(self.row).value("oec")
			unit = self.model.record(self.row).value("unit")
			self.label.setText(name)
			self.nameLineEdit.setText(name)
			self.surnameLineEdit.setText(surname)
			self.birthdayDateEdit.setDate(birthday)
			self.oecLineEdit.setText(oec)
			self.unitLineEdit.setText(unit)
			self.buttonBox.accepted.connect(self.editPerson)

		self.retranslateUi(Dialog)
		self.buttonBox.rejected.connect(self.reject)

	def retranslateUi(self, Dialog):
		Dialog.setWindowTitle(_translate("Dialog", "Osoba", None))
		self.label.setText(_translate("Dialog", "Jméno", None))
		self.label_2.setText(_translate("Dialog", "Příjmení", None))
		self.label_3.setText(_translate("Dialog", "Datum narození", None))
		self.label_4.setText(_translate("Dialog", "OEČ", None))
		self.label_5.setText(_translate("Dialog", "Organizace", None))
		self.addMemberCheckBox.setText(_translate("Dialog", u"Přidat do cvičení", None))

	def addPerson(self):
		"""Explicit prepared INSERT; the new id comes from this query's own
		lastInsertId() - never from a later SELECT LAST_INSERT_ID(), which
		after a failed insert returns an older, unrelated id (e.g. a member
		row's) and added the wrong person to the training (PERSON-ADD-01).
		On a DB error the dialog stays open and nothing is accepted."""
		query = QtSql.QSqlQuery(self.model.database())
		query.prepare("INSERT INTO person (name, surname, birthday, oec, unit) VALUES (?, ?, ?, ?, ?)")
		query.addBindValue(self.nameLineEdit.text())
		query.addBindValue(self.surnameLineEdit.text())
		query.addBindValue(self.birthdayDateEdit.date())
		query.addBindValue(self.oecLineEdit.text())
		query.addBindValue(self.unitLineEdit.text())
		if not query.exec_():
			error = query.lastError().text()
			logger.error(f"Adding person failed: {error}")
			QMessageBox.warning(self, 'Chyba', u'Osobu se nepodařilo uložit.\n\n' + error)
			return
		person_id = query.lastInsertId()
		if isinstance(person_id, int) and person_id > 0:
			self.personId = person_id
			self.addMember = self.addMemberCheckBox.isChecked()
		else:
			# Saved, but without a trustworthy id it must not be added to the training.
			logger.error(f"Person saved but lastInsertId() returned {person_id!r} - not adding to training")
		self.model.select()
		self.accept()

	def editPerson(self):
		"""Bound parameters, not string formatting: a name like O'Neil used
		to break the UPDATE silently, and SQL typed into a field ran as SQL
		(FORM-SQL-01). On a DB error the dialog stays open."""
		query = QtSql.QSqlQuery(self.model.database())
		query.prepare("UPDATE person SET name=?, surname=?, birthday=?, oec=?, unit=? WHERE idPerson=?")
		query.addBindValue(self.nameLineEdit.text())
		query.addBindValue(self.surnameLineEdit.text())
		query.addBindValue(self.birthdayDateEdit.date())
		query.addBindValue(self.oecLineEdit.text())
		query.addBindValue(self.unitLineEdit.text())
		query.addBindValue(int(self.model.record(self.row).value("idPerson")))
		if not exec_or_warn(self, query, u"Změny osoby se nepodařilo uložit."):
			return
		self.model.select()
		self.accept()

class MemberForm(QDialog):
	# WORKFLOW-02: stav_code (memberModel, 0 PŘIPRAVEN / 1 UVNITŘ / 2
	# DOKONČENO) -> which fields the operator usually fills in that state.
	# Only emphasis and the initial focus - every field stays editable.
	READY, INSIDE, DONE = 0, 1, 2
	# BOTTLE-01: bottle volumes (l) offered, ascending. A new member (DB
	# default volume 0.0) gets DEFAULT_VOLUME pre-selected; a stored volume
	# is always shown as stored (one outside the list is added to it).
	# The volume never sets the start pressure - that is the measured value
	# from the gauge, and a volume alone doesn't determine the working
	# pressure (6.0 and 7.0 l bottles exist for 200 and 300 bar).
	VOLUMES = ("4.7", "5.0", "6.0", "6.8", "6.9", "7.0", "8.0", "9.0")
	DEFAULT_VOLUME = "7.0"
	# Information only, not stored and never used to fill in a pressure.
	BOTTLE_INFO = {
		"4.7": u"4.7 l – 300 bar",
		"5.0": u"5.0 l – varianty 200 i 300 bar",
		"6.0": u"6.0 l – varianty 200 i 300 bar, ocel i kompozit",
		"6.8": u"6.8 l – 300 bar, kompozitní varianty",
		"6.9": u"6.9 l – 300 bar, kompozitní varianty",
		"7.0": u"7.0 l – varianty 200 i 300 bar",
		"8.0": u"8.0 l – 300 bar",
		"9.0": u"9.0 l – 300 bar, kompozitní varianty",
	}
	BOTTLE_NOTE = u"Pracovní tlak vždy ověřte podle označení konkrétní láhve."

	def __init__(self, model, row):
		QDialog.__init__(self)
		#super(PersonForm, self).__init__(parent)
		self.model = model
		self.row = row
		self.setupUi(self)

	def setupUi(self, MemberForm):
		MemberForm.setObjectName(_fromUtf8("Dialog"))
		MemberForm.resize(404, 371)
		self.buttonBox = QDialogButtonBox(MemberForm)
		self.buttonBox.setGeometry(QtCore.QRect(40, 310, 341, 32))
		self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
		self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
		self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
		self.label = QLabel(MemberForm)
		self.label.setGeometry(QtCore.QRect(20, 20, 350, 56))  # two lines of name — stav (y 20-76, fields from 80)
		font = QtGui.QFont()
		font.setPointSize(14)
		font.setBold(True)
		font.setWeight(75)
		self.label.setFont(font)
		self.label.setText(_fromUtf8(""))
		self.label.setObjectName(_fromUtf8("label"))
		self.label.setAlignment(QtCore.Qt.AlignCenter)
		self.label_2 = QLabel(MemberForm)
		self.label_2.setGeometry(QtCore.QRect(20, 80, 200, 30))
		self.label_2.setObjectName(_fromUtf8("label_2"))
		# BOTTLE-01: bottle info under the volume (y 112-154), fields below.
		self.bottleInfoLabel = QLabel(MemberForm)
		self.bottleInfoLabel.setGeometry(QtCore.QRect(20, 112, 364, 42))
		self.bottleInfoLabel.setObjectName(_fromUtf8("bottleInfoLabel"))
		self.bottleInfoLabel.setWordWrap(True)
		self.bottleInfoLabel.setStyleSheet("color: %s; font-size: 9pt;" % TEXT_MUTED)
		self.bottleInfoLabel.setToolTip(self.BOTTLE_NOTE)
		self.label_3 = QLabel(MemberForm)
		self.label_3.setGeometry(QtCore.QRect(20, 160, 200, 30))
		self.label_3.setObjectName(_fromUtf8("label_3"))
		self.label_4 = QLabel(MemberForm)
		self.label_4.setGeometry(QtCore.QRect(20, 210, 200, 30))
		self.label_4.setObjectName(_fromUtf8("label_4"))
		self.validator = QtGui.QIntValidator(0,999,self)
		self.comboBox_volume = QComboBox(MemberForm)
		self.comboBox_volume.setGeometry(QtCore.QRect(230, 80, 140, 30))
		self.comboBox_volume.setObjectName(_fromUtf8("comboBox_volume"))
		self.comboBox_volume.addItems(self.VOLUMES)
		self.comboBox_volume.currentIndexChanged.connect(self._update_bottle_info)
		self.lineEdit_3 = QLineEdit(MemberForm)
		self.lineEdit_3.setValidator(self.validator)
		self.lineEdit_3.setGeometry(QtCore.QRect(230, 160, 140, 30))
		self.lineEdit_3.setObjectName(_fromUtf8("lineEdit_3"))
		self.lineEdit_4 = QLineEdit(MemberForm)
		self.lineEdit_4.setValidator(self.validator)
		self.lineEdit_4.setGeometry(QtCore.QRect(230, 210, 140, 30))
		self.lineEdit_4.setObjectName(_fromUtf8("lineEdit_4"))
		# PRESS-END-NULL: an empty end pressure = "not entered yet" (SQL
		# NULL), never silently 0 - a real 0 bar is typed in as 0.
		self.lineEdit_4.setPlaceholderText(PRESS_END_NOT_ENTERED)

		if self.row < 0:self.row=0
		name = self.model.record(self.row).value("name")
		volume = self.model.record(self.row).value("volume")
		press_start = self.model.record(self.row).value("press_start")
		press_end = self.model.press_end(self.row)  # None = not entered (record() would turn NULL into 0)
		stav = self.model.record(self.row).value("stav")
		self.stav_code = self.model.record(self.row).value("stav_code")
		self.label.setWordWrap(True)  # "Jméno Příjmení — DOKONČENO" may need two lines
		self.label.setText(u"%s — %s" % (name, stav) if stav else name)
		self.volume_preselected = self._select_volume(volume)
		self._update_bottle_info()
		self.lineEdit_3.setText(str(press_start))
		self.lineEdit_4.setText("" if press_end is None else str(press_end))

		self.retranslateUi(MemberForm)
		self.buttonBox.rejected.connect(self.reject)
		self.buttonBox.accepted.connect(self.updateMember)
		self._apply_state_hints()

	def _apply_state_hints(self):
		"""WORKFLOW-02: bold labels for the fields usually filled in the
		member's state, and the initial focus moved there instead of the OK
		button. PŘIPRAVEN: volume + start pressure, DOKONČENO: end pressure
		(selected, for overtyping), UVNITŘ: no emphasis. Nothing is
		disabled - a wrong value stays correctable. Enter stays the standard
		QDialog confirmation (OK is the default button): it saves through the
		same validation as clicking OK, e.g. DOKONČENO -> type 40 -> Enter."""
		emphasized = {
			self.READY: (self.label_2, self.label_3),
			self.DONE: (self.label_4,),
		}.get(self.stav_code, ())
		for label in (self.label_2, self.label_3, self.label_4):
			font = label.font()
			font.setBold(label in emphasized)
			label.setFont(font)
		if self.stav_code == self.DONE:
			focus = self.lineEdit_4
			focus.selectAll()
		elif self.stav_code == self.READY and (self.volume_preselected or self.comboBox_volume.currentIndex() < 0):
			focus = self.comboBox_volume  # a new member: confirm or change the pre-selected 7.0
		else:
			focus = self.lineEdit_3
		self.initial_focus = focus
		focus.setFocus()  # before show(): becomes the dialog's focus widget

	def _select_volume(self, volume):
		"""BOTTLE-01: select the stored volume; returns True when
		DEFAULT_VOLUME was pre-selected for a new member (stored 0.0). A
		stored volume outside VOLUMES (older data) is added and selected -
		never replaced by the default."""
		try:
			value = float(volume or 0)
		except (TypeError, ValueError):
			value = 0.0
		if value <= 0:
			self.comboBox_volume.setCurrentIndex(self.comboBox_volume.findText(self.DEFAULT_VOLUME))
			return True
		text = "%.1f" % value
		if self.comboBox_volume.findText(text) < 0:
			self.comboBox_volume.addItem(text)
		self.comboBox_volume.setCurrentIndex(self.comboBox_volume.findText(text))
		return False

	def _update_bottle_info(self):
		"""BOTTLE-01: information for the selected volume + the general
		note. Display only - it never changes the start pressure."""
		info = self.BOTTLE_INFO.get(self.comboBox_volume.currentText())
		self.bottleInfoLabel.setText(u"%s\n%s" % (info, self.BOTTLE_NOTE) if info else self.BOTTLE_NOTE)

	def retranslateUi(self, Dialog):
		Dialog.setWindowTitle(_translate("Dialog", "Hodnoty", None))
		self.label_2.setText(_translate("Dialog", "Objem láhve (L)", None))
		self.label_3.setText(_translate("Dialog", "Tlak na začátku (Bar)", None))
		self.label_4.setText(_translate("Dialog", "Tlak na konci (Bar)", None))

	def updateMember(self):
		"""Validate first, then a bound UPDATE (FORM-SQL-01, FORM-01): an
		empty pressure or no volume selected (a new member's 0.0 isn't in
		the list) used to produce invalid SQL that failed silently while
		the dialog closed as saved. Invalid input or a DB error keeps the
		dialog open and the row unchanged. 0 bar is a valid value.

		PRESS-END-NULL: an empty end pressure is saved as SQL NULL ("not
		entered yet") - so editing only the volume or start pressure of a
		member whose end pressure isn't entered keeps it NULL, never 0."""
		press_start = pressure_value(self.lineEdit_3.text())
		press_end_text = self.lineEdit_4.text().strip()
		press_end = pressure_value(press_end_text)
		if self.comboBox_volume.currentIndex() < 0:
			QMessageBox.warning(self, u'Neplatné hodnoty', u'Vyberte objem láhve.')
			return
		if press_start is None:
			QMessageBox.warning(self, u'Neplatné hodnoty', u'Tlak na začátku musí být celé číslo 0–999 bar.')
			return
		if press_end is None and press_end_text:
			QMessageBox.warning(self, u'Neplatné hodnoty',
			                    u'Tlak na konci musí být celé číslo 0–999 bar, nebo prázdný (nezadáno).')
			return
		query = QtSql.QSqlQuery()  # memberModel is a QSqlQueryModel on the default connection
		query.prepare("UPDATE member SET volume=?, press_start=?, press_end=? WHERE idMember=?")
		query.addBindValue(float(self.comboBox_volume.currentText()))
		query.addBindValue(press_start)
		query.addBindValue(press_end)  # None -> SQL NULL
		query.addBindValue(int(self.model.record(self.row).value("idMember")))
		if not exec_or_warn(self, query, u"Hodnoty se nepodařilo uložit."):
			return
		self.model.view()
		self.accept()
