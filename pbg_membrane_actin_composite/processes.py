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
        # Coupling geometry. 'planar' = actin pushes UP against a membrane
        # patch above (wall_z barrier). 'spherical' = actin INSIDE a vesicle
        # pushes radially outward against the membrane sphere (wall_radius
        # barrier).
        'coupling_mode': {'_type': 'string', '_default': 'planar'},
        # When the gap drops below this threshold, count it as a ratchet
        # event and apply the contact force model.
        'contact_threshold': {'_type': 'float', '_default': 0.5},
        # Spring constant of the contact-force model: F = k * max(0,
        # contact_threshold - gap).
        'force_constant': {'_type': 'float', '_default': 1.0},
        # Multiplier from contact_force to osmotic_strength_offset. The
        # absolute value depends on Mem3DG's units; default scales the
        # bulge to a visibly large level for the included demo configurations.
        'osmotic_force_scale': {'_type': 'float', '_default': 0.5},
        # Wall offset published to ReaDDy. For planar mode this is a
        # z-offset (barrier sits this far below the lowest membrane vertex).
        # For spherical mode this is a radius-offset (barrier sits this
        # much smaller than the closest membrane vertex). Either way it
        # prevents the wall and the membrane from occupying the same space.
        'wall_offset': {'_type': 'float', '_default': 0.05},
        # When False, the coupler still computes diagnostics but emits
        # zero osmotic_offset and no wall publication. Used for the
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
        # Most outputs are *absolute readings* of the world (current
        # geometry, current contact force, current setpoint), NOT deltas
        # to be accumulated. They use overwrite[T] so each publish replaces
        # the store value rather than summing into it. The lone exception
        # is `ratchet_steps`, which IS a per-step delta — a sibling
        # consumer accumulating it gets the cumulative ratchet count.
        return {
            'wall_z': 'maybe[float]',           # maybe[T] is replace-by-default
            'wall_radius': 'maybe[float]',      # ditto
            'osmotic_strength_offset': 'overwrite[float]',
            'contact_force': 'overwrite[float]',
            'actin_max_z': 'overwrite[float]',
            'membrane_min_z': 'overwrite[float]',
            'actin_max_radius': 'overwrite[float]',
            'membrane_min_radius': 'overwrite[float]',
            'gap': 'overwrite[float]',
            'ratchet_steps': 'integer',         # additive — cumulative count
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
        mode = cfg['coupling_mode']

        # Default: no information yet, emit neutral signals.
        if not actin or not membrane:
            return self._neutral_output()

        actin_arr = np.asarray(actin, dtype=np.float64)
        membrane_arr = np.asarray(membrane, dtype=np.float64)

        # Compute per-mode geometry. Always populate every output key so
        # downstream consumers see consistent shape regardless of mode.
        actin_max_z = float(actin_arr[:, 2].max())
        membrane_min_z = float(membrane_arr[:, 2].min())
        actin_max_radius = float(np.linalg.norm(actin_arr, axis=1).max())
        membrane_min_radius = float(np.linalg.norm(membrane_arr, axis=1).min())

        if mode == 'spherical':
            # Inside-vesicle: gap = how much room the actin still has before
            # it hits the membrane. Negative = breached.
            gap = membrane_min_radius - actin_max_radius
        else:  # 'planar'
            gap = membrane_min_z - actin_max_z

        # Spring model — force grows linearly as the gap shrinks below the
        # contact threshold; clipped non-negative (membrane never pulls back).
        contact_force = max(0.0, cfg['force_constant'] * (cfg['contact_threshold'] - gap))
        is_ratchet = contact_force > 0.0
        if is_ratchet:
            self._ratchet_steps += 1

        wall_z = None
        wall_radius = None
        osmotic_offset = 0.0
        if cfg['closed_loop']:
            osmotic_offset = cfg['osmotic_force_scale'] * contact_force
            if mode == 'spherical':
                # Wall sits just inside the closest membrane point so the
                # membrane and the wall don't overlap.
                wall_radius = max(0.1, membrane_min_radius - cfg['wall_offset'])
            else:
                wall_z = membrane_min_z - cfg['wall_offset']

        ratchet_delta = 1 if is_ratchet else 0

        return {
            'wall_z': wall_z,
            'wall_radius': wall_radius,
            'osmotic_strength_offset': float(osmotic_offset),
            'contact_force': float(contact_force),
            'actin_max_z': actin_max_z,
            'membrane_min_z': membrane_min_z,
            'actin_max_radius': actin_max_radius,
            'membrane_min_radius': membrane_min_radius,
            'gap': float(gap),
            'ratchet_steps': ratchet_delta,
        }

    def _neutral_output(self):
        return {
            'wall_z': None,
            'wall_radius': None,
            'osmotic_strength_offset': 0.0,
            'contact_force': 0.0,
            'actin_max_z': 0.0,
            'membrane_min_z': 0.0,
            'actin_max_radius': 0.0,
            'membrane_min_radius': 0.0,
            'gap': 0.0,
            'ratchet_steps': 0,
        }
