"""Ratchet event rate — instantaneous + rolling-mean firing rate."""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    render_lines_html, coerce_series,
)


class RatchetEventRate(Visualization):
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
        return {'time': 'list[float]', 'ratchet_steps': 'list[float]'}

    def update(self, state, interval=1.0):
        t = coerce_series(state.get('time'))
        rs = coerce_series(state.get('ratchet_steps'))
        window = int((self.config or {}).get('window', 5))
        if len(t) > 1:
            self.times = t
            rates = [(r / (interval or 1.0) if interval else r)
                     for r in (rs if len(rs) == len(t) else [0.0] * len(t))]
            self.rate_per_step = rates
            self.rate_rolling = [
                sum(rates[max(0, i - window + 1):i + 1]) / min(i + 1, window)
                for i in range(len(rates))
            ]
        else:
            self.times.append(t[0] if t else len(self.times) * (interval or 1.0))
            r = (rs[0] if rs else 0.0)
            rate = r / (interval or 1.0) if interval else r
            self.rate_per_step.append(rate)
            w = self.rate_per_step[-window:]
            self.rate_rolling.append(sum(w) / max(1, len(w)))
        cfg = self.config or {}
        html = render_lines_html(
            div_id=f'ratchet-rate-{id(self)}',
            times=self.times,
            series={'rate (per step)': self.rate_per_step,
                    f'rolling mean (w={window})': self.rate_rolling},
            title=cfg.get('title', 'Ratchet event rate'),
            y_title='events / unit time',
            accent=cfg.get('accent', '#8b5cf6'),
            trace_colors={'rate (per step)': '#c4b5fd',
                          f'rolling mean (w={window})': '#7c3aed'},
        )
        return {'html': html}
