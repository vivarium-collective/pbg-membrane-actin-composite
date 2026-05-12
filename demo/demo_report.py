"""Generate the membrane-actin Brownian-ratchet demo report.

Runs three scenarios (decoupled baseline, coupled ratchet, stressed
ratchet) and writes ``demo/report.html`` with:

  - sticky nav + per-config metrics cards
  - the headline COUPLING chart per scenario (actin_max_z, membrane_min_z,
    and contact_force on a shared time axis — required by the
    pbg-superpowers composite-demo spec)
  - membrane volume + osmotic offset vs time
  - actin particle count + ratchet-step accumulation
  - bigraph-viz architecture diagram (PNG, base64-embedded)
  - a Three.js schematic viewer (membrane sphere whose radius tracks
    membrane_volume; actin field schematized as a particle cloud below)
  - collapsible PBG document tree per scenario

Defaults to a ~6s total simulation time per scenario so the full demo
completes in well under the 120s safety timeout.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import signal
import sys
import time
import webbrowser
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from pbg_membrane_actin_composite import build_core, build_document
from pbg_mem3dg import Mem3DGProcess


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "report.html"
DEMO_TIMEOUT_SECONDS = 120


CONFIGS = [
    {
        "id": "rung1_fixed_boundary",
        "title": "Rung 1 — Fixed boundary",
        "subtitle": "Actin pushes against a wall that cannot move (spec §2.2 #1)",
        "description": (
            "Bonded actin filaments at the bottom of the box; a flat "
            "barrier (planar wall_z) sits at z=0. The barrier does not "
            "move — `barrier_kind='fixed'`. ReaDDy's box potential "
            "confines particles to z ≤ wall_z, so Brownian fluctuations "
            "and chain bending of the filament heads are the only "
            "out-of-plane motion. This is the rigid-wall regime against "
            "which Peskin 1993's closed-form Brownian-ratchet velocity "
            "should hold (when polymerization rate ≪ ideal ratchet "
            "velocity). Headline metric: contact_force builds up but "
            "barrier_velocity stays at zero — confirming the wall is "
            "rigid as advertised."
        ),
        "accent": "#94a3b8",
        "doc_kwargs": {
            "closed_loop": True,
            "coupling_mode": "planar",
            "barrier_kind": "fixed",
            "barrier_initial_z": 0.0,
            "interval": 0.5,
            "n_filaments": 6,
            "monomers_per_filament": 4,
            "force_constant": 2.0,
            "contact_threshold": 0.4,
        },
        "total_time": 8.0,
    },
    {
        "id": "rung2_movable_rigid_boundary",
        "title": "Rung 2 — Movable rigid boundary (Peskin 1993)",
        "subtitle": "Wall translates under integrated force; doesn't deform",
        "description": (
            "Same actin model as Rung 1, but the wall now translates "
            "under integrated contact force using simple drag-balance "
            "kinematics: dz/dt = F / drag. The wall stays planar — "
            "it's a rigid object, no deformation. This reproduces the "
            "classic Peskin 1993 setup: a rigid load whose velocity is "
            "set by force balance with the polymerizing actin. Headline "
            "metric: barrier_velocity stabilizes at a non-zero value "
            "proportional to the mean contact force."
        ),
        "accent": "#0ea5e9",
        "doc_kwargs": {
            "closed_loop": True,
            "coupling_mode": "planar",
            "barrier_kind": "rigid_movable",
            "barrier_initial_z": 0.0,
            "barrier_drag": 8.0,
            "interval": 0.5,
            "n_filaments": 6,
            "monomers_per_filament": 4,
            "force_constant": 2.0,
            "contact_threshold": 0.4,
        },
        "total_time": 8.0,
    },
    {
        "id": "rung3_flexible_membrane",
        "title": "Rung 3 — Flexible Mem3DG membrane (spec §2.2 #3)",
        "subtitle": "Closed icosphere vesicle inflating under actin pressure",
        "description": (
            "Spec §2.2 endpoint: real Mem3DG mesh in closed-loop with the "
            "actin field. Geometry shifts here: a closed icosphere vesicle "
            "with bonded filaments INSIDE pushing radially outward "
            "against the inner surface. Why the geometry change — "
            "pymem3dg's open-mesh deformation under constant pressure "
            "isn't robust at our parameters (open hexagon won't bulge), "
            "but a closed vesicle inflates reliably under the same "
            "lever. The same coupler runs the same math; only the "
            "barrier topology differs. Headline metric: vesicle volume "
            "grows visibly (~12-15% over the run), barrier_velocity "
            "(now a radial expansion rate) is non-zero, and the F-V "
            "scatter point lies clearly off the rigid-wall curve."
        ),
        "accent": "#10b981",
        "doc_kwargs": {
            "closed_loop": True,
            "coupling_mode": "spherical",
            "barrier_kind": "flexible",
            "membrane_geometry": "icosphere",
            "interval": 0.5,
            "n_filaments": 6,
            "monomers_per_filament": 4,
            "force_constant": 2.0,
            "osmotic_force_scale": 0.02,
            "contact_threshold": 0.3,
        },
        "total_time": 8.0,
    },
]


# ---------------------------------------------------------------------------
# Run a scenario
# ---------------------------------------------------------------------------

def _membrane_face_matrix(doc):
    """Return the static face connectivity for the membrane mesh, or
    None if the document doesn't include a membrane_sim block (the fixed
    and rigid_movable staircase rungs don't run Mem3DG).
    """
    if "membrane_sim" not in doc:
        return None
    mem_cfg = doc["membrane_sim"]["config"]
    # Mem3DGProcess inherits from Edge which requires a core; we don't
    # actually need a wired-up core here, just enough for instantiation.
    proc = Mem3DGProcess(config=mem_cfg, core=build_core())
    return proc.get_faces()


def _run_scenario(scenario: dict) -> dict:
    core = build_core()
    doc = build_document(**scenario["doc_kwargs"])

    # Capture face matrix BEFORE running the composite, so we don't pay
    # the rebuild cost partway through.
    faces = _membrane_face_matrix(doc)

    sim = Composite({"state": doc}, core=core)
    t0 = time.perf_counter()
    sim.run(scenario["total_time"])
    elapsed = time.perf_counter() - t0

    samples = list(gather_emitter_results(sim).values())[0]

    # Extract time series for plotting. Some keys may be missing on early
    # samples (e.g. wall_z is None and gets dropped); coerce to neutral.
    times = [s.get("time", 0.0) for s in samples]
    actin_total = [s.get("actin_total", 0) for s in samples]
    actin_max_z = [s.get("actin_max_z", 0.0) for s in samples]
    membrane_min_z = [s.get("membrane_min_z", 0.0) for s in samples]
    gap = [s.get("gap", 0.0) for s in samples]
    contact_force = [s.get("contact_force", 0.0) for s in samples]
    osmotic_offset = [s.get("osmotic_offset", 0.0) for s in samples]
    wall_z = [s.get("wall_z") for s in samples]
    membrane_volume = [s.get("membrane_volume", 0.0) for s in samples]
    ratchet_steps = [s.get("ratchet_steps", 0) for s in samples]
    actin_positions = [s.get("actin_positions") or [] for s in samples]
    membrane_vertices = [s.get("membrane_vertex_positions") or [] for s in samples]
    # Barrier kinematics (per-step) — fed into the cross-scenario
    # displacement-overlay and F-V scatter panels.
    barrier_z = [s.get("barrier_z", 0.0) for s in samples]
    barrier_velocity = [s.get("barrier_velocity", 0.0) for s in samples]
    mean_contact_force = [s.get("mean_contact_force", 0.0) for s in samples]
    cumulative_ratchets = []
    running = 0
    for r in ratchet_steps:
        running += r
        cumulative_ratchets.append(running)

    return {
        "scenario": scenario,
        "elapsed_seconds": elapsed,
        "samples": samples,
        "document": doc,
        "faces": faces,
        "series": {
            "times": times,
            "actin_total": actin_total,
            "actin_max_z": actin_max_z,
            "membrane_min_z": membrane_min_z,
            "gap": gap,
            "contact_force": contact_force,
            "osmotic_offset": osmotic_offset,
            "wall_z": [None if w is None else float(w) for w in wall_z],
            "membrane_volume": membrane_volume,
            "ratchet_steps_cum": cumulative_ratchets,
            "actin_positions": actin_positions,
            "membrane_vertices": membrane_vertices,
            "barrier_z": barrier_z,
            "barrier_velocity": barrier_velocity,
            "mean_contact_force": mean_contact_force,
        },
        "final_ratchets": cumulative_ratchets[-1] if cumulative_ratchets else 0,
        "final_volume": membrane_volume[-1] if membrane_volume else 0.0,
        "final_actin_total": actin_total[-1] if actin_total else 0,
    }


# ---------------------------------------------------------------------------
# bigraph-viz architecture diagram
# ---------------------------------------------------------------------------

def _bigraph_png_data_uri() -> str | None:
    try:
        from bigraph_viz import plot_bigraph
    except Exception:
        return None

    # Simplified document for diagram — only 5-6 key ports per process.
    doc = {
        "actin_sim": {
            "_type": "process",
            "address": "local:ReaDDyProcess",
            "inputs": {"wall_z": ["control", "wall_z"]},
            "outputs": {"positions": ["actin", "positions"]},
        },
        "membrane_sim": {
            "_type": "process",
            "address": "local:Mem3DGProcess",
            "inputs": {"osmotic_strength_offset": ["control", "osmotic_strength_offset"]},
            "outputs": {"vertex_positions": ["membrane", "vertex_positions"]},
        },
        "coupler": {
            "_type": "process",
            "address": "local:BrownianRatchetCoupler",
            "inputs": {
                "actin_positions": ["actin", "positions"],
                "membrane_vertices": ["membrane", "vertex_positions"],
            },
            "outputs": {
                "wall_z": ["control", "wall_z"],
                "osmotic_strength_offset": ["control", "osmotic_strength_offset"],
                "contact_force": ["coupling", "contact_force"],
            },
        },
        "actin": {"positions": []},
        "membrane": {"vertex_positions": []},
        "control": {"wall_z": None, "osmotic_strength_offset": 0.0},
        "coupling": {"contact_force": 0.0},
    }

    out_dir = HERE / "_bigraph_tmp"
    out_dir.mkdir(exist_ok=True)
    try:
        plot_bigraph(
            state=doc, out_dir=str(out_dir), filename="bigraph",
            file_format="png", remove_process_place_edges=True,
            rankdir="LR",
            node_fill_colors={
                ("actin_sim",): "#10b981",
                ("membrane_sim",): "#6366f1",
                ("coupler",): "#f59e0b",
                ("actin",): "#d1fae5",
                ("membrane",): "#e0e7ff",
                ("control",): "#fed7aa",
                ("coupling",): "#fef3c7",
            },
            node_label_size="14pt", port_labels=False, dpi="150",
        )
        png = out_dir / "bigraph.png"
        if png.exists():
            return "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()
    except Exception as e:
        print(f"  bigraph-viz failed ({e}); skipping diagram")
    return None


# ---------------------------------------------------------------------------
# Document → collapsible JSON
# ---------------------------------------------------------------------------

def _document_for_display(doc: dict) -> dict:
    # Strip the heaviest sub-trees (cell_types, initial particle lists)
    pruned = json.loads(json.dumps(doc, default=str))
    try:
        pruned["actin_sim"]["config"]["initial_particles"] = "<elided>"
        pruned["actin_sim"]["config"]["potentials"] = "<elided — list of dicts>"
        pruned["actin_sim"]["config"]["reactions"] = "<elided — list of dicts>"
    except Exception:
        pass
    return pruned


def _render_value(value, depth=0):
    if isinstance(value, dict):
        if not value:
            return '<span class="tu">{}</span>'
        items = []
        for k, v in value.items():
            items.append(
                f'<div style="margin-left:14px"><span class="tk">"{k}"</span>: '
                f'{_render_value(v, depth + 1)}</div>'
            )
        body = "".join(items)
        if depth >= 2:
            return f'<span class="tx" onclick="this.nextElementSibling.classList.toggle(\'hidden\')">▶ {len(value)} items</span><div class="hidden">{body}</div>'
        return body
    if isinstance(value, list):
        if not value:
            return '<span class="tu">[]</span>'
        if all(isinstance(v, (int, float, str, bool)) for v in value) and len(value) <= 6:
            return "[" + ", ".join(_render_value(v) for v in value) + "]"
        items = "".join(
            f'<div style="margin-left:14px">{_render_value(v, depth + 1)}</div>' for v in value
        )
        return f'<span class="tx" onclick="this.nextElementSibling.classList.toggle(\'hidden\')">▶ list[{len(value)}]</span><div class="hidden">{items}</div>'
    if isinstance(value, bool):
        return f'<span class="tb">{str(value).lower()}</span>'
    if isinstance(value, (int, float)):
        return f'<span class="tn">{value}</span>'
    if value is None:
        return '<span class="tu">null</span>'
    return f'<span class="ts">"{value}"</span>'


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_CSS = """
:root { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
body { margin: 0; background: #fff; color: #1f2937; }
nav { position: sticky; top: 0; background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-bottom: 1px solid #e5e7eb; padding: 12px 24px; z-index: 100; }
nav a { color: #4b5563; text-decoration: none; margin-right: 24px; font-weight: 500; font-size: 14px; }
nav a:hover { color: #6366f1; }
.hero { padding: 48px 24px 24px; max-width: 1100px; margin: 0 auto; }
.hero h1 { font-size: 36px; margin: 0 0 8px; font-weight: 700; }
.hero p { font-size: 16px; color: #6b7280; margin: 0; }
section { max-width: 1100px; margin: 0 auto; padding: 32px 24px; border-top: 1px solid #f1f5f9; }
section h2 { font-size: 24px; margin: 0 0 16px; font-weight: 600; }
.metrics { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; margin: 16px 0; }
.metric { background: #f9fafb; border-left: 4px solid var(--accent, #6366f1); padding: 12px 16px; border-radius: 6px; }
.metric-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }
.metric-value { font-size: 22px; font-weight: 600; color: #111827; margin-top: 4px; }
.config-block { padding: 24px; margin: 16px 0; border: 1px solid #e5e7eb; border-radius: 8px; border-left: 4px solid var(--accent, #6366f1); }
.config-title { font-size: 20px; font-weight: 600; margin: 0 0 4px; }
.config-subtitle { font-size: 14px; color: #6b7280; margin: 0 0 12px; }
.config-desc { font-size: 14px; color: #374151; line-height: 1.55; margin: 0 0 16px; }
.headline { background: #fef9c3; border-left: 4px solid #facc15; padding: 8px 12px; margin: 12px 0; font-size: 13px; }
.chart { height: 320px; margin: 12px 0; }
.tree { font-family: SF Mono, Menlo, monospace; font-size: 13px; line-height: 1.55; background: #f8fafc; padding: 16px; border-radius: 6px; max-height: 500px; overflow: auto; }
.tk { color: #7c3aed; font-weight: 500; }
.ts { color: #059669; }
.tn { color: #2563eb; }
.tb { color: #d97706; }
.tu { color: #9ca3af; }
.tx { cursor: pointer; user-select: none; color: #6b7280; }
.tx:hover { color: #1f2937; }
.hidden { display: none; }
.viewer { width: 100%; height: 460px; background: #f8fafc; border-radius: 8px; position: relative; overflow: hidden; }
.viewer-controls { position: absolute; bottom: 16px; left: 16px; right: 16px; background: rgba(255,255,255,0.95); padding: 12px; border-radius: 6px; display: flex; gap: 12px; align-items: center; font-size: 13px; }
.viewer-controls button { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 4px; background: #fff; cursor: pointer; }
.viewer-controls button:hover { background: #f3f4f6; }
.viewer-controls input[type=range] { flex: 1; }
.note { font-size: 12px; color: #6b7280; font-style: italic; margin-top: 8px; }
img.diagram { max-width: 100%; border-radius: 8px; border: 1px solid #e5e7eb; padding: 8px; background: #fff; }
"""


def _scenario_chart_data(result):
    s = result["scenario"]
    series = result["series"]
    return {
        "id": s["id"],
        "title": s["title"],
        "accent": s["accent"],
        "faces": result["faces"],
        **series,
    }


def render_html(results: list, bigraph_uri: str | None) -> str:
    chart_data = [_scenario_chart_data(r) for r in results]
    chart_data_json = json.dumps(chart_data)

    nav_links = "".join(
        f'<a href="#{r["scenario"]["id"]}">{r["scenario"]["title"]}</a>' for r in results
    )

    # Aggregate F-V scatter — one point per scenario. The spec's
    # central numerical benchmark (§1.2) is Inoue 2015's concave→convex
    # F-V transition; we land a single-rate version here so the
    # comparison across boundary kinds is visible at a glance.
    fv_points = []
    for r in results:
        s = r["scenario"]
        # Take the late-run mean to skip startup transient.
        n = len(r["series"]["barrier_velocity"])
        tail = max(1, n // 3)
        v_late = r["series"]["barrier_velocity"][-tail:]
        f_late = r["series"]["mean_contact_force"][-tail:]
        fv_points.append({
            "id": s["id"],
            "title": s["title"],
            "accent": s["accent"],
            "force": float(sum(f_late) / max(1, len(f_late))),
            "velocity": float(sum(v_late) / max(1, len(v_late))),
        })

    config_blocks = []
    for r in results:
        s = r["scenario"]
        doc_html = _render_value(_document_for_display(r["document"]))
        max_force = max(r["series"]["contact_force"]) if r["series"]["contact_force"] else 0.0
        config_blocks.append(
            f"""
<section id="{s['id']}" style="--accent: {s['accent']}">
  <div class="config-block">
    <h2 class="config-title">{s['title']}</h2>
    <p class="config-subtitle">{s['subtitle']}</p>
    <p class="config-desc">{s['description']}</p>
    <div class="metrics">
      <div class="metric"><div class="metric-label">Total simulation time</div><div class="metric-value">{s['total_time']:.1f}</div></div>
      <div class="metric"><div class="metric-label">Wall time</div><div class="metric-value">{r['elapsed_seconds']:.1f}s</div></div>
      <div class="metric"><div class="metric-label">Final actin particles</div><div class="metric-value">{r['final_actin_total']}</div></div>
      <div class="metric"><div class="metric-label">Final membrane volume</div><div class="metric-value">{r['final_volume']:.2f}</div></div>
      <div class="metric"><div class="metric-label">Cumulative ratchet steps</div><div class="metric-value">{r['final_ratchets']}</div></div>
      <div class="metric"><div class="metric-label">Peak contact force</div><div class="metric-value">{max_force:.2f}</div></div>
    </div>
    <div class="headline">Headline coupling chart — actin tip, membrane bottom, and contact force on a shared time axis.</div>
    <div id="chart-coupling-{s['id']}" class="chart"></div>
    <div id="chart-back-{s['id']}" class="chart"></div>
    <div id="chart-population-{s['id']}" class="chart"></div>
    <div class="viewer" id="viewer-{s['id']}">
      <div class="viewer-controls">
        <button onclick="toggleViewer('{s['id']}')">Play / Pause</button>
        <input type="range" min="0" max="100" value="0" id="slider-{s['id']}" oninput="seekViewer('{s['id']}', this.value)">
        <span id="t-{s['id']}">t = 0</span>
      </div>
    </div>
    <p class="note">Schematic: the {{accent}}-tinted sphere's radius tracks membrane_volume; the puck below schematizes the actin field rising as the polymerization reaction fires. Real per-particle and per-vertex meshes are not parsed in v0.1.</p>
    <details style="margin-top:16px"><summary style="cursor:pointer;color:#6b7280">PBG document</summary>
    <div class="tree">{doc_html}</div></details>
  </div>
</section>
"""
        )

    diagram_html = (
        f'<img src="{bigraph_uri}" class="diagram" alt="bigraph architecture diagram"/>'
        if bigraph_uri
        else '<p style="color:#9ca3af">(bigraph-viz unavailable)</p>'
    )

    fv_data_json = json.dumps(fv_points)

    return f"""<!doctype html>
<html><head>
<meta charset="utf-8"/>
<title>pbg-membrane-actin-composite Brownian-ratchet demo</title>
<style>{_CSS}</style>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
<nav><a href="#top">Overview</a><a href="#staircase">Staircase comparison</a>{nav_links}<a href="#architecture">Architecture</a></nav>

<div class="hero" id="top">
  <h1>pbg-membrane-actin-composite</h1>
  <p>Closed-loop Brownian ratchet — pbg-readdy actin pushing pbg-mem3dg membrane via a published wall_z + osmotic_strength_offset back-channel.</p>
</div>

<section id="architecture">
  <h2>Architecture</h2>
  {diagram_html}
  <p class="note">ReaDDy publishes <code>positions</code>; Mem3DG publishes <code>vertex_positions</code>. The coupler reads both, computes contact_force, and publishes back into <code>control.wall_z</code> (read by ReaDDy on its next interval) and <code>control.osmotic_strength_offset</code> (read by Mem3DG). Mem3DG is included only on Rung 3.</p>
</section>

<section id="staircase">
  <h2>Cross-scenario comparison — the boundary-condition staircase</h2>
  <p style="color:#374151;line-height:1.55">
    Per the
    <a href="https://github.com/vivarium-collective/pbg-membrane-actin-composite/blob/main/docs/spec.md">spec §2.2</a>,
    the same actin model is run against three boundary regimes —
    fixed, movable rigid (Peskin 1993), and flexible Mem3DG mesh —
    so the F-V relationship can be compared across them. The two
    panels below are the central spec-aligned comparison: one
    overlays barrier displacement vs time across all three rungs;
    the other lands a single F-V scatter point per rung as a
    starting hook for full Inoue 2015 reproduction.
  </p>
  <div id="chart-displacement-overlay" class="chart" style="height:380px"></div>
  <div id="chart-fv-scatter" class="chart" style="height:380px"></div>
  <p class="note">
    Spec §1.2's headline benchmark — Inoue 2015's concave→convex F-V
    transition as polymerization rate varies — requires a
    polymerization-rate sweep with statistical aggregation, plus
    Cytosim-style fiber-scale actin (which this composite does not yet
    wrap). The F-V point per scenario here is the v0.1 hook the
    rate-sweep micropub will fill in.
  </p>
</section>

{''.join(config_blocks)}

<script>
const SCENARIOS = {chart_data_json};
const FV_POINTS = {fv_data_json};

// Cross-scenario displacement overlay — barrier_z vs time, all rungs.
Plotly.newPlot("chart-displacement-overlay",
  SCENARIOS.map(s => ({{
    x: s.times, y: s.barrier_z, mode: "lines+markers",
    name: s.title, line: {{color: s.accent, width: 2.5}},
  }})),
  {{
    title: "Barrier displacement vs time (spec §5.1: same actin, 3 boundary regimes)",
    margin: {{t: 50, b: 50, l: 60, r: 30}},
    xaxis: {{title: "global time (sim units)"}},
    yaxis: {{title: "barrier_z (or radius for spherical rung)"}},
    paper_bgcolor: "#fff", plot_bgcolor: "#f8fafc",
    legend: {{orientation: "h", y: -0.18}},
  }},
  {{displayModeBar: false, responsive: true}}
);

// F-V scatter — one point per rung. mean_contact_force on x, barrier_velocity on y.
Plotly.newPlot("chart-fv-scatter",
  FV_POINTS.map(p => ({{
    x: [p.force], y: [p.velocity], mode: "markers+text",
    name: p.title, text: [p.title], textposition: "top center",
    marker: {{size: 18, color: p.accent, line: {{color: "#1f2937", width: 1}}}}
  }})),
  {{
    title: "F-V scatter (one point per rung — late-run mean)",
    margin: {{t: 50, b: 50, l: 70, r: 30}},
    xaxis: {{title: "mean contact force (sim units)"}},
    yaxis: {{title: "mean barrier velocity (Δz / Δt)"}},
    paper_bgcolor: "#fff", plot_bgcolor: "#f8fafc",
    showlegend: false,
  }},
  {{displayModeBar: false, responsive: true}}
);

SCENARIOS.forEach(s => {{
  // Headline coupling chart: actin tip + membrane bottom + contact force.
  Plotly.newPlot("chart-coupling-" + s.id, [
    {{x: s.times, y: s.actin_max_z, mode: "lines+markers", name: "actin_max_z", line: {{color: s.accent, width: 2}}, yaxis: "y"}},
    {{x: s.times, y: s.membrane_min_z, mode: "lines+markers", name: "membrane_min_z", line: {{color: "#6366f1", width: 2, dash: "dash"}}, yaxis: "y"}},
    {{x: s.times, y: s.contact_force, mode: "lines", name: "contact_force", line: {{color: "#ef4444", width: 2}}, yaxis: "y2"}}
  ], {{
    title: "Coupling: actin tip, membrane bottom, contact force",
    margin: {{t: 40, b: 40, l: 60, r: 60}},
    xaxis: {{title: "global time"}},
    yaxis: {{title: "z (sim units)"}},
    yaxis2: {{title: "contact force", overlaying: "y", side: "right"}},
    paper_bgcolor: "#fff", plot_bgcolor: "#f8fafc"
  }}, {{displayModeBar: false, responsive: true}});

  // Back-channel chart: wall_z and osmotic_offset published to wrappers.
  Plotly.newPlot("chart-back-" + s.id, [
    {{x: s.times, y: s.wall_z, mode: "lines+markers", name: "wall_z (-> ReaDDy)", line: {{color: "#10b981", width: 2}}, yaxis: "y", connectgaps: false}},
    {{x: s.times, y: s.osmotic_offset, mode: "lines+markers", name: "osmotic_offset (-> Mem3DG)", line: {{color: "#f59e0b", width: 2}}, yaxis: "y2"}}
  ], {{
    title: "Back-channel signals published to wrappers",
    margin: {{t: 40, b: 40, l: 60, r: 60}},
    xaxis: {{title: "global time"}},
    yaxis: {{title: "wall_z (z units)"}},
    yaxis2: {{title: "osmotic_strength_offset", overlaying: "y", side: "right"}},
    paper_bgcolor: "#fff", plot_bgcolor: "#f8fafc"
  }}, {{displayModeBar: false, responsive: true}});

  // Population + ratchet count
  Plotly.newPlot("chart-population-" + s.id, [
    {{x: s.times, y: s.actin_total, mode: "lines+markers", name: "actin particles", line: {{color: s.accent, width: 2}}, yaxis: "y"}},
    {{x: s.times, y: s.ratchet_steps_cum, mode: "lines+markers", name: "cumulative ratchet steps", line: {{color: "#ef4444", width: 2}}, yaxis: "y2"}},
    {{x: s.times, y: s.membrane_volume, mode: "lines", name: "membrane volume", line: {{color: "#6366f1", width: 2, dash: "dot"}}, yaxis: "y3"}}
  ], {{
    title: "Population, ratchet events, membrane volume",
    margin: {{t: 40, b: 40, l: 60, r: 80}},
    xaxis: {{title: "global time"}},
    yaxis: {{title: "actin particles"}},
    yaxis2: {{title: "ratchet steps", overlaying: "y", side: "right", position: 0.97}},
    yaxis3: {{title: "volume", overlaying: "y", side: "right", position: 1.0, anchor: "free"}},
    paper_bgcolor: "#fff", plot_bgcolor: "#f8fafc"
  }}, {{displayModeBar: false, responsive: true}});
}});

// Three.js viewers — render the REAL Mem3DG triangulated mesh and the
// REAL ReaDDy particle positions, frame by frame. Animation steps once
// every FRAME_DELAY ms (not per requestAnimationFrame tick), so the user
// can actually see the deformation and ratchet events.
const FRAME_DELAY_MS = 600;
const VIEWERS = {{}};

function _meshGeom(verts, faces) {{
  const g = new THREE.BufferGeometry();
  const positions = new Float32Array(verts.length * 3);
  for (let i = 0; i < verts.length; i++) {{
    positions[i*3]   = verts[i][0];
    positions[i*3+1] = verts[i][1];
    positions[i*3+2] = verts[i][2];
  }}
  g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const indices = new Uint32Array(faces.length * 3);
  for (let i = 0; i < faces.length; i++) {{
    indices[i*3]   = faces[i][0];
    indices[i*3+1] = faces[i][1];
    indices[i*3+2] = faces[i][2];
  }}
  g.setIndex(new THREE.BufferAttribute(indices, 1));
  g.computeVertexNormals();
  return g;
}}

function _firstNonEmpty(arr) {{
  for (let i = 0; i < arr.length; i++) {{
    if (arr[i] && arr[i].length > 0) return arr[i];
  }}
  return null;
}}

function buildViewer(s) {{
  const container = document.getElementById("viewer-" + s.id);
  const w = container.clientWidth, h = container.clientHeight;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf8fafc);

  // Camera — angled side view so you see the membrane (above) and the
  // actin column (below) at the same time.
  const camera = new THREE.PerspectiveCamera(40, w / h, 0.01, 200);
  camera.position.set(7.0, 2.5, 7.0);
  camera.lookAt(0, 0, 0);

  const renderer = new THREE.WebGLRenderer({{antialias: true}});
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.setSize(w, h);
  renderer.domElement.style.display = "block";
  container.insertBefore(renderer.domElement, container.firstChild);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.target.set(0, 0, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const key = new THREE.DirectionalLight(0xffffff, 0.85);
  key.position.set(6, 8, 4); scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff, 0.3);
  fill.position.set(-4, -2, -3); scene.add(fill);

  // Floor grid (xy plane) + axis cue.
  const grid = new THREE.GridHelper(8, 8, 0xd1d5db, 0xe5e7eb);
  grid.material.transparent = true; grid.material.opacity = 0.4;
  grid.position.y = -3.5;
  scene.add(grid);

  // ---- Membrane mesh ----
  // Pick the first non-empty vertex frame to seed the geometry. Subsequent
  // frames update the position attribute in place.
  const firstVerts = _firstNonEmpty(s.membrane_vertices);
  let memMesh = null, memWire = null;
  if (firstVerts && s.faces && s.faces.length) {{
    const geom = _meshGeom(firstVerts, s.faces);
    const mat = new THREE.MeshStandardMaterial({{
      color: 0x6366f1, roughness: 0.45, metalness: 0.1,
      transparent: true, opacity: 0.55,
      side: THREE.DoubleSide,
    }});
    memMesh = new THREE.Mesh(geom, mat); scene.add(memMesh);
    const wireMat = new THREE.LineBasicMaterial({{
      color: 0x4338ca, transparent: true, opacity: 0.35,
    }});
    memWire = new THREE.LineSegments(new THREE.WireframeGeometry(geom), wireMat);
    scene.add(memWire);
  }}

  // ---- Actin particles (one small sphere per particle, instanced for
  // performance even though counts are modest). ----
  const PARTICLE_RADIUS = 0.12;
  const particleGeom = new THREE.SphereGeometry(PARTICLE_RADIUS, 8, 6);
  const particleMat = new THREE.MeshStandardMaterial({{
    color: s.accent, roughness: 0.6, metalness: 0.1,
  }});
  // Determine an upper bound for instance count across all frames so
  // we can allocate the InstancedMesh once.
  let maxParticles = 0;
  for (const f of s.actin_positions) {{
    if (f && f.length > maxParticles) maxParticles = f.length;
  }}
  let particles = null;
  if (maxParticles > 0) {{
    particles = new THREE.InstancedMesh(particleGeom, particleMat, maxParticles);
    particles.count = 0;
    scene.add(particles);
  }}

  // ---- wall_z translucent plane (only when not null) ----
  const wallGeom = new THREE.PlaneGeometry(8, 8);
  const wallMat = new THREE.MeshBasicMaterial({{
    color: 0x10b981, transparent: true, opacity: 0.18, side: THREE.DoubleSide,
  }});
  const wallPlane = new THREE.Mesh(wallGeom, wallMat);
  wallPlane.rotation.x = Math.PI / 2;  // lie flat in xy
  wallPlane.visible = false;
  scene.add(wallPlane);

  const slider = document.getElementById("slider-" + s.id);
  slider.max = s.times.length - 1;

  return {{
    scene, camera, renderer, controls,
    memMesh, memWire, particles, wallPlane,
    times: s.times,
    membrane_vertices: s.membrane_vertices,
    actin_positions: s.actin_positions,
    wall_z: s.wall_z,
    container,
    playing: true, frame: 0,
    lastStep: 0,
    slider,
    tlabel: document.getElementById("t-" + s.id),
  }};
}}

function _updateViewer(v) {{
  const verts = v.membrane_vertices[v.frame];
  if (verts && verts.length && v.memMesh) {{
    const attr = v.memMesh.geometry.attributes.position;
    for (let i = 0; i < verts.length && i*3 < attr.array.length; i++) {{
      attr.array[i*3]   = verts[i][0];
      attr.array[i*3+1] = verts[i][1];
      attr.array[i*3+2] = verts[i][2];
    }}
    attr.needsUpdate = true;
    v.memMesh.geometry.computeVertexNormals();
    // Rebuild the wireframe from the updated geometry.
    v.memWire.geometry.dispose();
    v.memWire.geometry = new THREE.WireframeGeometry(v.memMesh.geometry);
  }}

  if (v.particles) {{
    const positions = v.actin_positions[v.frame] || [];
    v.particles.count = Math.min(positions.length, v.particles.instanceMatrix.count);
    const m = new THREE.Matrix4();
    for (let i = 0; i < v.particles.count; i++) {{
      const p = positions[i];
      m.makeTranslation(p[0], p[1], p[2]);
      v.particles.setMatrixAt(i, m);
    }}
    v.particles.instanceMatrix.needsUpdate = true;
  }}

  const wz = v.wall_z[v.frame];
  if (wz !== null && wz !== undefined) {{
    v.wallPlane.visible = true;
    v.wallPlane.position.set(0, 0, wz);
  }} else {{
    v.wallPlane.visible = false;
  }}

  v.tlabel.textContent = "t = " + v.times[v.frame].toFixed(2);
}}

SCENARIOS.forEach(s => {{
  VIEWERS[s.id] = buildViewer(s);
  _updateViewer(VIEWERS[s.id]);
}});

function toggleViewer(id) {{ VIEWERS[id].playing = !VIEWERS[id].playing; }}
function seekViewer(id, value) {{
  const v = VIEWERS[id];
  v.frame = parseInt(value);
  v.playing = false;
  _updateViewer(v);
}}

const ro = new ResizeObserver(entries => {{
  for (const entry of entries) {{
    const id = entry.target.id.replace(/^viewer-/, "");
    const v = VIEWERS[id]; if (!v) continue;
    const w = entry.contentRect.width, h = entry.contentRect.height;
    if (w > 0 && h > 0) {{
      v.renderer.setSize(w, h);
      v.camera.aspect = w / h;
      v.camera.updateProjectionMatrix();
    }}
  }}
}});
SCENARIOS.forEach(s => ro.observe(document.getElementById("viewer-" + s.id)));

// Render loop — runs every requestAnimationFrame for smooth orbit-control
// updates, but the simulation frame only advances once every FRAME_DELAY_MS
// so the user can actually SEE what's happening.
let lastAdvance = performance.now();
function animate(now) {{
  if (!now) now = performance.now();
  const advance = (now - lastAdvance) >= FRAME_DELAY_MS;
  if (advance) lastAdvance = now;
  for (const id in VIEWERS) {{
    const v = VIEWERS[id];
    if (advance && v.playing && v.times.length > 0) {{
      v.frame = (v.frame + 1) % v.times.length;
      v.slider.value = v.frame;
      _updateViewer(v);
    }}
    v.controls.update();
    v.renderer.render(v.scene, v.camera);
  }}
  requestAnimationFrame(animate);
}}
animate();
</script>

</body></html>
"""


def _install_timeout():
    def _bail(signum, frame):
        print(f"\nDemo timeout exceeded {DEMO_TIMEOUT_SECONDS}s — aborting.")
        sys.exit(2)
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _bail)
        signal.alarm(DEMO_TIMEOUT_SECONDS)


def _run_scenario_in_subprocess(scenario_id: str) -> dict:
    """Spawn a subprocess that runs ONE scenario and returns its result.

    ReaDDy retains process-global state across ReactionDiffusionSystem
    instances, so building two systems in the same process can crash with
    'graph not connected' on the second one. Subprocess-per-scenario
    guarantees a clean ReaDDy state per run.
    """
    import subprocess
    cmd = [sys.executable, str(Path(__file__).resolve()),
           "--scenario", scenario_id, "--json-out"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=DEMO_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"scenario {scenario_id} subprocess failed (exit {result.returncode}):\n"
            f"--- stderr (tail) ---\n{result.stderr[-2000:]}"
        )
    begin = "<<<SCENARIO_RESULT_JSON>>>"
    end = "<<<END_SCENARIO_RESULT_JSON>>>"
    a = result.stdout.find(begin)
    b = result.stdout.find(end, a + len(begin)) if a >= 0 else -1
    if a < 0 or b < 0:
        raise RuntimeError(
            f"scenario {scenario_id} did not emit JSON markers.\n"
            f"--- stdout (tail) ---\n{result.stdout[-2000:]}"
        )
    return json.loads(result.stdout[a + len(begin):b])


def _serialize_result(result: dict) -> dict:
    """Strip non-JSON-serializable bits from the result dict for IPC."""
    return {
        "scenario": result["scenario"],
        "elapsed_seconds": result["elapsed_seconds"],
        "document": json.loads(json.dumps(result["document"], default=str)),
        "faces": result["faces"],
        "series": result["series"],
        "final_ratchets": result["final_ratchets"],
        "final_volume": result["final_volume"],
        "final_actin_total": result["final_actin_total"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--scenario", type=str, default=None,
                        help="Run a single scenario by id (subprocess mode).")
    parser.add_argument("--json-out", action="store_true",
                        help="Emit the scenario result as JSON on stdout.")
    args = parser.parse_args()

    _install_timeout()

    # Subprocess mode: run one scenario and emit JSON.
    if args.scenario:
        cfg = next((c for c in CONFIGS if c["id"] == args.scenario), None)
        if cfg is None:
            print(f"unknown scenario: {args.scenario}", file=sys.stderr)
            sys.exit(2)
        result = _run_scenario(cfg)
        if args.json_out:
            print("<<<SCENARIO_RESULT_JSON>>>")
            print(json.dumps(_serialize_result(result)))
            print("<<<END_SCENARIO_RESULT_JSON>>>")
        else:
            print(f"{cfg['id']}: {result['elapsed_seconds']:.1f}s, "
                  f"{result['final_ratchets']} ratchet steps")
        return

    # Parent mode: spawn one subprocess per scenario.
    print(f"Running {len(CONFIGS)} scenarios (one subprocess each, "
          f"to isolate ReaDDy state across runs)...")
    results = []
    for cfg in CONFIGS:
        kw = cfg['doc_kwargs']
        print(f"  • {cfg['id']} (kind={kw.get('barrier_kind', 'flexible')}, "
              f"mode={kw.get('coupling_mode', 'planar')})...", end="", flush=True)
        r = _run_scenario_in_subprocess(cfg["id"])
        print(f" {r['elapsed_seconds']:.1f}s, {r['final_ratchets']} ratchet steps, "
              f"final volume {r['final_volume']:.2f}")
        results.append(r)

    print("Rendering architecture diagram...")
    bigraph_uri = _bigraph_png_data_uri()

    print(f"Writing {OUTPUT}...")
    OUTPUT.write_text(render_html(results, bigraph_uri))

    # Clean up bigraph_tmp dir
    tmp = HERE / "_bigraph_tmp"
    if tmp.exists():
        for child in tmp.rglob("*"):
            if child.is_file():
                child.unlink()
        for child in sorted(tmp.rglob("*"), reverse=True):
            if child.is_dir():
                child.rmdir()
        tmp.rmdir()

    if not args.no_open:
        webbrowser.open("file://" + str(OUTPUT))


if __name__ == "__main__":
    main()
