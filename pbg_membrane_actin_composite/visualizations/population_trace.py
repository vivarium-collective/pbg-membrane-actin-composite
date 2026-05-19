"""Actin population — particle count + cumulative ratchet steps."""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    render_lines_html, coerce_series,
)


class PopulationTrace(Visualization):
    config_schema = {
        'title': {'_type': 'string', '_default': 'Actin population — particle count + cumulative ratchet steps'},
        'accent': {'_type': 'string', '_default': '#94a3b8'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.actin_total: list[float] = []
        self.cumulative_ratchets: list[float] = []

    def inputs(self):
        return {'time': 'list[float]', 'actin_total': 'list[float]',
                'ratchet_steps': 'list[float]'}

    def update(self, state, interval=1.0):
        t = coerce_series(state.get('time'))
        rs = coerce_series(state.get('ratchet_steps'))
        ac = coerce_series(state.get('actin_total'))
        if len(t) > 1:
            self.times = t
            self.actin_total = ac if len(ac) == len(t) else [0.0] * len(t)
            cum = []
            running = 0.0
            for r in (rs if len(rs) == len(t) else [0.0] * len(t)):
                running += r
                cum.append(running)
            self.cumulative_ratchets = cum
        else:
            self.times.append(t[0] if t else len(self.times) * (interval or 1.0))
            self.actin_total.append(ac[0] if ac else 0.0)
            running = (self.cumulative_ratchets[-1] if self.cumulative_ratchets else 0.0)
            running += (rs[0] if rs else 0.0)
            self.cumulative_ratchets.append(running)
        cfg = self.config or {}
        html = render_lines_html(
            div_id=f'population-trace-{id(self)}',
            times=self.times,
            series={'actin_total': self.actin_total,
                    'cumulative_ratchet_steps': self.cumulative_ratchets},
            title=cfg.get('title', 'Actin population'),
            y_title='count',
            accent=cfg.get('accent', '#94a3b8'),
        )
        return {'html': html}
