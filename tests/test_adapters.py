"""Unit tests for BrownianRatchetCoupler in isolation (no Composite).

The coupler is the only adapter/stub Process introduced by this composite.
Test it directly against synthetic inputs so failures don't entangle with
the wrapped simulators.
"""

from __future__ import annotations

import pytest
from process_bigraph import allocate_core

from pbg_membrane_actin_composite import BrownianRatchetCoupler


@pytest.fixture
def core():
    return allocate_core()


def test_coupler_autoregistered(core):
    assert 'BrownianRatchetCoupler' in core.link_registry


def test_inputs_outputs_shape(core):
    c = BrownianRatchetCoupler(config={}, core=core)
    assert c.inputs() == {
        'actin_positions': 'list',
        'membrane_vertices': 'list',
    }
    out = c.outputs()
    for port in ['wall_z', 'osmotic_strength_offset', 'contact_force',
                 'actin_max_z', 'membrane_min_z', 'gap', 'ratchet_steps']:
        assert port in out


def test_empty_inputs_emit_initial_barrier(core):
    """Before either upstream simulator publishes, coupler must publish
    the barrier's *initial* position (`barrier_initial_z` - `wall_offset`)
    so ReaDDy gets the correct confinement on the very first step. No
    contact force, no osmotic offset (nothing to push against yet).
    """
    c = BrownianRatchetCoupler(
        config={'barrier_initial_z': 5.0, 'wall_offset': 0.1},
        core=core,
    )
    r = c.update({'actin_positions': [], 'membrane_vertices': []}, interval=1.0)
    assert r['wall_z'] == pytest.approx(5.0 - 0.1)
    assert r['osmotic_strength_offset'] == 0.0
    assert r['contact_force'] == 0.0
    assert r['ratchet_steps'] == 0


def test_no_contact_emits_zero_force(core):
    """Membrane high above actin tip — gap > threshold, no ratchet event.
    wall_z still emitted (closed_loop default True)."""
    c = BrownianRatchetCoupler(config={}, core=core)
    r = c.update({
        'actin_positions': [[0, 0, -3.0], [0, 0, -2.5]],
        'membrane_vertices': [[0, 0, 1.0], [0, 0, 2.0]],
    }, interval=1.0)
    assert r['gap'] == pytest.approx(3.5)
    assert r['contact_force'] == 0.0
    assert r['ratchet_steps'] == 0
    assert r['wall_z'] == pytest.approx(1.0 - 0.05)
    assert r['osmotic_strength_offset'] == 0.0


def test_contact_emits_proportional_force(core):
    """Actin tip overlaps membrane bottom — force = k * (threshold - gap).
    Both wall_z and osmotic_offset must be non-zero in closed loop."""
    c = BrownianRatchetCoupler(
        config={'contact_threshold': 1.0, 'force_constant': 2.0,
                'osmotic_force_scale': 0.1},
        core=core,
    )
    r = c.update({
        'actin_positions': [[0, 0, 0.5]],
        'membrane_vertices': [[0, 0, 0.0]],
    }, interval=1.0)
    # gap = 0.0 - 0.5 = -0.5; force = 2.0 * (1.0 - (-0.5)) = 3.0
    assert r['gap'] == pytest.approx(-0.5)
    assert r['contact_force'] == pytest.approx(3.0)
    assert r['osmotic_strength_offset'] == pytest.approx(0.3)
    assert r['ratchet_steps'] == 1


def test_open_loop_emits_no_back_signals(core):
    """closed_loop=False: coupler still computes the diagnostic gap/force,
    but does NOT publish wall_z or osmotic_offset. This is the
    decoupled-baseline scenario for the demo."""
    c = BrownianRatchetCoupler(config={'closed_loop': False}, core=core)
    r = c.update({
        'actin_positions': [[0, 0, 0.5]],
        'membrane_vertices': [[0, 0, 0.0]],
    }, interval=1.0)
    assert r['gap'] == pytest.approx(-0.5)
    assert r['contact_force'] > 0.0
    # But the back-signals stay neutral.
    assert r['wall_z'] is None
    assert r['osmotic_strength_offset'] == 0.0


def test_ratchet_steps_accumulate_across_calls(core):
    """ratchet_steps is the per-call delta (additive integer port). The
    Process instance tracks cumulative count internally. Two contact
    events => instance counter = 2; the published deltas sum to 2."""
    c = BrownianRatchetCoupler(config={}, core=core)
    r1 = c.update({
        'actin_positions': [[0, 0, 0]], 'membrane_vertices': [[0, 0, 0]],
    }, interval=1.0)
    r2 = c.update({
        'actin_positions': [[0, 0, 0.1]], 'membrane_vertices': [[0, 0, 0]],
    }, interval=1.0)
    assert r1['ratchet_steps'] == 1
    assert r2['ratchet_steps'] == 1
    assert c._ratchet_steps == 2  # internal cumulative
