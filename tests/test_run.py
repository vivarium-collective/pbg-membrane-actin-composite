"""Integration: run the composite long enough for state to flow through
the full coupling loop — actin → coupler → wall_z → ReaDDy rebuild,
membrane → coupler → osmotic_offset → Mem3DG rebuild — and verify both
sides registered the back-channel."""

from __future__ import annotations

import pytest
from process_bigraph import Composite, gather_emitter_results

from pbg_membrane_actin_composite import build_core, build_document


@pytest.mark.skip(
    reason="Hits ReaDDy's process-global topology rebuild issue when run "
           "alongside other ReaDDy-using tests in the same pytest session. "
           "The full closed-loop coupling is exercised end-to-end by "
           "`python demo/demo_report.py` (each demo run starts in a fresh "
           "process) and verified visually in the generated report."
)
@pytest.mark.timeout(120)
def test_closed_loop_actually_couples():
    """After enough composite steps, the membrane must register a non-zero
    osmotic offset (Mem3DG side received it from the coupler) and ReaDDy
    must register a wall_z (coupler published it). If either is silent,
    the loop is broken."""
    core = build_core()
    sim = Composite({'state': build_document(closed_loop=True, interval=0.5)}, core=core)
    sim.run(2.0)  # 4 composite steps — enough for the lag-1 coupler to fire

    samples = list(gather_emitter_results(sim).values())[0]
    assert len(samples) >= 3
    last = samples[-1]
    # The headline assertions: both back-channels propagated.
    assert last['wall_z'] is not None, 'wall_z never published — coupler→ReaDDy broken'
    assert last['osmotic_offset'] != 0.0, 'osmotic_offset stayed zero — coupler→Mem3DG broken'
    # And at least one ratchet step happened cumulatively across samples.
    total_ratchets = sum(s['ratchet_steps'] for s in samples)
    assert total_ratchets >= 1, 'no ratchet events fired — gap never closed'


@pytest.mark.timeout(120)
def test_open_loop_runs_silently():
    """Decoupled baseline: the simulators run but the back-channels stay
    silent. ratchet diagnostics may still be non-zero (they're computed
    regardless), but wall_z stays None and osmotic_offset stays 0."""
    core = build_core()
    sim = Composite({'state': build_document(closed_loop=False, interval=0.5)}, core=core)
    sim.run(1.5)
    samples = list(gather_emitter_results(sim).values())[0]
    last = samples[-1]
    # In the open-loop case the coupler emits None for wall_z, which the
    # emitter omits entirely from samples. Either condition (missing key
    # OR explicit None) is acceptable.
    assert last.get('wall_z') is None
    assert last['osmotic_offset'] == 0.0
