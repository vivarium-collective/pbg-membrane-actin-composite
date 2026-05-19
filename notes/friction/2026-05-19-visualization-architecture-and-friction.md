# Friction log — visualization architecture (what works, what doesn't)

**Date:** 2026-05-19 (continuing from logs #1–#4 the day before).
**Scope:** A concentrated retro of the eight Visualization classes I shipped
for this workspace, the three different render paths the dashboard exposes,
and which paths can carry which data shapes. Companion to the earlier logs
which cover scaffolding, run-time, and PR-flow; this one is about what to
do (and not do) when authoring a viz for a pbg-template workspace.

If you're picking up this workspace cold and need to add a chart, start here.

---

## The three render paths (pick the one that matches your data)

The dashboard has **three** disjoint ways to drive a Visualization class:

### Path A — inline composite Step

The viz is wired into `state` as a `_type: step` with declared `inputs:`
that point at simulation stores. `composite.run(steps)` calls
`update(state)` once per composite tick with per-step scalar values.

**Used by:** mem3dg's `MembranePlots`, my earlier draft of `CouplingTrace`
that wired the step into `build_document` output.

**Carries:** scalar-per-step values only. The viz's declared inputs must
type-check against the upstream stores. `'float'` against a `Float` store
works; `'list[float]'` against a `Float` store **does not** — process-bigraph's
schema engine raises `cannot resolve types: Float vs List[Float]`.

**Limitation:** the viz `update()` is called once per step, in-process,
so it has no access to historical context. To draw a multi-step chart it
has to maintain its own `self.history` between calls. And the viz's
declared inputs must be scalars — list-typed inputs break inline wiring.

### Path B — auto-render from runs.db via typed wire

After a run completes, the dashboard's
`vivarium_dashboard.lib.investigations.render_visualizations` builds a
**fresh** composite per viz: one tiny composite containing the viz Step
plus an `inputs_store` populated from the SQLiteEmitter's `runs.db`.
The composite is run for **one** step; the viz receives `state` with
each port populated by the per-port resolved series.

The dispatch table in `build_viz_composite`
(`vivarium_dashboard/lib/investigations.py:1075`):

| Declared port type     | What `inputs_store[port]` gets         |
|------------------------|----------------------------------------|
| `'float'`              | **last** scalar only (`series[-1]`)   |
| `'list[float]'`        | full series for the one run            |
| `'list[list[float]]'`  | list-of-runs (each a per-tick series)  |
| anything else          | first run's full series                |

**Used by:** my 8 Plotly vizzes (CouplingTrace, BackpressureTrace,
PopulationTrace, BarrierKinematics, ForceVelocityScatter, EnergyBudget,
RatchetEventRate, MembraneVolumeStrain). All declare `'list[float]'`.

**Carries:** anything that fits the dispatch table. Critically:
- 1D scalar series (`'list[float]'`) ✓
- Per-tick lists where each tick is a list of scalars (`'list[list[float]]'`) ✓
  but only if the SECOND level is scalars
- **NOT** 3-level-nested arrays (e.g. per-tick `list[points][3]` for
  positions). The schema engine treats inner lists as element scalars
  and discards them. End up with empty arrays in `update()`.

**Limitation:** the viz `update()` is called exactly **once**, with the
full series already aggregated. So `self.history` accumulation logic is
irrelevant; the viz must handle bulk-input form. This is incompatible
with Path A (inline step that fires per-tick), so you can't reuse the
same class for both paths unless you defensively detect both shapes.

### Path C — direct runs.db read

The viz's `inputs()` returns `{}`. No dashboard wiring at all. In
`update()`, the viz opens `<workspace>/studies/<slug>/runs.db` directly
via `sqlite3`, pulls every per-step state for the latest simulation,
and embeds the result in the rendered HTML.

**Used by:** my new `Particles3D` (the real-data 3D mesh viewer).

**Carries:** anything in `runs.db`. The SQLiteEmitter writes the full
state as JSON per step — including 3-level-nested coordinate arrays
that the typed wire would have truncated. This is the **only** path
that gets real per-frame Mem3DG vertex positions and ReaDDy actin
positions into a viz.

**Limitation:** the viz has to know which study's runs.db to read.
Resolution heuristics:

  1. `config.study_slug` — explicit, set per-study in study.yaml.
     This is the recommended pattern.
  2. Most-recently-modified `runs.db` under `studies/*/runs.db`.
     Works for the dashboard's sequential render flow (called
     immediately after a baseline run), but races if multiple runs
     are in flight.

Also: anything not captured in `runs.db` (e.g. static mesh topology
like Mem3DG `faces`, which is computed at process construction and
never re-emitted) has to be reconstructed by re-instantiating the
process. See `_try_get_faces()` in `particles_3d.py`.

---

## Which path for which need (decision tree)

```
What does the viz need?
├─ Per-step scalar history of one or more observables
│   ├─ Auto-render is fine. Declare 'list[float]' inputs, accept the
│   │  full series in update(), draw a chart. → Path B
│   └─ Example: CouplingTrace, BarrierKinematics, all 8 Plotly vizzes.
│
├─ Per-step nested arrays (positions, vertex sets, matrices)
│   └─ Auto-render WILL truncate. Read from runs.db directly. → Path C
│       Example: Particles3D.
│
└─ Live, in-simulation overlay (e.g. a viz Step that fires per tick
    and writes to a wire other processes consume)
    └─ Inline composite step, scalar inputs only. → Path A
        Example: pbg-mem3dg's MembranePlots in its own composite spec.
```

---

## Concrete authoring rules

### Always do
- **Declare inputs() with types from the dispatch table.** Unknown
  type strings raise `'str' object does not support item assignment`
  during composite init (process-bigraph schema engine tries to mutate
  the type string as a schema).
- **Handle empty-input gracefully.** Return an `'html'` payload with an
  inline error message rather than raising. Other vizzes still render.
- **Append `_autosize_script(content_height)` to every viz's HTML.**
  The dashboard's iframe has `min-height: 1600px`; without the shim
  every viz appears in a giant iframe with white space below. See §32 in
  log #4.
- **Embed JS as a plain string, not an f-string.** Use `str.replace()`
  for template variables. F-string brace-escaping (`{{`/`}}`) is invisible
  in Python (renders to literal braces) and invalid JS in the browser.
  See §31 in log #4.

### Never do
- Don't mix Path A and Path B in one class without explicit shape
  detection. If `inputs()` returns `'list[float]'`, Path A breaks
  (scalar stores can't merge into list types). If it returns `'float'`,
  Path B only gives you the LAST scalar.
- Don't `setTimeout`-retry `fit()` against `document.scrollHeight`
  while also listening on `window.resize`. Plotly's responsive layout
  creates a feedback loop that grows the iframe monotonically.
  Use a one-shot fixed-height setter. See §31-32 above.
- Don't trust `__init__` to fire on the auto-render path. The
  dashboard does `viz_class.__new__(viz_class).inputs()` to introspect
  declared ports without instantiating, so `__init__` side effects
  (e.g. `self.history = []`) may be skipped. Initialize lazily in
  `update()`.
- Don't `id(self)` as the div id. The auto-render path may instantiate
  the same class twice in one page; `id()` collisions cause Plotly
  to render both charts into the same container. Use a stable hash
  of `(class_name, config['title'])`.

### Pragmatic
- The SQLiteEmitter `inject_sqlite_emitter` matches the existing
  emitter by `addr.endswith("Emitter")` (case-sensitive — capital E).
  My `build_document` had `'local:ram-emitter'` and SQLiteEmitter got
  installed with empty `inputs:` → `runs.db` rows were `state={}`.
  Renamed to `'local:RAMEmitter'`. Documented in friction log #3 §24.
  **Recommendation when porting a model package**: ensure your
  emitter's address ends with capital-E `Emitter`.
- ReaDDy/Mem3DG emit C++ libc log lines to fd 1, which pollute the
  dashboard's `@@@RESULTS@@@` JSON marker. `build_core()` in this
  workspace does a one-shot `os.dup2(2, 1)` to redirect those to
  stderr. See friction log #3 §23 for the full pattern.

---

## The viz inventory I shipped

After all this, the workspace ships:

| Viz | Path | Source data | Rendered as |
|---|---|---|---|
| CouplingTrace | B | actin_max_z, membrane_min_z, contact_force | Plotly 3-line chart |
| BackpressureTrace | B | membrane_volume, osmotic_offset, wall_z | Plotly 3-line chart |
| PopulationTrace | B | actin_total, cumulative ratchet_steps | Plotly 2-line chart |
| BarrierKinematics | B | barrier_z, barrier_velocity | Plotly dual-axis |
| ForceVelocityScatter | B | mean_contact_force, barrier_velocity | Plotly time-colored scatter |
| EnergyBudget | B | bending/surface/pressure energies | Plotly stacked area |
| RatchetEventRate | B | ratchet_steps (per-step) | Plotly 2-line with rolling mean |
| MembraneVolumeStrain | B | membrane_volume | Plotly line + 10% reference |
| SchematicVesicle3D | B | membrane_volume, actin_max_z, contact_force (scalars) | Three.js — abstract sphere + puck |
| Particles3D | C | actin_positions, membrane_vertex_positions, wall_z, **faces** (computed) | Three.js — real Mem3DG mesh + actin InstancedMesh |

**Particles3D is the only one that renders REAL geometry.** Everything
else (including SchematicVesicle3D) is rendered from scalar-per-step
series via the typed wire.

---

## What I'd push upstream (in priority order)

1. **A `'positions'` (or `'list[vec3]'`) primitive type in
   `bigraph-schema` + a matching dispatch branch in `build_viz_composite`.**
   Three-level nesting (frames × points × 3) is what every spatial
   simulator emits. Right now there's no way to wire it through.
   This single addition would let me retire the Path C runs.db
   workaround.

2. **`@composite_generator(visualizations=...)` defaults need
   `address:`** (extended from log #3 §26). When merged with study yaml
   vizzes, name-only defaults silently win and break rendering.

3. **`inject_sqlite_emitter`'s `addr.endswith("Emitter")` should be
   case-insensitive.** Otherwise a wrong-case emitter address fails
   silently — every `runs.db` row ends up `state={}` with no warning.

4. **Iframe sizing in `study-detail.html` should set `minHeight` to 0
   in the onload resizer**, not just `height`. The current
   `min-height: 1600px` inline style overrides any subsequent `height`
   set by the resize JS, forcing every viz into a giant frame.

5. **Document the three render paths in
   `docs/concepts/visualizations.md`.** The path you pick determines
   nearly everything else (data shape constraints, init-time guarantees,
   what `update()` receives). I learned all this empirically over
   several hours.

6. **Optional: an `auto_runs_db_for_study` config feature.** The
   dashboard knows the study_dir at render time; have it inject
   `runs_db_path` into every viz's config so Path-C vizzes don't need
   `study_slug` boilerplate in every study.yaml entry.

---

## Final recommendations to a future viz author

If your viz needs only scalar-per-step observables, Path B is fast and
clean — declare `'list[float]'`, handle the full-series input, return
HTML. The 8 Plotly vizzes in this workspace are templates.

If your viz needs nested arrays (positions, matrices, anything `[N][3]`
per step), skip the typed wire entirely. Use Path C: empty `inputs()`,
read `runs.db` directly, embed the data in the HTML. `Particles3D` is
the working template.

If your viz needs to react live during simulation (writing back to a
store other processes read), use Path A — but be aware that the same
class can't then also serve the auto-render path without significant
defensive code.
