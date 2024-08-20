import os
from PyQt5 import QtCore, QtGui, QtPrintSupport
from PyQt5.QtWebKitWidgets import QWebView

class createProtocol(object):
	def __init__(self, query, trainingid, user):
		self.query = query
		self.trainingid = trainingid
		self.user = user
		self.web = QWebView()
		self.query.exec_("SELECT time_start, time_cage, time_end "
						"FROM training WHERE idTraining=%d" % trainingid)
		self.query.first()
		time_start = QtCore.QDateTime(self.query.value(0))
		time_cage = QtCore.QDateTime.fromString(self.query.value(1), "hh:mm:ss").toString("mm:ss")
		time_end = QtCore.QDateTime.fromString(self.query.value(2), "hh:mm:ss").toString("mm:ss")
		trainingDate = time_start.toString("dd.MM.yyyy")
		self.today = QtCore.QDateTime.currentDateTime().toString("dd.MM.yyyy")
		self.query.exec_("SELECT training.time_start, training.time_cage, training.time_end, member.volume, member.press_start, member.press_end, person.unit, person.birthday, person.oec, CONCAT(person.name,' ', person.surname) AS name "
							"FROM member LEFT JOIN person ON member.person_id = person.idPerson "
							"LEFT JOIN training ON member.training_id = training.idTraining "
							"WHERE training_id=%d" % self.trainingid)
		groupData = []
		while self.query.next():
			volume = int(self.query.value(3))
			press_start = int(self.query.value(4))
			press_end = int(self.query.value(5))
			consumption =  f"{(((press_start-press_end)/10)*volume):02.1f}"
			volume = str(volume)
			press_start = str(press_start)
			press_end = str(press_end)
			unit = str(self.query.value(6))
			birthday = QtCore.QDateTime.fromString(self.query.value(7).toString(), "yyyy-MM-dd").toString("dd.MM.yyyy")
			oec = str(self.query.value(8))
			name = str(self.query.value(9))
			groupData.append({'volume':volume, 'press_start':press_start, 'press_end':press_end, 'unit':unit, 'birthday':birthday, 'oec':oec, 'name':name, 'consumption':consumption})
		baseUrl = QtCore.QUrl.fromLocalFile(os.path.join(os.path.abspath(os.path.dirname(__file__)), "../"))
		self.loop = QtCore.QEventLoop()
		self.web.loadFinished.connect(self.load_finished)
		self.web.setHtml(self.getContent(trainingDate, time_cage, time_end, groupData), baseUrl)
		self.loaded_ok = None
		self.loop.exec_()

	def load_finished(self, ok):
		self.loaded_ok = ok
		self.loop.quit()
		self.start_preview()

	def start_preview(self):
		printer = QtPrintSupport.QPrinter()
		printer.setPaperSize(QtPrintSupport.QPrinter.A4)
		printer.setPageMargins(40, 40, 40, 40, QtPrintSupport.QPrinter.DevicePixel)
		printer.setFullPage(True)
		printer.setColorMode(QtPrintSupport.QPrinter.Color)
		self.preview = QtPrintSupport.QPrintPreviewDialog(printer)
		self.preview.paintRequested.connect(self.web.print_)
		self.preview.exec_()

	def getContent(self, date, timeCage, timeEnd, groupData):
		content = u"<style media='all' type='text/css'>\
		body {\
		    margin: 0;\
		    color: #000;\
		    font-family: Arial,serif;\
	        font-size: 18px;\
		    background: #fff;\
		    line-height: 1;\
		}\
		h1, h2 {\
		    margin-top: 20px;\
    		margin-bottom: 10px;\
		}\
		h1 {\
			font-size: 1.8em;\
			text-transform: uppercase;\
			margin-top: 40px;\
   			margin-bottom: 40px;\
		}\
		p {\
			margin: 0 0 10px;\
		}\
		address {\
			font-style: normal;\
			font-size: 1em;\
		}\
		ul li {list-style: none;}\
		table {\
			width: 100%;\
			font-size: 1.4em;\
		}\
		th {\
			font-weight: normal;\
			text-align: left;\
		}\
		#company {\
			text-transform: uppercase;\
			margin-top: 60px;\
		}\
		.company-name, .area {\
			font-size: 1.8em;\
			font-weight: bold;\
		}\
		.company-name {\
			padding-top: 5px;\
		}\
		.container {\
			position: relative;\
			width: 90%;\
			margin: 0 auto;\
		}\
		.text-center {\
			text-align: center;\
		}\
		.text-small {\
			font-size: 0.8em;\
		}\
		.col-2 {\
			width: 50%;\
		}\
		.col-3 {\
			width: 33.33333333%;\
		}\
		.training {\
			margin-bottom: 40px;\
		}\
		.label {\
			font-size: 0.6em;\
			text-transform: uppercase;\
		}\
		.person {\
			border: 1px solid #000;\
			margin-bottom: 5px;\
			padding: 5px;\
		}	\
		.p-name {\
			font-size: 1.4em;\
			padding: 10px 0;\
		}\
		#footer {\
			position: absolute;\
			width: 90%;\
			left: 50%;\
			bottom: 20px;\
		}\
		#footer ul {\
			width: 250px;\
			line-height: 1.5;\
			float: right;\
		}\
		.line-dotted {\
			border-top: 1px dotted #000;\
			font-weight: bold;\
			text-transform: uppercase;\
			padding-top: 5px;\
		}\
		.abs-center {\
			position: relative;\
			left: -50%;\
		}\
		</style>"
		content += u"<html>\
<head>\
	<meta content='cs' http-equiv='Content-Language'>\
    <meta http-equiv='content-type' content='text/html; charset=utf-8'>\
	<title>Zpráva o absolvování výcvikové komory</title><body>\
</head>\
<body>\
	<div style='text-transform: uppercase;' id='company'>\
		<div class='container'>\
			<table>\
				<tr>\
					<td width='183'><img src='files/znak-hzs.png' width='143' height='200' alt='Znak HZS'></td>\
					<td>\
						<p class='company-name'>Hasičský záchranný sbor</p>\
						<p class='area'>Ústeckého kraje</p>\
						<address font-style: normal; font-size: 1em;>Horova 1340, 400 01 Ústí nad Labem</address>\
					</td>\
				</tr>\
			</table>\
		</div>\
	</div>\
	<div id='main-content'>\
		<div class='container'>\
			<h1>Zpráva o absolvování výcvikové komory</h1>\
			<table class='training'>\
				<thead class='label'>\
					<tr>\
						<th width='33.33333333%' class='col-3'>Datum výcviku</th>\
						<th width='33.33333333%' class='col-3'>Vstup do klece</th>\
						<th width='33.33333333%' class='col-3'>Konec výcviku</th>	\
					</tr>\
				</thead>\
				<tbody>\
					<tr>\
						<td class='col-3'>{0}</td>\
						<td class='col-3'>{1}</td>\
						<td class='col-3'>{2}</td>\
					</tr>\
				</tbody>\
			</table>".format(date, timeCage, timeEnd)
		for elements in groupData:
			content += "<table class='person'>\
				<thead class='p-name'>\
					<tr>\
						<th colspan='3'>%s</th>\
					</tr>\
				</thead>\
				<tbody>\
					<tr class='label'>\
						<th class='col-3'>Datum narození</th>\
						<th class='col-3'>OEČ</th>\
						<th class='col-3'>Organizace</th>	\
					</tr>\
					<tr>\
						<td class='col-3'>%s</td>\
						<td class='col-3'>%s</td>\
						<td class='col-3'>%s</td>	\
					</tr>\
					<tr>\
						<th colspan='3'>&nbsp;</th>\
					</tr>\
					<tr class='label'>\
						<td class='col-3'>Tlak před/po</td>\
						<td class='col-3'>Spotřeba</td>\
						<td class='col-3'>Objem lahve</td>	\
					</tr>\
					<tr>\
						<td class='col-3'>%s/%s Bar</td>\
						<td class='col-3'>%s l</td>\
						<td class='col-3'>%s l</td>	\
					</tr>\
				</tbody>\
			</table>" % (elements['name'], elements['birthday'], elements['oec'], elements['unit'], elements['press_start'], elements['press_end'], elements['consumption'], elements['volume'])
		#for x in range(1, 30 - 7*len(groupData)):
		#	content += "<br>"
		content += "</div>\
	</div>\
	<div id='footer'>\
		<div class='container abs-center'>\
			<table>\
				<tr>\
					<td class='col-2'>Teplice, {0}</td>\
					<td class='col-2 text-center'>\
						<ul>\
							<li class='line-dotted text-small'>{1}</li>\
							<li class='text-small'>Školitel výcvikové komory</li>\
						</ul>\
					</td>\
				</tr>\
			</table>\
		</div>\
	</div>\
</body>\
</html>".format(self.today, self.user)
		return(content)
