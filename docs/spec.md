# Spec: multiscale simulation of actin / membrane feedback for the Brownian ratchet

A specification for an AI agent building a multiscale simulation that recapitulates the (elastic) Brownian ratchet theory of force production by polymerizing actin filaments against a deformable membrane. Grounded in the Akamatsu lab's discourse graph (`akamatsulab`) and the AllenCell collaboration graph (`AllenCell`).

The spec is read-only on the graph — it cites the questions, hypotheses, issues, evidence, and literature already in place; it does not invent new ones. Every citation is a clickable Roam URL. Confirm any specific function/path/parameter against the current code (`subcell-pipeline`, `Mem3DG`, `cytosim`, `ReaDDy`) before relying on it — memories of code state can be stale.

---

## 0. Where this spec lives in the graph

**Primary project page (collaboration graph):** [Project/Subcellular membrane modeling](https://roamresearch.com/#/app/AllenCell/page/E6wmMvMN2) — `allencell` — Status 🚀 Ongoing, anchored on the question below. This is the working graph for the Akamatsu × AICS (Jess Yu) × Vivarium (Eran) × Lee lab (Chris/Honor) collaboration.

**Sister project page (lab graph):** [Project/subcellular multiscale modeling](https://roamresearch.com/#/app/akamatsulab/page/ndulqgWDp) — `matsulab` — where the bulk of the conceptual planning, issues, and meeting notes live.

**Anchoring scientific question (target node):** [[[QUE]] - How do forces from the plasma membrane influence actin's force-velocity relationship?](https://roamresearch.com/#/app/AllenCell/page/SLxU3WIZx) — this is the `Target::` of the project page, and is the question the spec is designed to answer.

**Two-phase roadmap (live):** [Subcellular models summaries — Next Micropub: Two-Phase Plan](https://roamresearch.com/#/app/AllenCell/page/1yBARa_PT)
- **Phase 1 (current):** [ReaDDy + Cytosim composite interoperability](https://roamresearch.com/#/app/AllenCell/page/xH5qe1fi6) via Vivarium.
- **Phase 2 (this spec's focus):** [ReaDDy + Mem3DG membrane interoperability](https://roamresearch.com/#/app/AllenCell/page/6itJp6-q1) — couple particle-based actin (ReaDDy) with mesh-based membrane (Mem3DG) to test the Brownian-ratchet hypotheses below.

**Four publishable themes** the work feeds into ([March 5, 2025 meeting](https://roamresearch.com/#/app/AllenCell/page/_Px2ShvoO)): interoperability methods; actin against rigid vs. responsive vs. flexible surfaces; force/velocity as a function of membrane complexity; particle-based vs. mesh-based membrane comparison.

---

## 1. Scientific specification

### 1.1 The three load-bearing hypotheses

These define what "recapitulate the Brownian ratchet" *means* for this project — the simulation is considered successful when it produces evidence bearing on each.

1. **[[HYP]] — A flexible responsive membrane is necessary to recapitulate the elastic brownian ratchet theory in cytoskeletal simulations.**
   - [allencell version](https://roamresearch.com/#/app/AllenCell/page/ukyHwGk7Q) (canonical for this collaboration, has Background + Deliverables filled in).
   - [matsulab version](https://roamresearch.com/#/app/akamatsulab/page/fcHnyym3g) (older twin).
   - Background block (allencell): "[The Elastic Brownian Ratchet theory was proposed to explain the mechanism by which a single polymerizing actin filament can generate force. The filament undergoes constant Brownian motion. For sufficient bending away from a membrane, an actin monomer can be inserted between the filament and the membrane, lengthening the filament and subsequently applying force on the membrane to push it forward.](https://roamresearch.com/#/app/AllenCell/page/k4odDKXn8)"
   - Three deliverables under this HYP, already enumerated: a ReaDDy actin model, a Mem3DG membrane model, and a [composite model that translates actin position to membrane force](https://roamresearch.com/#/app/AllenCell/page/1w9AXsVkN).

2. **[[HYP]] — A flexible responsive membrane will lead to different force/polymerization rate relationships than a rigid boundary.** [allencell](https://roamresearch.com/#/app/AllenCell/page/ZvUKpq8Ly). Tests both [the classic elastic brownian ratchet](https://roamresearch.com/#/app/AllenCell/page/_K-M4jAqB) and [the surface-delivery theory from @mullins2024actin](https://roamresearch.com/#/app/AllenCell/page/Ur-8PedFC). Matt notes this is "really a larger part of" HYP #1.

3. **[[HYP]] — Polymerization from surface-attached monomers is necessary to recapitulate the rates of polymerization predicted by surface-delivery theory from [@mullins2024actin](https://roamresearch.com/#/app/akamatsulab/page/6C5ZWODa-).**
   - [allencell](https://roamresearch.com/#/app/AllenCell/page/ug1iL31g_) / [matsulab](https://roamresearch.com/#/app/akamatsulab/page/p0y00nCoa).
   - Companion to HYP #1 — distinguishes the *bulk Brownian-ratchet* contribution from the *surface-clustered polymerase* contribution that Mullins/Skruber 2024 propose.

### 1.2 Concrete target observable to match

[[[EVD]] - Simulating multiple actin filaments against a fluctuating membrane led to a concave force/velocity relationship at low polymerization rates and convex force/velocity relationship at high polymerization rates - [[@inoue2015brownian]]](https://roamresearch.com/#/app/AllenCell/page/wewHzder2)

This is the **primary numerical benchmark** ([called out as the Phase-2 goal](https://roamresearch.com/#/app/AllenCell/page/2OkBVo-2Y) in the roadmap):

- Low polymerization rate → concave-up F/V curve, membrane predominantly sustained by **monomers**.
- High polymerization rate → concave-down F/V curve, membrane predominantly sustained by **filaments**.
- Velocity is measured by [linear fit to membrane displacement vs. time](https://roamresearch.com/#/app/AllenCell/page/7Vcakiq6z); force and velocity are [normalized by stall force F_s and zero-load velocity V(0)](https://roamresearch.com/#/app/AllenCell/page/bXMXsRPfo).
- A reproduction simulation that flips concave→convex purely as a function of polymerization rate is the headline win for this spec.

A follow-up question is whether the [Brownian-ratchet mechanism arises only with multiple filaments](https://roamresearch.com/#/app/AllenCell/page/jHU75j2DW) — i.e. it's a statistical/ensemble property. The hypothesis is yes; the simulation should be able to falsify it (run single-filament cases too).

### 1.3 Theoretical anchors (read these first)

| Citekey | Title (short) | What to extract | Roam page |
|---|---|---|---|
| [@peskin1993cellular](https://roamresearch.com/#/app/akamatsulab/page/sbRlxhJus) | Cellular motions and thermal fluctuations: the Brownian ratchet (Peskin, Odell, Oster 1993) | The original ratchet equation; the [closed-form simplification when v_poly, v_depoly ≪ ideal ratchet velocity](https://roamresearch.com/#/app/akamatsulab/page/w9v-4e_t_); [exponential force-dependence of polymerization velocity](https://roamresearch.com/#/app/akamatsulab/page/8Xsach-R3). | EVD in graph: [[EVD]] |
| [@mogilner1996cell](https://roamresearch.com/#/app/akamatsulab/page/CYLny_qZG) | Cell motility driven by actin polymerization (Mogilner/Oster 1996) | **Elastic** Brownian ratchet — thermal fluctuations of *filaments*, not just the load. Quantitatively explains Listeria + lamellipodia. | — |
| [@mogilner2003force](https://roamresearch.com/#/app/akamatsulab/page/98nqHgl7E) | Force generation II: The Elastic Ratchet and Tethered Filaments (Mogilner/Oster 2003) | **Tethered ratchet** — filaments transiently bound to the surface by a nucleation complex. Force-velocity for Listeria; ActA-bead symmetry breaking. Cited as the rationale for [transient barbed-end tethering in cytosim](https://roamresearch.com/#/app/akamatsulab/page/xxjbpTCJy). | — |
| [@kuo2000steps](https://roamresearch.com/#/app/akamatsulab/page/j37p6FJK1) | Steps and fluctuations of Listeria (Kuo/McGrath 2000) | Step-like motion at ~5.4 nm (F-actin spatial periodicity); positional fluctuations ~20× *less* than lipid droplets. **Disproves naive Brownian ratchet, constrains elastic/molecular ratchet variants.** | — |
| [@theriot2000polymerization](https://roamresearch.com/#/app/akamatsulab/page/F1B7EHal5) | The Polymerization Motor (Theriot 2000) | Review tying thermodynamic free-energy to mechanical force; useful sanity-check on energetics. | — |
| [@vanoudenaarden1999cooperative](https://roamresearch.com/#/app/akamatsulab/page/jSrTwptUU) | Cooperative symmetry-breaking by actin polymerization in a model for cell motility (van Oudenaarden/Theriot 1999) | Bead motility assay; stochastic elastic-ratchet theory; **symmetry-breaking requires significant subunit off-rate (k_off)** — this is the basis for the koff issue (§3.1.2). | — |
| [@mullins2024actin](https://roamresearch.com/#/app/akamatsulab/page/6C5ZWODa-) | Distributive polymerases clustered on membrane surfaces (Mullins/Skruber 2024) | **Surface-delivery theory.** At low [actin], elongation is monomer-delivery–limited; at high [actin], it's set by how fast fluctuating filaments search the surface. Load forces amplify the advantage of surface polymerases. Anchor for HYP #3. | — |
| [@inoue2015brownian](https://roamresearch.com/#/app/AllenCell/page/1F9Kae_19) | Brownian dynamics F-V relation (Inoue/Deji/Adachi 2015) | **Direct target paper.** Concave/convex F-V transition; polymerization angle criterion φ_c and direction vector d_p for asymmetric monomer accessibility; F̃ = F/F_s, Ṽ = V/V(0). | — |
| [@li2022molecular](https://roamresearch.com/#/app/akamatsulab/page/hV1SEj9XQ) | Load adaptation in branched networks (Li, Bieling, Weichsel, Mullins, Fletcher 2022) | Per-filament force-dependent capping (extends Brownian ratchet from elongation to capping). Provides *the* parameterization for force-dependent rates [[per Abhi's note](https://roamresearch.com/#/app/akamatsulab/page/jrFABjLbC)]; engineered CP-size variants. | — |
| [@funk2021barbed](https://roamresearch.com/#/app/akamatsulab/page/mHoLjokoL) | Barbed-end interference (Funk et al. 2021) | NPF tethering to filament tips; mechanism for the surface-association picture in HYP #3 + transient tethering ISS. | — |
| [@zhu2022mem3dg](https://roamresearch.com/#/app/akamatsulab/page/u6PiqnmcI) | Mem3DG (Zhu, Lee, Rangamani 2022) | The membrane simulator. Helfrich–Canham–Evans + discrete differential geometry on triangulated meshes; per-vertex bending rigidity / spontaneous curvature; CME budding worked example. | [Page/Mem3DG](https://roamresearch.com/#/app/akamatsulab/page/0H2Y2933A) for code-side notes. |
| [@lee2009forcevelocity](https://roamresearch.com/#/app/AllenCell/page/Z-1K9lK9w), [@schreiber2010simulation](https://roamresearch.com/#/app/AllenCell/page/W5Z0PM20A) | (Lee/Liu 2009; Schreiber/Stewart/Duke 2010) | Other reported F-V simulations to cross-validate against. | — |

Also queue: [@bibeau2023twist](https://roamresearch.com/#/app/akamatsulab/page/ca1lLfdLf) for persistence-length parameterization; [Membrane-MEDYAN (Ni & Papoian 2021)](https://roamresearch.com/#/app/akamatsulab/page/_qF9unZUN) as a prior-art comparator that Atsushi flagged.

### 1.4 What "recapitulate the Brownian ratchet" looks like in practice

From the [January 8, 2025 project meeting](https://roamresearch.com/#/app/akamatsulab/page/pBIl12BA8) — the canonical scoping discussion. Direct quotes:

- "[one fiber against a membrane: brownian ratchet](https://roamresearch.com/#/app/akamatsulab/page/Ce7HMvyuv)"
- "[+ monomer availability?](https://roamresearch.com/#/app/akamatsulab/page/2eOknUh8a)"
- "[calibrate to theory? (brownian ratchet, surface speed)](https://roamresearch.com/#/app/akamatsulab/page/QsWZbBpm5)"
- "[+ readdy, + cytosim](https://roamresearch.com/#/app/akamatsulab/page/fXS0D0sU6)"
- "[we could try to recapitulate the surface availability on brownian ratchet (@mullins2024actin)](https://roamresearch.com/#/app/akamatsulab/page/XA6o08DXj)"
- "[the feedback from the membrane's point of view is still pretty poorly understood](https://roamresearch.com/#/app/akamatsulab/page/aMbQKEXMF)" ← the *core open problem*
- "[it would be nice to anchor the actin filament](https://roamresearch.com/#/app/akamatsulab/page/UlHMtVeAL)" (per Mogilner 2003 tethered-ratchet)
- "[could implement distance-dependent polymerization rate in cytosim](https://roamresearch.com/#/app/akamatsulab/page/2w17GuXQe)"

These are the criteria a candidate simulation must address.

---

## 2. Architectural specification

### 2.1 Multiscale stack

Three simulators, federated via Vivarium 2.0 (BioSimulators/`pbest`).

| Layer | Simulator | What it owns | Vivarium wrapper status |
|---|---|---|---|
| Monomer-scale actin | **ReaDDy** | Individual G-actin particles, binding/unbinding, filament bending fluctuations at nm scale | [[[ISS]] - Build Vivarium wrapper for ReaDDy #62](https://roamresearch.com/#/app/AllenCell/page/6yjza2Y67) — in progress, pip package landing ([Mar 16 2026](https://roamresearch.com/#/app/AllenCell/page/SlvDmaDx7)) |
| Fiber-scale actin | **Cytosim** | Filaments as elastic rods; Arp2/3, CP, myosin, etc.; force-dependent capping/elongation | [[[ISS]] - Build vivarium wrapper for Cytosim](https://roamresearch.com/#/app/AllenCell/page/ivqcCyYHt) — wrapper exists |
| Membrane | **Mem3DG** | Triangulated mesh, Helfrich energy, per-vertex tension/bending/spontaneous curvature | [[[ISS]] - Build Vivarium wrapper for Mem3DG](https://roamresearch.com/#/app/AllenCell/page/-jXbWVpKc) — early; Honor (Lee lab) helping build the endpoint; [pbg-mem3dg adaptor v1](https://vivarium-collective.github.io/pbg-mem3dg/) landed [Apr 27 2026](https://roamresearch.com/#/app/AllenCell/page/JecWTOMhV). |

Bridging adapters: [[[ISS]] - Build monomer-to-fiber and fiber-to-monomer adapters](https://roamresearch.com/#/app/AllenCell/page/ZfbVFpOi1) (Phase 1 deliverable).

Pipeline & infra: [`subcell-pipeline`](https://github.com/simularium/subcell-pipeline), the `jessicasyu/subcellular_modeling` GitHub project, Simularium for viz. Shared Zotero collection: [SimulariumModels](https://www.zotero.org/groups/2512112/simulariummodels/library). Slack: `#subcellular-modeling` in the akamatsulab workspace.

### 2.2 Boundary-condition progression (the canonical staircase)

From the [January 8 2025 plan](https://roamresearch.com/#/app/akamatsulab/page/atopa65LI) — climb this ladder, do not skip rungs:

1. **Fixed boundary** — actin pushes against a wall that cannot move. ISS: [[[ISS]] - Simulate actin polymerization against a fixed boundary in ReaDDy](https://roamresearch.com/#/app/akamatsulab/page/vAAyY4_Q_) / [allencell instance](https://roamresearch.com/#/app/AllenCell/page/gsNpe83CU) (Status ⏸️ On hold, contributor: Blair). Already produced a [filament-bending result](https://roamresearch.com/#/app/AllenCell/page/aK9rIivow) using a fixed-box potential, which supported HYP #1.
2. **Movable rigid boundary** — wall can translate, but cannot deform. Reproduces classic Peskin 1993 setup.
3. **Flexible responsive boundary (Mem3DG)** — the Phase-2 endpoint. Membrane deforms according to local actin forces and Helfrich energetics.

Implementation gotchas surfaced in the meeting:
- "[the hard part is that we don't have arbitrary fixed boundaries in readdy](https://roamresearch.com/#/app/akamatsulab/page/0TwRGZgC7)" — work in progress, see [[[ISS]] - Evaluate how "fixed" particles in ReaDDy behave](https://roamresearch.com/#/app/AllenCell/page/9LYQpsnIF) and [[[ISS]] - Develop proof of concept particle-based mesh as membrane vertices in ReaDDy](https://roamresearch.com/#/app/AllenCell/page/SNq5aKu5z) (which evaluates whether a *mesh of fixed-ish particles* can substitute for a Mem3DG boundary until the Vivarium handshake is ready).
- The membrane↔actin coupling needs **bidirectional** force translation: actin tip position → membrane force; membrane displacement → updated actin tip constraint. The "[[[ISS]] - Prototype of composite model that translates actin position to membrane force](https://roamresearch.com/#/app/AllenCell/page/1w9AXsVkN)" issue formalizes this.

### 2.3 Inputs that must be passed across simulator boundaries

From the [Jan 8 2025 meeting "inputs necessary to translate"](https://roamresearch.com/#/app/akamatsulab/page/lHHQW3Boi):

- **Force on filament end** (computed in cytosim or ReaDDy; consumed by the membrane).
- **Barrier size / geometry** (membrane patch dimensions, mesh resolution; consumed by actin).

Add (implied by the surface-delivery hypothesis):
- **Local monomer availability** at the membrane surface (spatial map; for Mullins-style surface clustering).
- **Tether occupancy** at the membrane–barbed-end contact (for tethered-ratchet variants).

---

## 3. Concrete Issues to implement, with grounding

These are existing `[[ISS]]` nodes in the graph that map directly to engineering tasks. The agent should treat each as a unit of work and link results back to the corresponding issue UID.

### 3.1 Actin / force-generation side

**3.1.1 Localized binding pocket for monomer addition.** [[[ISS]] - Implement a localized binding pocket for the next monomer addition](https://roamresearch.com/#/app/AllenCell/page/s1dE4wthE). Without this, polymerization is geometrically isotropic and the Inoue 2015 concave→convex F/V transition cannot emerge (because it depends on the *angular accessibility* φ_c of the binding site, see [the Inoue snippet](https://roamresearch.com/#/app/AllenCell/page/VTTzC32d2)). Tunables: binding distance (start at 0 nm, expect overlap with particle radius); occlusion-dependent polymerization rate.

**3.1.2 Reversible polymerization (k_off, Brownian ratchet).** [[[ISS]] - Incorporate koff (Brownian ratchet) in cytosim treatment of force-dependent actin elongation](https://roamresearch.com/#/app/akamatsulab/page/ljUD3ND0H). Description: "[calculate the conditions in which the k_off from Pollard 1986 would appreciably impact the effective elongation rate](https://roamresearch.com/#/app/akamatsulab/page/tZpJ0I6M8)." Required because van Oudenaarden/Theriot 1999 showed symmetry-breaking *only happens* with significant subunit off-rate.

**3.1.3 Exponential force-dependent capping.** [[[ISS]] - Re-implement force-dependent capping in cytosim to reflect the exponential relationship between force and capping](https://roamresearch.com/#/app/akamatsulab/page/1AAAvql-O) — Status ✅ Complete, contributor Abhishek. Parameterized from [Li 2022 figure 2c (per-filament rates)](https://roamresearch.com/#/app/akamatsulab/page/jrFABjLbC). The agent should *reuse* this parameterization, not re-derive it.

**3.1.4 Transient barbed-end tethering.** [[[ISS]] - Incorporate transient filament barbed end tethering to plasma membrane in cytosim](https://roamresearch.com/#/app/akamatsulab/page/xxjbpTCJy) — Status 🤔 Considering. Rationale: implements the [tethered ratchet from @mogilner2003force](https://roamresearch.com/#/app/akamatsulab/page/8oKeNkH5x). Mechanism candidate: barbed-end binding to WH2 domain of N-WASP — see [Funk 2021](https://roamresearch.com/#/app/akamatsulab/page/mHoLjokoL) and [Li 2022](https://roamresearch.com/#/app/akamatsulab/page/hV1SEj9XQ).

**3.1.5 Surface-attached monomers (Mullins-style).** [[[ISS]] - Set up ReaDDy simulations with a boundary, soluble monomers, ± monomers stuck to the surface](https://roamresearch.com/#/app/akamatsulab/page/p8r-KzUK1) — direct deliverable for HYP #3.

**3.1.6 Polymerization-rate analysis pipeline.** [[[ISS]] - Calculate relative change in polymerization rate as a function of occlusion (compared to free actin filament)](https://roamresearch.com/#/app/AllenCell/page/-QW4lw8YP) — Status 🚀 Ongoing. Pipeline already exists at `subcell_pipeline/analysis/polymerization_rate/_calculate_polymerization_rate.py`. Reuses `parse_readdy_simulation_data` from `subcell_pipeline/simulation/readdy/parser.py`. Reports contour length over time → polymerization velocity. The agent should pipe into this rather than reinventing.

### 3.2 Membrane side

**3.2.1 Particle-based mesh boundary in ReaDDy.** [[[ISS]] - Develop proof of concept particle-based mesh as membrane vertices in ReaDDy](https://roamresearch.com/#/app/AllenCell/page/SNq5aKu5z) — fallback for when Vivarium↔Mem3DG handshake isn't ready. Mesh of constrained particles approximates a deformable surface.

**3.2.2 Vivarium↔Mem3DG.** [[[ISS]] - Build Vivarium wrapper for Mem3DG](https://roamresearch.com/#/app/AllenCell/page/-jXbWVpKc) — the path to a true continuum-mesh membrane. Honor (Lee lab) leading. v1 adapter shipped [Apr 27 2026](https://vivarium-collective.github.io/pbg-mem3dg/).

**3.2.3 ReaDDy/ReaDDy filament↔membrane interop.** [[[@simulation/test ReaDDy-ReaDDy switching filament/membrane](https://roamresearch.com/#/app/AllenCell/page/RNpGfqqgW)] — a pure-ReaDDy variant testing whether one simulator can carry both halves.

### 3.3 Validation / discourse-graph plumbing

**3.3.1 Theriot bacteria-size benchmark.** [[[ISS]] - Discourse graph Theriot lab evidence from bacteria of different sizes](https://roamresearch.com/#/app/akamatsulab/page/cbx8BXQ9s) — Type 📚 Literature search. Cited in HYP #1's experiment requests. The Theriot lab's data on actin tail force-velocity across bacterial sizes is an *external* calibration target for the membrane-flexibility prediction.

---

## 4. Quantitative parameters and constraints

Pull from the graph; don't invent.

| Quantity | Value | Source in graph |
|---|---|---|
| Actin persistence length | ~10 µm; 10.7 ± 1 µm from worm-like-chain fit | [[[CLM]] - The persistence length of actin filaments is around 10 µm](https://roamresearch.com/#/app/akamatsulab/page/2WaelD3Z9); [[[EVD]] - …Bibeau 2023 measurement](https://roamresearch.com/#/app/akamatsulab/page/ca1lLfdLf) |
| Persistence length, ADP-Pi vs ADP | 10 µm → 7 µm in ADP state | [[[CLM]] - decreases from ~10 µm to ~7 µm](https://roamresearch.com/#/app/akamatsulab/page/oI_Q95vl2) |
| F-actin spatial periodicity | ~5.4 nm (Listeria step size) | [@kuo2000steps abstract](https://roamresearch.com/#/app/akamatsulab/page/eBZEUco2R) |
| Force-dependent capping rate | Single exponential decay in force | [[[EVD]] - per-filament capping rate decreased exponentially as a function of applied force](https://roamresearch.com/#/app/akamatsulab/page/2P3TkKxn6) |
| Force-dependent elongation rate | Exponential dependence (Brownian ratchet) | [[[EVD]] - exponential dependence of polymerization velocity on force](https://roamresearch.com/#/app/akamatsulab/page/8Xsach-R3) |
| Membrane bending rigidity ratio at protein coats | k_c ≈ 3 × k_b (assumption used in [Zhu 2022 CME example](https://roamresearch.com/#/app/akamatsulab/page/oYokce7w9)) | [@zhu2022mem3dg](https://roamresearch.com/#/app/akamatsulab/page/u6PiqnmcI) |
| Membrane tension (cytosim definition) | "restorative spring constant that tries to prevent vesicle formation by pulling the membrane flat" | [Grounding context block](https://roamresearch.com/#/app/akamatsulab/page/sKgW4FCLE) on the confinement-force RES |
| Inoue 2015 polymerization-angle criterion | φ_c, position vector d_p relative to plus-end particle | [Inoue snippet](https://roamresearch.com/#/app/AllenCell/page/VTTzC32d2) |
| Compression-velocity sweep (existing reference run) | 0.15–150 µm/s, 8 velocities | [Feb 23 2026 meeting](https://roamresearch.com/#/app/AllenCell/page/oXBQQ90BS) |

**Empirical caveat** worth noting: in the cytosim endocytosis simulations, [mean confinement force on the force-producing actin filaments was independent of membrane tension](https://roamresearch.com/#/app/akamatsulab/page/r_Q9Kgn9t) — meaning a naive `membrane_tension → filament_force` coupling did *not* fall out of the Phase-1 setup. The new simulation needs an explicit, validated translation function (this is the heart of [ISS - Prototype composite model](https://roamresearch.com/#/app/AllenCell/page/1w9AXsVkN)).

---

## 5. Validation plan

For each hypothesis, what must the simulation produce?

### 5.1 HYP #1 (flexible membrane needed for elastic ratchet)

- Run the same actin model against (a) fixed wall, (b) movable rigid wall, (c) Mem3DG flexible mesh.
- Required outcome: the F-V curve shape and the polymerization rate distribution should *differ qualitatively* between (a) and (c). If they're the same, the hypothesis is *falsified* and the simulation has succeeded as evidence (a null result is informative — see [matsulab agent rule on scope creep](https://roamresearch.com/#/app/akamatsulab/page/2Tf326Gi3): be direct).
- Specific success: reproduce Inoue 2015's concave→convex transition (§1.2) on the Mem3DG side but *not* the fixed-wall side.

### 5.2 HYP #2 (different F/V relations under flexible vs. rigid)

- Same suite as 5.1, but the headline metric is the *fit* of F-V to theory:
  - Peskin 1993 closed-form (when v_poly ≪ ideal ratchet velocity) — see [grounding context](https://roamresearch.com/#/app/akamatsulab/page/w9v-4e_t_) — should hold for rigid boundary, low rate.
  - Inoue 2015 concave/convex shape — should hold for flexible boundary.
  - Compare also against [Lee/Liu 2009](https://roamresearch.com/#/app/AllenCell/page/Z-1K9lK9w) and [Schreiber 2010](https://roamresearch.com/#/app/AllenCell/page/W5Z0PM20A).

### 5.3 HYP #3 (surface-attached monomers needed for Mullins surface-delivery)

- Run (a) only-soluble monomers; (b) only surface-bound monomers; (c) mix.
- Required outcome: at high bulk [actin], (b) should outpace (a) — the Mullins 2024 prediction. Quantitative match to Mullins/Skruber 2024 fig of surface-mediated vs. solution-mediated rates is the win.

### 5.4 Multi-filament vs. single-filament

- Per the [follow-up QUE](https://roamresearch.com/#/app/AllenCell/page/jHU75j2DW): is Brownian ratchet behavior a single-filament property or an ensemble property?
- Required: run N=1 and N>1 (e.g. N=10, N=100) and report whether the F/V signature appears at N=1 or only emerges with N>1. Falsifies or supports the "[Hypothesis is yes you need multiple filaments](https://roamresearch.com/#/app/AllenCell/page/LztlMLY4X)".

### 5.5 Reporting

- Every produced metric should be persisted as a `[[RES]]` node in the AllenCell graph following the format `[[RES]] - {observation} - [[@source-experiment]]` (see graph guidelines), where `@source-experiment` is something like `@simulation/inoue-recap-{boundary-type}-{N-filaments}`.
- Link each RES to the HYP it supports or opposes via the discourse-graph **Supports/Opposes** relations.

---

## 6. Constraints / gotchas already discovered

A consolidated list of things the team has hit so far — the spec should not rediscover these.

- **ReaDDy fixed boundaries are awkward.** Workaround in progress: mesh of constrained particles, or wait for the Mem3DG endpoint. See [Mar 5 2025 discussion](https://roamresearch.com/#/app/AllenCell/page/_Px2ShvoO).
- **Confinement force did not track membrane tension** in the cytosim endocytosis runs ([RES](https://roamresearch.com/#/app/akamatsulab/page/r_Q9Kgn9t)). The composite model must demonstrate that its tension-coupling is *nontrivial*, not just inherit cytosim's null result.
- **ARM-vs-Intel circular dependency in ReaDDy** ([Nov 24 2025](https://roamresearch.com/#/app/AllenCell/page/-2GKk4RJe)) — packaging fix landed in [Mar 2026](https://roamresearch.com/#/app/AllenCell/page/SlvDmaDx7); confirm before assuming local install works.
- **Mem3DG curvature accuracy is uneven** ([Atsushi's note Feb 9 2026](https://roamresearch.com/#/app/akamatsulab/page/qahUnfAk3)): "Curvature calculation by Mem3DG is actually not reliable…" — the [mem-PINN project](https://roamresearch.com/#/app/akamatsulab/page/LvWgoTa3v) is working on a learned correction. Treat Mem3DG curvature/force outputs as approximate; cross-check against analytical cases (sphere, dumbbell, biconcave, see [Mem3DG validation suite](https://roamresearch.com/#/app/akamatsulab/page/9V7miyabT)).
- **Output sizes.** The `.nc` trajectory files grow fast; [tracked as a perf concern](https://roamresearch.com/#/app/AllenCell/page/PFb0U9ayr).
- **Title formats are load-bearing for the discourse graph.** Any RES/EVD/HYP/ISS created by the simulation pipeline must follow the regex exactly (`[[TYPE]] - … - [[@source]]` for RES/EVD, `[[TYPE]] - …` for HYP/ISS/CLM/CON; `@{topic}/{name}` for experiment sources). See the matsulab [Respect node title formats](https://roamresearch.com/#/app/akamatsulab/page/tU5grj6b6) rule.

---

## 7. Suggested execution order

Drawing on the [two-phase plan](https://roamresearch.com/#/app/AllenCell/page/-qj0iiZaL) and the [boundary staircase](https://roamresearch.com/#/app/akamatsulab/page/atopa65LI):

1. **Reproduce existing micropub** on the HPC ([Phase 0](https://roamresearch.com/#/app/AllenCell/page/3U_A4wafx)) — verifies the pipeline works before introducing the membrane. ([Open question Apr 27 2026](https://roamresearch.com/#/app/AllenCell/page/1ggBxD4gf) on whether this is done.)
2. **Single filament against fixed boundary in ReaDDy** — confirm the localized binding pocket (§3.1.1) produces sensible polymerization kinetics; measure F-V at fixed displacement constraint. Match Peskin 1993 closed form.
3. **Add k_off** (§3.1.2). Verify symmetry-breaking conditions from van Oudenaarden 1999.
4. **Multiple filaments against fixed boundary.** Check whether Inoue 2015 concave↔convex transition emerges at fixed rate; if not, the rate-tuned transition is the membrane-flexibility's job.
5. **Movable rigid boundary** — momentum/displacement coupling test.
6. **Mem3DG flexible boundary** — the headline run. Sweep polymerization rate, sweep filament count, sweep membrane tension and bending rigidity. Compare F-V to Inoue 2015 directly.
7. **Surface-attached monomers** (§3.1.5) — Mullins 2024 prediction; run with/without surface clustering, sweep bulk [actin].
8. **Force-dependent capping + tethering** (§3.1.3, 3.1.4) — add only if the simpler hypotheses are clean; otherwise leave for a follow-up micropub.

Each step should generate at least one `[[RES]]` node and trace back to the HYP it tests.

---

## 8. What the agent should *not* do

- **Don't propose new node types or rename existing ones.** The Roam discourse-graph plugin identifies nodes by title regex; malformed titles silently break the system. ([matsulab rule](https://roamresearch.com/#/app/akamatsulab/page/tU5grj6b6).)
- **Don't write into Roam unless instructed.** Both graphs are default-read-only for assistants ([matsulab rule](https://roamresearch.com/#/app/akamatsulab/page/Y4gtP3noo)). Generate RES/CON candidates as drafts the team can promote.
- **Don't pick a new theoretical anchor.** The seven literature sources in §1.3 plus Inoue 2015 are the canonical set; if a candidate paper appears to compete, surface it as a `[[QUE]]` or `#clm-candidate` and let the lab decide.
- **Don't optimize prematurely.** Stage 1–4 in §7 will reveal whether the headline question even requires the full Mem3DG stack; do not invest in interop until the simpler cases are clean.
- **Don't claim the Brownian ratchet is recapitulated from a single qualitative agreement.** The graph already lists three distinct hypotheses (§1.1) — at minimum, all three need an answer (support, oppose, or "doesn't bear on").

---

## 9. Quick reference: top-priority Roam links for the agent

- Project page: [Project/Subcellular membrane modeling (allencell)](https://roamresearch.com/#/app/AllenCell/page/E6wmMvMN2)
- Target QUE: [How do forces from the plasma membrane influence actin's force-velocity relationship?](https://roamresearch.com/#/app/AllenCell/page/SLxU3WIZx)
- Headline HYP: [Flexible responsive membrane is necessary…](https://roamresearch.com/#/app/AllenCell/page/ukyHwGk7Q)
- Target benchmark EVD: [Inoue 2015 concave/convex F-V](https://roamresearch.com/#/app/AllenCell/page/wewHzder2)
- Canonical scoping meeting: [Jan 8 2025](https://roamresearch.com/#/app/akamatsulab/page/pBIl12BA8)
- Roadmap: [Two-phase plan](https://roamresearch.com/#/app/AllenCell/page/1yBARa_PT)
- Anchor paper: [@inoue2015brownian](https://roamresearch.com/#/app/AllenCell/page/1F9Kae_19)
- Anchor paper: [@mullins2024actin](https://roamresearch.com/#/app/akamatsulab/page/6C5ZWODa-)
- Anchor paper: [@peskin1993cellular](https://roamresearch.com/#/app/akamatsulab/page/sbRlxhJus) / [@mogilner1996cell](https://roamresearch.com/#/app/akamatsulab/page/CYLny_qZG) / [@mogilner2003force](https://roamresearch.com/#/app/akamatsulab/page/98nqHgl7E)
- Pipeline repo: [`simularium/subcell-pipeline`](https://github.com/simularium/subcell-pipeline)
- Subcellular modeling working meetings: [github discussions](https://github.com/jessicasyu/subcellular_modeling/discussions)
