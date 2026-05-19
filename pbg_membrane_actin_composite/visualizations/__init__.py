"""Visualization Steps for the membrane-actin Brownian-ratchet composite.

These are the dashboard-driveable equivalents of the demo/report.html panels.
Each is a process_bigraph.Step subclass (via
pbg_superpowers.visualization.Visualization) that accumulates per-step
observable values and re-renders a styled Plotly HTML figure on every update().

The full set:

  CouplingTrace          — actin_max_z + membrane_min_z + contact_force
  BackpressureTrace      — membrane_volume + osmotic_offset + wall_z
  PopulationTrace        — actin_total + cumulative ratchet steps
  BarrierKinematics      — barrier_z + barrier_velocity (dual axis)
  ForceVelocityScatter   — (F, V) trail, time-colored — Inoue 2015 benchmark
  EnergyBudget           — stacked area of Mem3DG bending/surface/pressure energies
  RatchetEventRate       — instantaneous + rolling-mean ratchet firing rate
  MembraneVolumeStrain   — (V-V0)/V0 vs time with 10% reference line

See pbg_superpowers.visualization.Visualization for the base contract.
"""
from __future__ import annotations

from pbg_membrane_actin_composite.visualizations.coupling_trace import CouplingTrace
from pbg_membrane_actin_composite.visualizations.backpressure_trace import BackpressureTrace
from pbg_membrane_actin_composite.visualizations.population_trace import PopulationTrace
from pbg_membrane_actin_composite.visualizations.barrier_kinematics import BarrierKinematics
from pbg_membrane_actin_composite.visualizations.force_velocity_scatter import ForceVelocityScatter
from pbg_membrane_actin_composite.visualizations.energy_budget import EnergyBudget
from pbg_membrane_actin_composite.visualizations.ratchet_event_rate import RatchetEventRate
from pbg_membrane_actin_composite.visualizations.membrane_volume_strain import MembraneVolumeStrain
from pbg_membrane_actin_composite.visualizations.schematic_vesicle_3d import SchematicVesicle3D

__all__ = [
    "CouplingTrace",
    "BackpressureTrace",
    "PopulationTrace",
    "BarrierKinematics",
    "ForceVelocityScatter",
    "EnergyBudget",
    "RatchetEventRate",
    "MembraneVolumeStrain",
    "SchematicVesicle3D",
]
