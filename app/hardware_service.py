"""Hardware access layer for QUIDO I/O modules.

Selects the real or mock QUIDO implementation based on [DEV] mock_quido
and exposes config-driven read/write operations, so MainWindow never
constructs quido.Device / mock_quido.Device itself.

Each plain method opens a fresh connection and always disconnects before
returning (also after an error), matching the per-poll-tick / per-click
pattern. HW-READ-04: the emergency sequence uses output_session() instead -
ONE QUIDO Output connection for all its SETs and the read-back, with a
bounded reconnect, because the real QUIDO Output refuses a new TCP
connection opened right after the previous one closed (verified on the
device: an immediate reconnect -> Connection refused, ~1 s later OK).
HW-OUT-TOGGLE-01: the manual relay click goes the same way
(set_output_reliable) - an explicit SET instead of toggle_output(), whose
fresh connection right after an Output poll was refused at random.
"""
import socket
import time

from quido import Device as RealQuidoDevice
from mock_quido import Device as MockQuidoDevice
from logger_config import logger


def _disconnect(device):
    """Close a device connection; a failure to close never hides the result
    or the real error of the operation."""
    try:
        device.disconnect()
    except Exception as e:
        logger.warning(f"QUIDO disconnect failed: {e}")


OUTPUT_CONNECT_ATTEMPTS = 3        # per operation: attempt, wait, attempt, wait, last attempt
OUTPUT_SESSION_MAX_CONNECTS = 5    # connection attempts for a whole session, never more
OUTPUT_RECONNECT_WAIT = 1.0        # s - the real QUIDO Output refuses an immediate reconnect


class OutputSession:
    """One QUIDO Output connection reused for several operations.

    - The connection is opened lazily. A failed connect (OSError, e.g.
      Connection refused) is retried after `wait` s, at most `attempts`
      times per operation and `max_connects` times per session - never an
      endless loop; then the operation raises ConnectionError.
    - When an operation fails on the open connection, the connection is
      closed and the error raised: the caller records it for that step and
      goes on; the next operation waits and reconnects (bounded as above).
      A failed SET is never repeated - its result is judged by the read-back.
    - Only explicit SET (set_outputs_state) and read - never a toggle.
    """

    def __init__(self, service, attempts, max_connects, wait):
        self.service = service
        self.attempts = attempts
        self.max_connects = max_connects
        self.wait = wait
        self.device = None
        self.connects = 0          # connection attempts made so far
        self.connected = 0         # successful connections
        self._wait_first = False   # the previous connection just broke

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def _connect(self):
        last_error = None
        for attempt in range(self.attempts):
            if self.connects >= self.max_connects:
                break
            if attempt or self._wait_first:
                self.service.sleep(self.wait)
            self._wait_first = False
            self.connects += 1
            try:
                self.device = self.service.device_class(self.service.dout_ip)
                self.connected += 1
                return self.device
            except OSError as e:
                last_error = e
                logger.warning(f"QUIDO Output connect attempt {self.connects} failed: {e}")
        self._wait_first = True
        raise ConnectionError(f"QUIDO Output not connected after {self.connects} attempt(s): {last_error}")

    def _run(self, operation):
        device = self.device or self._connect()
        try:
            return operation(device)
        except Exception:
            self.close()          # a failed operation may leave the stream unusable
            self._wait_first = True
            raise

    def set_outputs(self, states: dict) -> None:
        """Explicit SET of {name: state} - one Spinel command on this connection."""
        if not states:
            return
        commands = self.service._output_commands(states)
        self._run(lambda device: device.set_outputs_state(*commands))

    def read_outputs(self) -> dict:
        """{relay_name: bool} per QUIDO_OUT, read on this connection."""
        return self.service._named_outputs(self._run(lambda device: device.get_outputs_state()))

    def close(self):
        if self.device is not None:
            _disconnect(self.device)
            self.device = None


class HardwareService:
    def __init__(self, conf: dict, device_class=None):
        self.mock_mode = bool(conf.get('DEV', {}).get('mock_quido', False))
        self.device_class = device_class or (MockQuidoDevice if self.mock_mode else RealQuidoDevice)
        quido_conf = conf.get('QUIDO', {})
        self.din_ip = quido_conf.get('din')
        self.dout_ip = quido_conf.get('dout')
        self.quido_in_config = conf.get('QUIDO_IN', {})    # {floor_name: "0".."9"}, 0-based
        self.quido_out_config = conf.get('QUIDO_OUT', {})  # {name: "1".."16"}, 1-based
        self.sleep = time.sleep  # output_session() reconnect wait - tests replace it

    def is_reachable(self, ip: str, port: int = 10001) -> bool:
        """TCP connect/close test. HW-READ-01: NOT used by the app any more and
        must never run right before Spinel communication - a real QUIDO drops
        the Spinel read/write that follows a connect/close on port 10001
        (verified on the device: test + immediate read 3x FAIL, read alone or
        test + 0.5 s + read 3x OK). A Spinel operation is its own test."""
        if self.mock_mode:
            return bool(ip)
        if not ip:
            return False
        try:
            with socket.create_connection((ip, port), timeout=0.5):
                return True
        except OSError:
            return False

    def read_input_states(self) -> list:
        """All QUIDO Input states (0-based) - one Spinel 0x31 read."""
        qin = self.device_class(self.din_ip)
        try:
            return qin.get_inputs_state()
        finally:
            _disconnect(qin)

    def read_inputs(self) -> dict:
        """{floor_name: bool}, per QUIDO_IN (0-based index into get_inputs_state())."""
        return self.map_inputs(self.read_input_states())

    def map_inputs(self, states) -> dict:
        """{floor_name: bool} per QUIDO_IN from all Input states - no I/O."""
        result = {}
        for floor, relay_str in self.quido_in_config.items():
            try:
                relay = int(relay_str)
                if 0 <= relay < len(states):
                    result[floor] = states[relay]
                else:
                    logger.warning(f"Invalid relay configuration for {floor}: index {relay} out of range")
            except ValueError as e:
                logger.warning(f"Invalid relay configuration for {floor}: {e}")
        return result

    def read_output_states(self) -> list:
        """All QUIDO Output states (index 0 = relay 1) - one Spinel 0x30 read."""
        qout = self.device_class(self.dout_ip)
        try:
            return qout.get_outputs_state()
        finally:
            _disconnect(qout)

    def read_outputs(self) -> dict:
        """{relay_name: bool}, per QUIDO_OUT (1-based index into get_outputs_state())."""
        return self._named_outputs(self.read_output_states())

    def map_outputs(self, states) -> dict:
        """{relay_name: bool} per QUIDO_OUT from all Output states - no I/O."""
        return self._named_outputs(states)

    def _named_outputs(self, states) -> dict:
        return {
            name: states[int(relay_str) - 1]
            for name, relay_str in self.quido_out_config.items()
        }

    def _output_commands(self, states: dict) -> list:
        """Signed relay numbers for set_outputs_state: +relay = on, -relay = off.
        KeyError for a name missing from QUIDO_OUT (before any connection)."""
        return [int(self.quido_out_config[name]) * (1 if state else -1)
                for name, state in states.items()]

    def toggle_output(self, relay: int) -> bool:
        """Toggle a 1-based relay; return the new state (True = on)."""
        qout = self.device_class(self.dout_ip)
        try:
            state = qout.get_output_state(relay)
            if state:
                qout.set_output_off(relay)
            else:
                qout.set_output_on(relay)
        finally:
            _disconnect(qout)
        return not state

    def set_outputs(self, states: dict) -> None:
        """EMERGENCY-01: set each QUIDO_OUT output in {name: state} to exactly
        that state (True = relay on) with ONE connection and ONE Spinel
        "set outputs" command (quido.Device.set_outputs_state: +relay = on,
        -relay = off). Never reads or inverts the current state, so a
        repeated call is a no-op. Raises KeyError for a name missing from
        QUIDO_OUT (before connecting) and whatever the device raises."""
        if not states:
            return
        commands = self._output_commands(states)
        qout = self.device_class(self.dout_ip)
        try:
            qout.set_outputs_state(*commands)
        finally:
            _disconnect(qout)

    def set_output(self, name: str, state: bool) -> None:
        """Set one QUIDO_OUT output to exactly `state` - see set_outputs()."""
        self.set_outputs({name: state})

    def set_output_reliable(self, name: str, state: bool) -> None:
        """HW-OUT-TOGGLE-01: the manual relay click - set one QUIDO_OUT output
        to exactly `state` through an OutputSession (no GET, no invert, so
        idempotent). A refused connect - before any command was sent - is
        retried after OUTPUT_RECONNECT_WAIT (bounded); once connected the SET
        runs once and is never repeated after an error: the error goes to
        the caller and the following Output read shows the real state.
        KeyError for a name missing from QUIDO_OUT (before connecting)."""
        with self.output_session() as session:
            session.set_outputs({name: state})

    def output_session(self, attempts=OUTPUT_CONNECT_ATTEMPTS, max_connects=OUTPUT_SESSION_MAX_CONNECTS,
                       wait=OUTPUT_RECONNECT_WAIT):
        """HW-READ-04: one QUIDO Output connection for a sequence of SETs and
        a read-back (the emergency sequence) - see OutputSession."""
        return OutputSession(self, attempts, max_connects, wait)

    def close(self):
        """Release hardware-protocol resources on app shutdown (real mode only)."""
        if self.mock_mode:
            return
        try:
            import pyspinel
            pyspinel.close_log()
        except Exception as e:
            logger.error(f"Error closing Spinel 97 log: {e}")
