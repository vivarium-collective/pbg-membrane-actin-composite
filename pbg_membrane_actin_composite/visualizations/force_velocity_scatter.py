"""Force-velocity scatter — the primary numerical benchmark (Inoue 2015).

Accumulates (mean_contact_force, barrier_velocity) per step and renders
a colored-by-time trail. A single run produces one trail; the dashboard
overlays multiple runs (sweep over growth_rate) to surface the
concave→convex F-V transition that defines a flexible-membrane ratchet
(spec §1.2).
"""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import render_scatter_html


class ForceVelocityScatter(Visualization):
    """(F, V) trail colored by time — concave→convex Inoue 2015 benchmark."""

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
        return {
            'time': 'float',
            'mean_contact_force': 'float',
            'barrier_velocity': 'float',
        }

    def update(self, state, interval=1.0):
        self.times.append(float(state.get('time', len(self.times) * (interval or 1.0))))
        self.force.append(float(state.get('mean_contact_force', 0.0) or 0.0))
        self.velocity.append(float(state.get('barrier_velocity', 0.0) or 0.0))
        cfg = self.config or {}
        html = render_scatter_html(
            div_id=f'fv-scatter-{id(self)}',
            xs=self.force,
            ys=self.velocity,
            color_by=self.times,
            title=cfg.get('title', 'Force–velocity scatter'),
            x_title='mean_contact_force (F)',
            y_title='barrier_velocity (V)',
            accent=cfg.get('accent', '#10b981'),
        )
        return {'html': html}
