"""Actin population + ratchet-step counter — third-row panel from demo/report.html.

Consumes actin_total (current particle count) and ratchet_steps (per-step
event count) and surfaces the cumulative ratchet count. The cumulative
curve is what tells you whether the closed loop is actually firing the
Brownian-ratchet reaction or whether the actin pool has stalled.
"""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import render_lines_html


class PopulationTrace(Visualization):
    """Actin particle count + cumulative ratchet steps vs time."""

    config_schema = {
        'title': {'_type': 'string', '_default': 'Actin population — particle count + cumulative ratchet steps'},
        'accent': {'_type': 'string', '_default': '#94a3b8'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self._cum_ratchets: int = 0
        self.history: dict[str, list[float]] = {
            'actin_total': [],
            'cumulative_ratchet_steps': [],
        }

    def inputs(self):
        return {
            'time': 'float',
            'actin_total': 'float',
            'ratchet_steps': 'float',
        }

    def update(self, state, interval=1.0):
        self.times.append(float(state.get('time', len(self.times) * (interval or 1.0))))
        self.history['actin_total'].append(float(state.get('actin_total', 0) or 0))
        self._cum_ratchets += int(state.get('ratchet_steps', 0) or 0)
        self.history['cumulative_ratchet_steps'].append(float(self._cum_ratchets))
        cfg = self.config or {}
        html = render_lines_html(
            div_id=f'population-trace-{id(self)}',
            times=self.times,
            series=self.history,
            title=cfg.get('title', 'Actin population'),
            y_title='count',
            accent=cfg.get('accent', '#94a3b8'),
        )
        return {'html': html}
