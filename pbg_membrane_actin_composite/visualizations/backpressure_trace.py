"""Membrane back-pressure — membrane_volume + osmotic_offset + wall_z."""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    render_lines_html, coerce_series,
)


class BackpressureTrace(Visualization):
    config_schema = {
        'title': {'_type': 'string', '_default': 'Membrane back-pressure — volume · osmotic offset · wall position'},
        'accent': {'_type': 'string', '_default': '#10b981'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.history: dict[str, list[float]] = {
            'membrane_volume': [], 'osmotic_offset': [], 'wall_z': [],
        }

    def inputs(self):
        return {'time': 'list[float]', 'membrane_volume': 'list[float]',
                'osmotic_offset': 'list[float]', 'wall_z': 'list[float]'}

    def update(self, state, interval=1.0):
        t = coerce_series(state.get('time'))
        if len(t) > 1:
            self.times = t
            for k in self.history:
                self.history[k] = coerce_series(state.get(k))
        else:
            self.times.append(t[0] if t else len(self.times) * (interval or 1.0))
            for k in self.history:
                vs = coerce_series(state.get(k))
                self.history[k].append(vs[0] if vs else 0.0)
        cfg = self.config or {}
        html = render_lines_html(
            div_id=f'backpressure-trace-{id(self)}',
            times=self.times, series=self.history,
            title=cfg.get('title', 'Membrane back-pressure'),
            y_title='volume · offset · z',
            accent=cfg.get('accent', '#10b981'),
        )
        return {'html': html}
