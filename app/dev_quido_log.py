"""DEV-LOG-01: QUIDO diagnostics log of one ./bin/polygon --dev run.

log/dev_quido_YYYY-MM-DD_HHMMSS.log - the run's mode and configuration
(KONFIG: whitelisted keys only, never credentials), every change of all 104 raw Inputs
(mapped or not), every Output change seen in a read (read-back), the
operator's relay clicks and their write result, QUIDO module OK/UNKNOWN
transitions, and a summary at shutdown: which mapped inputs reacted (how
often, in what order), which never changed, what stayed ACTIVE, which
unmapped inputs moved, per relay clicks / confirmed transitions / errors.

Only data the DEV tab already gets: DevQuidoTab passes on the reads of the
existing quido-in / quido-out workers, MainWindow the relay clicks. Nothing
here talks to QUIDO. A file that can't be opened or written is a warning in
polygon.log - the DEV diagnostics, the QUIDO workers and the GUI go on.
Each line is flushed (usable after a crash), no fsync.

Input polarity as on the map: QUIDO True = idle, False = ACTIVE (step).
"Without a single change" is diagnostic information for the physical walk,
not a verdict that the sensor is faulty.
"""

import os
from datetime import datetime

from logger_config import LOG_DIR, logger

IDLE_TEXT, ACTIVE_TEXT, UNKNOWN_TEXT = "idle", "ACTIVE", "?"
UNMAPPED = "UNMAPPED"


# KONFIG lines: only these keys are ever written - a whitelist, never whole
# sections, so no password, user name or camera URL (RTSP URLs carry
# credentials) can get into the DEV log. [QUIDO_IN] / [QUIDO_OUT] are
# written whole: names and numbers only.
CONFIG_KEYS = (
    ("DEV", ("mock_quido", "skip_login", "mock_camera")),
    ("MYSQL", ("host", "database")),
    ("QUIDO", ("din", "dout")),
    ("EMERGENCY", ("louver_open_relay",)),
    ("AUDIO", ("disable",)),
    ("PROTOCOL", ("disable",)),
    ("CAMERA", ("disable", "display_mode", "recording_fps")),
    ("REPORT_EMAIL", ("enabled", "allow_dev")),
)
MAPPING_SECTIONS = ("QUIDO_IN", "QUIDO_OUT")


def _number_key(item):
    name, value = item
    try:
        return int(value), name
    except (TypeError, ValueError):
        return 10 ** 6, name


def config_lines(conf, runtime=()):
    """Texts of the KONFIG lines: `runtime` [(label, value)] first (what
    really runs), then the whitelisted config keys and the QUIDO mappings."""
    lines = [f"{label}: {value}" for label, value in runtime]
    for section, keys in CONFIG_KEYS:
        values = conf.get(section)
        if values is None:
            lines.append(f"[{section}] chybí")
            continue
        shown = ", ".join(f"{key}={values[key]}" for key in keys if key in values)
        lines.append(f"[{section}] {shown or '(žádný ze sledovaných klíčů)'}")
    for section in MAPPING_SECTIONS:
        values = conf.get(section) or {}
        pairs = ", ".join(f"{name}={value}" for name, value in sorted(values.items(), key=_number_key))
        lines.append(f"[{section}] {len(values)} položek: {pairs or '—'}")
    return lines


def log_path(started_at, directory=LOG_DIR) -> str:
    return os.path.join(directory, f"dev_quido_{started_at:%Y-%m-%d_%H%M%S}.log")


def _input_text(value):
    if value is None:
        return UNKNOWN_TEXT
    return IDLE_TEXT if value else ACTIVE_TEXT


def _output_text(value):
    if value is None:
        return UNKNOWN_TEXT
    return "ON" if value else "OFF"


class DevQuidoLog:
    """input_names {0-based input: "floor_46 / floor_55"}, input_labels
    {0-based input: "Čidlo 46 / Čidlo 55"}, output_names {relay: name}."""

    def __init__(self, input_names, input_labels, output_names, input_count, output_count,
                 path=None, clock=datetime.now, opener=open):
        self._input_names = dict(input_names)
        self._input_labels = dict(input_labels)
        self._output_names = dict(output_names)
        self._input_count = input_count
        self._output_count = output_count
        self._clock = clock
        self.path = path or log_path(clock())
        self._file = None
        self._finished = False
        self._status = {"IN": None, "OUT": None}
        self._inputs = None
        self._outputs = None
        self._first_inputs = None
        self._input_changes = {}      # input -> number of changes
        self._first_reaction = {}     # input -> time of its first change
        self._clicks = {}             # relay -> clicks
        self._transitions = {}        # relay -> confirmed read-back changes
        self._failures = {}           # relay -> failed writes
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            self._file = opener(self.path, "a", encoding="utf-8", buffering=1)
        except Exception as e:
            logger.warning(f"DEV-LOG: {self.path} can't be opened ({type(e).__name__}) - "
                           "DEV diagnostics go on without the file")
            self._file = None

    @property
    def active(self) -> bool:
        return self._file is not None

    def _write(self, text):
        if self._file is None:
            return
        try:
            self._file.write(f"{self._clock():%H:%M:%S.%f}"[:-3] + f" {text}\n")
            self._file.flush()
        except Exception as e:
            logger.warning(f"DEV-LOG: writing {self.path} failed ({type(e).__name__}) - file log stopped")
            self._close()

    def _close(self):
        file, self._file = self._file, None
        if file is not None:
            try:
                file.close()
            except Exception:
                pass

    def _input_name(self, index):
        name = self._input_names.get(index)
        if name is None:
            return UNMAPPED
        label = self._input_labels.get(index)
        return f"{name} {label}" if label else name

    def _output_name(self, relay):
        return self._output_names.get(relay, "—")

    # -- events ---------------------------------------------------------------

    def start(self, din, dout):
        self._write(f"START  DEV-LOG-01, QUIDO IN {din} / OUT {dout}, {self._input_count} vstupů "
                    f"({len(self._input_names)} namapovaných), {self._output_count} výstupů "
                    f"({len(self._output_names)} namapovaných)")

    def config(self, conf, runtime=()):
        """The run's mode and configuration (whitelisted, no credentials)."""
        try:
            for line in config_lines(conf, runtime):
                self._write(f"KONFIG {line}")
        except Exception as e:
            logger.warning(f"DEV-LOG: config record failed ({type(e).__name__})")

    def _module(self, module, ok):
        state = "OK" if ok else "UNKNOWN"
        previous = self._status[module]
        if previous != state:
            self._write(f"STAV   QUIDO {module} {previous or 'ČEKÁ'} -> {state}")
            self._status[module] = state

    def inputs(self, states):
        """All Input states of one read (None = the read failed)."""
        try:
            self._module("IN", states is not None)
            if states is None:
                return
            values = [bool(v) for v in list(states)[:self._input_count]]
            if self._inputs is None:
                self._first_inputs = values
                mapped = [f"IN {i:03d} {self._input_name(i)}" for i, v in enumerate(values)
                          if v is False and i in self._input_names]
                unmapped = [f"{i:03d}" for i, v in enumerate(values) if v is False and i not in self._input_names]
                self._write("SNAP   IN ACTIVE v klidu (namapované): " + (", ".join(mapped) or "žádný"))
                self._write("SNAP   IN ACTIVE v klidu (nenamapované, mohou být nezapojené): "
                            + (", ".join(unmapped) or "žádný"))
            else:
                now = self._clock()
                for index, (old, new) in enumerate(zip(self._inputs, values)):
                    if old != new:
                        self._input_changes[index] = self._input_changes.get(index, 0) + 1
                        self._first_reaction.setdefault(index, now)
                        self._write(f"IN {index:03d} {self._input_name(index)} "
                                    f"{_input_text(old)} -> {_input_text(new)}")
            self._inputs = values
        except Exception as e:
            logger.warning(f"DEV-LOG: input record failed ({type(e).__name__})")

    def outputs(self, states):
        """All Output states of one read (None = the read failed)."""
        try:
            self._module("OUT", states is not None)
            if states is None:
                return
            values = [bool(v) for v in list(states)[:self._output_count]]
            if self._outputs is None:
                on = [f"{i + 1} {self._output_name(i + 1)}" for i, v in enumerate(values) if v]
                self._write("SNAP   OUT ON: " + (", ".join(on) or "žádný"))
            else:
                for index, (old, new) in enumerate(zip(self._outputs, values)):
                    if old != new:
                        relay = index + 1
                        self._transitions[relay] = self._transitions.get(relay, 0) + 1
                        self._write(f"OUT {relay:02d} {self._output_name(relay)} "
                                    f"{_output_text(old)} -> {_output_text(new)} (read-back)")
            self._outputs = values
        except Exception as e:
            logger.warning(f"DEV-LOG: output record failed ({type(e).__name__})")

    def _known_output(self, relay):
        if self._outputs is None or not 0 < relay <= len(self._outputs):
            return None
        return self._outputs[relay - 1]

    def click(self, relay):
        """The operator clicked relay `relay` (1-based) in the normal GUI."""
        self._clicks[relay] = self._clicks.get(relay, 0) + 1
        self._write(f"KLIK   relé {relay} {self._output_name(relay)} "
                    f"(předchozí známý stav {_output_text(self._known_output(relay))})")

    def click_ignored(self, relay, reason):
        self._write(f"KLIK   relé {relay} {self._output_name(relay)} ignorován ({reason})")

    def write_done(self, relay, error=None):
        """The write of a clicked relay finished: error = its exception or None."""
        if error is None:
            self._write(f"ZÁPIS  relé {relay} {self._output_name(relay)} odeslán, čeká na read-back")
        else:
            self._failures[relay] = self._failures.get(relay, 0) + 1
            self._write(f"CHYBA  relé {relay} {self._output_name(relay)} zápis selhal ({type(error).__name__})")

    # -- summary ----------------------------------------------------------------

    def summary_lines(self):
        mapped = sorted(self._input_names)
        reacted = [i for i in mapped if self._input_changes.get(i)]
        first = self._first_inputs or []
        stuck = [i for i in mapped if not self._input_changes.get(i) and i < len(first) and first[i] is False]
        unchanged = [i for i in mapped if not self._input_changes.get(i) and i not in stuck]
        unmapped = sorted(i for i in self._input_changes if i not in self._input_names)

        def names(indexes):
            return ", ".join(f"{self._input_names[i]} (IN {i:03d})" for i in indexes) or "žádný"

        lines = ["=== SOUHRN VSTUPŮ ==="]
        if self._first_inputs is None:
            lines.append("žádný úspěšný snapshot vstupů - souhrn nelze sestavit")
        else:
            lines += [
                "reagovala: " + (", ".join(f"{self._input_names[i]} ×{self._input_changes[i]}" for i in reacted)
                                 or "žádný"),
                "BEZ JEDINÉ ZMĚNY (idle celou dobu): " + names(unchanged),
                "trvale ACTIVE od prvního snapshotu: " + names(stuck),
                "NENAMAPOVANÉ INPUTY SE ZMĚNOU: " + (", ".join(f"IN {i:03d} ×{self._input_changes[i]}"
                                                            for i in unmapped) or "žádný"),
                "pořadí první reakce:",
            ]
            for index, when in sorted(self._first_reaction.items(), key=lambda item: (item[1], item[0])):
                name = self._input_names.get(index, UNMAPPED)
                lines.append(f"  {name} (IN {index:03d}) {when:%H:%M:%S.%f}"[:-3])
            lines.append("Pozn.: „bez jediné změny“ neznamená vadné čidlo - jen diagnostika fyzického průchodu.")
        lines.append("=== SOUHRN VÝSTUPŮ ===")
        relays = sorted(set(self._output_names) | set(self._clicks) | set(self._transitions) | set(self._failures))
        for relay in relays:
            lines.append(f"relé {relay:2d} {self._output_name(relay):<18} kliknutí {self._clicks.get(relay, 0)}, "
                         f"potvrzené přechody {self._transitions.get(relay, 0)}, chyby {self._failures.get(relay, 0)}")
        return lines

    def finish(self):
        """Summary + close; once (later calls do nothing)."""
        if self._finished:
            return
        self._finished = True
        try:
            for line in self.summary_lines():
                self._write(line)
            self._write("KONEC")
        except Exception as e:
            logger.warning(f"DEV-LOG: summary failed ({type(e).__name__})")
        self._close()
