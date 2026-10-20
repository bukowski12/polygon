"""LOGBOOK-01: the "Kniha provozu" tab - the view only.

LogbookTab shows operation_log records (filters, table, open count, a
banner when the log can't be read) and emits signals for the actions;
MainWindow talks to OperationLogService. When a refresh fails the last
successfully loaded table stays (it must never look like "no records")
and the writing actions are disabled until a refresh succeeds.
"""

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QDateEdit, QDateTimeEdit, QDialog,
                             QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QPlainTextEdit, QPushButton, QRadioButton, QSizePolicy, QSpacerItem, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

import polygon_map
import theme
from logbook_print import (DEFAULT_SCOPE, SCOPE_LABELS, SCOPE_PERIOD, LogbookScope,
                           format_datetime, location_text)  # noqa: F401 - formatters shared with the printed logbook
from operation_log_repository import CANCELLED, OPEN, RESOLVED
from operation_log_service import CATEGORY_LABELS, INJURY, LOCATION_MAX_LENGTH, SENSOR_FAULT

STATUS_FILTERS = (("Otevřené", OPEN), ("Vše", None), ("Vyřešené", RESOLVED), ("Stornované", CANCELLED))
COLUMNS = ("Datum/čas", "Typ", "Místo / zařízení", "Popis", "Stav", "Zapsal")
UNAVAILABLE_TEXT = "Kniha provozu není dostupná – databáze není dostupná."
DESCRIPTION_PREVIEW = 80   # characters of the description shown in the table
INJURY_HINT = "Zapisujte pouze provozní informace. Neuvádějte diagnózy ani jiné citlivé zdravotní údaje."
DATETIME_FORMAT = "dd.MM.yyyy HH:mm"
DATE_FORMAT = "dd.MM.yyyy"
PRINT_PREVIEW = "preview"   # LogbookPrintDialog actions (LOGBOOK-02)
PRINT_PDF = "pdf"
PRINT_SCOPE_HINT = "Tiskne vždy všechny typy záznamů – filtry tabulky se neuplatní."


def description_preview(text):
    line = " ".join((text or "").split())
    return line if len(line) <= DESCRIPTION_PREVIEW else line[:DESCRIPTION_PREVIEW - 1] + "…"


class LogbookTab(QWidget):
    newRequested = QtCore.pyqtSignal()
    refreshRequested = QtCore.pyqtSignal()       # Obnovit and every filter change
    detailRequested = QtCore.pyqtSignal(int)     # idLog
    resolveRequested = QtCore.pyqtSignal(int)
    cancelRequested = QtCore.pyqtSignal(int)
    printRequested = QtCore.pyqtSignal()         # LOGBOOK-02: Tisk / PDF…

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tabLogbook")
        self._records = []
        self._available = True
        layout = QVBoxLayout(self)

        self.banner = QLabel(UNAVAILABLE_TEXT, self)
        self.banner.setObjectName("logbookBanner")
        self.banner.setStyleSheet(theme.LOGBOOK_BANNER_STYLE)
        self.banner.setVisible(False)
        layout.addWidget(self.banner)

        top = QHBoxLayout()
        self.newButton = QPushButton("Nový záznam", self)
        self.newButton.setObjectName("logbookNewButton")
        self.newButton.setMinimumSize(QtCore.QSize(160, 40))
        theme.set_variant(self.newButton, "primary")
        top.addWidget(self.newButton)
        top.addSpacing(24)
        top.addWidget(QLabel("Stav:", self))
        self.statusCombo = QComboBox(self)
        self.statusCombo.setObjectName("logbookStatusCombo")
        for label, status in STATUS_FILTERS:
            self.statusCombo.addItem(label, status)
        top.addWidget(self.statusCombo)
        top.addSpacing(12)
        top.addWidget(QLabel("Typ:", self))
        self.categoryCombo = QComboBox(self)
        self.categoryCombo.setObjectName("logbookCategoryCombo")
        self.categoryCombo.addItem("Všechny", None)
        for code, label in CATEGORY_LABELS.items():
            self.categoryCombo.addItem(label, code)
        top.addWidget(self.categoryCombo)
        top.addSpacing(12)
        self.refreshButton = QPushButton("Obnovit", self)
        self.refreshButton.setObjectName("logbookRefreshButton")
        self.refreshButton.setMinimumSize(QtCore.QSize(120, 40))
        theme.set_variant(self.refreshButton, "secondary")
        top.addWidget(self.refreshButton)
        top.addSpacing(12)
        self.printButton = QPushButton("Tisk / PDF…", self)
        self.printButton.setObjectName("logbookPrintButton")
        self.printButton.setMinimumSize(QtCore.QSize(140, 40))
        theme.set_variant(self.printButton, "secondary")
        top.addWidget(self.printButton)
        top.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.openCountLabel = QLabel("", self)
        self.openCountLabel.setObjectName("logbookOpenCountLabel")
        top.addWidget(self.openCountLabel)
        layout.addLayout(top)

        self.table = QTableWidget(0, len(COLUMNS), self)
        self.table.setObjectName("logbookTable")
        self.table.setHorizontalHeaderLabels(COLUMNS)
        theme.style_table(self.table)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for column in range(len(COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Popis
        layout.addWidget(self.table)

        bottom = QHBoxLayout()
        self.detailButton = QPushButton("Detail", self)
        self.detailButton.setObjectName("logbookDetailButton")
        self.resolveButton = QPushButton("Označit jako vyřešené", self)
        self.resolveButton.setObjectName("logbookResolveButton")
        self.cancelButton = QPushButton("Stornovat", self)
        self.cancelButton.setObjectName("logbookCancelButton")
        for button, variant in ((self.detailButton, "secondary"), (self.resolveButton, "success"),
                                (self.cancelButton, "destructive")):
            button.setMinimumSize(QtCore.QSize(160, 40))
            theme.set_variant(button, variant)
            bottom.addWidget(button)
        bottom.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        layout.addLayout(bottom)

        self.newButton.clicked.connect(self.newRequested)
        self.refreshButton.clicked.connect(self.refreshRequested)
        # a read only - stays enabled while the log is unavailable; the
        # report is always loaded fresh, never printed from this table
        self.printButton.clicked.connect(self.printRequested)
        self.statusCombo.currentIndexChanged.connect(lambda _index: self.refreshRequested.emit())
        self.categoryCombo.currentIndexChanged.connect(lambda _index: self.refreshRequested.emit())
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.cellDoubleClicked.connect(lambda row, _col: self._emit_for_row(row, self.detailRequested))
        self.detailButton.clicked.connect(lambda: self._emit_selected(self.detailRequested))
        self.resolveButton.clicked.connect(lambda: self._emit_selected(self.resolveRequested))
        self.cancelButton.clicked.connect(lambda: self._emit_selected(self.cancelRequested))
        self._update_buttons()

    # --- filters ---------------------------------------------------------------

    def status_filter(self):
        return self.statusCombo.currentData()

    def category_filter(self):
        return self.categoryCombo.currentData()

    # --- content ---------------------------------------------------------------

    def show_records(self, records, open_count):
        """A successful load: fill the table, keep the selected record."""
        selected = self.selected_record()
        self._records = list(records)
        self.table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            cells = (format_datetime(record.event_at), record.category_label, location_text(record),
                     description_preview(record.description), record.status_label, record.created_by)
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(QtCore.Qt.UserRole, record.log_id)
                if column == 3:
                    item.setToolTip(record.description)
                self._style_item(item, record, column)
                self.table.setItem(row, column, item)
        self.openCountLabel.setText(f"Otevřené záznamy: {open_count}")
        self.table.clearSelection()
        if selected is not None:
            for row, record in enumerate(self._records):
                if record.log_id == selected.log_id:
                    self.table.selectRow(row)
        self._update_buttons()

    @staticmethod
    def _style_item(item, record, column):
        if record.status == OPEN and column == 4:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setForeground(QtGui.QColor(theme.DANGER_DARK))
        elif record.status == CANCELLED:
            item.setForeground(QtGui.QColor(theme.DISABLED_TEXT))

    def records(self):
        return list(self._records)

    def is_available(self):
        return self._available

    def set_available(self, available):
        """False: the log can't be read - banner on, the last table stays,
        writes disabled (Obnovit stays enabled)."""
        self._available = bool(available)
        self.banner.setVisible(not self._available)
        self._update_buttons()

    def selected_record(self):
        rows = {index.row() for index in self.table.selectionModel().selectedRows()} if self.table.selectionModel() else set()
        if not rows:
            return None
        row = min(rows)
        return self._records[row] if row < len(self._records) else None

    def select_record(self, log_id):
        for row, record in enumerate(self._records):
            if record.log_id == log_id:
                self.table.selectRow(row)
                return True
        return False

    def _update_buttons(self):
        record = self.selected_record()
        self.newButton.setEnabled(self._available)
        self.detailButton.setEnabled(record is not None)
        writable = self._available and record is not None and record.is_open
        self.resolveButton.setEnabled(writable)
        self.cancelButton.setEnabled(writable)

    def _emit_selected(self, signal):
        record = self.selected_record()
        if record is not None:
            signal.emit(record.log_id)

    def _emit_for_row(self, row, signal):
        if 0 <= row < len(self._records):
            signal.emit(self._records[row].log_id)


class LogRecordDialog(QDialog):
    """Nový záznam: Typ události *, Datum a čas události * (default now),
    Místo / zařízení (or Čidlo * for Nefunkční čidlo), Popis *. OK stays
    disabled until the description isn't blank."""

    def __init__(self, now, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nový záznam – Kniha provozu")
        self.setMinimumWidth(520)
        layout = QFormLayout(self)
        self.categoryCombo = QComboBox(self)
        for code, label in CATEGORY_LABELS.items():
            self.categoryCombo.addItem(label, code)
        layout.addRow("Typ události *", self.categoryCombo)
        self.eventEdit = QDateTimeEdit(QtCore.QDateTime(now.replace(second=0, microsecond=0)), self)
        self.eventEdit.setDisplayFormat(DATETIME_FORMAT)
        self.eventEdit.setCalendarPopup(True)
        layout.addRow("Datum a čas události *", self.eventEdit)
        self.locationLabel = QLabel("Místo / zařízení", self)
        self.locationEdit = QLineEdit(self)
        self.locationEdit.setMaxLength(LOCATION_MAX_LENGTH)
        self.locationEdit.setPlaceholderText("nepovinné")
        layout.addRow(self.locationLabel, self.locationEdit)
        self.floorLabel = QLabel("Čidlo *", self)
        self.floorCombo = QComboBox(self)
        for name in sorted(polygon_map.FLOOR_NAMES):
            self.floorCombo.addItem(f"Čidlo {polygon_map.segment_text(name)}", name)
        layout.addRow(self.floorLabel, self.floorCombo)
        self.injuryHint = QLabel(INJURY_HINT, self)
        self.injuryHint.setObjectName("logbookInjuryHint")
        self.injuryHint.setWordWrap(True)
        self.injuryHint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-style: italic;")
        layout.addRow(self.injuryHint)
        self.descriptionEdit = QPlainTextEdit(self)
        self.descriptionEdit.setMinimumHeight(110)
        layout.addRow("Popis *", self.descriptionEdit)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)
        self.categoryCombo.currentIndexChanged.connect(self._category_changed)
        self.descriptionEdit.textChanged.connect(self._update_ok)
        self._category_changed()
        self._update_ok()

    def _category_changed(self, *_):
        category = self.categoryCombo.currentData()
        sensor = category == SENSOR_FAULT
        for widget in (self.locationLabel, self.locationEdit):
            widget.setVisible(not sensor)
        for widget in (self.floorLabel, self.floorCombo):
            widget.setVisible(sensor)
        self.injuryHint.setVisible(category == INJURY)

    def _update_ok(self):
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(bool(self.descriptionEdit.toPlainText().strip()))

    def values(self):
        """dict for OperationLogService.create_record()."""
        category = self.categoryCombo.currentData()
        sensor = category == SENSOR_FAULT
        return {
            "category": category,
            "event_at": self.eventEdit.dateTime().toPyDateTime().replace(second=0, microsecond=0),
            "location_text": None if sensor else (self.locationEdit.text().strip() or None),
            "floor_name": self.floorCombo.currentData() if sensor else None,
            "description": self.descriptionEdit.toPlainText().strip(),
        }


class LogbookPrintDialog(QDialog):
    """LOGBOOK-02 Tisk / PDF: which records (one of SCOPE_LABELS, the
    shift handover by default) and what to do - Náhled / tisk or Uložit
    PDF. Accepted with `action` set; the dates are used for Období only
    and an Období with OD after DO can't be confirmed."""

    def __init__(self, today, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tisk / PDF – Kniha provozu")
        self.setMinimumWidth(460)
        self.today = today
        self.action = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Rozsah:", self))
        self.scopeGroup = QButtonGroup(self)
        self.scopeButtons = {}
        for kind, label in SCOPE_LABELS.items():
            button = QRadioButton(label, self)
            button.setObjectName(f"logbookPrintScope{kind.title()}")
            self.scopeGroup.addButton(button)
            self.scopeButtons[kind] = button
            layout.addWidget(button)
            if kind == SCOPE_PERIOD:
                dates = QHBoxLayout()
                dates.addSpacing(24)
                self.fromEdit, self.toEdit = (self._date_edit(), self._date_edit())
                for text, edit in (("od", self.fromEdit), ("do", self.toEdit)):
                    dates.addWidget(QLabel(text, self))
                    dates.addWidget(edit)
                dates.addStretch(1)
                layout.addLayout(dates)
        self.scopeButtons[DEFAULT_SCOPE].setChecked(True)
        hint = QLabel(PRINT_SCOPE_HINT, self)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-style: italic;")
        layout.addWidget(hint)
        self.buttonBox = QDialogButtonBox(self)
        self.previewButton = self.buttonBox.addButton("Náhled / tisk", QDialogButtonBox.AcceptRole)
        self.pdfButton = self.buttonBox.addButton("Uložit PDF", QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton("Zavřít", QDialogButtonBox.RejectRole)
        self.previewButton.clicked.connect(lambda: self._choose(PRINT_PREVIEW))
        self.pdfButton.clicked.connect(lambda: self._choose(PRINT_PDF))
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)
        self.scopeGroup.buttonToggled.connect(self._update)
        self.fromEdit.dateChanged.connect(self._update)
        self.toEdit.dateChanged.connect(self._update)
        self._update()

    def _date_edit(self):
        edit = QDateEdit(QtCore.QDate(self.today), self)
        edit.setDisplayFormat(DATE_FORMAT)
        edit.setCalendarPopup(True)
        return edit

    def scope_kind(self):
        return next(kind for kind, button in self.scopeButtons.items() if button.isChecked())

    def scope(self) -> LogbookScope:
        if self.scope_kind() == SCOPE_PERIOD:
            return LogbookScope(SCOPE_PERIOD, self.today, self.fromEdit.date().toPyDate(),
                                self.toEdit.date().toPyDate())
        return LogbookScope(self.scope_kind(), self.today)

    def _update(self, *_):
        period = self.scope_kind() == SCOPE_PERIOD
        self.fromEdit.setEnabled(period)
        self.toEdit.setEnabled(period)
        valid = self.scope().is_valid()
        self.previewButton.setEnabled(valid)
        self.pdfButton.setEnabled(valid)

    def _choose(self, action):
        if self.scope().is_valid():
            self.action = action
            self.accept()


LONG_DETAIL_FIELDS = ("Popis", "Poznámka k řešení", "Důvod storna")


def detail_rows(record, hw_state_text=None):
    """(label, value) rows of the read-only detail - only what applies."""
    rows = [("ID záznamu", str(record.log_id)),
            ("Skutečný čas události", format_datetime(record.event_at)),
            ("Čas zápisu", format_datetime(record.created_at)),
            ("Typ", record.category_label)]
    if record.floor_name:
        rows.append(("Čidlo", polygon_map.segment_text(record.floor_name)))
    else:
        rows.append(("Místo / zařízení", record.location_text or "—"))
    rows += [("Popis", record.description), ("Stav", record.status_label), ("Zapsal", record.created_by)]
    if record.training_id is not None:
        rows.append(("Cvičení", f"#{record.training_id}"))
    if record.status == RESOLVED:
        rows += [("Vyřešeno kdy", format_datetime(record.resolved_at)), ("Vyřešil", record.resolved_by or ""),
                 ("Poznámka k řešení", record.resolution_note or "—")]
    if record.status == CANCELLED:
        rows += [("Stornováno kdy", format_datetime(record.cancelled_at)), ("Stornoval", record.cancelled_by or ""),
                 ("Důvod storna", record.cancel_reason or "")]
    if record.floor_name and hw_state_text:
        rows.append(("Aktuální HW stav", hw_state_text))
    return rows


class LogRecordDetailDialog(QDialog):
    """Read-only detail of one record - records are never edited."""

    def __init__(self, record, hw_state_text=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Záznam #{record.log_id} – {record.category_label}")
        self.setMinimumWidth(560)
        layout = QFormLayout(self)
        self.rows = detail_rows(record, hw_state_text)
        for label, value in self.rows:
            if label in LONG_DETAIL_FIELDS:
                # free text: a read-only box (scrolls), never a clipped wrapped label
                field = QPlainTextEdit(value, self)
                field.setReadOnly(True)
                lines = 4 if label == "Popis" else 2
                field.setFixedHeight(field.fontMetrics().lineSpacing() * lines + 14)
            else:
                field = QLabel(value, self)
                field.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            layout.addRow(f"{label}:", field)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("Zavřít")
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
