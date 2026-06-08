"""Newton's-3rd-law residual decision figure for `actin-to-membrane-force-handshake`.

This is the pass/fail decision figure for the force-handshake study. The study
asks whether the coupling interface conserves force sample-by-sample (Newton's
3rd law): the force actin exerts on the membrane should be balanced by an equal
and opposite membrane-side reaction, so a per-step residual should sit at ≈ 0
and the cumulative residual impulse should stay flat.

  decision_figure:   actin force, membrane force, residual force, and residual
                     impulse vs time (residual → 0), plus a histogram of
                     transferred forces to flag numerical outliers.
  expected_pattern:  residual force ≈ 0 throughout; transferred-force histogram
                     has no heavy tails / outliers.
  acceptance_thr.:   |residual force| / |actin force| < 0.05 per step, sample-by-sample.

HONEST DATA-PROVENANCE GAP (read the amber stamp on the figure):
runs.db emits the actin-side interface signal (`contact_force`) but does NOT emit
a commensurate membrane-side *integrated force / reaction impulse*. The only
membrane-side scalar published by the coupler is `osmotic_offset`, which is a
*scaled pressure offset* (here osmotic_offset = 0.05 · contact_force), NOT a
force in the same units. We therefore plot it as a clearly-labelled
membrane-force PROXY and compute a PROXY residual = actin_force − membrane_proxy.
Because the proxy is not a true reaction force, the measured proxy ratio is large
(~0.95), NOT ≈ 0 — this is a data-provenance limitation, not a physics failure,
and an exact Newton residual cannot be validated until the coupler emits the
membrane-side integrated force/impulse. We do NOT fabricate a residual≈0 result.

Reads runs.db directly (Path C) so every run in the study is pooled.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pbg_superpowers.visualization import Visualization
from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    PLOTLY_CDN, _BASE_LAYOUT, _axis_style, PALETTE, _autosize_script,
)

# Color semantics required by the task brief.
C_ACTIN = "#2563eb"      # blue   — actin-side force
C_MEMBRANE = "#dc2626"   # red    — membrane-side proxy
C_FORCE = "#7c3aed"      # purple — residual / transferred force
C_BENCHMARK = "#111827"  # near-black — threshold / reference


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


def _cumulative_impulse(times: list[float], residual: list[float]) -> list[float]:
    """Trapezoidal running integral of residual force over time (the reaction impulse)."""
    out: list[float] = []
    acc = 0.0
    for i in range(len(residual)):
        if i > 0:
            dt = times[i] - times[i - 1]
            acc += 0.5 * (residual[i] + residual[i - 1]) * dt
        out.append(acc)
    return out


def _load_runs(db_path: Path) -> list[dict]:
    """One entry per simulation: time / actin force / membrane proxy / residual series."""
    conn = sqlite3.connect(str(db_path))
    try:
        meta: dict[str, dict] = {}
        try:
            for run_id, sim_name, n_steps, t0, t1 in conn.execute(
                "SELECT run_id, sim_name, n_steps, started_at, completed_at FROM runs_meta"
            ):
                rec = {"n_steps": n_steps,
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
            # actin-side interface force (the transferred force)
            actin = [float(s.get("contact_force") or 0.0) for s in states]
            # best available membrane-side proxy (scaled pressure offset — NOT a true force)
            mem = [float(s.get("osmotic_offset") or 0.0) for s in states]
            residual = [a - m for a, m in zip(actin, mem)]
            impulse = _cumulative_impulse(t, residual)
            m = meta.get(str(sim), {})
            runs.append({
                "sim": str(sim), "t": t, "actin": actin, "mem": mem,
                "residual": residual, "impulse": impulse,
                "n_steps": m.get("n_steps") or len(states),
                "duration": m.get("duration"),
            })
        return runs
    finally:
        conn.close()


class NewtonResidual(Visualization):
    """Newton's-3rd-law residual at the actin↔membrane coupling interface — the
    decision figure for `actin-to-membrane-force-handshake`.

    Panels: (A) actin force, membrane-force PROXY, and proxy residual vs time;
    (B) cumulative residual impulse vs time; (C) histogram of transferred forces
    to flag numerical outliers. Carries an Expected-Pattern box, the acceptance
    threshold band (|residual|/|actin| < 0.05) with the MEASURED proxy ratio, an
    amber NOT-YET-VALIDATED stamp naming the membrane-side provenance gap, and a
    provenance footer. Reads runs.db directly (Path C)."""

    config_schema = {
        'title': {'_type': 'string',
                  '_default': "Newton's 3rd law residual — coupling interface (DECISION FIGURE)"},
        'accent': {'_type': 'string', '_default': C_FORCE},
        'study_slug': {'_type': 'string', '_default': ''},
    }

    def inputs(self):
        # Path C: read runs.db directly so all runs are pooled.
        return {}

    def update(self, state, interval=1.0):
        cfg = self.config or {}
        slug = (cfg.get('study_slug') or '').strip() or None
        db = _find_runs_db(slug)
        if db is None:
            return {'html': '<p style="color:#991b1b">NewtonResidual: no runs.db found under studies/*/</p>'}
        runs = _load_runs(db)
        if not runs:
            return {'html': f'<p style="color:#991b1b">NewtonResidual: no history in {db.name}</p>'}

        # Pooled statistics for the measured proxy residual ratio (sample-by-sample).
        ratios: list[float] = []
        all_transferred: list[float] = []
        n_steps_total = 0
        for r in runs:
            n_steps_total += len(r["t"])
            all_transferred += r["actin"]
            for a, res in zip(r["actin"], r["residual"]):
                if abs(a) > 1e-9:
                    ratios.append(abs(res) / abs(a))
        ratios_sorted = sorted(ratios)
        median_ratio = (ratios_sorted[len(ratios_sorted) // 2] if ratios_sorted else float("nan"))
        max_ratio = (max(ratios_sorted) if ratios_sorted else float("nan"))
        frac_pass = (sum(1 for x in ratios if x < 0.05) / len(ratios)) if ratios else 0.0
        passed = bool(ratios) and (max_ratio < 0.05)

        # ---- traces ---------------------------------------------------------
        traces = []
        for i, r in enumerate(runs):
            first = (i == 0)
            grp_a, grp_m, grp_r = "actin", "membrane", "residual"
            # Panel A: actin force / membrane proxy / residual (xaxis/yaxis)
            traces.append({"x": r["t"], "y": r["actin"], "type": "scatter", "mode": "lines",
                           "name": "actin force (contact_force)", "legendgroup": grp_a,
                           "showlegend": first, "opacity": 0.55,
                           "line": {"color": C_ACTIN, "width": 1.6},
                           "xaxis": "x", "yaxis": "y", "hoverinfo": "skip"})
            traces.append({"x": r["t"], "y": r["mem"], "type": "scatter", "mode": "lines",
                           "name": "membrane force PROXY (osmotic_offset)", "legendgroup": grp_m,
                           "showlegend": first, "opacity": 0.55,
                           "line": {"color": C_MEMBRANE, "width": 1.6, "dash": "dot"},
                           "xaxis": "x", "yaxis": "y", "hoverinfo": "skip"})
            traces.append({"x": r["t"], "y": r["residual"], "type": "scatter", "mode": "lines",
                           "name": "proxy residual (actin − membrane PROXY)", "legendgroup": grp_r,
                           "showlegend": first, "opacity": 0.9,
                           "line": {"color": C_FORCE, "width": 2.2},
                           "xaxis": "x", "yaxis": "y"})
            # Panel B: cumulative residual impulse (xaxis2/yaxis2)
            traces.append({"x": r["t"], "y": r["impulse"], "type": "scatter", "mode": "lines",
                           "name": "residual impulse (∫ residual dt)", "legendgroup": "impulse",
                           "showlegend": first, "opacity": 0.8,
                           "line": {"color": C_FORCE, "width": 1.8},
                           "xaxis": "x2", "yaxis": "y2"})
        # Panel C: histogram of transferred forces (xaxis3/yaxis3)
        traces.append({"x": all_transferred, "type": "histogram",
                       "name": "transferred force (contact_force)", "showlegend": False,
                       "marker": {"color": C_FORCE, "opacity": 0.75,
                                  "line": {"color": "white", "width": 0.5}},
                       "nbinsx": 24, "xaxis": "x3", "yaxis": "y3"})

        # ---- threshold band on Panel A --------------------------------------
        # |residual|/|actin| < 0.05 → a band of ±0.05·median(actin) around zero
        med_actin = 0.0
        if all_transferred:
            sa = sorted(abs(a) for a in all_transferred)
            med_actin = sa[len(sa) // 2]
        band = 0.05 * med_actin

        shapes = [
            {  # acceptance band around residual=0 on Panel A
                "type": "rect", "xref": "paper", "yref": "y",
                "x0": 0, "x1": 1, "y0": -band, "y1": band,
                "fillcolor": "rgba(16,185,129,0.12)", "line": {"width": 0}, "layer": "below",
            },
            {  # residual = 0 reference line on Panel A
                "type": "line", "xref": "paper", "yref": "y",
                "x0": 0, "x1": 1, "y0": 0, "y1": 0,
                "line": {"color": C_BENCHMARK, "width": 1, "dash": "dash"},
            },
            {  # impulse = 0 reference on Panel B
                "type": "line", "xref": "paper", "yref": "y2",
                "x0": 0, "x1": 1, "y0": 0, "y1": 0,
                "line": {"color": C_BENCHMARK, "width": 1, "dash": "dash"},
            },
        ]

        verdict = "PASS" if passed else "FAIL (proxy)"
        layout = {
            **_BASE_LAYOUT,
            "height": 760,
            "title": {"text": "<b>Newton's 3rd law residual — coupling interface (DECISION FIGURE)</b>",
                      "x": 0.02, "xanchor": "left", "font": {"size": 14, "color": PALETTE["ink"]}},
            "hovermode": "closest",
            "legend": {"orientation": "h", "y": -0.06, "x": 0.5, "xanchor": "center",
                       "font": {"size": 10}},
            "margin": {"l": 60, "r": 30, "t": 50, "b": 70},
            # Panel A (top): time series
            "xaxis": {**_axis_style(""), "domain": [0.0, 1.0], "anchor": "y"},
            "yaxis": {**_axis_style("force  (actin / membrane PROXY / residual)"),
                      "domain": [0.70, 1.0]},
            # Panel B (middle): residual impulse
            "xaxis2": {**_axis_style("time"), "domain": [0.0, 1.0], "anchor": "y2"},
            "yaxis2": {**_axis_style("residual impulse  (∫ residual dt)"),
                       "domain": [0.40, 0.62]},
            # Panel C (bottom): histogram
            "xaxis3": {**_axis_style("transferred force (contact_force)"),
                       "domain": [0.0, 1.0], "anchor": "y3"},
            "yaxis3": {**_axis_style("count"), "domain": [0.0, 0.26]},
            "shapes": shapes,
            "annotations": [
                {  # EXPECTED PATTERN box
                    "xref": "paper", "yref": "paper", "x": 0.99, "y": 1.0,
                    "xanchor": "right", "yanchor": "top", "align": "left", "showarrow": False,
                    "bordercolor": PALETTE["rule"], "borderwidth": 1, "borderpad": 6,
                    "bgcolor": "rgba(255,255,255,0.92)",
                    "font": {"size": 10, "color": PALETTE["ink"]},
                    "text": ("<b>EXPECTED PATTERN (PASS)</b><br>"
                             "residual force ≈ 0 throughout (inside green band);<br>"
                             "residual impulse stays flat at ≈ 0;<br>"
                             "transferred-force histogram has no heavy tails / outliers.<br>"
                             "<b>Threshold:</b> |residual| / |actin| &lt; 0.05 per step."),
                },
                {  # measured-ratio readout
                    "xref": "paper", "yref": "paper", "x": 0.01, "y": 0.685,
                    "xanchor": "left", "yanchor": "top", "align": "left", "showarrow": False,
                    "bordercolor": PALETTE["rule"], "borderwidth": 1, "borderpad": 5,
                    "bgcolor": "rgba(255,255,255,0.92)",
                    "font": {"size": 10, "color": PALETTE["ink"]},
                    "text": (f"<b>MEASURED proxy ratio</b> |residual|/|actin|: "
                             f"median {median_ratio:.3f} · max {max_ratio:.3f}<br>"
                             f"samples under 0.05 threshold: {frac_pass*100:.0f}%  →  "
                             f"<b>{verdict}</b>"),
                },
                {  # honest amber stamp — the provenance gap
                    "xref": "paper", "yref": "paper", "x": 0.01, "y": 1.0,
                    "xanchor": "left", "yanchor": "top", "align": "left", "showarrow": False,
                    "bgcolor": "rgba(254,243,199,0.97)", "bordercolor": "#d97706",
                    "borderwidth": 1, "borderpad": 5,
                    "font": {"size": 10, "color": "#92400e"},
                    "text": ("<b>NOT YET VALIDATED · membrane force is a PROXY</b><br>"
                             "runs.db emits no membrane-side integrated force / reaction<br>"
                             "impulse. osmotic_offset is a scaled pressure offset<br>"
                             "(= 0.05·contact_force), NOT a true reaction force — so the<br>"
                             "proxy residual is large, not ≈0. Exact Newton residual needs<br>"
                             "the coupler to emit the membrane-side force/impulse."),
                },
                {  # Panel B title
                    "xref": "paper", "yref": "paper", "x": 0.0, "y": 0.63,
                    "xanchor": "left", "yanchor": "bottom", "showarrow": False,
                    "font": {"size": 11, "color": PALETTE["ink"]},
                    "text": "<b>Residual impulse vs time</b>  (should stay flat at ≈ 0)",
                },
                {  # Panel C title
                    "xref": "paper", "yref": "paper", "x": 0.0, "y": 0.27,
                    "xanchor": "left", "yanchor": "bottom", "showarrow": False,
                    "font": {"size": 11, "color": PALETTE["ink"]},
                    "text": "<b>Transferred-force histogram</b>  (flag heavy tails / outliers)",
                },
            ],
        }

        div_id = f"newton-residual-{id(self)}"
        dur = next((r["duration"] for r in runs if r.get("duration")), None)
        prov = (f'source: {db.parent.name}/runs.db · {len(runs)} run(s) · '
                f'{n_steps_total} step(s) pooled'
                f'{f" · ~{dur:.1f}s/run" if dur else ""} · '
                f'membrane force shown as PROXY (osmotic_offset) — '
                f'exact residual pending membrane-side force/impulse emission')
        accent = cfg.get('accent', C_FORCE)
        height = 760
        html = (
            f'<div style="height:3px;background:{accent};margin-bottom:6px;border-radius:2px"></div>'
            f'<div id="{div_id}" style="height:{height}px"></div>'
            f'<div style="font-size:11px;color:#6b7280;margin-top:4px">{prov}</div>'
            f'<script src="{PLOTLY_CDN}"></script>'
            f'<script>Plotly.newPlot("{div_id}",{json.dumps(traces)},{json.dumps(layout)},'
            f'{{responsive:true,displayModeBar:false}});</script>'
        )
        return {'html': html + _autosize_script(height + 40)}
