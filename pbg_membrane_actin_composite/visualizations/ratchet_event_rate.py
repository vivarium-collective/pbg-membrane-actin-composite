"""Ratchet event rate — instantaneous + rolling-window-smoothed step rate.

Complements PopulationTrace's cumulative count: this chart shows the
dynamic firing rate, making transients (e.g. an initial burst followed
by quasi-steady ratcheting) visually obvious.
"""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import render_lines_html


class RatchetEventRate(Visualization):
    """Per-step ratchet rate + rolling-mean smoothed trace."""

    config_schema = {
        'title': {'_type': 'string', '_default': 'Ratchet event rate (per step + rolling mean)'},
        'accent': {'_type': 'string', '_default': '#8b5cf6'},
        'window': {'_type': 'integer', '_default': 5},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.rate_per_step: list[float] = []
        self.rate_rolling: list[float] = []

    def inputs(self):
        return {
            'time': 'float',
            'ratchet_steps': 'float',
        }

    def update(self, state, interval=1.0):
        self.times.append(float(state.get('time', len(self.times) * (interval or 1.0))))
        per_step = float(state.get('ratchet_steps', 0) or 0)
        rate = per_step / float(interval) if interval else per_step
        self.rate_per_step.append(rate)
        # Rolling mean over the configured window
        window = int((self.config or {}).get('window', 5))
        w = self.rate_per_step[-window:]
        self.rate_rolling.append(sum(w) / max(1, len(w)))
        cfg = self.config or {}
        html = render_lines_html(
            div_id=f'ratchet-rate-{id(self)}',
            times=self.times,
            series={
                'rate (per step)': self.rate_per_step,
                f'rolling mean (w={window})': self.rate_rolling,
            },
            title=cfg.get('title', 'Ratchet event rate'),
            y_title='events / unit time',
            accent=cfg.get('accent', '#8b5cf6'),
            trace_colors={
                'rate (per step)': '#c4b5fd',
                f'rolling mean (w={window})': '#7c3aed',
            },
        )
        return {'html': html}
