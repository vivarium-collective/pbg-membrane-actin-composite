#!/usr/bin/env python3
"""Build a self-contained STATIC investigation report for GitHub Pages.

The interactive dashboard report (reports/index.html) is an API-backed SPA and
cannot be hosted on static Pages. This builder composes a standalone HTML page
from investigation.yaml + the per-study decision figures (which are already
self-contained Plotly HTML), so the README's Pages link can show the generated
report instead of the old demo.

Output: <out>/index.html + <out>/figures/<study>__<figure>.html (+ a copy of the
existing demo is left untouched by the publisher). Default out = ./_site.

Usage: python scripts/build-static-report.py [--out _site] [--slug membrane-actin-ratchet] [--date YYYY-MM-DD]
"""
from __future__ import annotations
import argparse, html, shutil
from pathlib import Path
import yaml

LADDER = [
    "fixed-boundary", "rigid-movable-boundary",
    "actin-to-membrane-force-handshake", "membrane-to-actin-displacement-feedback",
    "flexible-mem3dg-boundary", "coupled-ratchet-cycle-fv-reproduction",
]
# study -> its decision-figure viz name (None = not yet built)
DECISION_FIG = {
    "fixed-boundary": "gap-contact-decision",
    "rigid-movable-boundary": "fv-phase-portrait",
    "actin-to-membrane-force-handshake": "newton-residual",
    "membrane-to-actin-displacement-feedback": None,
    "flexible-mem3dg-boundary": None,
    "coupled-ratchet-cycle-fv-reproduction": "force-velocity-benchmark",
}
CONF_COLOR = {"Accepted": "#059669", "Investigating": "#d97706",
              "Planned": "#6b7280", "Refuted": "#dc2626"}
# friendly annotation keys (match the reviewer feedback YAML schema)
FB_KEY = {
    "fixed-boundary": "fixed_boundary",
    "rigid-movable-boundary": "rigid_movable_boundary",
    "actin-to-membrane-force-handshake": "force_handshake",
    "membrane-to-actin-displacement-feedback": "displacement_feedback",
    "flexible-mem3dg-boundary": "flexible_membrane",
    "coupled-ratchet-cycle-fv-reproduction": "fv_benchmark",
}
GH_OWNER_REPO = "vivarium-collective/pbg-membrane-actin-composite"
GH_BASE_BRANCH = "main"


def _fb(key: str, label: str) -> str:
    """A per-section feedback textarea that the YAML generator reads."""
    return (f'<details class="fb"><summary>✎ Add feedback on {e(label)}</summary>'
            f'<textarea data-fbkey="{e(key)}" rows="3" '
            f'placeholder="Your comment becomes an annotations.{e(key)}[] entry in the YAML"></textarea>'
            f'</details>')


def e(x): return html.escape(str(x or ""))


def md_to_p(text: str) -> str:
    """Very light markdown: paragraphs split on blank lines; *em* -> <em>."""
    import re
    out = []
    for para in (text or "").strip().split("\n\n"):
        p = e(para.strip()).replace("\n", " ")
        p = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", p)
        if p:
            out.append(f"<p>{p}</p>")
    return "\n".join(out)


def build(ws: Path, slug: str, out: Path, date: str) -> Path:
    inv = yaml.safe_load((ws / "investigations" / slug / "investigation.yaml").read_text())
    studies = {}
    for s in LADDER:
        sy = ws / "studies" / s / "study.yaml"
        studies[s] = yaml.safe_load(sy.read_text()) if sy.is_file() else {}

    out.mkdir(parents=True, exist_ok=True)
    figdir = out / "figures"; figdir.mkdir(exist_ok=True)

    # copy decision-figure HTML
    fig_src = {}
    for s, fig in DECISION_FIG.items():
        if not fig:
            continue
        src = ws / "studies" / s / "viz" / f"{fig}.html"
        if src.is_file():
            dst = f"{s}__{fig}.html"
            shutil.copyfile(src, figdir / dst)
            fig_src[s] = dst

    exe = inv.get("executive", {}) or {}
    sa = inv.get("scientific_argument", {}) or {}

    # validation-status matrix
    vrows = ""
    state_color = {"executable": "#6b7280", "calibrated": "#d97706",
                   "validated": "#059669", "blocked": "#dc2626"}
    for v in (exe.get("validation_status") or []):
        st = v.get("state", "")
        vrows += (f"<tr><td><code>{e(v.get('study'))}</code></td>"
                  f"<td><span class='pill' style='background:{state_color.get(st,'#6b7280')}'>{e(st)}</span></td>"
                  f"<td>{e(v.get('note'))}</td></tr>")

    def bullets(items):
        return "".join(f"<li>{e(x)}</li>" for x in (items or []))

    # study decision-figure cards
    cards = ""
    for s in LADDER:
        st = studies[s]
        title = st.get("title") or s
        conf = st.get("confidence", "Investigating")
        claim = st.get("claim", "")
        ep = st.get("expected_pattern", "")
        thr = st.get("acceptance_threshold", "")
        ev = st.get("evidence_status", "")
        fig = fig_src.get(s)
        figblock = (f"<iframe src='figures/{fig}' loading='lazy'></iframe>"
                    if fig else
                    "<div class='nofig'>Decision figure pending — needs additional emitted data "
                    "(mesh-quality / per-vertex fields). See investigation open_items.</div>")
        cards += f"""
        <section class="card">
          <div class="cardhead">
            <h3>{e(title)}</h3>
            <span class="pill" style="background:{CONF_COLOR.get(conf,'#6b7280')}">{e(conf)}</span>
          </div>
          <p class="claim">{e(claim)}</p>
          <div class="meta">
            <div><b>Expected pattern:</b> {e(ep)}</div>
            <div><b>Acceptance threshold:</b> {e(thr)}</div>
            {f'<div><b>Evidence:</b> <code>{e(ev)}</code></div>' if ev else ''}
          </div>
          {figblock}
          {_fb(FB_KEY.get(s, s.replace('-', '_')), title)}
        </section>"""

    glossary = "".join(
        f"<dt>{e(g.get('term'))}</dt><dd>{e(g.get('definition'))}</dd>"
        for g in (inv.get("glossary") or []))

    page = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(inv.get('title') or slug)}</title>
<style>
  :root {{ --ink:#1f2937; --muted:#6b7280; --rule:#e5e7eb; --accent:#10b981; }}
  * {{ box-sizing:border-box; }}
  body {{ font:15px/1.6 Inter,system-ui,-apple-system,sans-serif; color:var(--ink);
         max-width:980px; margin:0 auto; padding:32px 20px 80px; }}
  h1 {{ font-size:26px; margin:0 0 4px; }} h2 {{ font-size:19px; margin:36px 0 10px;
        border-bottom:2px solid var(--accent); padding-bottom:4px; }}
  h3 {{ font-size:16px; margin:0; }}
  .lead {{ font-size:17px; color:#374151; }}
  .badge {{ display:inline-block; padding:2px 10px; border-radius:999px; color:#fff;
            font-size:12px; font-weight:600; }}
  .pill {{ display:inline-block; padding:1px 9px; border-radius:999px; color:#fff;
           font-size:11px; font-weight:600; white-space:nowrap; }}
  .banner {{ background:#fef3c7; border:1px solid #d97706; color:#92400e; padding:10px 14px;
             border-radius:8px; font-size:13px; margin:14px 0; }}
  table {{ border-collapse:collapse; width:100%; font-size:13px; }}
  td,th {{ border:1px solid var(--rule); padding:6px 9px; text-align:left; vertical-align:top; }}
  th {{ background:#f9fafb; }}
  ul {{ margin:6px 0 6px 20px; }} code {{ background:#f3f4f6; padding:1px 5px; border-radius:4px; font-size:12px; }}
  .ladder {{ font-family:ui-monospace,monospace; font-size:13px; background:#f9fafb;
             border:1px solid var(--rule); border-radius:8px; padding:10px 14px; }}
  .card {{ border:1px solid var(--rule); border-radius:10px; padding:14px 16px; margin:16px 0;
           box-shadow:0 1px 2px rgba(0,0,0,.04); }}
  .cardhead {{ display:flex; justify-content:space-between; align-items:center; gap:10px; }}
  .claim {{ color:#374151; margin:8px 0; }}
  .meta {{ font-size:13px; color:var(--muted); margin:8px 0 12px; }}
  .meta b {{ color:var(--ink); }}
  iframe {{ width:100%; height:440px; border:1px solid var(--rule); border-radius:8px; background:#fff; }}
  .nofig {{ background:#f9fafb; border:1px dashed var(--rule); border-radius:8px; padding:18px;
            color:var(--muted); font-size:13px; }}
  dt {{ font-weight:600; margin-top:6px; }} dd {{ margin:0 0 4px 16px; color:#374151; }}
  .foot {{ margin-top:48px; padding-top:14px; border-top:1px solid var(--rule);
           color:var(--muted); font-size:12px; }}
  a {{ color:#0ea5e9; }}
  details.fb {{ margin:8px 0 2px; }}
  details.fb summary {{ cursor:pointer; color:#0ea5e9; font-size:12px; font-weight:600; }}
  details.fb textarea, .reviewer textarea, .reviewer input {{ width:100%; margin-top:6px;
     font:13px/1.5 Inter,system-ui,sans-serif; padding:7px 9px; border:1px solid var(--rule);
     border-radius:6px; resize:vertical; }}
  .reviewer {{ background:#f0f9ff; border:1px solid #bae6fd; border-radius:10px; padding:14px 16px; margin:16px 0; }}
  .reviewer label {{ font-size:12px; font-weight:600; color:#0369a1; display:block; margin-top:8px; }}
  .fbbar {{ position:sticky; bottom:0; background:#fff; border-top:2px solid var(--accent);
     padding:12px 0; margin-top:24px; display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
  .btn {{ border:0; border-radius:7px; padding:9px 16px; font-size:13px; font-weight:600;
     cursor:pointer; color:#fff; }}
  .btn.gen {{ background:#475569; }} .btn.issue {{ background:#1f883d; }} .btn.pr {{ background:#8250df; }}
  .btn.copy {{ background:#0ea5e9; }} .btn:disabled {{ opacity:.45; cursor:not-allowed; }}
  #yamlout {{ width:100%; height:240px; font:12px/1.5 ui-monospace,monospace; margin-top:10px;
     border:1px solid var(--rule); border-radius:8px; padding:10px; display:none; }}
  .hint {{ font-size:12px; color:var(--muted); }}
</style></head><body>

<h1>{e(inv.get('title') or slug)}</h1>
<span class="badge" style="background:var(--accent)">verdict: {e(exe.get('verdict_status','in-progress'))}</span>
<p class="lead">{e(inv.get('lead',''))}</p>
<div class="banner"><b>Status:</b> {e(exe.get('verdict',''))}</div>

<div class="reviewer">
  <b>📝 Expert review.</b> <span class="hint">Add comments in the ✎ boxes throughout, then generate a YAML feedback report and submit it to GitHub (as an issue or a PR file). No account setup needed — you review and submit in the GitHub UI.</span>
  <label>Your name (reviewer)</label>
  <input id="rev-name" type="text" placeholder="e.g. Jane Expert">
  <label>Overall assessment</label>
  <textarea id="rev-overall" rows="3" placeholder="One-paragraph overall assessment (meta.overall_assessment)"></textarea>
</div>

<h2>Executive summary</h2>
{md_to_p(exe.get('verdict_detail',''))}
<h3>Validation status</h3>
<table><tr><th>Study</th><th>State</th><th>Note</th></tr>{vrows}</table>
{_fb('executive', 'the executive summary')}

<h2>How to read this</h2>
<div class="ladder">Fixed Wall → Rigid Wall → Force Handshake → Feedback → Flexible Membrane → F-V Benchmark</div>
<p><b>Labels:</b> <code>OBSERVED</code> measured in a run · <code>INFERRED</code> expected from theory, not yet measured · <code>VALIDATED</code> measured AND matched to a benchmark. <b>Nothing is VALIDATED yet.</b></p>

<h2>Scientific argument</h2>
<p><b>Main claim.</b> {e(sa.get('main_claim',''))}</p>
<p><b>Evidence for</b></p><ul>{bullets(sa.get('evidence_for'))}</ul>
<p><b>Evidence against / open</b></p><ul>{bullets(sa.get('evidence_against'))}</ul>
<p><b>Caveats</b></p><ul>{bullets(sa.get('caveats'))}</ul>
{_fb('scientific_argument', 'the scientific argument')}

<h2>Decision figures</h2>
<p>Each study is organized around one pass/fail decision figure carrying its expected pattern and acceptance threshold.</p>
{cards}

<h2>Glossary</h2><dl>{glossary}</dl>

<h2>Cross-cutting feedback</h2>
<p class="hint">Comments that span the whole report rather than one study.</p>
{_fb('global_visual_design', 'visual design (across all figures)')}
{_fb('global_interpretation', 'interpretation (across the investigation)')}

<div class="fbbar">
  <button class="btn gen" id="btn-gen">① Generate feedback YAML</button>
  <button class="btn copy" id="btn-copy" disabled>Copy</button>
  <button class="btn issue" id="btn-issue" disabled>② Open as GitHub issue</button>
  <button class="btn pr" id="btn-pr" disabled>② Propose as PR file</button>
  <span class="hint" id="fb-status"></span>
</div>
<textarea id="yamlout" readonly spellcheck="false"></textarea>

<script>
(function() {{
  var OWNER_REPO = {GH_OWNER_REPO!r};
  var BASE = {GH_BASE_BRANCH!r};
  var SLUG = {slug!r};
  function blockScalar(text, indent) {{
    var pad = ' '.repeat(indent);
    return (text || '').replace(/\\r/g,'').split('\\n')
      .map(function(l) {{ return pad + l; }}).join('\\n');
  }}
  function buildYaml() {{
    var name = (document.getElementById('rev-name').value || 'anonymous').trim();
    var overall = (document.getElementById('rev-overall').value || '').trim();
    var y = 'meta:\\n';
    y += '  investigation: ' + SLUG + '\\n';
    y += '  reviewer: ' + JSON.stringify(name) + '\\n';
    y += '  focus: expert-review\\n';
    if (overall) y += '  overall_assessment: |\\n' + blockScalar(overall, 4) + '\\n';
    var fbs = document.querySelectorAll('textarea[data-fbkey]');
    var byKey = {{}};
    fbs.forEach(function(t) {{
      var v = (t.value || '').trim();
      if (!v) return;
      (byKey[t.getAttribute('data-fbkey')] = byKey[t.getAttribute('data-fbkey')] || []).push(v);
    }});
    var keys = Object.keys(byKey);
    if (keys.length) {{
      y += 'annotations:\\n';
      keys.forEach(function(k) {{
        y += '  ' + k + ':\\n';
        byKey[k].forEach(function(txt) {{
          y += '    - text: |\\n' + blockScalar(txt, 8) + '\\n';
        }});
      }});
    }}
    return {{yaml: y, name: name, hasAny: keys.length > 0 || !!overall}};
  }}
  var current = null;
  function fname(name) {{
    var d = new Date().toISOString().slice(0,10);
    var safe = (name||'anon').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'') || 'anon';
    return 'feedback/' + SLUG + '--' + safe + '--' + d + '.yaml';
  }}
  document.getElementById('btn-gen').onclick = function() {{
    current = buildYaml();
    var out = document.getElementById('yamlout');
    out.value = current.yaml; out.style.display = 'block';
    var on = current.hasAny;
    ['btn-copy','btn-issue','btn-pr'].forEach(function(id){{ document.getElementById(id).disabled = !on; }});
    document.getElementById('fb-status').textContent = on
      ? 'Review the YAML below, then submit.' : 'Add at least one comment or an overall assessment.';
  }};
  document.getElementById('btn-copy').onclick = function() {{
    navigator.clipboard.writeText(current.yaml).then(function(){{
      document.getElementById('fb-status').textContent = 'Copied to clipboard.';
    }});
  }};
  document.getElementById('btn-issue').onclick = function() {{
    var title = 'Expert feedback: ' + SLUG + ' (' + current.name + ')';
    var body = 'Generated from the investigation report.\\n\\n```yaml\\n' + current.yaml + '\\n```\\n';
    var url = 'https://github.com/' + OWNER_REPO + '/issues/new?title=' +
      encodeURIComponent(title) + '&labels=feedback&body=' + encodeURIComponent(body);
    window.open(url, '_blank');
  }};
  document.getElementById('btn-pr').onclick = function() {{
    var url = 'https://github.com/' + OWNER_REPO + '/new/' + BASE + '?filename=' +
      encodeURIComponent(fname(current.name)) + '&value=' + encodeURIComponent(current.yaml);
    window.open(url, '_blank');
  }};
}})();
</script>

<div class="foot">
  Generated {e(date)} from <code>investigations/{e(slug)}/investigation.yaml</code> + per-study decision figures.
  This is a static snapshot of the interactive vivarium-dashboard report.
  · <a href="https://github.com/vivarium-collective/pbg-membrane-actin-composite">Source</a>
  · <a href="demo/report.html">Original interactive demo</a>
</div>
</body></html>"""

    (out / "index.html").write_text(page, encoding="utf-8")
    return out / "index.html"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site")
    ap.add_argument("--slug", default="membrane-actin-ratchet")
    ap.add_argument("--date", default="")
    a = ap.parse_args()
    ws = Path.cwd()
    p = build(ws, a.slug, Path(a.out), a.date or "")
    print(f"wrote {p} ({p.stat().st_size} bytes) + figures/")


if __name__ == "__main__":
    raise SystemExit(main())
