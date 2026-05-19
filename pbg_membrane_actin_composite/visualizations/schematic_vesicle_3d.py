"""Schematic 3D viewer — a Three.js scene whose vesicle sphere radius
tracks membrane_volume and whose actin "puck" tracks actin_max_z. Works
on all three rungs from scalar observables alone (no mesh data required).

Ported from the Three.js viewer block in demo/report.html. Animated
through the time series with a play/pause button and a frame slider.
"""
from __future__ import annotations

import json

from pbg_superpowers.visualization import Visualization

from pbg_membrane_actin_composite.visualizations._plotly_helpers import (
    _autosize_script,
    PALETTE, coerce_series,
)


_THREE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
_ORBIT_CDN = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/controls/OrbitControls.js"


class SchematicVesicle3D(Visualization):
    """Schematic 3D vesicle + actin cloud, animated through the run.

    The vesicle radius is set by ``(V / V_0)^(1/3)`` so it inflates
    visibly in rung 3 (volume grows ~12-15% over a run → radius grows
    ~4-5%). The actin "cloud" is a colored disk at z = actin_max_z to
    visualize the polymerizing front pushing up.
    """

    config_schema = {
        'title': {'_type': 'string', '_default': 'Schematic vesicle + actin front'},
        'accent': {'_type': 'string', '_default': '#10b981'},
        'frame_delay_ms': {'_type': 'integer', '_default': 600},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: list[float] = []
        self.volume: list[float] = []
        self.actin_max_z: list[float] = []
        self.contact_force: list[float] = []

    def inputs(self):
        return {'time': 'list[float]', 'membrane_volume': 'list[float]',
                'actin_max_z': 'list[float]', 'contact_force': 'list[float]'}

    def update(self, state, interval=1.0):
        t = coerce_series(state.get('time'))
        v = coerce_series(state.get('membrane_volume'))
        amz = coerce_series(state.get('actin_max_z'))
        cf = coerce_series(state.get('contact_force'))
        if len(t) > 1:
            self.times = t
            self.volume = v if len(v) == len(t) else [1.0] * len(t)
            self.actin_max_z = amz if len(amz) == len(t) else [0.0] * len(t)
            self.contact_force = cf if len(cf) == len(t) else [0.0] * len(t)
        else:
            self.times.append(t[0] if t else len(self.times) * (interval or 1.0))
            self.volume.append(v[0] if v else 1.0)
            self.actin_max_z.append(amz[0] if amz else 0.0)
            self.contact_force.append(cf[0] if cf else 0.0)

        cfg = self.config or {}
        accent = cfg.get('accent', '#10b981')
        title = cfg.get('title', 'Schematic vesicle + actin front')
        frame_delay = int(cfg.get('frame_delay_ms', 600))
        div_id = f'schematic-3d-{id(self)}'

        # Serialize the per-frame data for the JS animation loop.
        # Compute V0 once (first non-zero volume) for the radius scaling.
        v0 = next((x for x in self.volume if x > 0.0), 1.0)
        frames = json.dumps([
            {"t": t, "r": (max(0.01, v) / max(v0, 0.01)) ** (1.0 / 3.0),
             "z": z, "f": f}
            for t, v, z, f in zip(self.times, self.volume,
                                  self.actin_max_z, self.contact_force)
        ])

        accent_bar = (
            f'<div style="height:3px;background:{accent};margin-bottom:6px;'
            f'border-radius:2px"></div>'
        )

        # Self-contained Three.js scene. Uses string templating (NOT f-string)
        # for the JS body so braces don't need escaping.
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
    const h = 380;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fafc);

    const camera = new THREE.PerspectiveCamera(40, w / h, 0.01, 200);
    camera.position.set(5.5, 2.0, 5.5);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(w, h);
    container.insertBefore(renderer.domElement, container.firstChild);

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 0.85);
    key.position.set(5, 7, 4); scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.3);
    fill.position.set(-3, -2, -2); scene.add(fill);

    // Floor grid.
    const grid = new THREE.GridHelper(6, 6, 0xd1d5db, 0xe5e7eb);
    grid.material.transparent = true; grid.material.opacity = 0.4;
    grid.position.y = -2.5;
    scene.add(grid);

    // Vesicle — translucent sphere whose radius tracks (V/V0)^(1/3).
    const sphereGeom = new THREE.SphereGeometry(1.0, 32, 24);
    const sphereMat = new THREE.MeshStandardMaterial({
      color: 0x6366f1, roughness: 0.45, metalness: 0.1,
      transparent: true, opacity: 0.42,
    });
    const vesicle = new THREE.Mesh(sphereGeom, sphereMat);
    scene.add(vesicle);

    // Reference shell — initial radius, frozen as dotted wireframe.
    const refGeom = new THREE.SphereGeometry(1.0, 24, 18);
    const refWire = new THREE.LineSegments(
      new THREE.WireframeGeometry(refGeom),
      new THREE.LineBasicMaterial({ color: 0x9ca3af, transparent: true, opacity: 0.4 }));
    scene.add(refWire);

    // Actin disk — a thin cylinder at z = actin_max_z + colored by accent.
    const actinGeom = new THREE.CylinderGeometry(0.7, 0.7, 0.08, 24);
    const actinMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(ACCENT),
      roughness: 0.5, metalness: 0.1,
      transparent: true, opacity: 0.85,
    });
    const actin = new THREE.Mesh(actinGeom, actinMat);
    actin.position.set(0, -1.6, 0);
    scene.add(actin);

    // Contact-force arrow — points up at the vesicle from the actin puck.
    const arrowHelper = new THREE.ArrowHelper(
      new THREE.Vector3(0, 1, 0),
      new THREE.Vector3(0, -1.6, 0),
      1.0, 0xdc2626, 0.18, 0.12,
    );
    scene.add(arrowHelper);

    // Frame indicator and controls.
    let frame = 0;
    let playing = true;
    let lastStep = performance.now();

    function applyFrame(i) {
      if (i < 0 || i >= FRAMES.length) return;
      const f = FRAMES[i];
      vesicle.scale.set(f.r, f.r, f.r);
      // Actin puck floats from the floor (y=-2.5) toward the vesicle as z grows.
      // Map actin_max_z (typically [-3, +0.5]) into the scene's y axis.
      const puckY = Math.max(-2.4, Math.min(-0.2, f.z));
      actin.position.set(0, puckY, 0);
      // Arrow length grows with contact_force; clamp to keep it on-scene.
      const arrowLen = Math.max(0.2, Math.min(1.6, 0.4 + f.f * 0.3));
      arrowHelper.setLength(arrowLen, 0.18, 0.12);
      arrowHelper.position.set(0, puckY + 0.05, 0);
      hud.textContent = "t = " + f.t.toFixed(2) + "    V/V₀ = " + (f.r*f.r*f.r).toFixed(3);
    }

    // HUD overlay.
    const hud = document.createElement("div");
    hud.style.cssText = "position:absolute;top:8px;left:12px;background:rgba(255,255,255,0.85);"
      + "padding:4px 10px;border-radius:4px;font:12px/1.2 'Inter', sans-serif;color:#1f2937;";
    container.style.position = "relative";
    container.appendChild(hud);

    // Play/pause + slider.
    const controls = document.createElement("div");
    controls.style.cssText = "position:absolute;bottom:8px;left:12px;right:12px;"
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
    controls.appendChild(btn); controls.appendChild(slider); controls.appendChild(label);
    container.appendChild(controls);

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

    // OrbitControls if available, else static camera.
    let orbit = null;
    if (THREE.OrbitControls) {
      orbit = new THREE.OrbitControls(camera, renderer.domElement);
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
      s2.onerror = init;  // fall back without OrbitControls
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
            f'<div id="{div_id}" style="height:380px;background:#f8fafc;'
            f'border-radius:8px;position:relative;overflow:hidden"></div>'
            f'<script>{js}</script>'
        )
        return {'html': html + _autosize_script(380)}
