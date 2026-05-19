"""Headline coupling chart — the demo/report.html signature panel.

Consumes actin_max_z, membrane_min_z, and contact_force on a shared time
axis. This is the per-scenario chart that makes the rigid-vs-flexible
boundary contrast visible at a glance — required by the pbg-superpowers
composite-demo spec.
"""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import render_lines_html


class CouplingTrace(Visualization):
    """Actin tip, membrane bottom, and contact force on a shared time axis."""

    config_schema = {
        'title': {'_type': 'string', '_default': 'Coupling trace — actin tip · membrane · contact force'},
        'accent': {'_type': 'string', '_default': '#0ea5e9'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.history: dict[str, list[float]] = {
            'actin_max_z': [],
            'membrane_min_z': [],
            'contact_force': [],
        }

    def inputs(self):
        return {
            'time': 'float',
            'actin_max_z': 'float',
            'membrane_min_z': 'float',
            'contact_force': 'float',
        }

    def update(self, state, interval=1.0):
        self.times.append(float(state.get('time', len(self.times) * (interval or 1.0))))
        for key in self.history:
            v = state.get(key)
            self.history[key].append(float(v) if v is not None else 0.0)
        cfg = self.config or {}
        html = render_lines_html(
            div_id=f'coupling-trace-{id(self)}',
            times=self.times,
            series=self.history,
            title=cfg.get('title', 'Coupling trace'),
            y_title='z (au) / force (au)',
            accent=cfg.get('accent', '#0ea5e9'),
        )
        return {'html': html}
