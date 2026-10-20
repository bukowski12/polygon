from PyQt5 import QtCore, QtGui, QtSql

import protocol_data


def query_failed(model):
	"""True if model's last load didn't succeed. lastError() alone isn't
	enough: with the connection closed/lost, Qt refuses to exec the query
	without setting any error - the query just stays inactive."""
	return model.lastError().isValid() or not model.query().isActive()


# PRESS-END-NULL: a not-yet-entered end pressure (member.press_end IS
# NULL) shows the same in the tables as in the printed protocol.
NOT_ENTERED_TEXT = protocol_data.NOT_ENTERED_TEXT


def nullable_int(model, row, column):
	"""int value of a nullable integer query column, or None for SQL NULL.

	QMYSQL hands a NULL SMALLINT to Python as 0 (value(), data() and
	record().value() alike), and for a model with an overridden data()
	even record(row).isNull() is lost (the record is filled through the
	Python data(), where the null QVariant already became 0). Only the
	model's own query still knows - so ask it directly."""
	query = model.query()
	if not query.seek(row) or query.isNull(column):
		return None
	return int(query.value(column))


# Per-member pass status from exercise_session (alias s), shared by the
# Osoby roster (memberModel) and the Provoz "who's where" table
# (exerciseSessionModel) so the two tabs can never disagree on the stav
# text or row order. No session row yet = PŘIPRAVEN.
SESSION_STAV_SQL = "CASE COALESCE(s.status,0) WHEN 0 THEN 'PŘIPRAVEN' WHEN 1 THEN 'UVNITŘ' WHEN 2 THEN 'DOKONČENO' ELSE '?' END"
SESSION_STAV_CODE_SQL = "COALESCE(s.status,0)"
SESSION_ORDER_SQL = "CASE COALESCE(s.status,0) WHEN 1 THEN 0 WHEN 0 THEN 1 ELSE 2 END, s.entry_at ASC, m.idMember ASC"
SESSION_INSIDE = 1

# UVNITŘ row highlight - same red family as theme.DANGER_TINT/DANGER_DARK.
INSIDE_BACKGROUND = QtGui.QColor(253, 231, 231)
INSIDE_FOREGROUND = QtGui.QColor(142, 27, 27)


def inside_highlight(model, index, role, stav_code_column):
	"""Background/foreground for an UVNITŘ row, None for every other row
	(PŘIPRAVEN/DOKONČENO keep the view's default colors). Only meaningful
	for Qt.BackgroundRole/ForegroundRole."""
	stav_code = model.data(model.index(index.row(), stav_code_column), QtCore.Qt.DisplayRole)
	if stav_code != SESSION_INSIDE:
		return None
	return INSIDE_BACKGROUND if role == QtCore.Qt.BackgroundRole else INSIDE_FOREGROUND


def duration_text(start, end):
	"""HH:MM:SS between two QDateTimes (hours may exceed 24), "" if
	either is missing/invalid. Negative spans clamp to 0 - entry time is
	operator-editable and may be "in the future"."""
	if not all(isinstance(v, QtCore.QDateTime) and v.isValid() for v in (start, end)):
		return ""
	seconds = max(0, start.secsTo(end))
	return "%02d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)


def clock_text(value):
	"""HH:MM:SS of a QDateTime, "" if missing/invalid."""
	if isinstance(value, QtCore.QDateTime) and value.isValid():
		return value.toString("HH:mm:ss")
	return ""


def duration_seconds(start, end):
	"""Whole seconds between two QDateTimes, clamped to >=0, or None if
	either is missing/invalid - same clamping as duration_text() above,
	but as a number (for protocol_data.compute_consumption()) rather than
	a formatted string."""
	if not all(isinstance(v, QtCore.QDateTime) and v.isValid() for v in (start, end)):
		return None
	return max(0, start.secsTo(end))


class personModel(QtSql.QSqlTableModel):
	ID_COLUMN = 0
	VALID_COLUMN = 6
	# Columns the person search looks in (UX-01): name, surname, birthday,
	# OEČ, unit - never the internal idPerson / valid.
	SEARCH_COLUMNS = (1, 2, 3, 4, 5)
	BIRTHDAY_COLUMN = 3

	def __init__(self, valid=1):
		"""valid=1: the normal person list. valid=0: the soft-deleted
		persons (DATA-02, Smazané osoby) - same columns, same display."""
		super(personModel, self).__init__()
		#self.setEditStrategy(QtSql.QSqlTableModel.OnFieldChange)
		self.setEditStrategy(QtSql.QSqlTableModel.OnManualSubmit)
		self.setTable("person")
		self.setFilter("valid=%d" % (1 if valid else 0))
		self.setSort(2, QtCore.Qt.AscendingOrder)
		self.select()
		self.setHeaderData(1, QtCore.Qt.Horizontal, u"Jméno")
		self.setHeaderData(2, QtCore.Qt.Horizontal, u"Příjmení")
		self.setHeaderData(3, QtCore.Qt.Horizontal, u"Datum narození")
		self.setHeaderData(4, QtCore.Qt.Horizontal, u"OEČ")
		self.setHeaderData(5, QtCore.Qt.Horizontal, u"Jednotka")

	def data(self, index, role=QtCore.Qt.DisplayRole):
		"""UX-03: Datum narození shown Czech (24.04.1981) instead of the
		system short format (4/24/81). Display only - EditRole (PersonForm,
		record(), sorting and search via the proxy) stays the real QDate."""
		if role == QtCore.Qt.DisplayRole and index.isValid() and index.column() == self.BIRTHDAY_COLUMN:
			value = super(personModel, self).data(index, QtCore.Qt.EditRole)
			if isinstance(value, QtCore.QDate) and value.isValid():
				return birthday_text(value)
		return super(personModel, self).data(index, role)

	def restore(self, person_id):
		"""DATA-02: undo a soft-delete - valid 0 -> 1 for exactly this
		idPerson, nothing else (no new person, member/training/
		exercise_session untouched, so the history stays attached). True
		only if that one soft-deleted row was really restored; the model
		is reloaded either way."""
		query = QtSql.QSqlQuery(self.database())
		query.prepare("UPDATE person SET valid=1 WHERE idPerson=? AND valid=0")
		query.addBindValue(int(person_id))
		restored = query.exec_() and query.numRowsAffected() == 1
		self.select()
		return restored


def birthday_text(date):
	"""UX-03: Czech date of birth, dd.MM.yyyy (1981-04-24 -> 24.04.1981)."""
	return date.toString("dd.MM.yyyy")


def _filter_texts(value, with_czech_dates):
	"""Texts the person search matches against. A QDate is matched as
	stored (ISO, 1990-01-01) and - for a search with a digit in it - also
	as shown (24.04.1981) and as typed without leading zeros (24.4.1981)
	(UX-03). Without a digit the Czech forms are skipped: their dots would
	make a literal "." find every person with a birthday."""
	if isinstance(value, QtCore.QDate):
		texts = (value.toString(QtCore.Qt.ISODate),)
		if with_czech_dates and value.isValid():
			texts += (birthday_text(value), value.toString("d.M.yyyy"))
		return texts
	if isinstance(value, QtCore.QDateTime):
		return (value.toString(QtCore.Qt.ISODateWithMs),)
	return ("" if value is None else str(value),)


class personFilterProxyModel(QtCore.QSortFilterProxyModel):
	"""Person list filter: the filter regexp (literal text, see
	MainWindow.on_lineEdit_textChanged) is matched only in
	personModel.SEARCH_COLUMNS.

	UX-03: filtering and sorting use the EditRole - the real QDate for
	Datum narození, not its dd.MM.yyyy display text, so the column sorts
	chronologically (as text 01.01.2000 < 24.04.1981). For the text
	columns EditRole == DisplayRole, nothing changes there."""

	def __init__(self, parent=None):
		super(personFilterProxyModel, self).__init__(parent)
		self.setSortRole(QtCore.Qt.EditRole)
		self.setFilterRole(QtCore.Qt.EditRole)

	def setSearchText(self, text):
		"""Filter by the typed text - literal, not a regex (UX-01: "(",
		".", "*" are plain characters), case-insensitive."""
		self.setFilterRegExp(QtCore.QRegExp(text, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.FixedString))

	def filterAcceptsRow(self, source_row, source_parent):
		regexp = self.filterRegExp()
		if regexp.isEmpty():
			return True
		with_czech_dates = any(c.isdigit() for c in regexp.pattern())
		source = self.sourceModel()
		return any(
			regexp.indexIn(text) != -1
			for column in personModel.SEARCH_COLUMNS
			for text in _filter_texts(source.index(source_row, column, source_parent).data(self.filterRole()),
			                          with_czech_dates))


class memberModel(QtSql.QSqlQueryModel):
	"""Osoby tab roster of the open training. Stav comes from the same
	exercise_session LEFT JOIN and shared SQL as exerciseSessionModel.

	Column layout: 0 idMember (hidden), 1 name, 2 unit (person.unit,
	WAVE2-01), 3 stav, 4 volume, 5 press_start, 6 press_end, 7
	consumption ("Spotřeba (l/min)", PRINT-02 corrective), 8 stav_code
	(hidden, 0/1/2), 9 entry_at (hidden), 10 exit_at (hidden). MemberForm
	reads values by column name, not index.

	consumption is a real SQL column (SELECT NULL AS consumption, kept at
	its normal position) whose DisplayRole value data() replaces with the
	computed text - deliberately NOT a synthetic column bolted on via
	columnCount()/index remapping: QSqlQueryModel.record(row) populates
	itself by calling (a possibly overridden) data() for every real query
	column, so remapping column numbers inside data() silently corrupts
	record(row) for every column after the insertion point. Keeping the
	column counts equal (one query column per model column) sidesteps
	that trap entirely."""
	NAME_COLUMN = 1
	UNIT_COLUMN = 2
	STAV_COLUMN = 3
	VOLUME_COLUMN = 4
	PRESS_START_COLUMN = 5
	PRESS_END_COLUMN = 6
	CONSUMPTION_COLUMN = 7
	STAV_CODE_COLUMN = 8
	ENTRY_AT_COLUMN = 9
	EXIT_AT_COLUMN = 10
	HEADERS = (u"Jméno", u"Jednotka", u"Stav", u"Objem lahve", u"Tlak zač.", u"Tlak kon.", u"Spotřeba (l/min)")

	def __init__(self, idTraining = None):
		super(memberModel, self).__init__()
		self.idtraining = idTraining
		self.view()

	def view(self):
		if self.idtraining is not None:
			self.setQuery(("SELECT m.idMember, CONCAT(p.name,' ', p.surname) AS name, p.unit, " + SESSION_STAV_SQL + " AS stav, "
							"m.volume, m.press_start, m.press_end, NULL AS consumption, "
							+ SESSION_STAV_CODE_SQL + " AS stav_code, s.entry_at, s.exit_at "
							"FROM member m "
							"LEFT JOIN person p ON m.person_id = p.idPerson "
							"LEFT JOIN training t ON m.training_id = t.idTraining "
							"LEFT JOIN exercise_session s ON s.member_id = m.idMember "
							"WHERE m.training_id=%d AND t.status<=2 "
							"ORDER BY " + SESSION_ORDER_SQL) % self.idtraining)
			for column, title in enumerate(self.HEADERS, start=self.NAME_COLUMN):
				self.setHeaderData(column, QtCore.Qt.Horizontal, title)

	def _consumption_text(self, row):
		"""PRINT-02 corrective: same compute_consumption()/consumption_text()
		as the printed protocol - never a second implementation of the
		formula or its ROUND_HALF_UP rounding. Meaningful only for a
		DOKONČENO member with a complete pass and valid values; PŘIPRAVEN/
		UVNITŘ (no exit_at yet) or any invalid input -> "—", same as the
		protocol documents."""
		record = self.record(row)
		duration = duration_seconds(record.value("entry_at"), record.value("exit_at"))
		volume = protocol_data.to_decimal(record.value("volume"))
		press_start = int(record.value("press_start") or 0)
		result = protocol_data.compute_consumption(volume, press_start, self.press_end(row), duration)
		return protocol_data.consumption_text(result[1] if result else None)

	def press_end(self, row):
		"""PRESS-END-NULL: None = not entered yet, 0 = a real 0 bar."""
		return nullable_int(self, row, self.PRESS_END_COLUMN)

	def data(self, index, role=QtCore.Qt.DisplayRole):
		if role in (QtCore.Qt.BackgroundRole, QtCore.Qt.ForegroundRole) and index.isValid():
			return inside_highlight(self, index, role, self.STAV_CODE_COLUMN)
		if index.isValid() and index.column() == self.CONSUMPTION_COLUMN and role == QtCore.Qt.DisplayRole:
			return self._consumption_text(index.row())
		if (index.isValid() and index.column() == self.PRESS_END_COLUMN and role == QtCore.Qt.DisplayRole
				and self.press_end(index.row()) is None):
			return NOT_ENTERED_TEXT
		return super(memberModel, self).data(index, role)

	def delete(self, idMember):
		query.exec_("DELETE FROM member WHERE idMember=%d" % (idMember))
		self.membermodel.select()

	def refresh(self, idTraining):
		self.idtraining = idTraining
		self.view()


class exerciseSessionModel(QtSql.QSqlQueryModel):
	""""Who's where" - every member of the current training, with their
	individual polygon pass if they have one (Etapa 7/8.2) - a plain
	QSqlQueryModel like memberModel/finishedTrainingModel, kept out of
	app/session_repository.py's stricter parametrized-statement
	discipline on purpose: GUI display models stay separate from the
	write-path service/repository layers (same precedent as Etapa 6).

	Driven FROM member, LEFT JOIN exercise_session - not the other way
	round - so a member who has never recorded an entry (no session row
	at all) still shows up as PŘIPRAVEN instead of being invisible. v1's
	SessionService guarantees at most one exercise_session row per member
	(reuses/finds via find_latest_session_for_member, never creates a
	second), so a plain LEFT JOIN is enough - no need to pick the latest
	of several.

	Column layout: 0 idMember (hidden), 1 name, 2 unit (person.unit,
	WAVE2-01), 3 source, 4 entry_at, 5 exit_at, 6 duration, 7 stav (text),
	8 stav_code (hidden, 0/1/2 - READY/INSIDE/DONE, read instead of
	re-parsing the Czech stav text). Use the *_COLUMN constants below,
	never literal indexes."""
	# Live "Doba" for UVNITŘ rows (Etapa 8.4): repainted at most once a
	# second from the already-loaded entry_at - never via setQuery()/DB,
	# which would reset the model (selection, row order) every tick.
	LIVE_INTERVAL_MS = 1000

	def __init__(self, idTraining=None):
		super(exerciseSessionModel, self).__init__()
		self.idtraining = idTraining
		self.now = QtCore.QDateTime.currentDateTime  # injectable clock (tests)
		self.live_timer = QtCore.QTimer(self)
		self.live_timer.setInterval(self.LIVE_INTERVAL_MS)
		self.live_timer.timeout.connect(self.tick_live_durations)
		self.view()

	def view(self):
		if self.idtraining is None:
			self.setQuery("SELECT 1 WHERE 0")
			self.live_timer.stop()
			return
		self.setQuery((
			"SELECT m.idMember, CONCAT(p.name,' ', p.surname) AS name, p.unit, s.source, "
			"s.entry_at, s.exit_at, "
			"SEC_TO_TIME(TIMESTAMPDIFF(SECOND, s.entry_at, s.exit_at)) AS duration, "
			+ SESSION_STAV_SQL + " AS stav, "
			+ SESSION_STAV_CODE_SQL + " AS stav_code "
			"FROM member m "
			"LEFT JOIN exercise_session s ON s.member_id = m.idMember "
			"LEFT JOIN person p ON p.idPerson = m.person_id "
			"WHERE m.training_id=%d "
			"ORDER BY " + SESSION_ORDER_SQL
		) % self.idtraining)
		for column, title in enumerate(self.HEADERS, start=self.NAME_COLUMN):
			self.setHeaderData(column, QtCore.Qt.Horizontal, title)
		# The timer only runs while someone is UVNITŘ.
		if self.inside_count():
			self.live_timer.start()
		else:
			self.live_timer.stop()

	def refresh(self, idTraining=None):
		if idTraining is not None:
			self.idtraining = idTraining
		self.view()

	# Column indexes - kept in one place instead of literals scattered
	# through data(). stav_code (0/1/2) is hidden in the view.
	NAME_COLUMN = 1
	UNIT_COLUMN = 2
	SOURCE_COLUMN = 3
	ENTRY_COLUMN = 4
	EXIT_COLUMN = 5
	DURATION_COLUMN = 6
	STAV_COLUMN = 7
	STAV_CODE_COLUMN = 8
	HEADERS = (u"Jméno", u"Jednotka", u"Zdroj", u"Vstup", u"Výstup", u"Doba", u"Stav")
	INSIDE = SESSION_INSIDE
	DONE = 2

	_INSIDE_BACKGROUND = INSIDE_BACKGROUND
	_INSIDE_FOREGROUND = INSIDE_FOREGROUND

	def data(self, index, role=QtCore.Qt.DisplayRole):
		"""UVNITŘ rows get a distinct background/text color (Etapa 8.3) -
		the whole point of this etapa is that "who's inside right now"
		must be provozně nepřehlédnutelný, not just a text column among
		others."""
		if role in (QtCore.Qt.BackgroundRole, QtCore.Qt.ForegroundRole) and index.isValid():
			return inside_highlight(self, index, role, self.STAV_CODE_COLUMN)
		if role == QtCore.Qt.DisplayRole and index.isValid() and index.column() == self.DURATION_COLUMN:
			return self._duration_text(index.row())
		# Vstup/Výstup: time only (same as Karta Cvičení), full date on hover.
		if index.isValid() and index.column() in (self.ENTRY_COLUMN, self.EXIT_COLUMN):
			value = self._raw(index.row(), index.column())
			if role == QtCore.Qt.DisplayRole:
				return clock_text(value)
			if role == QtCore.Qt.ToolTipRole:
				return value.toString("dd.MM.yyyy HH:mm:ss") if isinstance(value, QtCore.QDateTime) and value.isValid() else None
		return super(exerciseSessionModel, self).data(index, role)

	def _raw(self, row, column):
		return super(exerciseSessionModel, self).data(self.index(row, column), QtCore.Qt.DisplayRole)

	def _stav_code(self, row):
		return self._raw(row, self.STAV_CODE_COLUMN)

	def _duration_text(self, row):
		"""PŘIPRAVEN: empty. UVNITŘ: live, entry_at -> now. DOKONČENO:
		final, entry_at -> exit_at. Always HH:MM:SS (hours may exceed 24)."""
		stav_code = self._stav_code(row)
		if stav_code == self.INSIDE:
			end = self.now()
		elif stav_code == self.DONE:
			end = self._raw(row, self.EXIT_COLUMN)
		else:
			return ""
		return duration_text(self._raw(row, self.ENTRY_COLUMN), end)

	def tick_live_durations(self):
		"""live_timer slot: repaint only the Doba cells of UVNITŘ rows via
		dataChanged(DisplayRole) - no setQuery(), no DB access, so the
		selection, row order and any open editor stay untouched."""
		inside_rows = [row for row in range(self.rowCount()) if self._stav_code(row) == self.INSIDE]
		if not inside_rows:
			self.live_timer.stop()
			return
		for row in inside_rows:
			cell = self.index(row, self.DURATION_COLUMN)
			self.dataChanged.emit(cell, cell, [QtCore.Qt.DisplayRole])

	def inside_count(self):
		"""Number of UVNITŘ rows in the currently loaded query - the same
		rows the operator sees highlighted, so the counter and the table
		can never disagree. Returns None (not 0) if the query failed: a
		DB error must never read as "nobody is inside" (fail closed, same
		principle as SessionService's status reads)."""
		if query_failed(self):
			return None
		while self.canFetchMore():
			self.fetchMore()
		if query_failed(self):
			return None
		return sum(1 for row in range(self.rowCount()) if self._stav_code(row) == self.INSIDE)


class trainingModel(QtSql.QSqlTableModel):
	def __init__(self):
		super(trainingModel, self).__init__()
		self.setTable("training")
		self.setEditStrategy(QtSql.QSqlTableModel.OnManualSubmit)
		self.setFilter("status=0 OR status=1 OR status=2")
		self.select()

	def load_failed(self):
		"""True if the last select() failed - lets callers tell "no open
		training" (0 rows) apart from a DB error (also 0 rows)."""
		return query_failed(self)


class finishedTrainingModel(QtSql.QSqlQueryModel):
	"""Karta Cvičení, upper table: one row per saved training (Balík B).

	Column layout: 0 idTraining (hidden; _selected_training_id() reads it
	for the Zpráva/Potvrzení actions), 1 datum, 2 pocet, 3 first_entry, 4 last_exit, 5 zaznam.
	training.time_start is a DATE in production (SCHEMA-01) - there is no
	start time of day, first/last come from the individual passes.
	Trainings saved before exercise_session existed have no passes:
	their times stay empty and Záznam says why. The legacy squad
	time_cage/time_end are deliberately not shown (different meaning)."""
	DATE_COLUMN = 1
	FIRST_ENTRY_COLUMN = 3
	LAST_EXIT_COLUMN = 4
	INDIVIDUAL = u"INDIVIDUÁLNÍ"
	LEGACY = u"STARŠÍ ZÁZNAM"

	def __init__(self):
		super(finishedTrainingModel, self).__init__()
		self.view()

	def view(self):
		self.setQuery(
			"SELECT t.idTraining, t.time_start AS datum, COUNT(DISTINCT m.idMember) AS pocet, "
			"MIN(s.entry_at) AS first_entry, MAX(s.exit_at) AS last_exit, "
			"CASE WHEN COUNT(s.idSession) > 0 THEN '" + self.INDIVIDUAL + "' ELSE '" + self.LEGACY + "' END AS zaznam "
			"FROM training t "
			"LEFT JOIN member m ON m.training_id = t.idTraining "
			"LEFT JOIN exercise_session s ON s.member_id = m.idMember "
			"WHERE t.status=10 "
			"GROUP BY t.idTraining, t.time_start "
			# time_start has no time of day - idTraining keeps same-day order
			"ORDER BY t.time_start DESC, t.idTraining DESC")
		self.setHeaderData(1, QtCore.Qt.Horizontal, u"Datum")
		self.setHeaderData(2, QtCore.Qt.Horizontal, u"Počet osob")
		self.setHeaderData(3, QtCore.Qt.Horizontal, u"První vstup")
		self.setHeaderData(4, QtCore.Qt.Horizontal, u"Poslední výstup")
		self.setHeaderData(5, QtCore.Qt.Horizontal, u"Záznam")

	def data(self, index, role=QtCore.Qt.DisplayRole):
		if index.isValid() and role in (QtCore.Qt.DisplayRole, QtCore.Qt.ToolTipRole):
			column = index.column()
			value = super(finishedTrainingModel, self).data(index, QtCore.Qt.DisplayRole)
			if column == self.DATE_COLUMN:
				return value.toString("dd.MM.yyyy") if isinstance(value, QtCore.QDate) and value.isValid() else ""
			if column in (self.FIRST_ENTRY_COLUMN, self.LAST_EXIT_COLUMN):
				if role == QtCore.Qt.ToolTipRole:
					return value.toString("dd.MM.yyyy HH:mm:ss") if isinstance(value, QtCore.QDateTime) and value.isValid() else None
				return clock_text(value)
		return super(finishedTrainingModel, self).data(index, role)

	def refresh(self):
		self.view()


class personHistoryModel(QtSql.QSqlQueryModel):
	"""HISTORY-02: Historie cvičence - read-only list of one person's SAVED
	trainings (status 10), newest first. The current open training is
	never shown.

	Column layout: 0 idTraining (hidden), 1 datum, 2 entry_at, 3 exit_at,
	4 duration (computed in data()), 5 volume, 6 press_start, 7 press_end,
	8 consumption (computed in data()), 9 zaznam. Same patterns as
	trainingDetailModel: real "NULL AS ..." query columns whose
	DisplayRole data() replaces, PRINT-02 consumption only through
	protocol_data.compute_consumption()/consumption_text(), and
	press_end read via nullable_int() (QMYSQL reads NULL as 0).

	The pass is the member's latest exercise_session (MAX(idSession), the
	protocol's rule) so a stray duplicate session never doubles a row.
	Legacy trainings (saved before exercise_session) are kept: their
	times, duration and consumption show "—" - the squad time_cage/
	time_end are deliberately not used (different meaning)."""
	ID_COLUMN = 0
	DATE_COLUMN = 1
	ENTRY_COLUMN = 2
	EXIT_COLUMN = 3
	DURATION_COLUMN = 4
	VOLUME_COLUMN = 5
	PRESS_START_COLUMN = 6
	PRESS_END_COLUMN = 7
	CONSUMPTION_COLUMN = 8
	RECORD_COLUMN = 9
	HEADERS = (u"Datum", u"Vstup", u"Výstup", u"Doba", u"Objem lahve", u"Tlak zač.", u"Tlak kon.",
	           u"Spotřeba (l/min)", u"Záznam")

	def __init__(self, person_id):
		super(personHistoryModel, self).__init__()
		self.person_id = int(person_id)
		self.view()

	def view(self):
		self.setQuery(
			"SELECT t.idTraining, t.time_start AS datum, s.entry_at, s.exit_at, NULL AS duration, "
			"m.volume, m.press_start, m.press_end, NULL AS consumption, "
			"CASE WHEN EXISTS (SELECT 1 FROM member m2 JOIN exercise_session s2 ON s2.member_id = m2.idMember "
			"WHERE m2.training_id = t.idTraining) "
			"THEN '" + finishedTrainingModel.INDIVIDUAL + "' ELSE '" + finishedTrainingModel.LEGACY + "' END AS zaznam "
			"FROM member m "
			"JOIN training t ON t.idTraining = m.training_id "
			"LEFT JOIN exercise_session s ON s.idSession = "
			"(SELECT MAX(x.idSession) FROM exercise_session x WHERE x.member_id = m.idMember) "
			"WHERE m.person_id = %d AND t.status = 10 "
			# time_start is a DATE (no time of day) - idTraining keeps same-day order
			"ORDER BY t.time_start DESC, t.idTraining DESC, m.idMember DESC" % self.person_id)
		for column, title in enumerate(self.HEADERS, start=self.DATE_COLUMN):
			self.setHeaderData(column, QtCore.Qt.Horizontal, title)

	def _raw(self, row, column):
		return super(personHistoryModel, self).data(self.index(row, column), QtCore.Qt.DisplayRole)

	def press_end(self, row):
		"""PRESS-END-NULL: None = not entered (incl. migrated old 0s), 0 = a real 0 bar."""
		return nullable_int(self, row, self.PRESS_END_COLUMN)

	def _consumption_text(self, row):
		duration = duration_seconds(self._raw(row, self.ENTRY_COLUMN), self._raw(row, self.EXIT_COLUMN))
		volume = protocol_data.to_decimal(self._raw(row, self.VOLUME_COLUMN))
		press_start = int(self._raw(row, self.PRESS_START_COLUMN) or 0)
		result = protocol_data.compute_consumption(volume, press_start, self.press_end(row), duration)
		return protocol_data.consumption_text(result[1] if result else None)

	def data(self, index, role=QtCore.Qt.DisplayRole):
		if not index.isValid() or role not in (QtCore.Qt.DisplayRole, QtCore.Qt.ToolTipRole):
			return super(personHistoryModel, self).data(index, role)
		row, column = index.row(), index.column()
		if column == self.DATE_COLUMN:
			if role == QtCore.Qt.ToolTipRole:
				return None
			value = self._raw(row, column)
			return value.toString("dd.MM.yyyy") if isinstance(value, QtCore.QDate) and value.isValid() else ""
		if column in (self.ENTRY_COLUMN, self.EXIT_COLUMN):
			value = self._raw(row, column)
			if role == QtCore.Qt.ToolTipRole:
				return value.toString("dd.MM.yyyy HH:mm:ss") if isinstance(value, QtCore.QDateTime) and value.isValid() else None
			return clock_text(value) or NOT_ENTERED_TEXT
		if role == QtCore.Qt.ToolTipRole:
			return None
		if column == self.DURATION_COLUMN:
			return duration_text(self._raw(row, self.ENTRY_COLUMN), self._raw(row, self.EXIT_COLUMN)) or NOT_ENTERED_TEXT
		if column == self.CONSUMPTION_COLUMN:
			return self._consumption_text(row)
		if column == self.PRESS_END_COLUMN and self.press_end(row) is None:
			return NOT_ENTERED_TEXT
		return super(personHistoryModel, self).data(index, role)


class trainingDetailModel(QtSql.QSqlQueryModel):
	"""Karta Cvičení, lower table: every member of the selected training
	with their individual pass (Balík B). Legacy trainings have no
	exercise_session rows - Vstup/Výstup/Doba stay empty there.

	Column layout: 0 idMember (hidden), 1 name, 2 oec, 3 unit, 4 entry_at,
	5 exit_at, 6 duration (computed in data()), 7 volume, 8 press_start,
	9 press_end, 10 consumption ("Spotřeba (l/min)", PRINT-02, computed in
	data()). training_id None loads an empty table that keeps its headers.

	consumption is a real SQL column (NULL AS consumption) whose
	DisplayRole data() replaces - same pattern as memberModel, no
	synthetic column via columnCount()/index remapping."""
	ID_COLUMN = 0
	ENTRY_COLUMN = 4
	EXIT_COLUMN = 5
	DURATION_COLUMN = 6
	VOLUME_COLUMN = 7
	PRESS_START_COLUMN = 8
	PRESS_END_COLUMN = 9
	CONSUMPTION_COLUMN = 10

	def __init__(self, idTraining=None):
		super(trainingDetailModel, self).__init__()
		self.idtraining = idTraining
		self.view()

	def view(self):
		self.setQuery(
			"SELECT m.idMember, CONCAT(p.name,' ', p.surname) AS name, p.oec, p.unit, "
			"s.entry_at, s.exit_at, NULL AS duration, m.volume, m.press_start, m.press_end, NULL AS consumption "
			"FROM member m "
			"LEFT JOIN person p ON p.idPerson = m.person_id "
			"LEFT JOIN exercise_session s ON s.member_id = m.idMember "
			"WHERE m.training_id=%d "
			"ORDER BY s.entry_at IS NULL, s.entry_at ASC, m.idMember ASC" % (self.idtraining or 0))
		for column, title in enumerate((u"Jméno", u"OEČ", u"Jednotka", u"Vstup", u"Výstup", u"Doba",
		                                u"Objem lahve", u"Tlak zač.", u"Tlak kon.", u"Spotřeba (l/min)"), start=1):
			self.setHeaderData(column, QtCore.Qt.Horizontal, title)

	def refresh(self, idTraining=None):
		self.idtraining = idTraining
		self.view()

	def _raw(self, row, column):
		return super(trainingDetailModel, self).data(self.index(row, column), QtCore.Qt.DisplayRole)

	def _consumption_text(self, row):
		"""PRINT-02: same compute_consumption()/consumption_text() as the
		printed protocol and memberModel. Legacy trainings (no
		exercise_session) or any invalid input -> "—"."""
		duration = duration_seconds(self._raw(row, self.ENTRY_COLUMN), self._raw(row, self.EXIT_COLUMN))
		volume = protocol_data.to_decimal(self._raw(row, self.VOLUME_COLUMN))
		press_start = int(self._raw(row, self.PRESS_START_COLUMN) or 0)
		result = protocol_data.compute_consumption(volume, press_start, self.press_end(row), duration)
		return protocol_data.consumption_text(result[1] if result else None)

	def data(self, index, role=QtCore.Qt.DisplayRole):
		if index.isValid() and role == QtCore.Qt.DisplayRole:
			column = index.column()
			if column in (self.ENTRY_COLUMN, self.EXIT_COLUMN):
				return clock_text(self._raw(index.row(), column))
			if column == self.DURATION_COLUMN:
				return duration_text(self._raw(index.row(), self.ENTRY_COLUMN), self._raw(index.row(), self.EXIT_COLUMN))
			if column == self.CONSUMPTION_COLUMN:
				return self._consumption_text(index.row())
			if column == self.PRESS_END_COLUMN and self.press_end(index.row()) is None:
				return NOT_ENTERED_TEXT
		return super(trainingDetailModel, self).data(index, role)

	def press_end(self, row):
		"""PRESS-END-NULL: None = not entered (incl. migrated old 0s), 0 = a real 0 bar."""
		return nullable_int(self, row, self.PRESS_END_COLUMN)
