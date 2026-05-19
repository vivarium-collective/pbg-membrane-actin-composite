"""Shared Plotly HTML renderer for the membrane-actin Visualizations.

Each Visualization accumulates a per-key history dict and re-renders a
multi-trace Plotly figure on every update() call.
"""
from __future__ import annotations

import json


PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.27.0.min.js"


def render_lines_html(
    div_id: str,
    times: list[float],
    series: dict[str, list[float]],
    *,
    title: str,
    y_title: str = "",
    height: int = 320,
    accent: str | None = None,
) -> str:
    """Render a multi-line Plotly chart as a self-contained HTML fragment.

    Parameters
    ----------
    div_id : unique DOM id for the chart container.
    times : shared x-axis values.
    series : {label: ys} — one trace per key, all aligned with ``times``.
    title : figure title displayed at the top.
    y_title : optional y-axis label.
    height : pixel height of the chart container.
    accent : optional CSS color used as the title accent bar.
    """
    traces = [
        {"x": times, "y": ys, "type": "scatter", "mode": "lines", "name": label}
        for label, ys in series.items()
    ]
    layout = {
        "title": title,
        "margin": {"l": 55, "r": 15, "t": 35, "b": 40},
        "xaxis": {"title": "time"},
        "yaxis": {"title": y_title},
        "legend": {"orientation": "h", "y": -0.2},
    }
    accent_bar = (
        f'<div style="height:3px;background:{accent};margin-bottom:6px"></div>'
        if accent else ''
    )
    return (
        f'{accent_bar}'
        f'<div id="{div_id}" style="height:{height}px"></div>'
        f'<script src="{PLOTLY_CDN}"></script>'
        f'<script>Plotly.newPlot('
        f'"{div_id}",{json.dumps(traces)},{json.dumps(layout)},'
        f'{{responsive:true,displayModeBar:false}});</script>'
    )
