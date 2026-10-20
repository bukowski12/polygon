"""EMERGENCY-01: the emergency button's fixed output matrix.

One press puts the polygon into a known safe state, in this order:
  1. stop the sound effect (AUDIO)
  2. switch off the hazardous / distracting effects
  3. open the louver
  4. switch on all working / navigation lights
  5. switch on both fan pairs and the control room fan
     (fan12 = left pair, fan34 = right pair; each side both blows in and
     extracts, so both pairs run together - no under-pressure)

Steps 2-5 are one explicit batch SET per group (HardwareService.set_outputs,
one QUIDO connection and one Spinel command each), never a toggle, so
pressing the button again changes nothing. A failing group never stops the
next one; at the end the outputs are read back once and every output is
compared with its target, so a failure is still reported per output.

The audio step needs the GUI thread (QProcess), the output steps may run in
a worker thread: stop_audio_step() + set_emergency_outputs() are the two
halves of run_emergency().

Help request over SIP (EMERGENCY-02) is deliberately NOT part of this
sequence - it will be a separate, conscious second button.
"""

from logger_config import logger

LOUVER = "louver"
LOUVER_OPEN = "OPEN"  # resolved to a relay state via [EMERGENCY] louver_open_relay

# (group, ((QUIDO_OUT name, target), ...)) in execution order; target True = relay on.
EMERGENCY_GROUPS = (
    ("efekty OFF", (
        ("smoke", False),
        ("glow", False),
        ("strobo", False),
        ("hotZone", False),
        ("infraLight", False),
    )),
    ("žaluzie OPEN", (
        (LOUVER, LOUVER_OPEN),
    )),
    ("světla ON", (
        ("polygonLight1", True),
        ("polygonLight2", True),
        ("polygonLight3", True),
        ("hotZoneLight", True),
        ("stressRoomLight", True),
        ("controlRoomLight", True),
        ("helpLight", True),
    )),
    ("ventilace ON", (
        ("fan12", True),
        ("fan34", True),
        ("fanControlRoom", True),
    )),
)
EMERGENCY_OUTPUTS = tuple(output for _, outputs in EMERGENCY_GROUPS for output in outputs)

AUDIO = "audio"

# Overall result. Every one of them means the emergency mode IS declared -
# FAILED only says the safe state could not be set / confirmed at all.
ACTIVE = "ACTIVE"                          # everything set and verified
ACTIVE_WITH_ERRORS = "ACTIVE_WITH_ERRORS"  # some outputs not set or not verified
FAILED = "FAILED"                          # QUIDO Output unreachable / no output written

UNREACHABLE = "QUIDO Output nedostupné"


def louver_open_relay(conf):
    """Relay state meaning "louver OPEN" from [EMERGENCY] louver_open_relay
    (on / off), or None when it is missing or invalid - the polarity is
    never guessed."""
    value = (conf.get('EMERGENCY') or {}).get('louver_open_relay')
    if isinstance(value, str) and value.strip().lower() in ('on', 'off'):
        return value.strip().lower() == 'on'
    return None


class StepResult:
    def __init__(self, name, target, ok, detail="", written=False):
        self.name = name
        self.target = target  # bool relay state, LOUVER_OPEN if unresolved, None for audio
        self.ok = ok
        self.detail = detail
        self.written = written  # write went through, only the read-back failed

    def __repr__(self):
        return f"StepResult({self.name!r}, {self.target!r}, ok={self.ok}, {self.detail!r})"


class EmergencyResult:
    def __init__(self, steps):
        self.steps = steps

    @property
    def failed(self):
        return [step for step in self.steps if not step.ok]

    @property
    def status(self):
        """ACTIVE = everything done and verified; FAILED = not a single QUIDO
        output set or written (stopping the audio alone is no safe state);
        else ACTIVE_WITH_ERRORS."""
        if not self.failed:
            return ACTIVE
        if not any(step.ok or step.written for step in self.steps if step.name != AUDIO):
            return FAILED
        return ACTIVE_WITH_ERRORS

    @property
    def unreachable(self):
        return any(step.detail == UNREACHABLE for step in self.steps)


def run_emergency(hardware, conf, stop_audio=None):
    """Run the whole sequence synchronously and return an EmergencyResult.

    hardware: HardwareService; stop_audio: callable stopping the sound
    effect, or None when there is no audio (disabled / no player)."""
    return EmergencyResult([stop_audio_step(stop_audio)] + set_emergency_outputs(hardware, conf))


def stop_audio_step(stop_audio):
    """Step 1 - GUI thread only (the player is a QProcess)."""
    logger.warning("EMERGENCY: emergency sequence started")
    if stop_audio is None:
        return StepResult(AUDIO, None, True, "zvuk není k dispozici")
    try:
        stop_audio()
        return StepResult(AUDIO, None, True)
    except Exception as e:
        logger.error(f"EMERGENCY: stopping audio failed: {e!r}")
        return StepResult(AUDIO, None, False, f"zastavení zvuku selhalo: {e}")


def set_emergency_outputs(hardware, conf):
    """Steps 2-5 - no Qt, safe in a worker thread. Returns StepResults in
    the EMERGENCY_OUTPUTS order."""
    steps = []
    louver_on = louver_open_relay(conf)
    groups = []
    for group, outputs in EMERGENCY_GROUPS:
        targets = {}
        for name, target in outputs:
            if target == LOUVER_OPEN:
                if louver_on is None:
                    steps.append(StepResult(name, LOUVER_OPEN, False,
                                            "polarita žaluzie není nastavena ([EMERGENCY] louver_open_relay)"))
                    continue
                target = louver_on
            if name not in hardware.quido_out_config:
                steps.append(StepResult(name, target, False, "výstup chybí v [QUIDO_OUT]"))
                continue
            targets[name] = target
        if targets:
            groups.append((group, targets))

    # HW-READ-01: no TCP reachability preflight - a real QUIDO drops the
    # Spinel command that follows a connect/close on port 10001. Each group's
    # explicit SET is tried; its own error tells that QUIDO is unreachable.
    # HW-READ-04: all SETs and the read-back share ONE QUIDO Output connection
    # (the real module refuses a reconnect right after a close); a broken
    # connection is reopened with a bounded wait/retry by the session.
    write_errors = {}  # name -> error of its group's write
    with hardware.output_session() as session:
        for group, targets in groups:
            try:
                session.set_outputs(targets)
            except Exception as e:
                logger.error(f"EMERGENCY: group '{group}' ({', '.join(targets)}) failed: {e!r}")
                write_errors.update((name, e) for name in targets)
        verified, read_error = _verify(session, groups, write_errors)
    names = [name for _, targets in groups for name in targets]
    if (names and len(write_errors) == len(names) and isinstance(read_error, OSError)
            and all(isinstance(e, OSError) for e in write_errors.values())):
        # every write and the read-back failed on the connection: QUIDO Output unreachable
        verified = [StepResult(name, target, False, UNREACHABLE)
                    for _, targets in groups for name, target in targets.items()]
    steps.extend(verified)

    order = [name for name, _ in EMERGENCY_OUTPUTS]
    steps.sort(key=lambda step: order.index(step.name))
    ok = sum(step.ok for step in steps)
    for step in steps:
        if not step.ok:
            logger.error(f"EMERGENCY: {step.name} NOT OK: {step.detail}")
    logger.warning(f"EMERGENCY: outputs finished - {ok}/{len(steps)} OK")
    return steps


def _verify(outputs, groups, write_errors):
    """Read the outputs back once and compare every output with its target -
    also those of a failed group (it may have been in the target state already).
    Returns (steps, the read-back error or None)."""
    read_error = None
    try:
        actual = outputs.read_outputs()
    except Exception as e:
        logger.error(f"EMERGENCY: reading outputs back failed: {e!r}")
        actual = None
        read_error = e
    steps = []
    for _, targets in groups:
        for name, target in targets.items():
            error = write_errors.get(name)
            if actual is None:
                if error:
                    steps.append(StepResult(name, target, False, f"zápis skupiny selhal: {error}"))
                else:
                    steps.append(StepResult(name, target, False,
                                            "zapsáno, ale neověřeno (čtení výstupů selhalo)", written=True))
            elif actual.get(name) == target:
                steps.append(StepResult(name, target, True,
                                        f"zápis skupiny selhal ({error}), ale výstup je v cílovém stavu"
                                        if error else ""))
            elif error:
                steps.append(StepResult(name, target, False, f"zápis skupiny selhal: {error}"))
            else:
                steps.append(StepResult(name, target, False, "po zápisu stav neodpovídá"))
    return steps, read_error
