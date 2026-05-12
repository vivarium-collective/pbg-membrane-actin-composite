"""build_core() for the membrane-actin composite.

Allocates a process-bigraph core, registers the RAMEmitter (which is not
a pbg-* package, so allocate_core won't auto-discover it), and returns
the core. Mem3DGProcess, ReaDDyProcess, and BrownianRatchetCoupler are
all installed as pip-discoverable distributions and register
automatically — explicit register_link() calls would be redundant
boilerplate per the pbg-superpowers convention.
"""

from __future__ import annotations

from process_bigraph import allocate_core
from process_bigraph.emitter import RAMEmitter


def build_core():
    core = allocate_core()
    core.register_link('ram-emitter', RAMEmitter)
    return core
