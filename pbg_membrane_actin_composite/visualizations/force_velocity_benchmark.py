"""Force–velocity BENCHMARK decision figure (the dominant figure of the investigation).

This is the pass/fail decision figure for `coupled-ratchet-cycle-fv-reproduction`.
Per the visuals-and-interpretation review it must:

  * make the F-V relationship the primary object (one steady-state (F, V) point per
    growth-rate condition, plus the faint full trajectory for context);
  * carry an EXPECTED PATTERN box describing what a passing result looks like;
  * draw the ACCEPTANCE THRESHOLD on the plot;
  * overlay the literature reference (Inoue 2015) — drawn as a clearly-labelled
    *schematic* until digitized reference data is registered (see the investigation's
    decisions_needed); never present the schematic as validated evidence;
  * show provenance (source db, simulation ids, step count, duration).

Buildable today from scalar observables in runs.db (mean_contact_force, barrier_velocity,
time). Replicate uncertainty bands await multiple seeds per condition — noted on the figure
rather than faked. Reads runs.db directly (Path C) so every run in the study is overlaid.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pbg_superpowers.visualization import Visualization
from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    PLOTLY_CDN, _BASE_LAYOUT, _axis_style, PALETTE, _autosize_script,
)

# Color semantics from the investigation guidelines.visual_design block.
C_FORCE = "#7c3aed"      # purple
C_VELOCITY = "#059669"   # green
C_BENCHMARK = "#111827"  # near-black reference
_CONDITION_COLORS = ["#059669", "#0ea5e9", "#f97316", "#dc2626", "#7c3aed", "#a855f7"]


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
    """One entry per simulation in history, with its F/V series + best-effort provenance."""
    conn = sqlite3.connect(str(db_path))
    try:
        # provenance lookup: run_id/sim_name -> params_json, n_steps, duration
        meta: dict[str, dict] = {}
        try:
            for run_id, sim_name, params_json, n_steps, t0, t1 in conn.execute(
                "SELECT run_id, sim_name, params_json, n_steps, started_at, completed_at FROM runs_meta"
            ):
                rec = {"params": params_json, "n_steps": n_steps,
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
            t = [float(s.get("time") or 0.0) for s in states]
            f = [float(s.get("mean_contact_force") or s.get("contact_force") or 0.0) for s in states]
            v = [float(s.get("barrier_velocity") or 0.0) for s in states]
            m = meta.get(str(sim), {})
            growth = None
            if m.get("params"):
                try:
                    growth = (json.loads(m["params"]) or {}).get("growth_rate")
                except Exception:
                    growth = None
            runs.append({
                "sim": str(sim), "t": t, "f": f, "v": v,
                "F": _second_half_mean(f), "V": _second_half_mean(v),
                "growth_rate": growth, "n_steps": m.get("n_steps") or len(states),
                "duration": m.get("duration"),
            })
        return runs
    finally:
        conn.close()


class ForceVelocityBenchmark(Visualization):
    """Steady-state F-V points per condition with expected-pattern box, threshold, and
    a labelled (schematic) Inoue 2015 reference. The study's decision figure."""

    config_schema = {
        'title': {'_type': 'string', '_default': 'Force–velocity benchmark — Inoue 2015 (DECISION FIGURE)'},
        'accent': {'_type': 'string', '_default': '#10b981'},
        'study_slug': {'_type': 'string', '_default': ''},
    }

    def inputs(self):
        # Path C: read runs.db directly so all conditions/replicates overlay.
        return {}

    def update(self, state, interval=1.0):
        cfg = self.config or {}
        slug = (cfg.get('study_slug') or '').strip() or None
        db = _find_runs_db(slug)
        if db is None:
            return {'html': '<p style="color:#991b1b">ForceVelocityBenchmark: no runs.db found under studies/*/</p>'}
        runs = _load_runs(db)
        if not runs:
            return {'html': f'<p style="color:#991b1b">ForceVelocityBenchmark: no history in {db.name}</p>'}

        # Sort conditions by growth_rate when available (concave→convex is a growth-rate sweep).
        runs.sort(key=lambda r: (r["growth_rate"] is None, r["growth_rate"] if r["growth_rate"] is not None else 0.0))

        traces = []
        all_F, all_V = [], []
        for i, r in enumerate(runs):
            color = _CONDITION_COLORS[i % len(_CONDITION_COLORS)]
            label = (f"growth_rate={r['growth_rate']:g}" if r["growth_rate"] is not None
                     else f"run …{r['sim'][-6:]}")
            all_F += r["f"]; all_V += r["v"]
            # faint full trajectory
            traces.append({"x": r["f"], "y": r["v"], "type": "scatter", "mode": "lines",
                           "name": f"{label} (trajectory)", "showlegend": False,
                           "line": {"color": color, "width": 1, "dash": "dot"}, "opacity": 0.35,
                           "hoverinfo": "skip"})
            # steady-state decision point (second-half mean)
            traces.append({"x": [r["F"]], "y": [r["V"]], "type": "scatter", "mode": "markers+text",
                           "name": label, "text": [label], "textposition": "top center",
                           "textfont": {"size": 10, "color": color},
                           "marker": {"size": 14, "color": color, "symbol": "diamond",
                                      "line": {"color": "white", "width": 1.5}}})

        # Schematic Inoue 2015 reference (clearly labelled as pending real data) — a smooth
        # concave→convex curve spanning the observed force range, NOT validated data.
        if all_F:
            fmin, fmax = min(all_F), max(all_F)
            vmax = max(all_V) if all_V else 1.0
            if fmax <= fmin:
                fmax = fmin + 1.0
            n = 24
            ref_x = [fmin + (fmax - fmin) * k / (n - 1) for k in range(n)]
            # S-shaped (concave then convex) schematic, scaled to the data envelope
            def _s(u):  # u in [0,1] -> sigmoid-ish 0..1
                import math
                return 1.0 / (1.0 + math.exp(-8 * (u - 0.5)))
            ref_y = [vmax * _s((x - fmin) / (fmax - fmin)) for x in ref_x]
            traces.append({"x": ref_x, "y": ref_y, "type": "scatter", "mode": "lines",
                           "name": "Inoue 2015 (schematic — data pending)",
                           "line": {"color": C_BENCHMARK, "width": 2, "dash": "dash"},
                           "opacity": 0.5})

        layout = {
            **_BASE_LAYOUT,
            "title": {"text": "<b>Force–velocity benchmark — DECISION FIGURE</b>",
                      "x": 0.02, "xanchor": "left", "font": {"size": 14, "color": PALETTE["ink"]}},
            "xaxis": _axis_style("mean_contact_force  (F)"),
            "yaxis": _axis_style("barrier_velocity  (V)"),
            "hovermode": "closest",
            "legend": {"orientation": "h", "y": -0.28, "x": 0.5, "xanchor": "center"},
            "annotations": [
                {  # EXPECTED PATTERN box
                    "xref": "paper", "yref": "paper", "x": 0.98, "y": 0.98,
                    "xanchor": "right", "yanchor": "top", "align": "left", "showarrow": False,
                    "bordercolor": PALETTE["rule"], "borderwidth": 1, "borderpad": 6,
                    "bgcolor": "rgba(255,255,255,0.92)",
                    "font": {"size": 10, "color": PALETTE["ink"]},
                    "text": ("<b>EXPECTED PATTERN (PASS)</b><br>"
                             "F-V curvature flips concave→convex as<br>"
                             "growth_rate increases, tracking Inoue 2015.<br>"
                             "<b>Threshold:</b> quantified curvature sign-flip<br>"
                             "across the sweep, within the Inoue band."),
                },
                {  # honest status stamp
                    "xref": "paper", "yref": "paper", "x": 0.02, "y": 0.98,
                    "xanchor": "left", "yanchor": "top", "showarrow": False,
                    "bgcolor": "rgba(254,243,199,0.95)", "bordercolor": "#d97706",
                    "borderwidth": 1, "borderpad": 4,
                    "font": {"size": 10, "color": "#92400e"},
                    "text": "NOT YET VALIDATED · reference is schematic",
                },
            ],
        }

        div_id = f"fv-benchmark-{id(self)}"
        n_growth = sum(1 for r in runs if r["growth_rate"] is not None)
        dur = next((r["duration"] for r in runs if r.get("duration")), None)
        prov = (f'source: {db.parent.name}/runs.db · {len(runs)} run(s)'
                f'{f" · {n_growth} with growth_rate" if n_growth else ""}'
                f' · steady state = 2nd-half mean'
                f'{f" · ~{dur:.1f}s/run" if dur else ""}'
                f' · replicate bands pending (need multiple seeds per condition)')
        accent = cfg.get('accent', '#10b981')
        height = 380
        html = (
            f'<div style="height:3px;background:{accent};margin-bottom:6px;border-radius:2px"></div>'
            f'<div id="{div_id}" style="height:{height}px"></div>'
            f'<div style="font-size:11px;color:#6b7280;margin-top:4px">{prov}</div>'
            f'<script src="{PLOTLY_CDN}"></script>'
            f'<script>Plotly.newPlot("{div_id}",{json.dumps(traces)},{json.dumps(layout)},'
            f'{{responsive:true,displayModeBar:false}});</script>'
        )
        return {'html': html + _autosize_script(height + 30)}
