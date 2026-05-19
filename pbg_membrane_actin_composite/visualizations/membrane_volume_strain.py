"""Membrane volume strain — (V(t) - V(0)) / V(0) vs time, with a reference
horizontal line at the 10% inflation threshold used by the
`membrane-curvature-relaxes-load` acceptance criterion.

Makes "did the vesicle inflate?" answerable at a glance — rung 1 and
rung 2 sit at zero strain; rung 3 should climb above the reference line.
"""
from __future__ import annotations

import json

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    PALETTE, _BASE_LAYOUT, _axis_style, PLOTLY_CDN,
)


class MembraneVolumeStrain(Visualization):
    """Volume strain (V-V0)/V0 vs time with a 10% reference line."""

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
        return {
            'time': 'float',
            'membrane_volume': 'float',
        }

    def update(self, state, interval=1.0):
        v = float(state.get('membrane_volume', 0.0) or 0.0)
        if self._v0 is None or self._v0 == 0.0:
            self._v0 = v if v > 0.0 else 1.0
        self.times.append(float(state.get('time', len(self.times) * (interval or 1.0))))
        self.strain.append((v - self._v0) / self._v0)
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
        return {'html': html}
