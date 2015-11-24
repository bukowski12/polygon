# -*- coding: utf-8 -*-

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class PersonForm(QtGui.QDialog):
	def __init__(self, model):
		QtGui.QDialog.__init__(self)
		#super(PersonForm, self).__init__(parent)
		self.model = model
		self.setupUi(self)

	def setupUi(self, PersonForm):
		PersonForm.setObjectName(_fromUtf8("Dialog"))
		PersonForm.resize(404, 341)
		self.buttonBox = QtGui.QDialogButtonBox(PersonForm)
		self.buttonBox.setGeometry(QtCore.QRect(40, 280, 341, 32))
		self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
		self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
		self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
		self.label = QtGui.QLabel(PersonForm)
		self.label.setGeometry(QtCore.QRect(20, 30, 53, 15))
		self.label.setObjectName(_fromUtf8("label"))
		self.label_2 = QtGui.QLabel(PersonForm)
		self.label_2.setGeometry(QtCore.QRect(20, 80, 53, 15))
		self.label_2.setObjectName(_fromUtf8("label_2"))
		self.label_3 = QtGui.QLabel(PersonForm)
		self.label_3.setGeometry(QtCore.QRect(20, 130, 53, 15))
		self.label_3.setObjectName(_fromUtf8("label_3"))
		self.label_4 = QtGui.QLabel(PersonForm)
		self.label_4.setGeometry(QtCore.QRect(20, 180, 91, 16))
		self.label_4.setObjectName(_fromUtf8("label_4"))
		self.lineEdit = QtGui.QLineEdit(PersonForm)
		self.lineEdit.setGeometry(QtCore.QRect(100, 30, 113, 23))
		self.lineEdit.setObjectName(_fromUtf8("lineEdit"))
		self.lineEdit_2 = QtGui.QLineEdit(PersonForm)
		self.lineEdit_2.setGeometry(QtCore.QRect(100, 80, 113, 23))
		self.lineEdit_2.setObjectName(_fromUtf8("lineEdit_2"))
		self.lineEdit_3 = QtGui.QLineEdit(PersonForm)
		self.lineEdit_3.setGeometry(QtCore.QRect(100, 130, 113, 23))
		self.lineEdit_3.setObjectName(_fromUtf8("lineEdit_3"))
		self.lineEdit_4 = QtGui.QLineEdit(PersonForm)
		self.lineEdit_4.setGeometry(QtCore.QRect(120, 180, 113, 23))
		self.lineEdit_4.setObjectName(_fromUtf8("lineEdit_4"))
		self.label_5 = QtGui.QLabel(PersonForm)
		self.label_5.setGeometry(QtCore.QRect(20, 230, 71, 16))
		self.label_5.setObjectName(_fromUtf8("label_5"))
		self.lineEdit_5 = QtGui.QLineEdit(PersonForm)
		self.lineEdit_5.setGeometry(QtCore.QRect(120, 230, 113, 23))
		self.lineEdit_5.setObjectName(_fromUtf8("lineEdit_5"))

		self.mapper = QtGui.QDataWidgetMapper(self)
		self.mapper.setSubmitPolicy(QtGui.QDataWidgetMapper.AutoSubmit)
		self.mapper.setModel(self.model)
		self.mapper.addMapping(self.lineEdit,1)
		self.mapper.addMapping(self.lineEdit_2,2)
		self.mapper.addMapping(self.lineEdit_3,3)
		self.mapper.addMapping(self.lineEdit_4,4)
		self.mapper.addMapping(self.lineEdit_5,5)

		row = self.model.rowCount()
		self.mapper.submit()
		self.model.insertRow(row)
		self.mapper.setCurrentIndex(row)

		self.retranslateUi(PersonForm)
		self.buttonBox.rejected.connect(self.reject)
		self.buttonBox.accepted.connect(self.addPerson)

	def retranslateUi(self, Dialog):
		Dialog.setWindowTitle(_translate("Dialog", "Dialog", None))
		self.label.setText(_translate("Dialog", "Jmeno", None))
		self.label_2.setText(_translate("Dialog", "Prijmeni", None))
		self.label_3.setText(_translate("Dialog", "Datum narozeni", None))
		self.label_4.setText(_translate("Dialog", "OEC", None))
		self.label_5.setText(_translate("Dialog", "Organizace", None))

	def addPerson(self):
		row = self.mapper.currentIndex()
		self.mapper.submit()
		self.mapper.setCurrentIndex(row)
		self.model.submitAll()
		self.accept()


class MemberForm(QtGui.QDialog):
	def __init__(self, model, row):
		QtGui.QDialog.__init__(self)
		#super(PersonForm, self).__init__(parent)
		self.model = model
		self.row = row
		self.setupUi(self)

	def setupUi(self, MemberForm):
		MemberForm.setObjectName(_fromUtf8("Dialog"))
		MemberForm.resize(404, 341)
		self.buttonBox = QtGui.QDialogButtonBox(MemberForm)
		self.buttonBox.setGeometry(QtCore.QRect(40, 280, 341, 32))
		self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
		self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
		self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
		self.label = QtGui.QLabel(MemberForm)
		self.label.setGeometry(QtCore.QRect(70, 20, 231, 41))
		font = QtGui.QFont()
		font.setPointSize(14)
		font.setBold(True)
		font.setWeight(75)
		self.label.setFont(font)
		self.label.setText(_fromUtf8(""))
		self.label.setObjectName(_fromUtf8("label"))
		self.label_2 = QtGui.QLabel(MemberForm)
		self.label_2.setGeometry(QtCore.QRect(20, 80, 71, 16))
		self.label_2.setObjectName(_fromUtf8("label_2"))
		self.label_3 = QtGui.QLabel(MemberForm)
		self.label_3.setGeometry(QtCore.QRect(20, 130, 91, 16))
		self.label_3.setObjectName(_fromUtf8("label_3"))
		self.label_4 = QtGui.QLabel(MemberForm)
		self.label_4.setGeometry(QtCore.QRect(20, 180, 71, 16))
		self.label_4.setObjectName(_fromUtf8("label_4"))
		self.lineEdit_2 = QtGui.QLineEdit(MemberForm)
		self.validator = QtGui.QIntValidator(0,999,self)
		self.lineEdit_2.setValidator(self.validator)
		self.lineEdit_2.setGeometry(QtCore.QRect(120, 80, 113, 23))
		self.lineEdit_2.setObjectName(_fromUtf8("lineEdit_2"))
		self.lineEdit_3 = QtGui.QLineEdit(MemberForm)
		self.lineEdit_3.setValidator(self.validator)
		self.lineEdit_3.setGeometry(QtCore.QRect(120, 130, 113, 23))
		self.lineEdit_3.setObjectName(_fromUtf8("lineEdit_3"))
		self.lineEdit_4 = QtGui.QLineEdit(MemberForm)
		self.lineEdit_4.setValidator(self.validator)
		self.lineEdit_4.setGeometry(QtCore.QRect(120, 180, 113, 23))
		self.lineEdit_4.setObjectName(_fromUtf8("lineEdit_4"))

		
		if self.row < 0:self.row=0
		name = self.model.record(self.row).value("name").toString()
		volume = self.model.record(self.row).value("volume").toString()
		press_start = self.model.record(self.row).value("press_start").toString()
		press_end = self.model.record(self.row).value("press_end").toString()
		self.label.setText(name)
		self.lineEdit_2.setText(volume)
		self.lineEdit_3.setText(press_start)
		self.lineEdit_4.setText(press_end)

		self.retranslateUi(MemberForm)
		self.buttonBox.rejected.connect(self.reject)
		self.buttonBox.accepted.connect(self.updateMember)
        	

	def retranslateUi(self, Dialog):
		Dialog.setWindowTitle(_translate("Dialog", "Dialog", None))
		self.label_2.setText(_translate("Dialog", "Objem láhve", None))
		self.label_3.setText(_translate("Dialog", "Tlak na začátku", None))
		self.label_4.setText(_translate("Dialog", "Tlak na konci", None))

	def updateMember(self):
		query = self.model.query()
		idmember = name = self.model.record(self.row).value("idMember").toString()
		volume = self.lineEdit_2.text()
		press_start =  self.lineEdit_3.text()
		press_end =  self.lineEdit_4.text()
		query.exec_("UPDATE member SET volume=%s, press_start=%s, press_end=%s WHERE idMember=%s" % (volume,press_start,press_end,idmember))
		self.model.view()
		self.accept()