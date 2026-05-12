"""Composite document factories for the membrane-actin Brownian ratchet.

`build_document(...)` returns a process-bigraph Composite document wiring
ReaDDyProcess + Mem3DGProcess + BrownianRatchetCoupler per `wiring.py`,
plus an RAMEmitter that snapshots all coupling diagnostics.
"""

from __future__ import annotations

# pbg-readdy + pbg-mem3dg are auto-discovered by allocate_core() through
# bigraph_schema.package.discover — no explicit import or register_link
# needed here. Their classes are referenced by the document's `address`
# fields ("local:ReaDDyProcess", "local:Mem3DGProcess").


# Default ReaDDy actin scenario: a band of monomers near the bottom of the
# box, with a fusion reaction G + G -> F representing actin polymerization.
def _planar_actin_config(box_size=(4.0, 4.0, 4.0), n_filaments=6,
                         monomers_per_filament=5, growth_rate=4.0,
                         barrier_z=0.0):
    """Bonded actin filaments below a planar barrier, growing upward.

    Filaments are stacked vertically with their HEADS placed close to the
    barrier (within ~0.3 of barrier_z) so the head Brownian fluctuations
    actually probe the contact zone within demo runtime — without true
    polymerization growth (which would require ReaDDy spatial topology
    reactions, deferred to v0.2), the heads just bend / diffuse against
    the barrier rather than extending.

    Inspired by the multiscale-actin layout: filaments distributed on a
    grid in the xy plane, all oriented along +z, with the barrier
    perpendicular to the filament axis.
    """
    bond_length = 0.4
    spacing = 0.8
    grid_side = max(1, int(round(n_filaments ** 0.5)))
    initial_topologies = []
    for i in range(n_filaments):
        gx = (i % grid_side) - (grid_side - 1) / 2.0
        gy = (i // grid_side) - (grid_side - 1) / 2.0
        x = gx * spacing
        y = gy * spacing
        # Top monomer (filament head) sits at barrier_z - small gap.
        head_z = barrier_z - 0.3
        positions = [
            [float(x), float(y), float(head_z - (monomers_per_filament - 1 - k) * bond_length)]
            for k in range(monomers_per_filament)
        ]
        initial_topologies.append({
            'type': 'filament',
            'particle_types': ['F'] * monomers_per_filament,
            'positions': positions,
        })

    # Free G monomers — bath that supplies polymerization (in a future
    # version with topology reactions wired in). For now they're just
    # diffusing background.
    half = [s / 2.0 for s in box_size]
    n_g = max(2, int(growth_rate * 2))
    g_initial = [
        [float(((i % 4) - 1.5) * 0.4),
         float(((i // 4) % 4 - 1.5) * 0.4),
         float(-half[2] + 0.2 + 0.15 * (i // 16))]
        for i in range(n_g)
    ]

    return _actin_config_common(box_size, g_initial, initial_topologies, bond_length)


def _spherical_actin_config(box_size=(8.0, 8.0, 8.0),
                            vesicle_radius=2.0,
                            n_filaments=8,
                            monomers_per_filament=5,
                            growth_rate=4.0):
    """Bonded actin filaments INSIDE a vesicle, oriented radially outward
    from the origin. Used by the spherical (icosphere vesicle) scenarios:
    each filament is a short bonded chain whose tail is near the origin
    and whose head points outward. As they grow / diffuse, the heads
    push against the inner surface of the membrane sphere.
    """
    bond_length = 0.4
    initial_topologies = []
    # Distribute filament directions roughly uniformly on a sphere via a
    # simple golden-ratio Fibonacci point set.
    import math
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(n_filaments):
        # Fibonacci sphere points (unit vectors).
        y = 1 - (i + 0.5) * (2.0 / n_filaments)  # in (-1, 1)
        r_xy = math.sqrt(max(0.0, 1 - y * y))
        theta = i * golden
        ux = math.cos(theta) * r_xy
        uy = y
        uz = math.sin(theta) * r_xy

        # Tail near origin, head pointing outward; chain length stays well
        # inside the vesicle so the filament can grow into the membrane.
        base_r = 0.2
        positions = [
            [float((base_r + k * bond_length) * ux),
             float((base_r + k * bond_length) * uy),
             float((base_r + k * bond_length) * uz)]
            for k in range(monomers_per_filament)
        ]
        initial_topologies.append({
            'type': 'filament',
            'particle_types': ['F'] * monomers_per_filament,
            'positions': positions,
        })

    # A handful of free G monomers also inside the vesicle.
    n_g = max(2, int(growth_rate * 2))
    g_initial = []
    for i in range(n_g):
        # Place near origin, jittered.
        gx = ((i % 4) - 1.5) * 0.3
        gy = ((i // 4 % 4) - 1.5) * 0.3
        gz = ((i // 16) - 0.5) * 0.3
        g_initial.append([float(gx), float(gy), float(gz)])

    return _actin_config_common(box_size, g_initial, initial_topologies, bond_length)


def _actin_config_common(box_size, g_initial, initial_topologies, bond_length):
    """Shared ReaDDy config — species, reactions, potentials, topology
    templates — across both planar and spherical actin layouts."""
    return {
        'box_size': box_size,
        'periodic': (False, False, False),
        'species': {'G': 0.5},
        'reactions': [],
        'potentials': [
            {'type': 'harmonic_repulsion', 'species1': 'G', 'species2': 'G',
             'force_constant': 10.0, 'interaction_distance': 0.4},
        ],
        'initial_particles': {'G': g_initial},
        # Bonded filaments — harmonic bonds + angle potential at ~180°.
        'topology_species': {'F': 0.05},
        'topology_types': ['filament'],
        'topology_bonds': [
            {'type1': 'F', 'type2': 'F',
             'force_constant': 200.0, 'length': bond_length},
        ],
        'topology_angles': [
            {'type1': 'F', 'type2': 'F', 'type3': 'F',
             'force_constant': 30.0, 'equilibrium_angle': 3.14159},
        ],
        'initial_topologies': initial_topologies,
        'timestep': 0.005,
        'observe_stride': 10,
    }


# Backwards-compatible default — used when the caller doesn't pass a
# layout to build_document(). Equivalent to the planar layout.
def _default_actin_config(box_size=(8.0, 8.0, 8.0), n_filaments=6,
                          monomers_per_filament=5, growth_rate=4.0):
    return _planar_actin_config(box_size, n_filaments, monomers_per_filament,
                                growth_rate)


def _vesicle_membrane_config(radius=2.0, subdivision=2):
    """Closed icosphere vesicle using the *constant pressure* osmotic
    model. With this model, a positive `osmotic_strength_offset` from
    the coupler adds to the constant pressure → an outward force on
    every vertex → the vesicle inflates. The preferredVolume model
    converges to a setpoint and so cannot represent runaway inflation,
    which is why we don't use it here.

    Surface tension is intentionally STIFF (tension_modulus=1.0,
    preferred_area_scale=1.0) so the membrane provides a real
    counter-force to the added pressure. Without a preferred-volume
    setpoint, only tension prevents runaway inflation; soft tension
    lets even a tiny pressure offset blow the mesh out to infinity.
    """
    return {
        'mesh_type': 'icosphere',
        'radius': radius,
        'subdivision': subdivision,
        'characteristic_timestep': 0.5,
        'tolerance': 1e-9,
        'osmotic_model': 'constant',
        'osmotic_pressure': 0.0,
        'tension_modulus': 1.0,        # stiff — bounds the inflation
        'preferred_area_scale': 1.0,   # tension restores toward initial area
    }


def _hexagon_membrane_config(radius=2.0, subdivision=2, barrier_initial_z=0.5):
    """Flat hexagonal membrane patch — used by the staircase's flexible
    rung. The patch sits at z=`barrier_initial_z` initially and bulges
    upward when osmotic_strength_offset (driven by the coupler) is
    positive. The constant-pressure osmotic model applies a force normal
    to each face, which on an upward-facing flat sheet pushes vertices
    in +z — exactly the response the spec's HYP #1 requires."""
    return {
        'mesh_type': 'hexagon',
        'radius': radius,
        'subdivision': subdivision,
        'characteristic_timestep': 0.5,
        'tolerance': 1e-9,
        'osmotic_model': 'constant',
        'osmotic_pressure': 0.0,
        # Stiff tension to bound out-of-plane bulging — without a
        # preferred-volume setpoint, only tension prevents runaway flap.
        'tension_modulus': 1.0,
        'preferred_area_scale': 1.0,
    }


# Back-compat alias — the legacy build_document caller sees the vesicle.
def _default_membrane_config(radius=2.0, subdivision=2):
    return _vesicle_membrane_config(radius, subdivision)


def build_document(
    *,
    interval: float = 0.5,
    closed_loop: bool = True,
    coupling_mode: str = 'planar',           # 'planar' or 'spherical'
    membrane_geometry: str = 'icosphere',     # 'icosphere' or 'hexagon'
    barrier_kind: str = 'flexible',           # 'fixed' | 'rigid_movable' | 'flexible'
    barrier_initial_z: float = 2.5,
    barrier_drag: float = 5.0,
    contact_threshold: float = 0.5,
    force_constant: float = 1.0,
    osmotic_force_scale: float = 0.02,
    growth_rate: float = 4.0,
    n_filaments: int = 6,
    monomers_per_filament: int = 5,
    actin_config_overrides: dict | None = None,
    membrane_config_overrides: dict | None = None,
) -> dict:
    """Build the full membrane-actin Composite document.

    Parameters
    ----------
    interval : float
        Time interval each Process advances per composite step.
    closed_loop : bool
        When False, the coupler computes diagnostics but emits zero
        osmotic_offset and no wall publication — decoupled-baseline scenario.
    coupling_mode : 'planar' | 'spherical'
        'planar': actin pushes UP against a membrane patch, coupler
                  publishes wall_z to ReaDDy.
        'spherical': actin INSIDE a vesicle pushes radially outward,
                  coupler publishes wall_radius to ReaDDy.
    membrane_geometry : 'icosphere' | 'hexagon'
        'icosphere': closed vesicle (works with osmotic-pressure coupling).
        'hexagon': flat patch (osmotic_strength_offset has no effect, so
                   this geometry is intended for decoupled scenarios only).
    contact_threshold, force_constant, osmotic_force_scale : float
        Coupler tunables. See BrownianRatchetCoupler.config_schema.
    growth_rate : float
        Drives the actin pool size (more free G monomers in stressed scenario).
    """
    if membrane_geometry == 'hexagon':
        membrane_cfg = _hexagon_membrane_config()
    else:
        membrane_cfg = _vesicle_membrane_config()
    if membrane_config_overrides:
        membrane_cfg.update(membrane_config_overrides)

    if coupling_mode == 'spherical':
        actin_cfg = _spherical_actin_config(
            n_filaments=n_filaments,
            monomers_per_filament=monomers_per_filament,
            growth_rate=growth_rate)
    else:
        actin_cfg = _planar_actin_config(
            n_filaments=n_filaments,
            monomers_per_filament=monomers_per_filament,
            growth_rate=growth_rate,
            barrier_z=barrier_initial_z)
    if actin_config_overrides:
        actin_cfg.update(actin_config_overrides)

    # Mem3DG instance is included only on the flexible rung — the fixed
    # and rigid_movable rungs of the staircase don't have a deformable
    # membrane (the wall is just a plane the coupler tracks internally).
    include_mem3dg = (barrier_kind == 'flexible')

    doc = {
        'actin_sim': {
            '_type': 'process',
            'address': 'local:ReaDDyProcess',
            'config': actin_cfg,
            'interval': interval,
            'inputs': {
                'wall_z': ['control', 'wall_z'],
                'wall_radius': ['control', 'wall_radius'],
            },
            'outputs': {
                'particle_counts': ['actin', 'particle_counts'],
                'total_particles': ['actin', 'total_particles'],
                'positions': ['actin', 'positions'],
                'energy': ['actin', 'energy'],
                'time': ['actin', 'time'],
            },
        },
        'coupler': {
            '_type': 'process',
            'address': 'local:BrownianRatchetCoupler',
            'config': {
                'closed_loop': closed_loop,
                'coupling_mode': coupling_mode,
                'barrier_kind': barrier_kind,
                'barrier_initial_z': barrier_initial_z,
                'barrier_drag': barrier_drag,
                'contact_threshold': contact_threshold,
                'force_constant': force_constant,
                'osmotic_force_scale': osmotic_force_scale,
            },
            'interval': interval,
            'inputs': {
                'actin_positions': ['actin', 'positions'],
                'membrane_vertices': ['membrane', 'vertex_positions'],
            },
            'outputs': {
                'wall_z': ['control', 'wall_z'],
                'wall_radius': ['control', 'wall_radius'],
                'osmotic_strength_offset': ['control', 'osmotic_strength_offset'],
                'contact_force': ['coupling', 'contact_force'],
                'actin_max_z': ['coupling', 'actin_max_z'],
                'membrane_min_z': ['coupling', 'membrane_min_z'],
                'actin_max_radius': ['coupling', 'actin_max_radius'],
                'membrane_min_radius': ['coupling', 'membrane_min_radius'],
                'gap': ['coupling', 'gap'],
                'barrier_z': ['coupling', 'barrier_z'],
                'barrier_velocity': ['coupling', 'barrier_velocity'],
                'mean_contact_force': ['coupling', 'mean_contact_force'],
                'ratchet_steps': ['coupling', 'ratchet_steps'],
            },
        },
        'control': {
            'wall_z': None,
            'wall_radius': None,
            'osmotic_strength_offset': 0.0,
        },
        'actin': {
            'particle_counts': {},
            'total_particles': 0,
            'positions': [],
            'energy': 0.0,
            'time': 0.0,
        },
        'membrane': {
            'vertex_positions': [],
            'mean_curvatures': [],
            'total_energy': 0.0,
            'bending_energy': 0.0,
            'surface_energy': 0.0,
            'pressure_energy': 0.0,
            'surface_area': 0.0,
            'volume': 0.0,
            'converged': False,
        },
        'coupling': {
            'contact_force': 0.0,
            'actin_max_z': 0.0,
            'membrane_min_z': 0.0,
            'actin_max_radius': 0.0,
            'membrane_min_radius': 0.0,
            'gap': 0.0,
            'barrier_z': barrier_initial_z,
            'barrier_velocity': 0.0,
            'mean_contact_force': 0.0,
            'ratchet_steps': 0,
        },
        'emitter': {
            '_type': 'step',
            'address': 'local:ram-emitter',
            'config': {
                'emit': {
                    'time': 'float',
                    'actin_total': 'integer',
                    'actin_max_z': 'float',
                    'membrane_min_z': 'float',
                    'gap': 'float',
                    'contact_force': 'float',
                    'osmotic_offset': 'float',
                    'wall_z': 'maybe[float]',
                    'wall_radius': 'maybe[float]',
                    'membrane_volume': 'float',
                    'membrane_energy': 'float',
                    'ratchet_steps': 'integer',
                    # Barrier kinematics — published by the coupler every
                    # step so the demo can plot displacement-vs-time and
                    # F-V scatter across the staircase regimes.
                    'barrier_z': 'float',
                    'barrier_velocity': 'float',
                    'mean_contact_force': 'float',
                    # Radial diagnostics — only meaningful in spherical mode
                    # but always emitted for consistent demo plotting.
                    'actin_max_radius': 'float',
                    'membrane_min_radius': 'float',
                    # Per-step real geometry.
                    'actin_positions': 'list',
                    'membrane_vertex_positions': 'list',
                }
            },
            'inputs': {
                'time': ['global_time'],
                'actin_total': ['actin', 'total_particles'],
                'actin_max_z': ['coupling', 'actin_max_z'],
                'membrane_min_z': ['coupling', 'membrane_min_z'],
                'actin_max_radius': ['coupling', 'actin_max_radius'],
                'membrane_min_radius': ['coupling', 'membrane_min_radius'],
                'gap': ['coupling', 'gap'],
                'contact_force': ['coupling', 'contact_force'],
                'osmotic_offset': ['control', 'osmotic_strength_offset'],
                'wall_z': ['control', 'wall_z'],
                'wall_radius': ['control', 'wall_radius'],
                'membrane_volume': ['membrane', 'volume'],
                'membrane_energy': ['membrane', 'total_energy'],
                'barrier_z': ['coupling', 'barrier_z'],
                'barrier_velocity': ['coupling', 'barrier_velocity'],
                'mean_contact_force': ['coupling', 'mean_contact_force'],
                'ratchet_steps': ['coupling', 'ratchet_steps'],
                'actin_positions': ['actin', 'positions'],
                'membrane_vertex_positions': ['membrane', 'vertex_positions'],
            },
        },
    }

    # Insert Mem3DG only on the flexible rung. The other two rungs of
    # the staircase don't have a deformable membrane: the wall is a
    # plane the coupler tracks and publishes from internally.
    if include_mem3dg:
        doc['membrane_sim'] = {
            '_type': 'process',
            'address': 'local:Mem3DGProcess',
            'config': membrane_cfg,
            'interval': interval,
            'inputs': {
                'osmotic_strength_offset': ['control', 'osmotic_strength_offset'],
            },
            'outputs': {
                'vertex_positions': ['membrane', 'vertex_positions'],
                'mean_curvatures': ['membrane', 'mean_curvatures'],
                'total_energy': ['membrane', 'total_energy'],
                'bending_energy': ['membrane', 'bending_energy'],
                'surface_energy': ['membrane', 'surface_energy'],
                'pressure_energy': ['membrane', 'pressure_energy'],
                'surface_area': ['membrane', 'surface_area'],
                'volume': ['membrane', 'volume'],
                'converged': ['membrane', 'converged'],
            },
        }
    return doc
