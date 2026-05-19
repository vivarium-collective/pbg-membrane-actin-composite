"""Barrier kinematics dual-axis chart — barrier_z + barrier_velocity vs time.

The headline per-rung diagnostic that visually distinguishes the three
boundary regimes: rung 1 has barrier_velocity ≡ 0; rung 2 settles to a
non-zero steady-state proportional to load; rung 3 shows a fluctuating
expansion rate as the Mem3DG mesh redistributes force.
"""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import render_dual_axis_html


class BarrierKinematics(Visualization):
    """Barrier position (left axis) + barrier velocity (right axis)."""

    config_schema = {
        'title': {'_type': 'string', '_default': 'Barrier kinematics — z and dz/dt'},
        'accent': {'_type': 'string', '_default': '#0ea5e9'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.barrier_z: list[float] = []
        self.barrier_velocity: list[float] = []

    def inputs(self):
        return {
            'time': 'float',
            'barrier_z': 'float',
            'barrier_velocity': 'float',
        }

    def update(self, state, interval=1.0):
        self.times.append(float(state.get('time', len(self.times) * (interval or 1.0))))
        self.barrier_z.append(float(state.get('barrier_z', 0.0) or 0.0))
        self.barrier_velocity.append(float(state.get('barrier_velocity', 0.0) or 0.0))
        cfg = self.config or {}
        html = render_dual_axis_html(
            div_id=f'barrier-kinematics-{id(self)}',
            times=self.times,
            left_series={'barrier_z': self.barrier_z},
            right_series={'barrier_velocity': self.barrier_velocity},
            title=cfg.get('title', 'Barrier kinematics'),
            left_title='z (au)',
            right_title='dz/dt (au · t⁻¹)',
            accent=cfg.get('accent', '#0ea5e9'),
        )
        return {'html': html}
