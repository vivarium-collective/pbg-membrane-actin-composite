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
def _default_actin_config(box_size=(8.0, 8.0, 8.0), n_filaments=6,
                          monomers_per_filament=5, growth_rate=4.0):
    """Seed actin as N bonded filaments at the box bottom, growing upward.

    Each filament is a true ReaDDy topology — a chain of
    monomers_per_filament F particles bonded by harmonic springs and
    angle potentials, so the chain has bending stiffness. When the head
    pushes against the wall_z barrier, the chain physically bends in
    response (which is the visual the demo wants to convey).

    The `growth_rate` parameter currently scales an attached-monomer pool
    of free G particles whose presence makes the demo's `actin_total`
    metric meaningful, but bonded-filament *growth* (G → adds to chain
    end) requires structural reactions which v0.1 doesn't enable. The
    filaments themselves are static-length but free to deform.
    """
    half = [s / 2.0 for s in box_size]

    # Place filament bases on a small grid in the xy plane near the bottom.
    spacing = 1.2
    grid_side = max(1, int(round(n_filaments ** 0.5)))
    bond_length = 0.5
    initial_topologies = []
    for i in range(n_filaments):
        gx = (i % grid_side) - (grid_side - 1) / 2.0
        gy = (i // grid_side) - (grid_side - 1) / 2.0
        x = gx * spacing
        y = gy * spacing
        # Vertical chain, base near the floor.
        positions = [
            [float(x), float(y), -half[2] + 0.5 + k * bond_length]
            for k in range(monomers_per_filament)
        ]
        initial_topologies.append({
            'type': 'filament',
            'particle_types': ['F'] * monomers_per_filament,
            'positions': positions,
        })

    # Free G monomers floating around the bottom — give the
    # `total_particles` and polymerization-rate metrics in the demo
    # something to track. Their count is scaled by growth_rate so the
    # 'stressed' scenario (2x growth rate) has 2x more free monomers
    # in the bath, broadly approximating an enhanced supply.
    n_g = max(2, int(growth_rate * 2))
    g_initial = [
        [float(((i % 4) - 1.5) * 0.7),
         float(((i // 4) % 4 - 1.5) * 0.7),
         float(-half[2] + 0.3 + 0.2 * (i // 16))]
        for i in range(n_g)
    ]

    return {
        'box_size': box_size,
        'periodic': (False, False, False),
        'species': {'G': 0.5},  # G = free monomer
        'reactions': [],
        'potentials': [
            # Soft repulsion so free monomers don't pile through bonded chains.
            {'type': 'harmonic_repulsion', 'species1': 'G', 'species2': 'G',
             'force_constant': 10.0, 'interaction_distance': 0.4},
        ],
        'initial_particles': {'G': g_initial},
        # Bonded filaments — F particles in topology chains. Harmonic bonds
        # give each filament rod-like behavior; angle potentials around 180°
        # add bending stiffness so the chain prefers to stay straight, but
        # bends visibly when the head is blocked.
        'topology_species': {'F': 0.05},  # very low diffusion — filaments are heavy
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
        'timestep': 0.005,  # tighter timestep — bonded forces are stiffer
        'observe_stride': 10,
    }


def _default_membrane_config(radius=2.0, subdivision=2):
    # Default Mem3DGProcess config tuned for a small icosphere that bulges
    # visibly when the osmotic offset rises. Numerically modest so a single
    # demo step stays under a few seconds.
    return {
        'mesh_type': 'icosphere',
        'radius': radius,
        'subdivision': subdivision,
        'characteristic_timestep': 0.5,
        'tolerance': 1e-9,
        'osmotic_strength': 0.02,
        'preferred_volume_fraction': 0.7,
        'tension_modulus': 0.05,
    }


def build_document(
    *,
    interval: float = 0.5,
    closed_loop: bool = True,
    contact_threshold: float = 0.5,
    force_constant: float = 1.0,
    osmotic_force_scale: float = 0.05,
    growth_rate: float = 4.0,
    actin_config_overrides: dict | None = None,
    membrane_config_overrides: dict | None = None,
) -> dict:
    """Build the full membrane-actin Composite document.

    Parameters
    ----------
    interval : float
        Time interval each Process advances per composite step. Used by
        ReaDDy, Mem3DG, and the coupler so they tick together.
    closed_loop : bool
        When False, the coupler computes diagnostics but emits zero
        osmotic_offset and no wall_z — produces the decoupled-baseline
        scenario for the demo.
    contact_threshold, force_constant, osmotic_force_scale : float
        Coupler tunables. See BrownianRatchetCoupler.config_schema.
    growth_rate : float
        Multiplier on the actin polymerization rate (G + G -> F). Drives
        the stressed scenario in the demo.
    """
    actin_cfg = _default_actin_config(growth_rate=growth_rate)
    if actin_config_overrides:
        actin_cfg.update(actin_config_overrides)
    membrane_cfg = _default_membrane_config()
    if membrane_config_overrides:
        membrane_cfg.update(membrane_config_overrides)

    return {
        'actin_sim': {
            '_type': 'process',
            'address': 'local:ReaDDyProcess',
            'config': actin_cfg,
            'interval': interval,
            'inputs': {
                'wall_z': ['control', 'wall_z'],
            },
            'outputs': {
                'particle_counts': ['actin', 'particle_counts'],
                'total_particles': ['actin', 'total_particles'],
                'positions': ['actin', 'positions'],
                'energy': ['actin', 'energy'],
                'time': ['actin', 'time'],
            },
        },
        'membrane_sim': {
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
        },
        'coupler': {
            '_type': 'process',
            'address': 'local:BrownianRatchetCoupler',
            'config': {
                'closed_loop': closed_loop,
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
                'osmotic_strength_offset': ['control', 'osmotic_strength_offset'],
                'contact_force': ['coupling', 'contact_force'],
                'actin_max_z': ['coupling', 'actin_max_z'],
                'membrane_min_z': ['coupling', 'membrane_min_z'],
                'gap': ['coupling', 'gap'],
                'ratchet_steps': ['coupling', 'ratchet_steps'],
            },
        },
        'control': {
            'wall_z': None,
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
            'gap': 0.0,
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
                    'membrane_volume': 'float',
                    'membrane_energy': 'float',
                    'ratchet_steps': 'integer',
                    # Per-step real geometry — used by the demo report's
                    # Three.js viewer to render the actual mesh deforming
                    # and the actual particles drifting, rather than a
                    # schematic disk and sphere driven by aggregate stats.
                    'actin_positions': 'list',
                    'membrane_vertex_positions': 'list',
                }
            },
            'inputs': {
                'time': ['global_time'],
                'actin_total': ['actin', 'total_particles'],
                'actin_max_z': ['coupling', 'actin_max_z'],
                'membrane_min_z': ['coupling', 'membrane_min_z'],
                'gap': ['coupling', 'gap'],
                'contact_force': ['coupling', 'contact_force'],
                'osmotic_offset': ['control', 'osmotic_strength_offset'],
                'wall_z': ['control', 'wall_z'],
                'membrane_volume': ['membrane', 'volume'],
                'membrane_energy': ['membrane', 'total_energy'],
                'ratchet_steps': ['coupling', 'ratchet_steps'],
                'actin_positions': ['actin', 'positions'],
                'membrane_vertex_positions': ['membrane', 'vertex_positions'],
            },
        },
    }
