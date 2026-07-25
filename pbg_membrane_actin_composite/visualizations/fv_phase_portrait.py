"""Force–velocity PHASE PORTRAIT decision figure for `rigid-movable-boundary`.

This is the pass/fail decision figure for the rigid-movable-boundary study. Per its
study.yaml:

  * decision_figure: "force–velocity phase portrait, low-drag vs high-drag on shared
    axes, with transient/steady-state windows marked and the Peskin stall bound drawn";
  * expected_pattern: "velocity settles to a non-zero steady state; force and drag
    balance; stall force ≤ Peskin ceiling";
  * acceptance_threshold: "steady-state mean barrier_velocity in (0, Peskin ceiling]".

The figure plots barrier_velocity (y) against mean_contact_force (x) as a trajectory
per run. Each trajectory's first half (transient) is faint/dotted and its second half
(approach to steady state) is solid; a diamond marks the steady-state point (second-half
mean of F and V). Conditions are colored/labelled by barrier_drag when that value is
recorded in runs_meta.params_json (low-drag vs high-drag); runs without a recorded drag
are shown generically.

The Peskin stall bound is drawn as a clearly-labelled SCHEMATIC load–velocity reference
(declining line from a zero-load velocity ceiling to a stall force) — NOT digitized data
— carried with an amber "NOT YET VALIDATED · Peskin bound schematic" stamp until a real
Peskin ceiling is registered. The acceptance threshold (steady-state V in (0, ceiling])
is drawn and the measured steady-state V per run is shown with a pass/fail (V > 0) flag.

Reads runs.db directly (Path C) so every run/condition in the study is overlaid.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from viva_superpowers.visualization import Visualization
from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    PLOTLY_CDN, _BASE_LAYOUT, _axis_style, PALETTE, _autosize_script,
)

# Color semantics from the investigation guidelines.visual_design block.
C_FORCE = "#7c3aed"      # purple — force axis
C_VELOCITY = "#059669"   # green — velocity axis
C_BENCHMARK = "#111827"  # near-black — Peskin reference

# Distinct colors per drag condition; generic (un-recorded drag) runs cycle through a
# muted-leaning fallback set so they stay visually subordinate to the labelled conditions.
_DRAG_COLORS = {
    "low": "#0ea5e9",   # sky-500 — low drag (light wall, faster)
    "high": "#dc2626",  # red-600 — high drag (heavy wall, near stall)
}
_GENERIC_COLORS = ["#9ca3af", "#6b7280", "#a855f7", "#f97316", "#14b8a6", "#64748b"]


def _find_runs_db(study_slug: str | None) -> Path | None:
    cwd = Path.cwd()
    if study_slug:
        explicit = cwd / "studies" / study_slug / "runs.db"
        if explicit.is_file():
            return explicit
    candidates = list((cwd / "studies").glob("*/runs.db"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _second_half_mean(xs: list[float]) -> float:
    if not xs:
        return 0.0
    half = xs[len(xs) // 2:]
    return sum(half) / len(half) if half else 0.0


def _load_runs(db_path: Path) -> list[dict]:
    """One entry per simulation in history, with its F/V series + drag/label provenance."""
    conn = sqlite3.connect(str(db_path))
    try:
        # provenance: run_id / sim_name -> label, barrier_drag, n_steps, duration
        meta: dict[str, dict] = {}
        try:
            for run_id, sim_name, params_json, n_steps, t0, t1 in conn.execute(
                "SELECT run_id, sim_name, params_json, n_steps, started_at, completed_at "
                "FROM runs_meta"
            ):
                drag = None
                try:
                    drag = (json.loads(params_json) or {}).get("barrier_drag")
                except Exception:
                    drag = None
                rec = {"label": sim_name, "drag": drag, "n_steps": n_steps,
                       "duration": (t1 - t0) if (t0 and t1) else None}
                if run_id:
                    meta[str(run_id)] = rec
                if sim_name:
                    meta.setdefault(str(sim_name), rec)
        except sqlite3.OperationalError:
            pass

        sim_ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT simulation_id FROM history ORDER BY rowid")]
        runs = []
        for sim in sim_ids:
            states = [json.loads(b) for (b,) in conn.execute(
                "SELECT state FROM history WHERE simulation_id=? ORDER BY step", (sim,))]
            if not states:
                continue
            f = [float(s.get("mean_contact_force") or s.get("contact_force") or 0.0)
                 for s in states]
            v = [float(s.get("barrier_velocity") or 0.0) for s in states]
            m = meta.get(str(sim), {})
            runs.append({
                "sim": str(sim), "f": f, "v": v,
                "F": _second_half_mean(f), "V": _second_half_mean(v),
                "drag": m.get("drag"), "label": m.get("label"),
                "n_steps": m.get("n_steps") or len(states),
                "duration": m.get("duration"),
            })
        return runs
    finally:
        conn.close()


def _drag_bucket(drag) -> str | None:
    """Coarse low/high bucket for color/label when a numeric drag is recorded."""
    if drag is None:
        return None
    try:
        d = float(drag)
    except (TypeError, ValueError):
        return None
    # The study sweeps barrier_drag=2.0 (low) vs 16.0 (high); split at the geometric mid.
    return "low" if d < 6.0 else "high"


class FVPhasePortrait(Visualization):
    """Force–velocity phase portrait (barrier_velocity vs mean_contact_force) overlaying
    the drag conditions, with transient/steady-state windows marked, the acceptance
    threshold drawn, per-run pass/fail (V > 0), and a schematic Peskin stall bound.

    The decision figure for the rigid-movable-boundary study."""

    config_schema = {
        'title': {'_type': 'string',
                  '_default': 'Force–velocity phase portrait — rigid movable boundary (DECISION FIGURE)'},
        'accent': {'_type': 'string', '_default': '#0ea5e9'},
        'study_slug': {'_type': 'string', '_default': 'rigid-movable-boundary'},
    }

    def inputs(self):
        # Path C: read runs.db directly so all drag conditions overlay.
        return {}

    def update(self, state, interval=1.0):
        cfg = self.config or {}
        slug = (cfg.get('study_slug') or '').strip() or None
        db = _find_runs_db(slug)
        if db is None:
            return {'html': '<p style="color:#991b1b">FVPhasePortrait: no runs.db found '
                            'under studies/*/</p>'}
        runs = _load_runs(db)
        if not runs:
            return {'html': f'<p style="color:#991b1b">FVPhasePortrait: no history in '
                            f'{db.name}</p>'}

        # Order: labelled drag conditions first (low → high), generic runs after.
        runs.sort(key=lambda r: (_drag_bucket(r["drag"]) is None,
                                 float(r["drag"]) if r["drag"] is not None else 0.0))

        traces = []
        all_F, all_V = [], []
        generic_i = 0
        n_pass = 0
        for r in runs:
            bucket = _drag_bucket(r["drag"])
            if bucket is not None:
                color = _DRAG_COLORS[bucket]
                label = (r["label"] or f"{bucket}-drag")
                if r["drag"] is not None:
                    label = f"{label} (drag={float(r['drag']):g})"
            else:
                color = _GENERIC_COLORS[generic_i % len(_GENERIC_COLORS)]
                generic_i += 1
                label = (r["label"] or f"run …{r['sim'][-6:]}") + " (drag n/r)"

            f, v = r["f"], r["v"]
            all_F += f
            all_V += v
            half = len(f) // 2
            # First half = transient (faint dotted).
            traces.append({"x": f[:half + 1], "y": v[:half + 1], "type": "scatter",
                           "mode": "lines", "name": f"{label} — transient",
                           "showlegend": False, "hoverinfo": "skip", "opacity": 0.30,
                           "line": {"color": color, "width": 1.2, "dash": "dot"}})
            # Second half = approach to steady state (solid).
            traces.append({"x": f[half:], "y": v[half:], "type": "scatter",
                           "mode": "lines", "name": f"{label} — steady-state window",
                           "showlegend": False, "hoverinfo": "skip", "opacity": 0.85,
                           "line": {"color": color, "width": 2.0}})

            # Steady-state decision point (second-half mean of F and V).
            passed = r["V"] > 0.0
            n_pass += int(passed)
            sym = "diamond" if passed else "x-thin"
            flag = "PASS V&gt;0" if passed else "FAIL V≤0"
            traces.append({
                "x": [r["F"]], "y": [r["V"]], "type": "scatter", "mode": "markers+text",
                "name": f"{label} · ss V={r['V']:.4g} ({flag})",
                "text": [f"V={r['V']:.3g}"], "textposition": "top center",
                "textfont": {"size": 9, "color": color},
                "marker": {"size": 14, "color": color, "symbol": sym,
                           "line": {"color": ("white" if passed else "#7f1d1d"),
                                    "width": 1.5}},
                "hovertemplate": (f"{label}<br>steady-state F=%{{x:.4g}}<br>"
                                  f"steady-state V=%{{y:.4g}}<br>{flag}<extra></extra>"),
            })

        # Axis envelope.
        fmin = min(all_F) if all_F else 0.0
        fmax = max(all_F) if all_F else 1.0
        vmax = max(all_V) if all_V else 1.0
        if fmax <= fmin:
            fmax = fmin + 1.0
        if vmax <= 0:
            vmax = 1.0

        # --- Schematic Peskin stall bound (NOT digitized data) -----------------------
        # Classic Brownian-ratchet load–velocity: velocity is maximal at zero load (the
        # "Peskin ceiling") and declines to zero at the stall force. Drawn as a declining
        # schematic line spanning the observed force range, scaled to sit above the data
        # envelope so it reads as an upper bound until a real ceiling is registered.
        v_ceiling = vmax * 1.25           # schematic zero-load velocity ceiling
        f_stall = fmax * 1.20             # schematic stall force (V -> 0)
        n = 24
        ref_x = [f_stall * k / (n - 1) for k in range(n)]
        ref_y = [max(0.0, v_ceiling * (1.0 - x / f_stall)) for x in ref_x]
        traces.append({
            "x": ref_x, "y": ref_y, "type": "scatter", "mode": "lines",
            "name": "Peskin stall bound (schematic — data pending)",
            "line": {"color": C_BENCHMARK, "width": 2, "dash": "dash"}, "opacity": 0.6,
            "hoverinfo": "skip",
        })

        layout = {
            **_BASE_LAYOUT,
            "title": {"text": "<b>Force–velocity phase portrait — DECISION FIGURE</b>",
                      "x": 0.02, "xanchor": "left",
                      "font": {"size": 14, "color": PALETTE["ink"]}},
            "xaxis": {**_axis_style("mean_contact_force  (F)"), "color": C_FORCE,
                      "range": [min(0.0, fmin), f_stall * 1.05]},
            "yaxis": {**_axis_style("barrier_velocity  (V)"), "color": C_VELOCITY,
                      "range": [min(0.0, min(all_V) if all_V else 0.0), v_ceiling * 1.08]},
            "hovermode": "closest",
            "legend": {"orientation": "h", "y": -0.30, "x": 0.5, "xanchor": "center",
                       "font": {"size": 9}},
            "shapes": [
                {  # acceptance-threshold lower bound: V must be > 0
                    "type": "line", "xref": "paper", "x0": 0, "x1": 1,
                    "yref": "y", "y0": 0.0, "y1": 0.0,
                    "line": {"color": C_VELOCITY, "width": 1.5, "dash": "dot"},
                },
                {  # schematic zero-load velocity ceiling (upper bound of acceptance band)
                    "type": "line", "xref": "paper", "x0": 0, "x1": 1,
                    "yref": "y", "y0": v_ceiling, "y1": v_ceiling,
                    "line": {"color": C_BENCHMARK, "width": 1, "dash": "dot"},
                    "opacity": 0.5,
                },
                {  # shaded acceptance band: 0 < V ≤ ceiling
                    "type": "rect", "xref": "paper", "x0": 0, "x1": 1,
                    "yref": "y", "y0": 0.0, "y1": v_ceiling,
                    "fillcolor": C_VELOCITY, "opacity": 0.05,
                    "line": {"width": 0}, "layer": "below",
                },
            ],
            "annotations": [
                {  # EXPECTED PATTERN box (pass condition)
                    "xref": "paper", "yref": "paper", "x": 0.98, "y": 0.98,
                    "xanchor": "right", "yanchor": "top", "align": "left",
                    "showarrow": False, "bordercolor": PALETTE["rule"], "borderwidth": 1,
                    "borderpad": 6, "bgcolor": "rgba(255,255,255,0.92)",
                    "font": {"size": 10, "color": PALETTE["ink"]},
                    "text": ("<b>EXPECTED PATTERN (PASS)</b><br>"
                             "Velocity settles to a non-zero steady state;<br>"
                             "force and drag balance; stall force ≤ Peskin<br>"
                             "ceiling.<br>"
                             "<b>Threshold:</b> steady-state mean barrier_velocity<br>"
                             "in (0, Peskin ceiling]  (shaded green band)."),
                },
                {  # acceptance band lower-bound label
                    "xref": "paper", "yref": "y", "x": 0.01, "y": 0.0,
                    "xanchor": "left", "yanchor": "bottom", "showarrow": False,
                    "font": {"size": 9, "color": C_VELOCITY},
                    "text": "V = 0  (must exceed)",
                },
                {  # Peskin ceiling label
                    "xref": "paper", "yref": "y", "x": 0.99, "y": v_ceiling,
                    "xanchor": "right", "yanchor": "bottom", "showarrow": False,
                    "font": {"size": 9, "color": C_BENCHMARK},
                    "text": "Peskin ceiling (schematic)",
                },
                {  # honest status stamp
                    "xref": "paper", "yref": "paper", "x": 0.02, "y": 0.98,
                    "xanchor": "left", "yanchor": "top", "showarrow": False,
                    "bgcolor": "rgba(254,243,199,0.95)", "bordercolor": "#d97706",
                    "borderwidth": 1, "borderpad": 4,
                    "font": {"size": 10, "color": "#92400e"},
                    "text": "NOT YET VALIDATED · Peskin bound schematic",
                },
                {  # transient vs steady-state legend cue
                    "xref": "paper", "yref": "paper", "x": 0.02, "y": 0.02,
                    "xanchor": "left", "yanchor": "bottom", "showarrow": False,
                    "bgcolor": "rgba(255,255,255,0.85)", "bordercolor": PALETTE["rule"],
                    "borderwidth": 1, "borderpad": 4,
                    "font": {"size": 9, "color": PALETTE["ink"]},
                    "text": ("dotted = transient (1st half) · solid = steady-state "
                             "window (2nd half)<br>◇ = steady-state mean (V&gt;0 pass) · "
                             "✕ = fail (V≤0)"),
                },
            ],
        }

        div_id = f"fv-phase-portrait-{id(self)}"
        n_drag = sum(1 for r in runs if _drag_bucket(r["drag"]) is not None)
        steps = sorted({r["n_steps"] for r in runs})
        steps_str = (f"{steps[0]}" if len(steps) == 1
                     else f"{min(steps)}–{max(steps)}")
        dur = next((r["duration"] for r in runs if r.get("duration")), None)
        drag_note = (f"{n_drag} with barrier_drag recorded"
                     if n_drag else "barrier_drag not recorded in params")
        prov = (f'source: {db.parent.name}/runs.db · {len(runs)} run(s) · '
                f'{steps_str} steps/run · {drag_note} · '
                f'{n_pass}/{len(runs)} runs steady-state V&gt;0 · '
                f'steady state = 2nd-half mean'
                f'{f" · ~{dur:.1f}s/run" if dur else ""} · '
                f'Peskin ceiling schematic (digitized bound pending)')
        accent = cfg.get('accent', '#0ea5e9')
        height = 420
        html = (
            f'<div style="height:3px;background:{accent};margin-bottom:6px;'
            f'border-radius:2px"></div>'
            f'<div id="{div_id}" style="height:{height}px"></div>'
            f'<div style="font-size:11px;color:#6b7280;margin-top:4px">{prov}</div>'
            f'<script src="{PLOTLY_CDN}"></script>'
            f'<script>Plotly.newPlot("{div_id}",{json.dumps(traces)},'
            f'{json.dumps(layout)},{{responsive:true,displayModeBar:false}});</script>'
        )
        return {'html': html + _autosize_script(height + 30)}
