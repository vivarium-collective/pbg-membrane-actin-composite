"""Brownian-ratchet coupler Process for the membrane-actin composite.

Sits between pbg-readdy (actin field, particle positions) and pbg-mem3dg
(triangulated membrane, vertex positions). Each step:

  1. Reads the highest actin-particle z-coordinate (the leading filament tip)
     and the lowest membrane-vertex z-coordinate (the closest part of the
     membrane facing the actin).
  2. Computes the contact gap = membrane_min_z - actin_max_z. Positive gap
     means the membrane is above the actin (no contact); negative or
     small-positive gap means a Brownian ratchet event.
  3. Publishes a `wall_z` setpoint to ReaDDy (≈ membrane_min_z) so the
     particle field is confined below the current membrane position. When
     the membrane lifts, the wall lifts with it — that's the ratchet.
  4. Publishes an `osmotic_strength_offset` to Mem3DG that scales with the
     instantaneous contact force, so the membrane bulges away from regions
     where actin is pushing.
  5. Tracks cumulative `ratchet_steps` (count of update() calls where a
     contact event occurred) and an instantaneous `contact_force` value
     for the demo report.

The coupler is a `Process` (not a Step) so it can run at its own interval
alongside Mem3DG and ReaDDy. All scientific tunables (force scale,
ratchet threshold) live in `config_schema`.
"""

from __future__ import annotations

import numpy as np
from process_bigraph import Process


class BrownianRatchetCoupler(Process):
    """Bidirectional analysis-layer coupler for the membrane-actin demo.

    Inputs
    ------
    actin_positions : list of [x, y, z]
        Live particle positions emitted by ReaDDy.
    membrane_vertices : list of [x, y, z]
        Live mesh vertex positions emitted by Mem3DG.

    Outputs
    -------
    wall_z : maybe[float]
        Membrane-tracking barrier published to ReaDDy's `wall_z` input port.
        None until first input arrives.
    osmotic_strength_offset : float
        Pressure boost published to Mem3DG's `osmotic_strength_offset` input
        port. Bulges the membrane proportionally to contact_force.
    contact_force : float
        Instantaneous magnitude of the spring-model ratchet force. Diagnostic.
    actin_max_z : float
        z-coordinate of the highest actin tip this step. Diagnostic.
    membrane_min_z : float
        z-coordinate of the lowest membrane vertex this step. Diagnostic.
    gap : float
        membrane_min_z - actin_max_z. Negative when actin has crossed the
        membrane (contact), positive when free. Diagnostic.
    ratchet_steps : integer
        Cumulative count of update() calls where a contact event was
        registered (gap < contact_threshold). Diagnostic.
    """

    config_schema = {
        # When the gap drops below this threshold, count it as a ratchet
        # event and apply the contact force model.
        'contact_threshold': {'_type': 'float', '_default': 0.5},
        # Spring constant of the contact-force model: F = k * max(0,
        # contact_threshold - gap).
        'force_constant': {'_type': 'float', '_default': 1.0},
        # Multiplier from contact_force to osmotic_strength_offset. The
        # absolute value depends on Mem3DG's units; the default scales the
        # bulge to a visible level for the included demo configurations.
        'osmotic_force_scale': {'_type': 'float', '_default': 0.05},
        # Wall z-offset published to ReaDDy. The barrier sits this far
        # below the lowest membrane vertex, so the membrane and the wall
        # don't try to occupy the same space.
        'wall_offset': {'_type': 'float', '_default': 0.05},
        # When False, the coupler still computes diagnostics but emits
        # zero osmotic_offset and a static wall_z. Used for the
        # decoupled-baseline demo configuration.
        'closed_loop': {'_type': 'boolean', '_default': True},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._ratchet_steps = 0

    def inputs(self):
        return {
            'actin_positions': 'list',
            'membrane_vertices': 'list',
        }

    def outputs(self):
        return {
            'wall_z': 'maybe[float]',
            'osmotic_strength_offset': 'float',
            'contact_force': 'float',
            'actin_max_z': 'float',
            'membrane_min_z': 'float',
            'gap': 'float',
            'ratchet_steps': 'integer',
        }

    def initial_state(self):
        return {
            'actin_positions': [],
            'membrane_vertices': [],
        }

    def update(self, state, interval):
        actin = state.get('actin_positions') or []
        membrane = state.get('membrane_vertices') or []
        cfg = self.config

        # Default: no information yet, emit neutral signals.
        if not actin or not membrane:
            return {
                'wall_z': None,
                'osmotic_strength_offset': 0.0,
                'contact_force': 0.0,
                'actin_max_z': 0.0,
                'membrane_min_z': 0.0,
                'gap': 0.0,
                'ratchet_steps': 0,
            }

        actin_arr = np.asarray(actin, dtype=np.float64)
        membrane_arr = np.asarray(membrane, dtype=np.float64)
        actin_max_z = float(actin_arr[:, 2].max())
        membrane_min_z = float(membrane_arr[:, 2].min())
        gap = membrane_min_z - actin_max_z

        # Spring model: force grows linearly as the gap shrinks below the
        # contact threshold; zero above the threshold. Clipped to be
        # non-negative because the membrane never pulls the actin.
        contact_force = max(0.0, cfg['force_constant'] * (cfg['contact_threshold'] - gap))

        # Ratchet step counter — incremented on this step iff in contact.
        is_ratchet = contact_force > 0.0
        if is_ratchet:
            self._ratchet_steps += 1

        if cfg['closed_loop']:
            wall_z = membrane_min_z - cfg['wall_offset']
            osmotic_offset = cfg['osmotic_force_scale'] * contact_force
        else:
            wall_z = None
            osmotic_offset = 0.0

        # Note: ratchet_steps is wired to a `delta` semantics store via the
        # `integer` schema (additive), so we publish the per-step delta
        # (1 if a ratchet event happened this step, else 0). Cumulative
        # tracking lives on the Process instance for diagnostics in the
        # update return; downstream consumers see the additive delta.
        ratchet_delta = 1 if is_ratchet else 0

        return {
            'wall_z': wall_z,
            'osmotic_strength_offset': float(osmotic_offset),
            'contact_force': float(contact_force),
            'actin_max_z': actin_max_z,
            'membrane_min_z': membrane_min_z,
            'gap': float(gap),
            'ratchet_steps': ratchet_delta,
        }
