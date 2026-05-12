# pbg-membrane-actin-composite

A process-bigraph composite that wires
[pbg-mem3dg](https://github.com/vivarium-collective/pbg-mem3dg) (lipid-membrane
mechanics) and [pbg-readdy](https://github.com/vivarium-collective/pbg-readdy)
(particle-based reaction-diffusion) together as a closed-loop **Brownian
ratchet**: actin filaments push the membrane up, the membrane pushes back on
the actin field, the actin grows and pushes harder.

## Science motivation

The Brownian ratchet model of actin polymerization (Peskin, Odell & Oster, 1993)
explains how thermal fluctuations of a constraining membrane allow polymerizing
filaments to occasionally insert a monomer in the gap. Each successful
insertion permanently advances the filament tip — the membrane has been
ratcheted up by one monomer length. This composite reproduces the qualitative
behavior of that model with two real, independent simulators:

- **ReaDDy** evolves the actin field as a particle-based reaction-diffusion
  system. Polymerization is modelled as a `G + G → F` fusion reaction.
- **Mem3DG** evolves the membrane as a triangulated surface under bending,
  surface-tension, and osmotic-pressure forces.
- The **`BrownianRatchetCoupler`** Process sits between them, computes the
  contact gap on each step, and publishes:
  - `wall_z` to ReaDDy (constrains particles to z ≤ wall_z; rebuilds the
    ReaDDy simulation with a new box potential)
  - `osmotic_strength_offset` to Mem3DG (bulges the membrane upward when
    the contact force is non-zero; rebuilds the Mem3DG System with the
    new effective osmotic strength)

## Wiring table

| # | Producer | Consumer | Kind | Store |
|---|---|---|---|---|
| 1 | `ReaDDyProcess.positions` | `BrownianRatchetCoupler.actin_positions` | pass-through | `actin/positions` |
| 2 | `Mem3DGProcess.vertex_positions` | `BrownianRatchetCoupler.membrane_vertices` | pass-through | `membrane/vertex_positions` |
| 3 | `BrownianRatchetCoupler.wall_z` | `ReaDDyProcess.wall_z` | pass-through (closed-loop) | `control/wall_z` |
| 4 | `BrownianRatchetCoupler.osmotic_strength_offset` | `Mem3DGProcess.osmotic_strength_offset` | pass-through (closed-loop) | `control/osmotic_strength_offset` |
| 5–9 | `BrownianRatchetCoupler.{contact_force, gap, actin_max_z, membrane_min_z, ratchet_steps}` | `<emitter>` | sink | `coupling/*` |

No adapters or stubs are needed. The wiring works because pbg-mem3dg and
pbg-readdy were extended (as part of building this composite) to expose the
new `osmotic_strength_offset` and `wall_z` input ports respectively. Both
extensions implement the back-channel via a **rebuild-on-change** pattern:
when the input changes, the wrapper snapshots its state, drops its
underlying simulator, builds a fresh one with the updated parameter, and
restores state. See the upstream commits for details.

## Installation

This composite depends on two heavy upstream wrappers (which in turn depend
on `pymem3dg` and `readdy`). Editable installs against local clones are the
recommended path during development:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ../pbg-mem3dg
uv pip install -e ../pbg-readdy
uv pip install -e ".[dev,demo]"
```

> Once installed, all three classes (`Mem3DGProcess`, `ReaDDyProcess`,
> `BrownianRatchetCoupler`) register automatically via
> `bigraph_schema.package.discover` — no manual `register_link()` calls
> needed.

## Quick start

```python
from process_bigraph import Composite, gather_emitter_results
from pbg_membrane_actin_composite import build_core, build_document

core = build_core()
doc = build_document(closed_loop=True, growth_rate=4.0, interval=0.5)
sim = Composite({'state': doc}, core=core)
sim.run(6.0)

samples = list(gather_emitter_results(sim).values())[0]
final = samples[-1]
print(f"final actin total: {final['actin_total']}")
print(f"final wall_z published: {final['wall_z']}")
print(f"final osmotic_offset: {final['osmotic_offset']}")
print(f"cumulative ratchet steps: {sum(s['ratchet_steps'] for s in samples)}")
```

## Architecture

```
ReaDDyProcess.positions ──┐
                          │
                          ▼
                  BrownianRatchetCoupler ──► control.wall_z ──► ReaDDyProcess.wall_z
                          ▲                       (rebuild)
                          │
Mem3DGProcess.vertex_positions ──┘
                          ▼
                  control.osmotic_strength_offset ──► Mem3DGProcess.osmotic_strength_offset
                                                        (rebuild)
```

A bigraph-viz PNG of the full document is embedded in `demo/report.html`.

## Running the demo

```bash
python demo/demo_report.py
```

Generates `demo/report.html` and opens it in the default browser. Three
scenarios:

| Scenario | `closed_loop` | `growth_rate` | What to look for |
|---|---|---|---|
| `decoupled_baseline` | `False` | 4.0 | wall_z stays None, osmotic_offset stays 0; ratchet diagnostics still computed but not fed back. |
| `coupled_ratchet` | `True` | 4.0 | wall_z and osmotic_offset move; ratchet_steps accumulates. |
| `stressed_ratchet` | `True` | 8.0 | Doubled polymerization rate — ratchet_steps climbs faster. |

The "headline coupling chart" required by the pbg-superpowers composite-demo
spec plots `actin_max_z`, `membrane_min_z`, and `contact_force` on a shared
time axis — making the gap closures visible.

## Limitations and assumptions

- **Coupling is at the parameter level, not per-vertex / per-particle.**
  pymem3dg 0.0.7.dev's external-force API path
  (`Parameters.external.form` + `point.prescribeNotableVertex`) segfaults
  on `System.initialize()` for our configuration, so the Mem3DG side
  drives a global osmotic-pressure offset rather than localized vertex
  forces. ReaDDy's barrier is similarly a global box potential, not a
  per-particle force.
- **The coupling is rebuild-driven, not in-place.** When either
  back-channel changes, the corresponding wrapper destroys its underlying
  simulator and rebuilds. This is significantly cheaper than calling
  `run()` for short bursts inside a single update interval, but every
  rebuild loses the simulator's internal integrator state (velocities,
  observable buffers, accumulated random-number-generator state).
- **One-step lag.** In the composite execution order, the coupler sees
  wrapper outputs from the *previous* interval. This is a normal
  consequence of process-bigraph scheduling and not a bug, but the very
  first composite step has the coupler emitting no back-channel at all
  (no upstream data yet).
- **Mock or schematic visualization.** The Three.js viewer in the demo
  report shows a stylized membrane sphere (radius tracking
  `membrane_volume`) and an actin disk below (radius tracking
  `actin_total`). The real per-cell triangulated mesh and per-particle
  positions are emitted by the wrappers but not rendered in v0.1.

## Related repos

- [pbg-mem3dg](https://github.com/vivarium-collective/pbg-mem3dg) — the membrane wrapper. The
  `osmotic_strength_offset` input port was added as part of this composite work
  (commit `6eabc32`).
- [pbg-readdy](https://github.com/vivarium-collective/pbg-readdy) — the actin wrapper. The
  `wall_z` input port was added as part of this composite work (commit `47c2d86`).
- [pbg-superpowers](https://github.com/vivarium-collective/pbg-superpowers) — the
  process-bigraph workflow plugin whose `/pbg-expert` composite mode generated
  this scaffold.
