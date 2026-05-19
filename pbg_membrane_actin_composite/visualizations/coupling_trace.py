"""Headline coupling chart — the demo/report.html signature panel.

Consumes actin_max_z, membrane_min_z, and contact_force on a shared time
axis. This is the per-scenario chart that makes the rigid-vs-flexible
boundary contrast visible at a glance — required by the pbg-superpowers
composite-demo spec.

Handles both invocation modes:
- Inline composite Step (scalar per step → appended to history).
- Dashboard auto-render against runs.db (full list per port → replaces
  history wholesale on every update).
"""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    render_lines_html, coerce_series,
)


class CouplingTrace(Visualization):
    config_schema = {
        'title': {'_type': 'string', '_default': 'Coupling trace — actin tip · membrane · contact force'},
        'accent': {'_type': 'string', '_default': '#0ea5e9'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.history: dict[str, list[float]] = {
            'actin_max_z': [], 'membrane_min_z': [], 'contact_force': [],
        }

    def inputs(self):
        return {'time': 'list[float]', 'actin_max_z': 'list[float]',
                'membrane_min_z': 'list[float]', 'contact_force': 'list[float]'}

    def update(self, state, interval=1.0):
        t = coerce_series(state.get('time'))
        if len(t) > 1:
            # Bulk path (dashboard auto-render): replace, don't accumulate.
            self.times = t
            for k in self.history:
                self.history[k] = coerce_series(state.get(k))
        else:
            # Incremental path (inline Step in a composite.run loop).
            self.times.append(t[0] if t else len(self.times) * (interval or 1.0))
            for k in self.history:
                vs = coerce_series(state.get(k))
                self.history[k].append(vs[0] if vs else 0.0)
        cfg = self.config or {}
        html = render_lines_html(
            div_id=f'coupling-trace-{id(self)}',
            times=self.times, series=self.history,
            title=cfg.get('title', 'Coupling trace'),
            y_title='z (au) / force (au)',
            accent=cfg.get('accent', '#0ea5e9'),
        )
        return {'html': html}
