"""DEV-only QUIDO simulator window.

Lets a developer flip simulated floor inputs on/off and watch the relay
outputs the main application drives, without any physical QUIDO hardware.
Only ever instantiated when [DEV] mock_quido = true.
"""

from PyQt5 import QtCore
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from logger_config import logger
from mock_quido import Device as MockDevice


class QuidoSimulatorDialog(QDialog):
    """Simple control panel for the mock QUIDO devices."""

    def __init__(self, din_ip, dout_ip, quido_in_config, quido_out_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QUIDO Simulator")

        # Own Device handles for the same (ip, port) as the main app - they
        # share state through mock_quido's registry, so toggling here is
        # immediately visible to the app's normal polling cycle.
        self.din_device = MockDevice(din_ip)
        self.dout_device = MockDevice(dout_ip)
        self._quido_out_config = quido_out_config

        self._input_checkboxes = {}
        self._output_labels = {}
        self._build_ui(quido_in_config, quido_out_config)

        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setInterval(500)
        self._refresh_timer.timeout.connect(self._refresh_outputs)
        self._refresh_timer.start()
        self._refresh_outputs()

    def _build_ui(self, quido_in_config, quido_out_config):
        layout = QVBoxLayout(self)

        inputs_group = QGroupBox("Inputs")
        inputs_layout = QVBoxLayout(inputs_group)
        for name, index_str in self._sorted_by_number(quido_in_config):
            index = int(index_str)
            checkbox = QCheckBox(name)
            checkbox.stateChanged.connect(
                lambda state, i=index: self.din_device.set_mock_input(i, state == QtCore.Qt.Checked)
            )
            inputs_layout.addWidget(checkbox)
            self._input_checkboxes[index] = checkbox
        layout.addWidget(inputs_group)

        outputs_group = QGroupBox("Outputs")
        outputs_layout = QVBoxLayout(outputs_group)
        for name, relay_str in self._sorted_by_number(quido_out_config):
            relay = int(relay_str)
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            row.addStretch()
            state_label = QLabel("OFF")
            row.addWidget(state_label)
            outputs_layout.addLayout(row)
            self._output_labels[relay] = state_label
        layout.addWidget(outputs_group)

        buttons_row = QHBoxLayout()
        reset_inputs_btn = QPushButton("Reset inputs")
        reset_inputs_btn.clicked.connect(self._reset_inputs)
        reset_all_btn = QPushButton("Reset all")
        reset_all_btn.clicked.connect(self._reset_all)
        buttons_row.addWidget(reset_inputs_btn)
        buttons_row.addWidget(reset_all_btn)
        layout.addLayout(buttons_row)

    @staticmethod
    def _sorted_by_number(config_section):
        try:
            return sorted(config_section.items(), key=lambda kv: int(kv[1]))
        except (TypeError, ValueError) as e:
            logger.warning(f"QUIDO Simulator: invalid config entry, using unsorted order: {e}")
            return list(config_section.items())

    def _refresh_outputs(self):
        states = self.dout_device.get_outputs_state()
        for relay, label in self._output_labels.items():
            state = 0 <= relay - 1 < len(states) and states[relay - 1]
            label.setText("ON" if state else "OFF")
            label.setStyleSheet("color: green; font-weight: bold;" if state else "color: gray;")

    def _reset_inputs(self):
        self.din_device.reset_inputs()
        for checkbox in self._input_checkboxes.values():
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)

    def _reset_all(self):
        self.din_device.reset_all()
        self.dout_device.reset_all()
        self._reset_inputs()
        self._refresh_outputs()
