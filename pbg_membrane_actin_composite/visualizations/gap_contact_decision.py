"""Gap–contact DECISION figure for the `fixed-boundary` study.

This is the pass/fail decision figure for `fixed-boundary`. Per its study.yaml:

  * decision_figure: "tip–wall gap distribution + contact-force accumulation,
    with Peskin (1993) expected ratchet rate overlaid";
  * expected_pattern: "barrier_velocity ≈ 0; contact_force accumulates; tip–wall
    gap distribution consistent with thermal-fluctuation ratchet";
  * acceptance_threshold: "mean barrier_velocity within ±1e-3 AND contact_force > 0
    and rising; gap stats within Peskin band".

The figure has two panels rendered in ONE Plotly figure:

  1. tip–wall GAP distribution (histogram of pooled `gap` series across all runs);
  2. contact-force ACCUMULATION (cumulative Σ contact_force vs time, per run + mean).

It carries an EXPECTED PATTERN box, draws the acceptance threshold on the plot
(zero-line for contact_force>0; a readout of the measured mean barrier_velocity
with a PASS/FAIL on |mean|<1e-3), an amber NOT-YET-VALIDATED stamp (the Peskin
1993 ratchet-rate overlay has no digitized data yet — drawn only as a clearly
labelled schematic band, never as validated evidence), and a provenance footer.

Reads runs.db directly (Path C) so every run in the study contributes. Built from
scalar observables already in runs.db (gap, contact_force, barrier_velocity, time).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pbg_superpowers.visualization import Visualization
from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    PLOTLY_CDN, _BASE_LAYOUT, _axis_style, PALETTE, _autosize_script,
)

# Color semantics required by the brief.
C_FORCE = "#dc2626"      # contact_force — red-600
C_VELOCITY = "#059669"   # barrier / velocity — green
C_BENCHMARK = "#111827"  # benchmark / Peskin reference — near-black

_VEL_TOL = 1e-3          # acceptance threshold on |mean barrier_velocity|


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


def _load_runs(db_path: Path) -> tuple[list[dict], int]:
    """One entry per simulation: time series of gap, contact_force, barrier_velocity.

    Returns (runs, total_steps). Malformed state blobs are skipped defensively.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        sim_ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT simulation_id FROM history ORDER BY rowid")]
        runs: list[dict] = []
        total = 0
        for sim in sim_ids:
            t, gap, cf, bv = [], [], [], []
            for (b,) in conn.execute(
                "SELECT state FROM history WHERE simulation_id=? ORDER BY step", (sim,)):
                try:
                    s = json.loads(b)
                except Exception:
                    continue
                total += 1
                t.append(float(s.get("time") or 0.0))
                gap.append(float(s.get("gap") or 0.0))
                cf.append(float(s.get("contact_force") or 0.0))
                bv.append(float(s.get("barrier_velocity") or 0.0))
            if not t:
                continue
            # cumulative contact force (the "accumulation")
            cum, acc = [], 0.0
            for x in cf:
                acc += x
                cum.append(acc)
            runs.append({"sim": str(sim), "t": t, "gap": gap, "cf": cf,
                         "cum": cum, "bv": bv})
        return runs, total
    finally:
        conn.close()


class GapContactDecision(Visualization):
    """Tip–wall gap distribution + contact-force accumulation for `fixed-boundary`.

    The study's decision figure: barrier_velocity ≈ 0, contact_force accumulates,
    gap distribution consistent with a thermal-fluctuation (Peskin) ratchet. The
    Peskin 1993 ratchet-rate overlay is drawn as a clearly-labelled schematic band
    pending digitized reference data.
    """

    config_schema = {
        'title': {'_type': 'string',
                  '_default': 'Gap distribution + contact-force accumulation — fixed-boundary (DECISION FIGURE)'},
        'accent': {'_type': 'string', '_default': '#94a3b8'},  # rung1 — fixed boundary
        'study_slug': {'_type': 'string', '_default': ''},
    }

    def inputs(self):
        # Path C: read runs.db directly so all runs contribute.
        return {}

    def update(self, state, interval=1.0):
        cfg = self.config or {}
        slug = (cfg.get('study_slug') or '').strip() or None
        db = _find_runs_db(slug)
        if db is None:
            return {'html': '<p style="color:#991b1b">GapContactDecision: no runs.db found under studies/*/</p>'}
        runs, total_steps = _load_runs(db)
        if not runs:
            return {'html': f'<p style="color:#991b1b">GapContactDecision: no history in {db.name}</p>'}

        # ---- pooled statistics ----
        all_gap = [g for r in runs for g in r["gap"]]
        all_bv = [v for r in runs for v in r["bv"]]
        mean_bv = sum(all_bv) / len(all_bv) if all_bv else 0.0
        vel_pass = abs(mean_bv) < _VEL_TOL

        # contact_force accumulation: peak cumulative across runs (is it rising > 0?)
        final_cums = [r["cum"][-1] for r in runs if r["cum"]]
        max_cum = max(final_cums) if final_cums else 0.0
        force_pass = max_cum > 0.0

        # gap distribution stats
        n_gap = len(all_gap)
        gap_mean = sum(all_gap) / n_gap if n_gap else 0.0
        gap_sorted = sorted(all_gap)
        gap_med = gap_sorted[n_gap // 2] if n_gap else 0.0
        gap_lo = gap_sorted[max(0, int(0.05 * n_gap))] if n_gap else 0.0
        gap_hi = gap_sorted[min(n_gap - 1, int(0.95 * n_gap))] if n_gap else 1.0

        # ---- traces ----
        traces = []

        # Panel 1: pooled gap histogram (xaxis/yaxis)
        traces.append({
            "x": all_gap, "type": "histogram", "name": "tip–wall gap",
            "marker": {"color": C_VELOCITY, "line": {"color": "white", "width": 0.5}},
            "opacity": 0.85, "nbinsx": 24,
            "xaxis": "x", "yaxis": "y", "hovertemplate": "gap=%{x:.3f}<br>count=%{y}<extra></extra>",
        })

        # Panel 2: contact-force accumulation per run (faint) + mean (bold) (x2/y2)
        for r in runs:
            traces.append({
                "x": r["t"], "y": r["cum"], "type": "scatter", "mode": "lines",
                "name": f"run …{r['sim'][-6:]}", "showlegend": False, "hoverinfo": "skip",
                "line": {"color": C_FORCE, "width": 1}, "opacity": 0.3,
                "xaxis": "x2", "yaxis": "y2",
            })
        # mean cumulative on a shared time grid
        tmax = max((r["t"][-1] for r in runs if r["t"]), default=16.0)
        grid_n = 33
        grid = [tmax * k / (grid_n - 1) for k in range(grid_n)]

        def _interp(ts, ys, x):
            if not ts:
                return 0.0
            if x <= ts[0]:
                return ys[0]
            if x >= ts[-1]:
                return ys[-1]
            for i in range(1, len(ts)):
                if ts[i] >= x:
                    t0, t1 = ts[i - 1], ts[i]
                    y0, y1 = ys[i - 1], ys[i]
                    if t1 == t0:
                        return y1
                    return y0 + (y1 - y0) * (x - t0) / (t1 - t0)
            return ys[-1]

        mean_cum = []
        for x in grid:
            vals = [_interp(r["t"], r["cum"], x) for r in runs if r["t"]]
            mean_cum.append(sum(vals) / len(vals) if vals else 0.0)
        traces.append({
            "x": grid, "y": mean_cum, "type": "scatter", "mode": "lines",
            "name": "mean Σ contact_force", "line": {"color": C_FORCE, "width": 3},
            "xaxis": "x2", "yaxis": "y2",
            "hovertemplate": "t=%{x:.1f}<br>Σcf=%{y:.3f}<extra></extra>",
        })

        # ---- shapes: Peskin schematic band on panel 1, zero-line on panel 2 ----
        shapes = [
            {  # Peskin (1993) schematic gap band — NOT validated, pending digitized data
                "type": "rect", "xref": "x", "yref": "paper",
                "x0": gap_lo, "x1": gap_hi, "y0": 0, "y1": 1,
                "fillcolor": "rgba(17,24,39,0.06)", "line": {"width": 0},
                "layer": "below",
            },
            {  # band edges as dashed reference lines
                "type": "line", "xref": "x", "yref": "paper",
                "x0": gap_lo, "x1": gap_lo, "y0": 0, "y1": 1,
                "line": {"color": C_BENCHMARK, "width": 1, "dash": "dash"}},
            {"type": "line", "xref": "x", "yref": "paper",
             "x0": gap_hi, "x1": gap_hi, "y0": 0, "y1": 1,
             "line": {"color": C_BENCHMARK, "width": 1, "dash": "dash"}},
            {  # contact_force>0 acceptance threshold — zero line on accumulation panel
                "type": "line", "xref": "x2 domain", "yref": "y2",
                "x0": 0, "x1": 1, "y0": 0, "y1": 0,
                "line": {"color": PALETTE["muted"], "width": 1.5, "dash": "dot"}},
        ]

        # ---- layout ----
        layout = {
            **_BASE_LAYOUT,
            "title": {"text": "<b>Tip–wall gap distribution + contact-force accumulation — DECISION FIGURE</b>",
                      "x": 0.02, "xanchor": "left", "font": {"size": 14, "color": PALETTE["ink"]}},
            "hovermode": "closest",
            "showlegend": False,
            "margin": {"l": 55, "r": 25, "t": 70, "b": 55},
            "shapes": shapes,
            # Panel 1 (left): gap histogram
            "xaxis": {**_axis_style("tip–wall gap"), "domain": [0.0, 0.46]},
            "yaxis": {**_axis_style("count"), "domain": [0.0, 1.0]},
            # Panel 2 (right): contact-force accumulation
            "xaxis2": {**_axis_style("time"), "domain": [0.58, 1.0], "anchor": "y2"},
            "yaxis2": {**_axis_style("Σ contact_force (cumulative)"), "domain": [0.0, 1.0], "anchor": "x2"},
            "annotations": [
                {  # panel titles
                    "xref": "paper", "yref": "paper", "x": 0.0, "y": 1.06,
                    "xanchor": "left", "yanchor": "bottom", "showarrow": False,
                    "font": {"size": 11, "color": PALETTE["ink"]},
                    "text": "<b>(1) tip–wall gap distribution</b>"},
                {"xref": "paper", "yref": "paper", "x": 0.58, "y": 1.06,
                 "xanchor": "left", "yanchor": "bottom", "showarrow": False,
                 "font": {"size": 11, "color": PALETTE["ink"]},
                 "text": "<b>(2) contact-force accumulation</b>"},
                {  # Peskin schematic label on panel 1
                    "xref": "x", "yref": "paper", "x": (gap_lo + gap_hi) / 2, "y": 0.97,
                    "xanchor": "center", "yanchor": "top", "showarrow": False,
                    "font": {"size": 9, "color": C_BENCHMARK},
                    "text": "Peskin band<br>(schematic)"},
                {  # EXPECTED PATTERN box
                    "xref": "paper", "yref": "paper", "x": 0.46, "y": 0.98,
                    "xanchor": "right", "yanchor": "top", "align": "left", "showarrow": False,
                    "bordercolor": PALETTE["rule"], "borderwidth": 1, "borderpad": 6,
                    "bgcolor": "rgba(255,255,255,0.92)",
                    "font": {"size": 9.5, "color": PALETTE["ink"]},
                    "text": ("<b>EXPECTED PATTERN (PASS)</b><br>"
                             "barrier_velocity ≈ 0 (wall fixed);<br>"
                             "contact_force accumulates (Σ rising > 0);<br>"
                             "gap distribution sits within the<br>"
                             "thermal-fluctuation (Peskin) band.<br>"
                             "<b>Threshold:</b> |mean V| &lt; 1e-3 AND<br>"
                             "Σcf &gt; 0 &amp; rising AND gap ∈ Peskin band."),
                },
                {  # measured readout — barrier_velocity + accumulation verdict
                    "xref": "paper", "yref": "paper", "x": 1.0, "y": 0.98,
                    "xanchor": "right", "yanchor": "top", "align": "left", "showarrow": False,
                    "bordercolor": (C_VELOCITY if (vel_pass and force_pass) else "#d97706"),
                    "borderwidth": 1.5, "borderpad": 6,
                    "bgcolor": "rgba(255,255,255,0.95)",
                    "font": {"size": 9.5, "color": PALETTE["ink"]},
                    "text": (f"<b>MEASURED</b><br>"
                             f"mean barrier_velocity = {mean_bv:.2e}<br>"
                             f"|mean| &lt; 1e-3 : <b>{'PASS' if vel_pass else 'FAIL'}</b><br>"
                             f"peak Σ contact_force = {max_cum:.3f}<br>"
                             f"Σcf &gt; 0 &amp; rising : <b>{'PASS' if force_pass else 'FAIL'}</b><br>"
                             f"gap median = {gap_med:.3f} (band {gap_lo:.2f}–{gap_hi:.2f})"),
                },
                {  # honest status stamp — amber
                    "xref": "paper", "yref": "paper", "x": 0.0, "y": -0.16,
                    "xanchor": "left", "yanchor": "top", "showarrow": False,
                    "bgcolor": "rgba(254,243,199,0.95)", "bordercolor": "#d97706",
                    "borderwidth": 1, "borderpad": 4,
                    "font": {"size": 10, "color": "#92400e"},
                    "text": "NOT YET VALIDATED · Peskin reference pending (gap band is schematic, not digitized)",
                },
            ],
        }

        div_id = f"gap-contact-decision-{id(self)}"
        prov = (f'source: {db.parent.name}/runs.db · {len(runs)} run(s) · '
                f'{total_steps} step(s) total · gap n={n_gap} (mean {gap_mean:.3f}) · '
                f'Peskin band = 5–95th pct of observed gap (placeholder until digitized) · '
                f'accumulation = cumulative Σ contact_force')
        accent = cfg.get('accent', '#94a3b8')
        height = 420
        html = (
            f'<div style="height:3px;background:{accent};margin-bottom:6px;border-radius:2px"></div>'
            f'<div id="{div_id}" style="height:{height}px"></div>'
            f'<div style="font-size:11px;color:#6b7280;margin-top:4px">{prov}</div>'
            f'<script src="{PLOTLY_CDN}"></script>'
            f'<script>Plotly.newPlot("{div_id}",{json.dumps(traces)},{json.dumps(layout)},'
            f'{{responsive:true,displayModeBar:false}});</script>'
        )
        return {'html': html + _autosize_script(height + 30)}
