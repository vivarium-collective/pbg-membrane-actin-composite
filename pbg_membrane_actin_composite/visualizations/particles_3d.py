"""Real-data 3D viewer — ported from the Three.js scene in demo/report.html.

Renders the actual simulation objects, frame by frame:

  * Mem3DG membrane mesh — real triangulated geometry (vertices + faces),
    surface + wireframe + frozen reference shell so deformation is
    visible against a fixed baseline.
  * Actin particles — one sphere per ReaDDy particle at its real position,
    rendered via THREE.InstancedMesh.
  * Wall plane — translucent disk at z = wall_z (planar rungs only).

The dashboard's typed wire truncates 3-level-nested coordinate arrays
(see notes/friction/2026-05-18-3d-viz-and-pr-flow.md §30), so this viz
**bypasses the wire entirely**. The ``update()`` method opens the
study's ``runs.db`` directly, pulls the per-step state for the latest
simulation, calls ``Mem3DGProcess.get_faces()`` for the static
triangulation, and embeds the full position arrays + faces into the
rendered HTML.

Which study's runs.db to read:

  1. ``config.study_slug`` — explicit (recommended in study.yaml).
  2. The most-recently-modified ``runs.db`` under
     ``<workspace>/studies/*/runs.db``. Works for the dashboard's
     sequential render flow (called immediately after a baseline run).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pbg_superpowers.visualization import Visualization
from pbg_membrane_actin_composite.visualizations._plotly_helpers import _autosize_script


_THREE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
_ORBIT_CDN = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/controls/OrbitControls.js"


def _find_runs_db(study_slug: str | None) -> Path | None:
    cwd = Path.cwd()
    if study_slug:
        explicit = cwd / "studies" / study_slug / "runs.db"
        if explicit.is_file():
            return explicit
    candidates = list((cwd / "studies").glob("*/runs.db"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _load_latest_run(db_path: Path) -> tuple[list[dict], str]:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT simulation_id FROM history ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        if not row:
            return [], ""
        sim_id = row[0]
        states = [
            json.loads(blob)
            for (blob,) in conn.execute(
                "SELECT state FROM history WHERE simulation_id=? ORDER BY step",
                (sim_id,),
            )
        ]
        return states, sim_id
    finally:
        conn.close()


def _try_get_faces(states: list[dict]) -> list[list[int]]:
    if not any(s.get("membrane_vertex_positions") for s in states):
        return []
    try:
        from pbg_mem3dg import Mem3DGProcess
        from pbg_membrane_actin_composite.core import build_core
        # Mirrors _vesicle_membrane_config in document.py — same topology.
        cfg = {
            "mesh_type": "icosphere",
            "radius": 2.0,
            "subdivision": 2,
            "Kbc": 8.22e-5,
            "tension_modulus": 0.1,
            "osmotic_strength": 0.02,
            "preferred_volume_fraction": 0.7,
            "characteristic_timestep": 1.0,
        }
        proc = Mem3DGProcess(config=cfg, core=build_core())
        faces = proc.get_faces()
        return [[int(a), int(b), int(c)] for a, b, c in faces]
    except Exception:
        return []


class Particles3D(Visualization):
    """Three.js renderer for the real per-frame simulation state."""

    config_schema = {
        'title': {'_type': 'string', '_default': 'Particles in 3D — actin · membrane · wall'},
        'accent': {'_type': 'string', '_default': '#10b981'},
        'frame_delay_ms': {'_type': 'integer', '_default': 600},
        'study_slug': {'_type': 'string', '_default': ''},
    }

    def inputs(self):
        # Empty — we read data directly from runs.db, bypassing the
        # dashboard's typed wire (which truncates list[list[float]]
        # of length-3 inner lists; see friction log #4 §30).
        return {}

    def update(self, state, interval=1.0):
        cfg = self.config or {}
        slug = (cfg.get('study_slug') or '').strip() or None
        db = _find_runs_db(slug)
        if db is None:
            return {'html': '<p style="color:#991b1b">Particles3D: no runs.db found under studies/*/</p>'}
        states, sim_id = _load_latest_run(db)
        if not states:
            return {'html': f'<p style="color:#991b1b">Particles3D: no history in {db.name}</p>'}

        faces = _try_get_faces(states)
        frames = []
        for s in states:
            frames.append({
                "t": float(s.get("time") or 0.0),
                "actin": s.get("actin_positions") or [],
                "membrane": s.get("membrane_vertex_positions") or [],
                "wall_z": s.get("wall_z"),
                "barrier_z": float(s.get("barrier_z") or 0.0),
            })

        accent = cfg.get('accent', '#10b981')
        title = cfg.get('title', 'Particles in 3D')
        frame_delay = int(cfg.get('frame_delay_ms', 600))
        div_id = f'particles-3d-{id(self)}'
        source_line = (
            f'<div style="font-size:11px;color:#6b7280;margin-top:2px">'
            f'source: {db.parent.name}/runs.db · simulation_id …{sim_id[-12:]} · '
            f'{len(frames)} frames · {len(faces)} faces</div>'
        )

        payload = json.dumps({"frames": frames, "faces": faces})

        accent_bar = (
            f'<div style="height:3px;background:{accent};margin-bottom:6px;'
            f'border-radius:2px"></div>'
        )

        js = """
(function() {
  const DATA = __PAYLOAD__;
  const ACCENT = "__ACCENT__";
  const FRAME_DELAY = __FRAME_DELAY__;
  const containerId = "__DIV_ID__";

  function init() {
    const container = document.getElementById(containerId);
    if (!container || !window.THREE) { setTimeout(init, 50); return; }
    const w = container.clientWidth || 600, h = 460;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fafc);

    function bounds() {
      let xs=[], ys=[], zs=[];
      for (const f of DATA.frames) {
        for (const p of (f.actin||[]))    { xs.push(p[0]); ys.push(p[1]); zs.push(p[2]); }
        for (const p of (f.membrane||[])) { xs.push(p[0]); ys.push(p[1]); zs.push(p[2]); }
      }
      if (!xs.length) return { cx:0,cy:0,cz:0, r:2 };
      const mx=(Math.min(...xs)+Math.max(...xs))/2;
      const my=(Math.min(...ys)+Math.max(...ys))/2;
      const mz=(Math.min(...zs)+Math.max(...zs))/2;
      const r = Math.max(
        Math.max(...xs)-Math.min(...xs),
        Math.max(...ys)-Math.min(...ys),
        Math.max(...zs)-Math.min(...zs), 1) * 0.65;
      return { cx:mx, cy:my, cz:mz, r };
    }
    const b = bounds();

    const camera = new THREE.PerspectiveCamera(40, w/h, 0.01, 200);
    camera.position.set(b.cx + b.r*2.6, b.cy + b.r*1.8, b.cz + b.r*2.6);
    camera.lookAt(b.cx, b.cy, b.cz);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(w, h);
    container.insertBefore(renderer.domElement, container.firstChild);

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 0.85);
    key.position.set(6, 8, 4); scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.3);
    fill.position.set(-4, -2, -3); scene.add(fill);

    const grid = new THREE.GridHelper(b.r*4, 12, 0xd1d5db, 0xe5e7eb);
    grid.material.transparent = true; grid.material.opacity = 0.4;
    grid.position.set(b.cx, b.cy - b.r*1.2, b.cz);
    scene.add(grid);

    function _meshGeom(verts, faces) {
      const g = new THREE.BufferGeometry();
      const pos = new Float32Array(verts.length * 3);
      for (let i=0; i<verts.length; i++) {
        pos[i*3]=verts[i][0]; pos[i*3+1]=verts[i][1]; pos[i*3+2]=verts[i][2];
      }
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      const idx = new Uint32Array(faces.length * 3);
      for (let i=0; i<faces.length; i++) {
        idx[i*3]=faces[i][0]; idx[i*3+1]=faces[i][1]; idx[i*3+2]=faces[i][2];
      }
      g.setIndex(new THREE.BufferAttribute(idx, 1));
      g.computeVertexNormals();
      return g;
    }
    const firstVerts = (function(){for (const f of DATA.frames) if (f.membrane && f.membrane.length) return f.membrane; return null;})();
    let memMesh = null, memWire = null;
    if (firstVerts && DATA.faces && DATA.faces.length) {
      const geom = _meshGeom(firstVerts, DATA.faces);
      memMesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({
        color: 0x6366f1, roughness: 0.45, metalness: 0.1,
        transparent: true, opacity: 0.5, side: THREE.DoubleSide,
      }));
      scene.add(memMesh);
      memWire = new THREE.LineSegments(
        new THREE.WireframeGeometry(geom),
        new THREE.LineBasicMaterial({ color: 0x4338ca, transparent: true, opacity: 0.35 }));
      scene.add(memWire);
      const refGeom = _meshGeom(firstVerts, DATA.faces);
      const refWire = new THREE.LineSegments(
        new THREE.WireframeGeometry(refGeom),
        new THREE.LineBasicMaterial({ color: 0x9ca3af, transparent: true, opacity: 0.3 }));
      scene.add(refWire);
    } else if (firstVerts) {
      // Vertices but no faces — render as point cloud fallback.
      const arr = new Float32Array(firstVerts.length * 3);
      for (let i=0; i<firstVerts.length; i++) {
        arr[i*3]=firstVerts[i][0]; arr[i*3+1]=firstVerts[i][1]; arr[i*3+2]=firstVerts[i][2];
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(arr, 3));
      memMesh = new THREE.Points(g, new THREE.PointsMaterial({
        color: 0x6366f1, size: 0.10, sizeAttenuation: true,
        transparent: true, opacity: 0.85,
      }));
      scene.add(memMesh);
    }

    // Actin particles — InstancedMesh.
    let maxParticles = 0;
    for (const f of DATA.frames)
      if (f.actin && f.actin.length > maxParticles) maxParticles = f.actin.length;
    let particles = null;
    if (maxParticles > 0) {
      const pgeom = new THREE.SphereGeometry(0.12, 8, 6);
      const pmat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(ACCENT), roughness: 0.55, metalness: 0.1,
      });
      particles = new THREE.InstancedMesh(pgeom, pmat, maxParticles);
      particles.count = 0;
      scene.add(particles);
    }

    // Wall plane (rungs 1/2 set wall_z, rung 3 leaves it null).
    const wallGeom = new THREE.PlaneGeometry(b.r*4, b.r*4);
    const wallMat = new THREE.MeshBasicMaterial({
      color: 0xdc2626, transparent: true, opacity: 0.18, side: THREE.DoubleSide,
    });
    const wall = new THREE.Mesh(wallGeom, wallMat);
    wall.rotation.x = Math.PI / 2;
    wall.visible = false;
    scene.add(wall);

    // HUD + controls.
    container.style.position = "relative";
    const hud = document.createElement("div");
    hud.style.cssText = "position:absolute;top:8px;left:12px;background:rgba(255,255,255,0.85);"
      + "padding:4px 10px;border-radius:4px;font:12px/1.2 'Inter',sans-serif;color:#1f2937;";
    container.appendChild(hud);

    const ctrls = document.createElement("div");
    ctrls.style.cssText = "position:absolute;bottom:8px;left:12px;right:12px;"
      + "background:rgba(255,255,255,0.92);padding:6px 10px;border-radius:6px;"
      + "display:flex;gap:10px;align-items:center;font:12px 'Inter',sans-serif;";
    const btn = document.createElement("button");
    btn.textContent = "⏸";
    btn.style.cssText = "padding:2px 10px;cursor:pointer;border:1px solid #d1d5db;"
      + "background:#fff;border-radius:4px;";
    const slider = document.createElement("input");
    slider.type = "range"; slider.min = 0; slider.max = DATA.frames.length - 1;
    slider.value = 0; slider.style.cssText = "flex:1;";
    const label = document.createElement("span");
    label.textContent = "0 / " + (DATA.frames.length - 1);
    ctrls.appendChild(btn); ctrls.appendChild(slider); ctrls.appendChild(label);
    container.appendChild(ctrls);

    function applyFrame(i) {
      const f = DATA.frames[i];
      if (memMesh && memMesh.geometry && memMesh.geometry.attributes
          && memMesh.geometry.attributes.position && f.membrane && f.membrane.length) {
        const attr = memMesh.geometry.attributes.position;
        for (let j = 0; j < f.membrane.length && j*3 < attr.array.length; j++) {
          attr.array[j*3]   = f.membrane[j][0];
          attr.array[j*3+1] = f.membrane[j][1];
          attr.array[j*3+2] = f.membrane[j][2];
        }
        attr.needsUpdate = true;
        if (memMesh.geometry.computeVertexNormals) memMesh.geometry.computeVertexNormals();
        if (memWire) {
          memWire.geometry.dispose();
          memWire.geometry = new THREE.WireframeGeometry(memMesh.geometry);
        }
      }
      if (particles && f.actin) {
        particles.count = Math.min(f.actin.length, maxParticles);
        const m = new THREE.Matrix4();
        for (let j = 0; j < particles.count; j++) {
          const p = f.actin[j];
          m.makeTranslation(p[0], p[1], p[2]);
          particles.setMatrixAt(j, m);
        }
        particles.instanceMatrix.needsUpdate = true;
      }
      if (f.wall_z !== null && f.wall_z !== undefined) {
        wall.visible = true;
        wall.position.set(b.cx, f.wall_z, b.cz);
      } else {
        wall.visible = false;
      }
      hud.textContent = "t = " + f.t.toFixed(2)
        + "    actin: " + ((f.actin||[]).length)
        + "    membrane: " + ((f.membrane||[]).length)
        + (f.wall_z !== null && f.wall_z !== undefined ? "    wall_z: " + f.wall_z.toFixed(2) : "");
    }

    let frame = 0, playing = true, lastStep = performance.now();
    btn.onclick = function() { playing = !playing; btn.textContent = playing ? "⏸" : "▶"; };
    slider.oninput = function() {
      playing = false; btn.textContent = "▶";
      frame = parseInt(slider.value);
      applyFrame(frame);
      label.textContent = frame + " / " + (DATA.frames.length - 1);
    };

    let orbit = null;
    if (THREE.OrbitControls) {
      orbit = new THREE.OrbitControls(camera, renderer.domElement);
      orbit.target.set(b.cx, b.cy, b.cz);
      orbit.enableDamping = true; orbit.dampingFactor = 0.08;
    }

    function tick(now) {
      if (playing && now - lastStep >= FRAME_DELAY) {
        frame = (frame + 1) % DATA.frames.length;
        slider.value = frame;
        label.textContent = frame + " / " + (DATA.frames.length - 1);
        applyFrame(frame);
        lastStep = now;
      }
      if (orbit) orbit.update();
      renderer.render(scene, camera);
      requestAnimationFrame(tick);
    }
    applyFrame(0);
    requestAnimationFrame(tick);
  }

  if (window.THREE) init();
  else {
    const s1 = document.createElement("script");
    s1.src = "__THREE_CDN__";
    s1.onload = function() {
      const s2 = document.createElement("script");
      s2.src = "__ORBIT_CDN__";
      s2.onload = init;
      s2.onerror = init;
      document.head.appendChild(s2);
    };
    document.head.appendChild(s1);
  }
})();
"""
        js = (js
              .replace("__PAYLOAD__", payload)
              .replace("__ACCENT__", accent)
              .replace("__FRAME_DELAY__", str(frame_delay))
              .replace("__DIV_ID__", div_id)
              .replace("__THREE_CDN__", _THREE_CDN)
              .replace("__ORBIT_CDN__", _ORBIT_CDN))

        html = (
            f'{accent_bar}'
            f'<div style="font:600 14px/1.3 \'Inter\',sans-serif;color:#1f2937;'
            f'margin:4px 0 2px 0">{title}</div>'
            f'{source_line}'
            f'<div id="{div_id}" style="height:460px;background:#f8fafc;'
            f'border-radius:8px;position:relative;overflow:hidden;margin-top:8px"></div>'
            f'<script>{js}</script>'
        )
        return {'html': html + _autosize_script(530)}
