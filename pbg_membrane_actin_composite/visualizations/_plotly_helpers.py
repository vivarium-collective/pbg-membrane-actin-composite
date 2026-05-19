"""Shared Plotly HTML renderer for the membrane-actin Visualizations.

Provides a coherent visual identity across all workspace Visualizations:
a curated color palette, consistent typography, subtle grid styling,
and uniform hover behaviour. Each Visualization renders a self-contained
HTML fragment (Plotly CDN script + container div) on every update().
"""
from __future__ import annotations

import json
from typing import Any


def coerce_series(value: Any) -> list[float]:
    """Normalize a viz input to a list[float] regardless of upstream path.

    Handles three shapes the dashboard's auto-render path may hand us:

    - scalar         (single-call composite Step path)         → `[value]`
    - list[float]    (one run, port_type='list[float]')        → pass-through
    - list[list[float]]
                     (multiple runs accumulated in runs.db)    → take latest
                     run (last element), since overlay semantics aren't
                     defined for our scalar-series vizzes. Multi-run
                     overlay is a separate concern and would need a viz
                     that explicitly accepts the nested shape.
    - None / unparseable                                        → `[]`
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        if value and isinstance(value[0], (list, tuple)):
            # Nested — pick the last (most recent) run.
            inner = value[-1] if value else []
            return [float(v) if v is not None else 0.0 for v in inner]
        return [float(v) if v is not None else 0.0 for v in value]
    try:
        return [float(value)]
    except (TypeError, ValueError):
        return []


PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.27.0.min.js"


# Tiny JS shim — the dashboard wraps each viz HTML in an iframe with
# `min-height: 1600px` and an `onload` resizer that sets `style.height`
# only. The min-height keeps the iframe at 1600px regardless of how
# small our content is, leaving the empty band you see below most
# Plotly charts. Same-origin, so we reach up, clear the min-height,
# and trigger a re-measure after Plotly settles its async render.
_AUTOSIZE_SCRIPT = """
<script>
(function autosize(retries) {
  try {
    if (window.parent === window) return;
    var iframes = window.parent.document.querySelectorAll('iframe');
    var self = null;
    for (var i = 0; i < iframes.length; i++) {
      if (iframes[i].contentWindow === window) { self = iframes[i]; break; }
    }
    if (!self) { if (retries > 0) setTimeout(function(){autosize(retries-1);}, 80); return; }
    self.style.minHeight = '0px';
    function fit() {
      var h = Math.max(
        document.documentElement.scrollHeight,
        document.body ? document.body.scrollHeight : 0
      );
      if (h > 60) self.style.height = (h + 16) + 'px';
    }
    fit();
    setTimeout(fit, 120);
    setTimeout(fit, 400);
    setTimeout(fit, 900);
    window.addEventListener('resize', fit);
  } catch (e) {}
})(20);
</script>
"""

# Shared palette — three-rung accent + neutral grays. Index matches the
# demo/report.html accent assignments so workspace charts and the legacy
# demo are visually congruent.
PALETTE = {
    "rung1": "#94a3b8",  # slate-400 — fixed boundary
    "rung2": "#0ea5e9",  # sky-500 — rigid movable
    "rung3": "#10b981",  # emerald-500 — flexible Mem3DG
    "accent_warm": "#f97316",  # orange-500 — contact force / load
    "accent_cool": "#6366f1",  # indigo-500 — membrane / mesh
    "muted": "#9ca3af",  # gray-400 — secondary trace
    "ink": "#1f2937",  # gray-800 — text / axes
    "rule": "#e5e7eb",  # gray-200 — grid / dividers
}

# Default trace colors by semantic key. New Visualizations should look
# up here so the same observable appears in the same color across charts.
COLOR_BY_OBSERVABLE = {
    "actin_max_z": PALETTE["accent_warm"],
    "actin_total": PALETTE["accent_warm"],
    "contact_force": "#dc2626",            # red-600
    "membrane_min_z": PALETTE["accent_cool"],
    "membrane_volume": PALETTE["rung3"],
    "osmotic_offset": "#a855f7",           # purple-500
    "wall_z": PALETTE["muted"],
    "barrier_z": PALETTE["rung2"],
    "barrier_velocity": PALETTE["rung1"],
    "cumulative_ratchet_steps": "#8b5cf6", # violet-500
    "bending_energy": "#3b82f6",            # blue-500
    "surface_energy": "#22c55e",            # green-500
    "pressure_energy": "#eab308",           # yellow-500
    "total_energy": PALETTE["ink"],
}


_BASE_LAYOUT: dict = {
    "font": {"family": "Inter, system-ui, -apple-system, sans-serif",
             "size": 12, "color": PALETTE["ink"]},
    "paper_bgcolor": "white",
    "plot_bgcolor": "#fafafa",
    "margin": {"l": 55, "r": 25, "t": 45, "b": 45},
    "hovermode": "x unified",
    "legend": {"orientation": "h", "y": -0.22, "x": 0.5,
               "xanchor": "center", "bgcolor": "rgba(255,255,255,0)"},
}


def _axis_style(title: str = "") -> dict:
    return {
        "title": title,
        "gridcolor": PALETTE["rule"],
        "zerolinecolor": PALETTE["rule"],
        "linecolor": PALETTE["rule"],
        "ticks": "outside",
        "tickcolor": PALETTE["rule"],
        "tickfont": {"color": PALETTE["ink"], "size": 11},
        "titlefont": {"color": PALETTE["ink"], "size": 12},
    }


def render_lines_html(
    div_id: str,
    times: list[float],
    series: dict[str, list[float]],
    *,
    title: str,
    y_title: str = "",
    height: int = 320,
    accent: str | None = None,
    trace_colors: dict[str, str] | None = None,
) -> str:
    """Render a multi-line Plotly chart as a self-contained HTML fragment."""
    colors = trace_colors or {}
    traces = []
    for label, ys in series.items():
        color = colors.get(label) or COLOR_BY_OBSERVABLE.get(label) or None
        spec: dict = {"x": times, "y": ys, "type": "scatter", "mode": "lines",
                      "name": label, "line": {"width": 2.2}}
        if color:
            spec["line"]["color"] = color
        traces.append(spec)
    layout = {
        **_BASE_LAYOUT,
        "title": {"text": f"<b>{title}</b>", "x": 0.02, "xanchor": "left",
                  "font": {"size": 14, "color": PALETTE["ink"]}},
        "xaxis": _axis_style("time"),
        "yaxis": _axis_style(y_title),
    }
    accent_bar = (
        f'<div style="height:3px;background:{accent};margin-bottom:6px;border-radius:2px"></div>'
        if accent else ''
    )
    return (
        f'{accent_bar}'
        f'<div id="{div_id}" style="height:{height}px"></div>'
        f'<script src="{PLOTLY_CDN}"></script>'
        f'<script>Plotly.newPlot('
        f'"{div_id}",{json.dumps(traces)},{json.dumps(layout)},'
        f'{{responsive:true,displayModeBar:false}});</script>'
    ) + _AUTOSIZE_SCRIPT


def render_dual_axis_html(
    div_id: str,
    times: list[float],
    left_series: dict[str, list[float]],
    right_series: dict[str, list[float]],
    *,
    title: str,
    left_title: str,
    right_title: str,
    height: int = 320,
    accent: str | None = None,
) -> str:
    """Two y-axes — left + right — for quantities with different units."""
    traces = []
    for label, ys in left_series.items():
        color = COLOR_BY_OBSERVABLE.get(label, PALETTE["rung2"])
        traces.append({"x": times, "y": ys, "type": "scatter", "mode": "lines",
                       "name": label, "line": {"width": 2.2, "color": color}})
    for label, ys in right_series.items():
        color = COLOR_BY_OBSERVABLE.get(label, PALETTE["accent_warm"])
        traces.append({"x": times, "y": ys, "type": "scatter", "mode": "lines",
                       "name": label, "yaxis": "y2",
                       "line": {"width": 2.2, "color": color, "dash": "dot"}})
    layout = {
        **_BASE_LAYOUT,
        "title": {"text": f"<b>{title}</b>", "x": 0.02, "xanchor": "left",
                  "font": {"size": 14, "color": PALETTE["ink"]}},
        "xaxis": _axis_style("time"),
        "yaxis": _axis_style(left_title),
        "yaxis2": {**_axis_style(right_title), "overlaying": "y", "side": "right"},
    }
    accent_bar = (
        f'<div style="height:3px;background:{accent};margin-bottom:6px;border-radius:2px"></div>'
        if accent else ''
    )
    return (
        f'{accent_bar}'
        f'<div id="{div_id}" style="height:{height}px"></div>'
        f'<script src="{PLOTLY_CDN}"></script>'
        f'<script>Plotly.newPlot('
        f'"{div_id}",{json.dumps(traces)},{json.dumps(layout)},'
        f'{{responsive:true,displayModeBar:false}});</script>'
    ) + _AUTOSIZE_SCRIPT


def render_scatter_html(
    div_id: str,
    xs: list[float],
    ys: list[float],
    *,
    color_by: list[float] | None = None,
    title: str,
    x_title: str,
    y_title: str,
    height: int = 320,
    accent: str | None = None,
) -> str:
    """Single scatter trace, optionally colored by a third quantity (e.g. time)."""
    trace = {
        "x": xs, "y": ys, "type": "scatter", "mode": "lines+markers",
        "marker": {"size": 7,
                   "color": color_by if color_by is not None else PALETTE["rung3"],
                   "colorscale": "Viridis" if color_by is not None else None,
                   "showscale": True if color_by is not None else False,
                   "colorbar": {"title": "time"} if color_by is not None else None,
                   "line": {"color": "white", "width": 1}},
        "line": {"color": PALETTE["muted"], "width": 1.2, "dash": "dot"},
    }
    layout = {
        **_BASE_LAYOUT,
        "title": {"text": f"<b>{title}</b>", "x": 0.02, "xanchor": "left",
                  "font": {"size": 14, "color": PALETTE["ink"]}},
        "xaxis": _axis_style(x_title),
        "yaxis": _axis_style(y_title),
        "hovermode": "closest",
        "legend": {"orientation": "h", "y": -0.25, "x": 0.5, "xanchor": "center"},
    }
    accent_bar = (
        f'<div style="height:3px;background:{accent};margin-bottom:6px;border-radius:2px"></div>'
        if accent else ''
    )
    return (
        f'{accent_bar}'
        f'<div id="{div_id}" style="height:{height}px"></div>'
        f'<script src="{PLOTLY_CDN}"></script>'
        f'<script>Plotly.newPlot('
        f'"{div_id}",{json.dumps([trace])},{json.dumps(layout)},'
        f'{{responsive:true,displayModeBar:false}});</script>'
    ) + _AUTOSIZE_SCRIPT


def render_stacked_area_html(
    div_id: str,
    times: list[float],
    series: dict[str, list[float]],
    *,
    title: str,
    y_title: str = "",
    height: int = 320,
    accent: str | None = None,
) -> str:
    """Stacked area chart (e.g. energy budget components)."""
    traces = []
    for label, ys in series.items():
        color = COLOR_BY_OBSERVABLE.get(label, PALETTE["muted"])
        traces.append({"x": times, "y": ys, "type": "scatter", "mode": "lines",
                       "name": label, "stackgroup": "one",
                       "line": {"width": 0.8, "color": color},
                       "fillcolor": color, "opacity": 0.75})
    layout = {
        **_BASE_LAYOUT,
        "title": {"text": f"<b>{title}</b>", "x": 0.02, "xanchor": "left",
                  "font": {"size": 14, "color": PALETTE["ink"]}},
        "xaxis": _axis_style("time"),
        "yaxis": _axis_style(y_title),
    }
    accent_bar = (
        f'<div style="height:3px;background:{accent};margin-bottom:6px;border-radius:2px"></div>'
        if accent else ''
    )
    return (
        f'{accent_bar}'
        f'<div id="{div_id}" style="height:{height}px"></div>'
        f'<script src="{PLOTLY_CDN}"></script>'
        f'<script>Plotly.newPlot('
        f'"{div_id}",{json.dumps(traces)},{json.dumps(layout)},'
        f'{{responsive:true,displayModeBar:false}});</script>'
    ) + _AUTOSIZE_SCRIPT
