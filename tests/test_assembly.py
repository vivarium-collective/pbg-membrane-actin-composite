"""Schema-reconciliation tests — instantiate the Composite without running it.

If `Composite(...)` raises, the wiring table in document.py declared a
schema mismatch between two ports that should be pass-through. Catching
that here is much cheaper than catching it from a 60s ReaDDy run.
"""

from __future__ import annotations

from process_bigraph import Composite

from pbg_membrane_actin_composite import build_core, build_document


def test_closed_loop_assembles():
    core = build_core()
    Composite({'state': build_document(closed_loop=True)}, core=core)


def test_open_loop_assembles():
    core = build_core()
    Composite({'state': build_document(closed_loop=False)}, core=core)


def test_overrides_assemble():
    """Confirm the demo-tunable knobs all reconcile cleanly."""
    core = build_core()
    Composite({
        'state': build_document(
            interval=0.25,
            closed_loop=True,
            contact_threshold=0.3,
            force_constant=2.5,
            osmotic_force_scale=0.1,
            growth_rate=8.0,
        )
    }, core=core)
