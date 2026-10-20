"""Mock QUIDO device for development without physical QUIDO hardware.

Mirrors the public interface of quido.Device (get/set inputs and outputs)
so app/main.py can use either implementation interchangeably. State is
shared per (ip, port), because main.py creates a fresh Device(ip) instance
on every poll cycle - without shared state each poll would see a freshly
reset device.

No network I/O is ever performed here; this module must stay completely
isolated from the real QUIDO hardware.
"""

import threading

# Spinel addresses one input/output with a 7-bit number (1-127), see
# quido.py's set_outputs_state(). 128 slots covers that whole range.
_STATE_SIZE = 128

_registry_lock = threading.Lock()
_registry = {}


class _MockDeviceState:
    """Shared, thread-safe state for one simulated QUIDO module."""

    def __init__(self):
        self._lock = threading.Lock()
        self.inputs = [False] * _STATE_SIZE
        self.outputs = [False] * _STATE_SIZE

    def get_inputs(self):
        with self._lock:
            return list(self.inputs)

    def get_outputs(self):
        with self._lock:
            return list(self.outputs)

    def set_input(self, index, state):
        with self._lock:
            self.inputs[index] = bool(state)

    def set_output(self, index, state):
        with self._lock:
            self.outputs[index] = bool(state)

    def reset_inputs(self):
        with self._lock:
            self.inputs = [False] * _STATE_SIZE

    def reset_outputs(self):
        with self._lock:
            self.outputs = [False] * _STATE_SIZE


def _get_state(ip, port):
    key = (ip, port)
    with _registry_lock:
        state = _registry.get(key)
        if state is None:
            state = _MockDeviceState()
            _registry[key] = state
        return state


class Device:
    """Drop-in mock replacement for quido.Device.

    Device(ip) instances created for the same (ip, port) share state, the
    same way repeatedly polling the real hardware would observe the same
    device. Input/output numbering matches quido.Device and the app's own
    conventions: get_inputs_state()/set_mock_input() are 0-based (as used
    directly by main.py against QUIDO_IN config values), while the
    output-related methods are 1-based (as used by QUIDO_OUT config values
    and click_button()).
    """

    def __init__(self, ip, port=10001):
        self.ip = ip
        self.port = port
        self._state = _get_state(ip, port)

    def disconnect(self):
        """No-op: the mock never opens a real connection."""
        pass

    # --- quido.Device-compatible API ------------------------------------

    def get_outputs_state(self):
        return self._state.get_outputs()

    def get_output_state(self, output_number):
        return self._state.get_outputs()[output_number - 1]

    def set_outputs_state(self, *outputs_state):
        for value in outputs_state:
            self._state.set_output(abs(value) - 1, value > 0)

    def set_output_on(self, output):
        self._state.set_output(output - 1, True)

    def set_output_off(self, output):
        self._state.set_output(output - 1, False)

    def get_inputs_state(self):
        return self._state.get_inputs()

    def get_input_state(self, input_number):
        return self._state.get_inputs()[input_number - 1]

    def invertState(self, output):
        if self.get_output_state(output):
            self.set_output_off(output)
        else:
            self.set_output_on(output)

    # --- DEV-only helpers, not part of the real quido.Device API --------

    def set_mock_input(self, index, state):
        """Set input at 0-based `index`, matching the QUIDO_IN config convention."""
        self._state.set_input(index, state)

    def reset_inputs(self):
        self._state.reset_inputs()

    def reset_outputs(self):
        self._state.reset_outputs()

    def reset_all(self):
        self.reset_inputs()
        self.reset_outputs()
