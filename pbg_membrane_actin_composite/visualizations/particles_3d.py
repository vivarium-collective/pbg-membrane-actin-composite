"""Three.js viewer showing the actual simulation objects in 3D:

  * membrane vertices (Mem3DG mesh as a point cloud — faces not yet
    emitted by the workspace's pipeline, so we render vertices only),
  * actin particle positions (ReaDDy point cloud),
  * a translucent barrier plane (rungs 1/2) or sphere (rung 3) sitting
    at `barrier_z`.

Per-frame data is delivered as ``list[list[float]]`` per object (frames ×
flattened-xyz). The dashboard's auto-renderer passes the full per-run
series unchanged because the declared input type isn't in its dispatch
table — falls through to ``per_run_values[0]``. We coerce defensively.

Animated through the run with a play/pause button and a frame slider in
the HUD, like ``SchematicVesicle3D``.
"""
from __future__ import annotations

import json
from typing import Any

from pbg_superpowers.visualization import Visualization
from pbg_membrane_actin_composite.visualizations._plotly_helpers import _autosize_script


_THREE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
_ORBIT_CDN = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/controls/OrbitControls.js"


def _coerce_positions_series(value: Any) -> list[list[list[float]]]:
    """Normalize positions input to list[frames][points][3].

    Handles three shapes:
      - None → []
      - list[points][3] (single frame) → [single-frame]
      - list[frames][points][3] → pass-through
      - list[runs][frames][points][3] (multi-run) → take latest run
    """
    if not isinstance(value, list) or not value:
        return []
    # If first element is a coord list (length 3 of numbers), single frame.
    first = value[0]
    if isinstance(first, list) and first and not isinstance(first[0], list):
        # single frame: list[points][3]
        return [_coerce_frame(value)]
    if isinstance(first, list) and first and isinstance(first[0], list):
        second = first[0]
        if second and isinstance(second[0], list):
            # multi-run: list[runs][frames][points][3] — take last run
            return _coerce_frames_series(value[-1])
        # frames × points × 3
        return _coerce_frames_series(value)
    return []


def _coerce_frame(frame: Any) -> list[list[float]]:
    if not isinstance(frame, list):
        return []
    out = []
    for p in frame:
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            try:
                out.append([float(p[0]), float(p[1]), float(p[2])])
            except (TypeError, ValueError):
                continue
    return out


def _coerce_frames_series(frames: Any) -> list[list[list[float]]]:
    if not isinstance(frames, list):
        return []
    return [_coerce_frame(f) for f in frames]


def _coerce_scalars(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, list):
        if value and isinstance(value[0], list):
            # multi-run nested; take last
            inner = value[-1]
            return [float(x) if x is not None else 0.0 for x in inner]
        return [float(x) if x is not None else 0.0 for x in value]
    try:
        return [float(value)]
    except (TypeError, ValueError):
        return []


class Particles3D(Visualization):
    """Real-data 3D point cloud: actin + membrane vertices + barrier."""

    config_schema = {
        'title': {'_type': 'string', '_default': 'Particles in 3D — actin · membrane · barrier'},
        'accent': {'_type': 'string', '_default': '#10b981'},
        'frame_delay_ms': {'_type': 'integer', '_default': 600},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actin_frames: list[list[list[float]]] = []
        self.membrane_frames: list[list[list[float]]] = []
        self.barrier_z: list[float] = []
        self.times: list[float] = []

    def inputs(self):
        # 'list[list[float]]' is the dashboard-aware "nested" type. The
        # auto-renderer assigns `per_run_values` (list-of-runs, each a
        # list of per-frame values) to such ports; for a single run our
        # per-frame value is itself list[points][3], so we end up with
        # list[runs][frames][points][3]. _coerce_positions_series walks
        # whichever depth comes through.
        return {
            'time': 'list[float]',
            'actin_positions': 'list[list[float]]',
            'membrane_vertex_positions': 'list[list[float]]',
            'barrier_z': 'list[float]',
        }

    def update(self, state, interval=1.0):
        self.times = _coerce_scalars(state.get('time'))
        self.actin_frames = _coerce_positions_series(state.get('actin_positions'))
        self.membrane_frames = _coerce_positions_series(state.get('membrane_vertex_positions'))
        self.barrier_z = _coerce_scalars(state.get('barrier_z'))

        # Align lengths defensively.
        n = max(len(self.times), len(self.actin_frames),
                len(self.membrane_frames), len(self.barrier_z))
        # If only a single-frame snapshot reached us, treat it as t=0 only.
        if n == 0:
            return {'html': '<p>Particles3D: no data</p>'}
        while len(self.times) < n:
            self.times.append(len(self.times) * (interval or 1.0))
        while len(self.actin_frames) < n:
            self.actin_frames.append([])
        while len(self.membrane_frames) < n:
            self.membrane_frames.append([])
        while len(self.barrier_z) < n:
            self.barrier_z.append(0.0)

        cfg = self.config or {}
        accent = cfg.get('accent', '#10b981')
        title = cfg.get('title', 'Particles in 3D')
        frame_delay = int(cfg.get('frame_delay_ms', 600))
        div_id = f'particles-3d-{id(self)}'

        frames = json.dumps([
            {
                "t": t,
                "actin": a,
                "membrane": m,
                "bz": bz,
            }
            for t, a, m, bz in zip(
                self.times, self.actin_frames,
                self.membrane_frames, self.barrier_z,
            )
        ])

        accent_bar = (
            f'<div style="height:3px;background:{accent};margin-bottom:6px;'
            f'border-radius:2px"></div>'
        )

        js = """
(function() {
  const FRAMES = __FRAMES__;
  const ACCENT = "__ACCENT__";
  const FRAME_DELAY = __FRAME_DELAY__;
  const containerId = "__DIV_ID__";

  function init() {
    const container = document.getElementById(containerId);
    if (!container || !window.THREE) { setTimeout(init, 50); return; }
    const w = container.clientWidth || 600;
    const h = 460;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fafc);

    // Auto-fit camera by finding the data bounding box on frame 0.
    function bounds() {
      let xs = [], ys = [], zs = [];
      for (const f of FRAMES) {
        for (const p of (f.actin || [])) { xs.push(p[0]); ys.push(p[1]); zs.push(p[2]); }
        for (const p of (f.membrane || [])) { xs.push(p[0]); ys.push(p[1]); zs.push(p[2]); }
      }
      if (!xs.length) return { cx:0, cy:0, cz:0, r:2 };
      const minX=Math.min(...xs), maxX=Math.max(...xs);
      const minY=Math.min(...ys), maxY=Math.max(...ys);
      const minZ=Math.min(...zs), maxZ=Math.max(...zs);
      return {
        cx: (minX+maxX)/2, cy: (minY+maxY)/2, cz: (minZ+maxZ)/2,
        r: Math.max(maxX-minX, maxY-minY, maxZ-minZ, 1) * 0.65,
      };
    }
    const b = bounds();

    const camera = new THREE.PerspectiveCamera(40, w / h, 0.01, 200);
    camera.position.set(b.cx + b.r * 2.4, b.cy + b.r * 1.6, b.cz + b.r * 2.4);
    camera.lookAt(b.cx, b.cy, b.cz);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(w, h);
    container.insertBefore(renderer.domElement, container.firstChild);

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const key = new THREE.DirectionalLight(0xffffff, 0.6);
    key.position.set(5, 7, 4); scene.add(key);

    // Floor grid at the data's min-Y.
    const grid = new THREE.GridHelper(b.r * 4, 12, 0xd1d5db, 0xe5e7eb);
    grid.material.transparent = true; grid.material.opacity = 0.4;
    grid.position.set(b.cx, b.cy - b.r * 1.2, b.cz);
    scene.add(grid);

    // Axis cue at the center.
    const axes = new THREE.AxesHelper(b.r * 0.4);
    axes.position.set(b.cx, b.cy, b.cz);
    scene.add(axes);

    // Membrane point cloud (indigo).
    const memMat = new THREE.PointsMaterial({
      color: 0x6366f1, size: 0.10, sizeAttenuation: true,
      transparent: true, opacity: 0.85,
    });
    let memPts = null;
    function setMembrane(coords) {
      const arr = new Float32Array(coords.length * 3);
      for (let i = 0; i < coords.length; i++) {
        arr[i*3] = coords[i][0]; arr[i*3+1] = coords[i][1]; arr[i*3+2] = coords[i][2];
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(arr, 3));
      if (memPts) { scene.remove(memPts); memPts.geometry.dispose(); }
      memPts = new THREE.Points(g, memMat); scene.add(memPts);
    }

    // Actin particles (accent-colored, larger size).
    const actinMat = new THREE.PointsMaterial({
      color: new THREE.Color(ACCENT), size: 0.16, sizeAttenuation: true,
      transparent: true, opacity: 0.95,
    });
    let actinPts = null;
    function setActin(coords) {
      const arr = new Float32Array(coords.length * 3);
      for (let i = 0; i < coords.length; i++) {
        arr[i*3] = coords[i][0]; arr[i*3+1] = coords[i][1]; arr[i*3+2] = coords[i][2];
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(arr, 3));
      if (actinPts) { scene.remove(actinPts); actinPts.geometry.dispose(); }
      actinPts = new THREE.Points(g, actinMat); scene.add(actinPts);
    }

    // Barrier — translucent disk at barrier_z (planar rungs).
    const barrierGeom = new THREE.CircleGeometry(b.r * 1.4, 32);
    const barrierMat = new THREE.MeshBasicMaterial({
      color: 0xdc2626, transparent: true, opacity: 0.18,
      side: THREE.DoubleSide,
    });
    const barrier = new THREE.Mesh(barrierGeom, barrierMat);
    barrier.rotation.x = Math.PI / 2;
    scene.add(barrier);

    // HUD + controls.
    container.style.position = "relative";
    const hud = document.createElement("div");
    hud.style.cssText = "position:absolute;top:8px;left:12px;background:rgba(255,255,255,0.85);"
      + "padding:4px 10px;border-radius:4px;font:12px/1.2 'Inter', sans-serif;color:#1f2937;";
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
    slider.type = "range"; slider.min = 0; slider.max = FRAMES.length - 1;
    slider.value = 0; slider.style.cssText = "flex:1;";
    const label = document.createElement("span");
    label.textContent = "0 / " + (FRAMES.length - 1);
    ctrls.appendChild(btn); ctrls.appendChild(slider); ctrls.appendChild(label);
    container.appendChild(ctrls);

    let frame = 0, playing = true, lastStep = performance.now();

    function applyFrame(i) {
      if (i < 0 || i >= FRAMES.length) return;
      const f = FRAMES[i];
      if ((f.actin || []).length) setActin(f.actin);
      if ((f.membrane || []).length) setMembrane(f.membrane);
      barrier.position.set(b.cx, f.bz, b.cz);
      hud.textContent = "t = " + f.t.toFixed(2)
        + "    actin: " + (f.actin || []).length
        + "    membrane: " + (f.membrane || []).length
        + "    barrier_z: " + f.bz.toFixed(2);
    }

    btn.onclick = function() {
      playing = !playing;
      btn.textContent = playing ? "⏸" : "▶";
    };
    slider.oninput = function() {
      playing = false; btn.textContent = "▶";
      frame = parseInt(slider.value);
      applyFrame(frame);
      label.textContent = frame + " / " + (FRAMES.length - 1);
    };

    let orbit = null;
    if (THREE.OrbitControls) {
      orbit = new THREE.OrbitControls(camera, renderer.domElement);
      orbit.target.set(b.cx, b.cy, b.cz);
      orbit.enableDamping = true; orbit.dampingFactor = 0.08;
    }

    function tick(now) {
      if (playing && now - lastStep >= FRAME_DELAY) {
        frame = (frame + 1) % FRAMES.length;
        slider.value = frame;
        label.textContent = frame + " / " + (FRAMES.length - 1);
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
              .replace("__FRAMES__", frames)
              .replace("__ACCENT__", accent)
              .replace("__FRAME_DELAY__", str(frame_delay))
              .replace("__DIV_ID__", div_id)
              .replace("__THREE_CDN__", _THREE_CDN)
              .replace("__ORBIT_CDN__", _ORBIT_CDN))

        html = (
            f'{accent_bar}'
            f'<div style="font:600 14px/1.3 \'Inter\',sans-serif;color:#1f2937;'
            f'margin:4px 0 8px 0">{title}</div>'
            f'<div id="{div_id}" style="height:460px;background:#f8fafc;'
            f'border-radius:8px;position:relative;overflow:hidden"></div>'
            f'<script>{js}</script>'
        )
        return {'html': html + _autosize_script(460)}
