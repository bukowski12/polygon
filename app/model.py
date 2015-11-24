# -*- coding: utf-8 -*-

from PyQt4 import QtCore, QtGui, QtSql

class personModel(QtSql.QSqlTableModel):
	def __init__(self):
		super(personModel, self).__init__()
		self.setEditStrategy(QtSql.QSqlTableModel.OnFieldChange)
		self.setTable("person")
		self.setFilter("valid=1")
		self.select()
		self.setHeaderData(1, QtCore.Qt.Horizontal, u"Jméno")
		self.setHeaderData(2, QtCore.Qt.Horizontal, u"Příjmení")
		self.setHeaderData(3, QtCore.Qt.Horizontal, u"Datum narození")
		self.setHeaderData(4, QtCore.Qt.Horizontal, u"OEČ")
		self.setHeaderData(5, QtCore.Qt.Horizontal, u"Jednotka")


class memberModel(QtSql.QSqlQueryModel):
	def __init__(self, idTraining = None):
		super(memberModel, self).__init__()
		self.idtraining = idTraining
		self.view()

	def view(self):
		if self.idtraining is not None:
			self.setQuery("SELECT idMember, CONCAT(person.name,' ', person.surname) AS name , volume, member.press_start, member.press_end FROM member "
							"LEFT JOIN person ON member.person_id = person.idPerson "
							"LEFT JOIN training ON member.training_id = training.idTraining "
							"WHERE member.training_id=%d AND training.status<=2" % self.idtraining)
			self.setHeaderData(1, QtCore.Qt.Horizontal, u"Jméno")
			self.setHeaderData(2, QtCore.Qt.Horizontal, u"Objem lahve")
			self.setHeaderData(3, QtCore.Qt.Horizontal, u"Tlak na začátku")
			self.setHeaderData(4, QtCore.Qt.Horizontal, u"Tlak na konci")
			print self.lastError().text()

	def delete(self, idMember):
		query.exec_("DELETE FROM member WHERE idMember=%d" % (idMember))
		self.membermodel.select()

	def refresh(self, idTraining):
		self.idtraining = idTraining
		self.view()


class trainingModel(QtSql.QSqlTableModel):
	def __init__(self, finished = False):
		super(trainingModel, self).__init__()
		self.setTable("training")
		if finished == True:
			self.setFilter("status=10")
			self.setHeaderData(1, QtCore.Qt.Horizontal, u"Datum")
			self.setHeaderData(2, QtCore.Qt.Horizontal, u"Čas vstupu do klece")
			self.setHeaderData(3, QtCore.Qt.Horizontal, u"Čas ukončení")
			#self.setHeaderData(4, QtCore.Qt.Horizontal, u"Tlak na konci")
		else:
			self.setEditStrategy(QtSql.QSqlTableModel.OnManualSubmit)
			self.setFilter("status=0 OR status=1")
		self.select()