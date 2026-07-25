import json, sys, traceback
try:
    from pbg_membrane_actin_composite.core import build_core
    from process_bigraph import Composite, gather_emitter_results
    from process_bigraph.emitter import SQLiteEmitter
    from viva_superpowers.composite_generator import (
        _REGISTRY, build_generator, discover_generators,
    )
    from vivarium_dashboard.lib import composite_runs as cr
    from bigraph_schema.json_codec import BigraphJSONEncoder as _BJE
    _payload = {'spec_id': 'pbg_membrane_actin_composite.composites.rung3_flexible_mem3dg_boundary', 'overrides': {'force_constant': 2.0}, 'run_id': 'pbg_membrane_actin_composite.composites.rung3_flexible_mem3dg_boundary__1779244289__adb232', 'db_file': '/Users/eranagmon/code/pbg-membrane-actin-composite/studies/actin-to-membrane-force-handshake/runs.db', 'steps': 5, 'emit_paths': []}
    if not _REGISTRY: discover_generators()
    entry = _REGISTRY[_payload['spec_id']]
    core = build_core()
    core.register_link('SQLiteEmitter', SQLiteEmitter)
    doc = build_generator(entry, overrides=_payload['overrides'])
    state = doc.get('state', doc) if isinstance(doc, dict) else doc
    if _payload.get('emit_paths'):
        state = cr.inject_emitter_for_paths(state, _payload['emit_paths'])
    state = cr.inject_sqlite_emitter(
        state, run_id=_payload['run_id'], db_file=_payload['db_file'])
    composite = Composite({'state': state}, core=core)
    composite.run(_payload['steps'])
    results = gather_emitter_results(composite)

    # Flatten tuple keys to JSON-friendly dotted strings
    out = {}
    for path_tuple, entries in results.items():
        key = '.'.join(str(p) for p in path_tuple)
        out[key] = entries
    # Gather rendered viz HTML, if viva_superpowers is importable.
    viz_html = {}
    try:
        from viva_superpowers.visualization import render_results
        rendered = render_results(composite)
        for path_tuple, payload in rendered.items():
            key = '.'.join(str(p) for p in path_tuple)
            viz_html[key] = payload
    except Exception:
        viz_html = {}
    from bigraph_schema.json_codec import BigraphJSONEncoder as _BJE
    print('@@@RESULTS@@@')
    print(json.dumps({'results': out, 'viz_html': viz_html}, cls=_BJE))
except Exception as e:
    print('@@@ERROR@@@')
    print(traceback.format_exc())
