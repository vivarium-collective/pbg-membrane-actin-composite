"""Mem3DG energy budget — stacked area of bending / surface / pressure."""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    render_stacked_area_html, coerce_series,
)


class EnergyBudget(Visualization):
    config_schema = {
        'title': {'_type': 'string', '_default': 'Membrane energy budget'},
        'accent': {'_type': 'string', '_default': '#3b82f6'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.history: dict[str, list[float]] = {
            'bending_energy': [], 'surface_energy': [], 'pressure_energy': [],
        }

    def inputs(self):
        return {'time': 'list[float]', 'bending_energy': 'list[float]',
                'surface_energy': 'list[float]', 'pressure_energy': 'list[float]'}

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
        html = render_stacked_area_html(
            div_id=f'energy-budget-{id(self)}',
            times=self.times, series=self.history,
            title=cfg.get('title', 'Membrane energy budget'),
            y_title='energy (au)',
            accent=cfg.get('accent', '#3b82f6'),
        )
        return {'html': html}
