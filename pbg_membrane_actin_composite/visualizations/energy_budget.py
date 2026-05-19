"""Mem3DG energy budget — stacked area of the bending / surface / pressure
components vs time. Rung 3 only (the flexible-membrane rung is the only
one with a Mem3DG process emitting these scalars).
"""
from __future__ import annotations

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import render_stacked_area_html


class EnergyBudget(Visualization):
    """Stacked area of Mem3DG bending / surface / pressure energies."""

    config_schema = {
        'title': {'_type': 'string', '_default': 'Membrane energy budget'},
        'accent': {'_type': 'string', '_default': '#3b82f6'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.history: dict[str, list[float]] = {
            'bending_energy': [],
            'surface_energy': [],
            'pressure_energy': [],
        }

    def inputs(self):
        return {
            'time': 'float',
            'bending_energy': 'float',
            'surface_energy': 'float',
            'pressure_energy': 'float',
        }

    def update(self, state, interval=1.0):
        self.times.append(float(state.get('time', len(self.times) * (interval or 1.0))))
        for key in self.history:
            v = state.get(key)
            # Pressure energy can be negative; keep its sign for stacked area
            # but clamp tiny noise to zero so the floor of the stack is clean.
            self.history[key].append(float(v) if v is not None else 0.0)
        cfg = self.config or {}
        html = render_stacked_area_html(
            div_id=f'energy-budget-{id(self)}',
            times=self.times,
            series=self.history,
            title=cfg.get('title', 'Membrane energy budget'),
            y_title='energy (au)',
            accent=cfg.get('accent', '#3b82f6'),
        )
        return {'html': html}
