"""Connection table for the membrane-actin composite.

Encodes every cross-process wire as a (producer-port, consumer-port) pair.
Read this file to understand which schema reconciles with which without
having to spelunk the wrappers' inputs() / outputs() definitions.

Per the pbg-superpowers /pbg-expert composite-mode rules, each row is one
of: pass-through (same schema, direct wire), adapter (Step that translates
between mismatched schemas), stub (a placeholder source for a missing
input), or sink (output with no consumer, routed to the emitter only).
"""

# Each entry: (producer_class.port, consumer_class.port, kind, store_path).
# Stores at composite root use the structure:
#   {
#     "actin": {...},                # ReaDDyProcess emits here
#     "membrane": {...},             # Mem3DGProcess emits here
#     "coupling": {...},             # BrownianRatchetCoupler emits here
#     "control": {...},              # back-channel into the simulators
#   }
WIRING = [
    # ReaDDy -> Coupler
    {
        'producer': 'ReaDDyProcess.positions',
        'consumer': 'BrownianRatchetCoupler.actin_positions',
        'kind': 'pass-through',
        'store': ['actin', 'positions'],
    },
    # Mem3DG -> Coupler
    {
        'producer': 'Mem3DGProcess.vertex_positions',
        'consumer': 'BrownianRatchetCoupler.membrane_vertices',
        'kind': 'pass-through',
        'store': ['membrane', 'vertex_positions'],
    },
    # Coupler -> ReaDDy (closed loop: membrane lifts -> wall lifts -> actin
    # gets a fresh slot to push into).
    {
        'producer': 'BrownianRatchetCoupler.wall_z',
        'consumer': 'ReaDDyProcess.wall_z',
        'kind': 'pass-through',
        'store': ['control', 'wall_z'],
    },
    # Coupler -> Mem3DG (closed loop: actin pushes -> coupler raises
    # osmotic strength -> membrane bulges away).
    {
        'producer': 'BrownianRatchetCoupler.osmotic_strength_offset',
        'consumer': 'Mem3DGProcess.osmotic_strength_offset',
        'kind': 'pass-through',
        'store': ['control', 'osmotic_strength_offset'],
    },
    # Diagnostic outputs from the coupler — sinks routed through the
    # emitter so the demo can plot them.
    {
        'producer': 'BrownianRatchetCoupler.contact_force',
        'consumer': '<emitter>',
        'kind': 'sink',
        'store': ['coupling', 'contact_force'],
    },
    {
        'producer': 'BrownianRatchetCoupler.actin_max_z',
        'consumer': '<emitter>',
        'kind': 'sink',
        'store': ['coupling', 'actin_max_z'],
    },
    {
        'producer': 'BrownianRatchetCoupler.membrane_min_z',
        'consumer': '<emitter>',
        'kind': 'sink',
        'store': ['coupling', 'membrane_min_z'],
    },
    {
        'producer': 'BrownianRatchetCoupler.gap',
        'consumer': '<emitter>',
        'kind': 'sink',
        'store': ['coupling', 'gap'],
    },
    {
        'producer': 'BrownianRatchetCoupler.ratchet_steps',
        'consumer': '<emitter>',
        'kind': 'sink',
        'store': ['coupling', 'ratchet_steps'],
    },
]
