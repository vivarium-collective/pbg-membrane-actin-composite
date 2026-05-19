"""Barrier kinematics dual-axis — barrier_z + barrier_velocity."""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    render_dual_axis_html, coerce_series,
)


class BarrierKinematics(Visualization):
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
        return {'time': 'list[float]', 'barrier_z': 'list[float]',
                'barrier_velocity': 'list[float]'}

    def update(self, state, interval=1.0):
        t = coerce_series(state.get('time'))
        bz = coerce_series(state.get('barrier_z'))
        bv = coerce_series(state.get('barrier_velocity'))
        if len(t) > 1:
            self.times = t
            self.barrier_z = bz if len(bz) == len(t) else [0.0] * len(t)
            self.barrier_velocity = bv if len(bv) == len(t) else [0.0] * len(t)
        else:
            self.times.append(t[0] if t else len(self.times) * (interval or 1.0))
            self.barrier_z.append(bz[0] if bz else 0.0)
            self.barrier_velocity.append(bv[0] if bv else 0.0)
        cfg = self.config or {}
        html = render_dual_axis_html(
            div_id=f'barrier-kinematics-{id(self)}',
            times=self.times,
            left_series={'barrier_z': self.barrier_z},
            right_series={'barrier_velocity': self.barrier_velocity},
            title=cfg.get('title', 'Barrier kinematics'),
            left_title='z (au)', right_title='dz/dt (au · t⁻¹)',
            accent=cfg.get('accent', '#0ea5e9'),
        )
        return {'html': html}
