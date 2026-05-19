#!/usr/bin/env python3
"""Regenerate pbg_membrane_actin_composite/composites/*.composite.yaml.

Each composite spec is generated from build_document(**rung_kwargs) plus
a set of Visualization Steps wired to the appropriate store paths. The
factory + the YAML stay in sync via this script — re-run after any
change to document.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from pbg_membrane_actin_composite import build_document


HERE = Path(__file__).resolve().parent.parent
OUT_DIR = HERE / "pbg_membrane_actin_composite" / "composites"


RUNGS = [
    {
        "name": "rung1-fixed-boundary",
        "stem": "rung1_fixed_boundary",
        "title": "Rung 1 — Fixed boundary",
        "description": "Actin pushes against a wall held at fixed z (spec §2.2 #1). Brownian-ratchet kinetics against an immovable boundary; barrier_velocity is zero by construction.",
        "tags": ["brownian-ratchet", "fixed-boundary", "spec-2.2-rung1"],
        "accent": "#94a3b8",
        "kwargs": dict(
            closed_loop=True, coupling_mode='planar', barrier_kind='fixed',
            barrier_initial_z=0.0, interval=0.5, n_filaments=6,
            monomers_per_filament=4, force_constant=2.0, contact_threshold=0.4,
        ),
    },
    {
        "name": "rung2-rigid-movable-boundary",
        "stem": "rung2_rigid_movable_boundary",
        "title": "Rung 2 — Movable rigid boundary (Peskin 1993)",
        "description": "Wall translates under integrated contact force using drag-balance kinematics. Reproduces Peskin 1993 setup (spec §2.2 #2).",
        "tags": ["brownian-ratchet", "rigid-movable", "peskin-1993", "spec-2.2-rung2"],
        "accent": "#0ea5e9",
        "kwargs": dict(
            closed_loop=True, coupling_mode='planar', barrier_kind='rigid_movable',
            barrier_initial_z=0.0, barrier_drag=8.0, interval=0.5,
            n_filaments=6, monomers_per_filament=4, force_constant=2.0,
            contact_threshold=0.4,
        ),
    },
    {
        "name": "rung3-flexible-mem3dg-boundary",
        "stem": "rung3_flexible_mem3dg_boundary",
        "title": "Rung 3 — Flexible Mem3DG membrane",
        "description": "Closed Mem3DG icosphere vesicle inflating under bonded actin pushing radially outward (spec §2.2 #3). Phase-2 endpoint: full mem3dg ↔ readdy bidirectional handshake.",
        "tags": ["brownian-ratchet", "flexible-membrane", "mem3dg", "readdy", "spec-2.2-rung3"],
        "accent": "#10b981",
        "kwargs": dict(
            closed_loop=True, coupling_mode='spherical', barrier_kind='flexible',
            membrane_geometry='icosphere', interval=0.5, n_filaments=6,
            monomers_per_filament=4, force_constant=5.0,
            osmotic_force_scale=0.05, contact_threshold=0.3,
        ),
    },
]


# Visualization Step specs — each maps to a class in pbg_membrane_actin_composite.visualizations
VIZ_STEPS = [
    {
        "key": "viz_coupling",
        "class": "CouplingTrace",
        "html_store": "viz_coupling_html",
        "inputs": {
            "time": ["global_time"],
            "actin_max_z": ["coupling", "actin_max_z"],
            "membrane_min_z": ["coupling", "membrane_min_z"],
            "contact_force": ["coupling", "contact_force"],
        },
    },
    {
        "key": "viz_backpressure",
        "class": "BackpressureTrace",
        "html_store": "viz_backpressure_html",
        "inputs": {
            "time": ["global_time"],
            "membrane_volume": ["membrane", "volume"],
            "osmotic_offset": ["control", "osmotic_strength_offset"],
            "wall_z": ["control", "wall_z"],
        },
    },
    {
        "key": "viz_population",
        "class": "PopulationTrace",
        "html_store": "viz_population_html",
        "inputs": {
            "time": ["global_time"],
            "actin_total": ["actin", "total_particles"],
            "ratchet_steps": ["coupling", "ratchet_steps"],
        },
    },
    {
        "key": "viz_barrier_kinematics",
        "class": "BarrierKinematics",
        "html_store": "viz_barrier_kinematics_html",
        "inputs": {
            "time": ["global_time"],
            "barrier_z": ["coupling", "barrier_z"],
            "barrier_velocity": ["coupling", "barrier_velocity"],
        },
    },
    {
        "key": "viz_fv_scatter",
        "class": "ForceVelocityScatter",
        "html_store": "viz_fv_scatter_html",
        "inputs": {
            "time": ["global_time"],
            "mean_contact_force": ["coupling", "mean_contact_force"],
            "barrier_velocity": ["coupling", "barrier_velocity"],
        },
    },
    {
        "key": "viz_energy_budget",
        "class": "EnergyBudget",
        "html_store": "viz_energy_budget_html",
        "inputs": {
            "time": ["global_time"],
            "bending_energy": ["membrane", "bending_energy"],
            "surface_energy": ["membrane", "surface_energy"],
            "pressure_energy": ["membrane", "pressure_energy"],
        },
    },
    {
        "key": "viz_ratchet_rate",
        "class": "RatchetEventRate",
        "html_store": "viz_ratchet_rate_html",
        "inputs": {
            "time": ["global_time"],
            "ratchet_steps": ["coupling", "ratchet_steps"],
        },
    },
    {
        "key": "viz_volume_strain",
        "class": "MembraneVolumeStrain",
        "html_store": "viz_volume_strain_html",
        "inputs": {
            "time": ["global_time"],
            "membrane_volume": ["membrane", "volume"],
        },
    },
]


def _viz_step(spec: dict, accent: str, rung_title: str) -> dict:
    """Build the YAML node for one Visualization Step wired to its inputs."""
    return {
        "_type": "step",
        "address": f'local:{spec["class"]}',
        "config": {
            "title": f'{spec["class"]} — {rung_title}',
            "accent": accent,
        },
        "inputs": {wire: list(path) for wire, path in spec["inputs"].items()},
        "outputs": {"html": ["stores", spec["html_store"]]},
    }


def _build_state(rung: dict) -> dict:
    state = build_document(**rung["kwargs"])
    # Coerce to plain JSON-able types for clean YAML.
    state = json.loads(json.dumps(state, default=str))
    # Pre-seed empty html stores so process-bigraph can wire outputs cleanly.
    state.setdefault("stores", {})
    for spec in VIZ_STEPS:
        state["stores"][spec["html_store"]] = ""
        state[spec["key"]] = _viz_step(spec, rung["accent"], rung["title"])
    return state


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    init = OUT_DIR / "__init__.py"
    if not init.exists():
        init.write_text(
            '"""Composite specs for the membrane-actin Brownian-ratchet composite.\n\n'
            "Each *.composite.yaml file is a declarative state document discovered by\n"
            "pbg_superpowers.composite_discovery. Specs are regenerated from\n"
            "build_document(...) plus Visualization Step wires — re-run\n"
            "scripts/regen-composites.py to refresh.\n"
            '"""\n'
        )
    for rung in RUNGS:
        spec = {
            "name": rung["name"],
            "description": rung["description"],
            "tags": rung["tags"],
            "state": _build_state(rung),
        }
        path = OUT_DIR / f'{rung["stem"]}.composite.yaml'
        path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
        print(f"wrote {path.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
