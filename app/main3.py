# -*- coding: utf-8 -*-
import sys

from quido import Device as kvido
from PyQt4 import QtCore, QtGui, QtSql
from ui_mainwindow import Ui_MainWindow, PersonForm, MemberForm


class MainWindow(QtGui.QMainWindow, Ui_MainWindow):
	def __init__(self):
		super(MainWindow, self).__init__()
		
		self.setupUi(self)
		
	
		self.assignWidgets()
		self.show()

	def assignWidgets(self):
		
		self.fan12Button.clicked.connect(self.click)

		
	def click(self):
		self.a = kvido("192.168.16.232",10001)
		i = self.a.get_output_state(2)
		print i
		self.a.disconnect()


if __name__ == '__main__':
	
#	inClient = ModbusClient(din[address])
#	outClient = ModbusClient(dout[address])
#	rr = client.read_coils(1,1)
#	print rr
#	inClient.close()
#	outClient.close()
	a = kvido("192.168.16.231",10001)
	#n = a.query(0x31,"")
	#print n
	#i = a.get_inputs_state()
	#o = a.get_outputs_state()
	i = a.get_input_state(70)
	#i = a.get_output_state(1)
	print i
	#a.invertState(1)
	#i = a.get_output_state(1)
	#print i
	#i = a.get_output_state(1)
	#print i
	#b = Test()
	#for x in range(0, 1000):
	#	if a.get_output_state(1) == True:
	#		print "ano"
	#a.set_output_off(2)

	#app = QtGui.QApplication(sys.argv)
	#mainWin = MainWindow()
	#ret = app.exec_()
	#sys.exit( ret )
