"""build_core() for the membrane-actin composite.

Allocates a process-bigraph core, registers the RAMEmitter (which is not
a pbg-* package, so allocate_core won't auto-discover it), and returns
the core. Mem3DGProcess, ReaDDyProcess, and BrownianRatchetCoupler are
all installed as pip-discoverable distributions and register
automatically — explicit register_link() calls would be redundant
boilerplate per the pbg-superpowers convention.

Also: when stdout is not a TTY (i.e. captured by the dashboard's
subprocess runner, pytest's capsys, or any other pipe), redirect the
C-level file descriptor 1 to file descriptor 2 so ReaDDy/Mem3DG's
noisy libc-level log lines go to stderr instead of polluting the
``@@@RESULTS@@@`` marker the dashboard parses. Without this redirect,
``json.loads`` of the captured stdout fails with "Extra data" because
ReaDDy's C++ logger writes trailing "Simulation completed" lines after
the Python ``print`` statements have already emitted the JSON payload.
"""

from __future__ import annotations

import os
import sys

from process_bigraph import allocate_core
from process_bigraph.emitter import RAMEmitter


# Module-level idempotency flag. Process-scoped (NOT env-scoped) — so each
# fresh subprocess re-runs the redirect even when spawned from a parent
# that already redirected. An env-var-based flag would leak the
# "already-redirected" state into every child via os.environ inheritance,
# making only the first subprocess get the redirect and breaking every
# subsequent run.
_FD1_ALREADY_REDIRECTED = False


def _redirect_cxx_logs_to_stderr_if_piped() -> None:
    """One-shot fd redirect for non-TTY callers. Idempotent within a process.

    The C++ side of ReaDDy/Mem3DG writes log lines to OS fd 1 via libc.
    When the dashboard's subprocess runner captures stdout with a PIPE,
    those C++ writes end up AFTER our Python `print('@@@RESULTS@@@')`
    in the captured stream because the C++ buffer is flushed at process
    teardown, after Python's exit. The dashboard's
    ``json.loads(out.split('@@@RESULTS@@@', 1)[1].strip())`` then fails
    with "Extra data" because the JSON has trailing log lines after it.

    Fix: duplicate the *original* fd 1 (the pipe back to the dashboard)
    onto a new fd, repoint sys.stdout at the new fd, then ``dup2(2, 1)``
    so OS-level fd 1 is now stderr. Net result:
      - Python's sys.stdout still writes to the original pipe → marker
        and JSON land cleanly in the dashboard's captured stdout.
      - C++ libc writes (ReaDDy/Mem3DG logs) go to fd 1 which is now
        stderr → captured in the dashboard's stderr field, harmless.
    """
    global _FD1_ALREADY_REDIRECTED
    if _FD1_ALREADY_REDIRECTED:
        return
    try:
        if sys.stdout.isatty():
            return
    except (AttributeError, ValueError):
        return
    try:
        sys.stdout.flush()
        new_stdout_fd = os.dup(1)
        os.dup2(2, 1)
        sys.stdout = os.fdopen(new_stdout_fd, "w", buffering=1)
        _FD1_ALREADY_REDIRECTED = True
    except OSError:
        pass


def build_core():
    _redirect_cxx_logs_to_stderr_if_piped()
    core = allocate_core()
    core.register_link('ram-emitter', RAMEmitter)
    return core
