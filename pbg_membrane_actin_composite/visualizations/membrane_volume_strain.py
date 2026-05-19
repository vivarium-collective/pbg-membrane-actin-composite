"""Membrane volume strain — (V(t) - V(0)) / V(0) with 10% reference line."""
from __future__ import annotations

import json

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    _AUTOSIZE_SCRIPT,
    PALETTE, _BASE_LAYOUT, _axis_style, PLOTLY_CDN, coerce_series,
)


class MembraneVolumeStrain(Visualization):
    config_schema = {
        'title': {'_type': 'string', '_default': 'Membrane volume strain'},
        'accent': {'_type': 'string', '_default': '#10b981'},
        'reference_strain': {'_type': 'float', '_default': 0.10},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.strain: list[float] = []
        self._v0: float | None = None

    def inputs(self):
        return {'time': 'list[float]', 'membrane_volume': 'list[float]'}

    def update(self, state, interval=1.0):
        t = coerce_series(state.get('time'))
        v = coerce_series(state.get('membrane_volume'))
        if len(t) > 1:
            self.times = t
            v0 = next((x for x in v if x > 0.0), 1.0) if v else 1.0
            self.strain = [(x - v0) / v0 for x in v] if v else [0.0] * len(t)
        else:
            x = v[0] if v else 0.0
            if self._v0 is None or self._v0 == 0.0:
                self._v0 = x if x > 0.0 else 1.0
            self.times.append(t[0] if t else len(self.times) * (interval or 1.0))
            self.strain.append((x - self._v0) / self._v0)
        cfg = self.config or {}
        ref = float(cfg.get('reference_strain', 0.10))
        accent = cfg.get('accent', '#10b981')
        div_id = f'volume-strain-{id(self)}'
        trace_strain = {
            'x': self.times, 'y': self.strain, 'type': 'scatter', 'mode': 'lines',
            'name': '(V - V₀) / V₀', 'line': {'color': accent, 'width': 2.6},
            'fill': 'tozeroy', 'fillcolor': accent + '22',
        }
        trace_ref = {
            'x': self.times, 'y': [ref] * len(self.times),
            'type': 'scatter', 'mode': 'lines',
            'name': f'{int(ref*100)}% reference',
            'line': {'color': PALETTE['muted'], 'width': 1.5, 'dash': 'dash'},
        }
        layout = {
            **_BASE_LAYOUT,
            'title': {'text': f'<b>{cfg.get("title", "Membrane volume strain")}</b>',
                      'x': 0.02, 'xanchor': 'left',
                      'font': {'size': 14, 'color': PALETTE['ink']}},
            'xaxis': _axis_style('time'),
            'yaxis': _axis_style('strain'),
        }
        accent_bar = (
            f'<div style="height:3px;background:{accent};margin-bottom:6px;border-radius:2px"></div>'
        )
        html = (
            f'{accent_bar}'
            f'<div id="{div_id}" style="height:320px"></div>'
            f'<script src="{PLOTLY_CDN}"></script>'
            f'<script>Plotly.newPlot('
            f'"{div_id}",{json.dumps([trace_strain, trace_ref])},{json.dumps(layout)},'
            f'{{responsive:true,displayModeBar:false}});</script>'
        )
        return {'html': html + _AUTOSIZE_SCRIPT}
