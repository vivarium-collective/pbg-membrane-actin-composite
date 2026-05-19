"""Composite generators + specs for the membrane-actin Brownian-ratchet.

Three rungs of the spec §2.2 boundary-condition staircase, each exposed
through two complementary conventions:

1. **`@composite_generator`** (this file) — dynamic, registered at import
   time, parameterizable. Used by the dashboard's Run / Investigations
   tabs and by `_post_study_run_baseline`. Always reflects the latest
   `build_document` behavior.
2. **`*.composite.yaml`** (sibling files) — declarative snapshots, useful
   for diffs, code review, and inspecting the wired state without
   running Python. Regenerate with `scripts/regen-composites.py`.

Both forms share `build_document(barrier_kind=k)` and the eight viz
Steps the regen script wires in.
"""
from __future__ import annotations

from typing import Any

from pbg_superpowers.composite_generator import composite_generator

from pbg_membrane_actin_composite import build_document


# ---------------------------------------------------------------------------
# Viz wiring — applied to every rung so all 8 charts appear in every run.
# ---------------------------------------------------------------------------

_VIZ_STEPS = [
    ("viz_coupling", "CouplingTrace", "viz_coupling_html", {
        "time": ["global_time"],
        "actin_max_z": ["coupling", "actin_max_z"],
        "membrane_min_z": ["coupling", "membrane_min_z"],
        "contact_force": ["coupling", "contact_force"],
    }),
    ("viz_backpressure", "BackpressureTrace", "viz_backpressure_html", {
        "time": ["global_time"],
        "membrane_volume": ["membrane", "volume"],
        "osmotic_offset": ["control", "osmotic_strength_offset"],
        "wall_z": ["control", "wall_z"],
    }),
    ("viz_population", "PopulationTrace", "viz_population_html", {
        "time": ["global_time"],
        "actin_total": ["actin", "total_particles"],
        "ratchet_steps": ["coupling", "ratchet_steps"],
    }),
    ("viz_barrier_kinematics", "BarrierKinematics", "viz_barrier_kinematics_html", {
        "time": ["global_time"],
        "barrier_z": ["coupling", "barrier_z"],
        "barrier_velocity": ["coupling", "barrier_velocity"],
    }),
    ("viz_fv_scatter", "ForceVelocityScatter", "viz_fv_scatter_html", {
        "time": ["global_time"],
        "mean_contact_force": ["coupling", "mean_contact_force"],
        "barrier_velocity": ["coupling", "barrier_velocity"],
    }),
    ("viz_energy_budget", "EnergyBudget", "viz_energy_budget_html", {
        "time": ["global_time"],
        "bending_energy": ["membrane", "bending_energy"],
        "surface_energy": ["membrane", "surface_energy"],
        "pressure_energy": ["membrane", "pressure_energy"],
    }),
    ("viz_ratchet_rate", "RatchetEventRate", "viz_ratchet_rate_html", {
        "time": ["global_time"],
        "ratchet_steps": ["coupling", "ratchet_steps"],
    }),
    ("viz_volume_strain", "MembraneVolumeStrain", "viz_volume_strain_html", {
        "time": ["global_time"],
        "membrane_volume": ["membrane", "volume"],
    }),
]


def _attach_viz_steps(state: dict, accent: str, rung_title: str) -> dict:
    """No-op: viz Steps now render against runs.db post-run, not inline.

    Earlier versions wired Visualization Steps directly into the composite
    so they fired every step. After switching declared inputs to
    ``list[float]`` (so the dashboard's auto-render path passes the full
    time series), inline wiring no longer type-checks against the scalar
    stores. The auto-render path (``_render_study_visualizations`` →
    ``render_visualizations``) reads runs.db, instantiates each viz, and
    writes ``studies/<name>/viz/*.html``. That is now the sole render
    path, eliminating the type-check conflict.
    """
    return state


_SHARED_PARAMS: dict[str, dict] = {
    "interval": {"type": "float", "default": 0.5,
                 "description": "Time per composite step."},
    "n_filaments": {"type": "int", "default": 6,
                    "description": "Number of bonded actin filaments."},
    "monomers_per_filament": {"type": "int", "default": 4,
                              "description": "Initial monomers per filament."},
    "force_constant": {"type": "float", "default": 2.0,
                       "description": "Coupler force-to-displacement scale."},
    "contact_threshold": {"type": "float", "default": 0.4,
                          "description": "Distance under which a tip is in contact."},
    "growth_rate": {"type": "float", "default": 4.0,
                    "description": "Actin polymerization rate. Sweep this for the F-V scan."},
}


@composite_generator(
    name="rung1_fixed_boundary",
    description=(
        "Actin pushes against a wall held at fixed z (spec §2.2 rung 1). "
        "Brownian-ratchet kinetics against an immovable boundary; "
        "barrier_velocity is zero by construction."
    ),
    parameters=_SHARED_PARAMS,
    default_n_steps=16,
    visualizations=[
        {"name": "coupling-trace"},
        {"name": "population-trace"},
        {"name": "barrier-kinematics"},
        {"name": "ratchet-event-rate"},
    ],
)
def rung1_fixed_boundary(core=None, **kwargs: Any) -> dict:
    overrides = {k: v for k, v in kwargs.items() if v is not None}
    state = build_document(
        closed_loop=True, coupling_mode='planar', barrier_kind='fixed',
        barrier_initial_z=0.0, **{
            'interval': 0.5, 'n_filaments': 6, 'monomers_per_filament': 4,
            'force_constant': 2.0, 'contact_threshold': 0.4,
            **overrides,
        }
    )
    return _attach_viz_steps(state, "#94a3b8", "Rung 1 — Fixed boundary")


@composite_generator(
    name="rung2_rigid_movable_boundary",
    description=(
        "Wall translates under integrated contact force using drag-balance "
        "kinematics (spec §2.2 rung 2). Reproduces Peskin 1993 setup."
    ),
    parameters={**_SHARED_PARAMS, "barrier_drag": {
        "type": "float", "default": 8.0,
        "description": "Drag coefficient of the movable rigid wall.",
    }},
    default_n_steps=16,
    visualizations=[
        {"name": "coupling-trace"},
        {"name": "population-trace"},
        {"name": "barrier-kinematics"},
        {"name": "force-velocity-scatter"},
        {"name": "ratchet-event-rate"},
    ],
)
def rung2_rigid_movable_boundary(core=None, **kwargs: Any) -> dict:
    overrides = {k: v for k, v in kwargs.items() if v is not None}
    state = build_document(
        closed_loop=True, coupling_mode='planar', barrier_kind='rigid_movable',
        barrier_initial_z=0.0, **{
            'interval': 0.5, 'n_filaments': 6, 'monomers_per_filament': 4,
            'force_constant': 2.0, 'contact_threshold': 0.4, 'barrier_drag': 8.0,
            **overrides,
        }
    )
    return _attach_viz_steps(state, "#0ea5e9", "Rung 2 — Rigid movable")


@composite_generator(
    name="rung3_flexible_mem3dg_boundary",
    description=(
        "Closed Mem3DG icosphere vesicle inflating under bonded actin pushing "
        "radially outward (spec §2.2 rung 3). Phase-2 endpoint: full "
        "mem3dg ↔ readdy bidirectional handshake."
    ),
    parameters={**_SHARED_PARAMS, "osmotic_force_scale": {
        "type": "float", "default": 0.05,
        "description": "Per-contact osmotic offset gain into Mem3DG.",
    }},
    default_n_steps=16,
    visualizations=[
        {"name": "coupling-trace"},
        {"name": "backpressure-trace"},
        {"name": "population-trace"},
        {"name": "barrier-kinematics"},
        {"name": "energy-budget"},
        {"name": "membrane-volume-strain"},
        {"name": "ratchet-event-rate"},
        {"name": "force-velocity-scatter"},
    ],
)
def rung3_flexible_mem3dg_boundary(core=None, **kwargs: Any) -> dict:
    overrides = {k: v for k, v in kwargs.items() if v is not None}
    state = build_document(
        closed_loop=True, coupling_mode='spherical', barrier_kind='flexible',
        membrane_geometry='icosphere', **{
            'interval': 0.5, 'n_filaments': 6, 'monomers_per_filament': 4,
            'force_constant': 5.0, 'osmotic_force_scale': 0.05,
            'contact_threshold': 0.3,
            **overrides,
        }
    )
    return _attach_viz_steps(state, "#10b981", "Rung 3 — Flexible Mem3DG")
