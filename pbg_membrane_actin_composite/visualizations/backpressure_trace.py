"""Membrane back-pressure chart — second-row panel from demo/report.html.

Consumes membrane_volume, osmotic_offset, and (where present) wall_z to
show how the membrane is responding to the actin push: vesicle inflation
(volume), pressure imbalance the coupler is applying (osmotic_offset),
and the wall position published back to ReaDDy (wall_z).
"""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import render_lines_html


class BackpressureTrace(Visualization):
    """Membrane volume + osmotic offset + wall_z vs time."""

    config_schema = {
        'title': {'_type': 'string', '_default': 'Membrane back-pressure — volume · osmotic offset · wall position'},
        'accent': {'_type': 'string', '_default': '#10b981'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.history: dict[str, list[float]] = {
            'membrane_volume': [],
            'osmotic_offset': [],
            'wall_z': [],
        }

    def inputs(self):
        return {
            'time': 'float',
            'membrane_volume': 'float',
            'osmotic_offset': 'float',
            'wall_z': 'float',
        }

    def update(self, state, interval=1.0):
        self.times.append(float(state.get('time', len(self.times) * (interval or 1.0))))
        for key in self.history:
            v = state.get(key)
            self.history[key].append(float(v) if v is not None else 0.0)
        cfg = self.config or {}
        html = render_lines_html(
            div_id=f'backpressure-trace-{id(self)}',
            times=self.times,
            series=self.history,
            title=cfg.get('title', 'Membrane back-pressure'),
            y_title='volume · offset · z',
            accent=cfg.get('accent', '#10b981'),
        )
        return {'html': html}
