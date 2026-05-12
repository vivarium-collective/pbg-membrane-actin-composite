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
        # Coupling geometry. 'planar' = actin pushes UP against a barrier
        # above (wall_z). 'spherical' = actin INSIDE a vesicle pushes
        # radially outward (wall_radius). Most spec-aligned scenarios use
        # 'planar'; spherical is preserved for the inside-vesicle demo.
        'coupling_mode': {'_type': 'string', '_default': 'planar'},
        # Barrier dynamics — the spec §2.2 boundary-condition staircase:
        #   'fixed':         wall_z stays at barrier_initial_z; doesn't move.
        #                    Models the rigid-wall regime (rung 1).
        #   'rigid_movable': wall_z translates under integrated contact force.
        #                    Drag-balance kinematics — Peskin 1993 (rung 2).
        #   'flexible':      wall_z follows membrane_min_z (or _radius), and
        #                    coupler publishes osmotic_offset to inflate
        #                    Mem3DG. Phase-2 headline run (rung 3).
        'barrier_kind': {'_type': 'string', '_default': 'flexible'},
        # Initial position of the barrier. For planar this is the z-plane
        # height; for spherical it would be the initial sphere radius.
        # Used by 'fixed' and 'rigid_movable' modes (which don't have a
        # Mem3DG to read the position from).
        'barrier_initial_z': {'_type': 'float', '_default': 0.0},
        # Drag coefficient for 'rigid_movable' mode: barrier_velocity =
        # contact_force / drag. Higher drag = barrier resists motion more.
        'barrier_drag': {'_type': 'float', '_default': 5.0},
        # When the gap drops below this threshold, count it as a ratchet
        # event and apply the contact force model.
        'contact_threshold': {'_type': 'float', '_default': 0.5},
        # Spring constant of the contact-force model: F = k * max(0,
        # contact_threshold - gap).
        'force_constant': {'_type': 'float', '_default': 1.0},
        # Multiplier from contact_force to osmotic_strength_offset (only
        # applied in barrier_kind='flexible'). Pressure scale in pymem3dg
        # is sensitive — defaults are tuned for ~10-20% inflation over
        # the demo's run length.
        'osmotic_force_scale': {'_type': 'float', '_default': 0.02},
        # Distance the published wall sits below the actual barrier
        # surface so the wall and the surface don't try to occupy the
        # same space.
        'wall_offset': {'_type': 'float', '_default': 0.05},
        # When False, the coupler still computes diagnostics but doesn't
        # update wall_z or osmotic_offset. Used for the decoupled-baseline
        # scenario.
        'closed_loop': {'_type': 'boolean', '_default': True},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._ratchet_steps = 0
        # Standalone barrier state — used by 'fixed' and 'rigid_movable'
        # modes (which have no Mem3DG to read position from). Initialized
        # lazily on first update() so the config defaults are honored.
        self._barrier_z = None
        # Sample history for barrier velocity estimation. Each entry:
        # (sim_time, barrier_z). The coupler publishes the linear-fit
        # slope of the most recent samples so the demo can plot a real
        # F-V point per scenario.
        self._barrier_history = []
        self._mean_force = 0.0  # rolling mean of contact_force samples

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
            # Barrier kinematics — published every step so the demo can
            # plot displacement-vs-time curves and F-V scatter points
            # across the staircase regimes.
            'barrier_z': 'overwrite[float]',           # current z position
            'barrier_velocity': 'overwrite[float]',    # linear-fit slope
            'mean_contact_force': 'overwrite[float]',  # rolling mean force
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
        kind = cfg['barrier_kind']

        # Lazy-init the standalone barrier_z (used by 'fixed' and
        # 'rigid_movable' modes — they have no Mem3DG to read from).
        if self._barrier_z is None:
            self._barrier_z = float(cfg['barrier_initial_z'])

        actin_arr = np.asarray(actin, dtype=np.float64) if actin else np.zeros((0, 3))
        membrane_arr = np.asarray(membrane, dtype=np.float64) if membrane else np.zeros((0, 3))

        # ---- Geometry probes -------------------------------------------------
        actin_max_z = float(actin_arr[:, 2].max()) if len(actin_arr) else 0.0
        actin_max_radius = float(np.linalg.norm(actin_arr, axis=1).max()) if len(actin_arr) else 0.0
        if len(membrane_arr):
            membrane_min_z = float(membrane_arr[:, 2].min())
            membrane_min_radius = float(np.linalg.norm(membrane_arr, axis=1).min())
        else:
            membrane_min_z = self._barrier_z
            membrane_min_radius = self._barrier_z

        # ---- Barrier position (regime-dependent) ----------------------------
        # Decide where the current barrier sits in space — this is what
        # ReaDDy's wall_z (or wall_radius) is published from.
        if kind == 'flexible' and len(membrane_arr):
            # Phase-2 endpoint: the barrier IS the membrane.
            barrier_position = membrane_min_z if mode == 'planar' else membrane_min_radius
        else:
            # 'fixed' and 'rigid_movable' (and 'flexible' before Mem3DG
            # has emitted) use the standalone barrier_z. (rigid_movable
            # advances it below.)
            barrier_position = self._barrier_z

        # ---- Contact gap + force --------------------------------------------
        if mode == 'spherical':
            gap = barrier_position - actin_max_radius
        else:  # 'planar'
            gap = barrier_position - actin_max_z
        contact_force = max(0.0, cfg['force_constant'] * (cfg['contact_threshold'] - gap))
        is_ratchet = contact_force > 0.0
        if is_ratchet:
            self._ratchet_steps += 1

        # ---- Barrier kinematics (regime-dependent) --------------------------
        # 'fixed':         barrier_z unchanged.
        # 'rigid_movable': drag-balance: dz/dt = F / drag.
        # 'flexible':      barrier_z follows the live membrane reading.
        if kind == 'rigid_movable':
            self._barrier_z += contact_force / cfg['barrier_drag'] * interval
            barrier_position = self._barrier_z
        elif kind == 'flexible' and len(membrane_arr):
            self._barrier_z = barrier_position  # mirror for diagnostics
        # 'fixed': barrier_z stays put.

        # Track barrier samples for velocity estimation.
        sim_time = self._barrier_history[-1][0] + interval if self._barrier_history else 0.0
        self._barrier_history.append((sim_time, barrier_position))
        # Use only the last 8 samples for the slope fit so the published
        # velocity reflects recent dynamics, not the whole-run average.
        recent = self._barrier_history[-8:]
        if len(recent) >= 2:
            ts = np.asarray([t for t, _ in recent], dtype=np.float64)
            zs = np.asarray([z for _, z in recent], dtype=np.float64)
            slope, _ = np.polyfit(ts, zs, 1)
            barrier_velocity = float(slope)
        else:
            barrier_velocity = 0.0

        # Rolling mean of contact force (window = 8 to match velocity window).
        n = min(8, len(self._barrier_history))
        # Approximate: track via exponential moving average.
        alpha = 2.0 / (n + 1)
        self._mean_force = (1 - alpha) * self._mean_force + alpha * contact_force

        # ---- Closed-loop back-channel publication ---------------------------
        wall_z = None
        wall_radius = None
        osmotic_offset = 0.0
        if cfg['closed_loop']:
            # ReaDDy barrier publication — always emitted (all 3 regimes
            # publish a wall to ReaDDy so the actin field is confined).
            if mode == 'spherical':
                wall_radius = max(0.1, barrier_position - cfg['wall_offset'])
            else:
                wall_z = barrier_position - cfg['wall_offset']
            # Mem3DG-side publication only meaningful in the 'flexible'
            # regime (the other regimes have no Mem3DG instance).
            if kind == 'flexible':
                osmotic_offset = cfg['osmotic_force_scale'] * contact_force

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
            'barrier_z': float(barrier_position),
            'barrier_velocity': float(barrier_velocity),
            'mean_contact_force': float(self._mean_force),
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
            'barrier_z': float(self.config.get('barrier_initial_z', 0.0)),
            'barrier_velocity': 0.0,
            'mean_contact_force': 0.0,
            'ratchet_steps': 0,
        }
