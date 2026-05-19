"""Force-velocity scatter — Inoue 2015 benchmark, time-colored trail."""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    render_scatter_html, coerce_series,
)


class ForceVelocityScatter(Visualization):
    config_schema = {
        'title': {'_type': 'string', '_default': 'Force–velocity scatter (time-colored)'},
        'accent': {'_type': 'string', '_default': '#10b981'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.force: list[float] = []
        self.velocity: list[float] = []

    def inputs(self):
        return {'time': 'list[float]', 'mean_contact_force': 'list[float]',
                'barrier_velocity': 'list[float]'}

    def update(self, state, interval=1.0):
        t = coerce_series(state.get('time'))
        f = coerce_series(state.get('mean_contact_force'))
        v = coerce_series(state.get('barrier_velocity'))
        if len(t) > 1:
            self.times = t
            self.force = f if len(f) == len(t) else [0.0] * len(t)
            self.velocity = v if len(v) == len(t) else [0.0] * len(t)
        else:
            self.times.append(t[0] if t else len(self.times) * (interval or 1.0))
            self.force.append(f[0] if f else 0.0)
            self.velocity.append(v[0] if v else 0.0)
        cfg = self.config or {}
        html = render_scatter_html(
            div_id=f'fv-scatter-{id(self)}',
            xs=self.force, ys=self.velocity, color_by=self.times,
            title=cfg.get('title', 'Force–velocity scatter'),
            x_title='mean_contact_force (F)',
            y_title='barrier_velocity (V)',
            accent=cfg.get('accent', '#10b981'),
        )
        return {'html': html}
