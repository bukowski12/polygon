from PyQt5 import QtCore, QtGui, QtWidgets

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

class Ui_Login_Dialog(object):
	def setupUi(self, loginDialog):
		loginDialog.setObjectName(_fromUtf8("loginDialog"))
		loginDialog.resize(487, 267)
		self.groupBox = QtWidgets.QGroupBox(loginDialog)
		self.groupBox.setGeometry(QtCore.QRect(19, 29, 451, 221))
		font = QtGui.QFont()
		font.setPointSize(10)
		font.setBold(False)
		font.setWeight(50)
		self.groupBox.setFont(font)
		self.groupBox.setObjectName(_fromUtf8("groupBox"))
		self.formLayoutWidget = QtWidgets.QWidget(self.groupBox)
		self.formLayoutWidget.setGeometry(QtCore.QRect(20, 30, 421, 171))
		self.formLayoutWidget.setObjectName(_fromUtf8("formLayoutWidget"))
		self.formLayout = QtWidgets.QFormLayout(self.formLayoutWidget)
		self.formLayout.setLabelAlignment(QtCore.Qt.AlignCenter)
		self.formLayout.setContentsMargins(23, 10, 0, 0)
		self.formLayout.setHorizontalSpacing(20)
		self.formLayout.setVerticalSpacing(14)
		self.formLayout.setObjectName(_fromUtf8("formLayout"))
		self.label = QtWidgets.QLabel(self.formLayoutWidget)
		self.label.setObjectName(_fromUtf8("label"))
		self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label)
		self.userLineEdit = QtWidgets.QLineEdit(self.formLayoutWidget)
		self.userLineEdit.setObjectName(_fromUtf8("userLineEdit"))
		self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.userLineEdit)
		self.label_2 = QtWidgets.QLabel(self.formLayoutWidget)
		self.label_2.setObjectName(_fromUtf8("label_2"))
		self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_2)
		self.passwordLineEdit = QtWidgets.QLineEdit(self.formLayoutWidget)
		self.passwordLineEdit.setInputMask(_fromUtf8(""))
		self.passwordLineEdit.setText(_fromUtf8(""))
		self.passwordLineEdit.setEchoMode(QtWidgets.QLineEdit.Password)
		self.passwordLineEdit.setObjectName(_fromUtf8("passwordLineEdit"))
		self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.passwordLineEdit)
		self.buttonBox = QtWidgets.QDialogButtonBox(self.formLayoutWidget)
		self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
		self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
		self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
		self.formLayout.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.buttonBox)

		self.retranslateUi(loginDialog)
		QtCore.QMetaObject.connectSlotsByName(loginDialog)

	def retranslateUi(self, loginDialog):
		loginDialog.setWindowTitle(_translate("loginDialog", "Přihlášení", None))
		self.groupBox.setTitle(_translate("loginDialog", "Přihlášení do aplikace Polygon", None))
		self.label.setText(_translate("loginDialog", "OEČ", None))
		self.label_2.setText(_translate("loginDialog", "Heslo", None))
