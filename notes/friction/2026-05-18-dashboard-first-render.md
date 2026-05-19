# Friction log — first-render of the workspace dashboard

**Date:** 2026-05-18 (same session as the in-place scaffolding log).
**Task:** After the workspace was scaffolded and two investigations were
seeded, get the vivarium-dashboard to actually show the workspace's
mem3dg + readdy composites and the investigations' studies. The user
opened the dashboard URL and saw the wrong simulators (compucell) and
a "Study not found" 404 on `fixed-boundary`.

Companion to `2026-05-18-workspace-onboarding-from-composite.md` —
that one covered scaffolding the files; this one covers the runtime
gap between "files exist" and "dashboard is useful."

---

## 12. The dashboard at `/` is a static stub from `pbg-template` until `/pbg-report` runs

The pbg-template `reports/index.html.j2` is a **placeholder**:

```
No models registered yet. Run /pbg-add-model <name> to begin.
Full dashboard renders once /pbg-report runs (Task 20+ of pbg-superpowers).
```

The vivarium-dashboard server serves whatever is at `<workspace>/reports/index.html` at `/`. After `template-init.sh` (or the in-place sed loop) renders the `.j2`, the file IS this placeholder — verbatim. The real SPA only lands after `scripts/render-dashboard.py` (or `/pbg-report`) runs, which invokes `vivarium_dashboard.lib.report.render_dashboard` and writes a ~92 KB SPA to the same path.

**The user reasonably concluded the workspace was broken** — they saw the placeholder text after I'd done all the scaffolding, set up the venv, registered composites and studies, and reported "dashboard is live." It was live. It was serving the wrong file.

**Recommendation:** `pbg-dashboard start` should call `render_dashboard()` once on startup before serving (or, more conservatively, refuse to start if `reports/index.html` still matches the placeholder body and print the exact fix command). The placeholder is technically a working HTTP response but it is **always** a bug for an end user to see it. There's no scenario where "workspace successfully scaffolded but no SPA rendered yet" is desirable.

## 13. Compucell-vs-mem3dg confusion was a binary-resolution misfire

The `/pbg-dashboard start` skill resolves the dashboard binary in this order:

1. `<workspace>/.venv/bin/vivarium-dashboard`
2. `$(which vivarium-dashboard)`
3. `python -m vivarium_dashboard.server`

The workspace `.venv/` didn't have `vivarium-dashboard` installed (because the in-place scaffolder skipped `template-init.sh`'s auto-pin step — see §6 of the sibling log). It fell through to `$(which vivarium-dashboard)` which pointed at `/Users/eranagmon/code/venv/` — a SHARED venv with `pbg-compucell3d` and `pbg-simucell3d` installed. The dashboard's process-discovery then walked **that** venv's site-packages and surfaced compucell composites.

The user opened the Composites tab and saw `pbg_compucell3d.*` everywhere — totally unrelated to this workspace's mem3dg/readdy model. Reasonable response: "this should not have compucell installed."

**Fix in-context:** `uv pip install --python .venv/bin/python -e /path/to/vivarium-dashboard` into the workspace venv. Now binary-resolution step 1 succeeds and the dashboard discovers from the workspace's own (compucell-free) site-packages.

**Recommendation:** Have `pbg-dashboard start` REFUSE to fall through to step 2 by default. Either step 1 resolves or the skill prints "vivarium-dashboard not installed in workspace venv — run `uv pip install …`." Silently using a sibling environment that has different packages installed is the worst-case UX.

## 14. Two pbg_superpowers versions in two venvs caused mysterious ImportErrors

The shared venv had `pbg-superpowers@0.9.0` (editable from `/Users/eranagmon/code/pbg-superpowers`). The workspace `.venv/` had `pbg-superpowers@0.2.0` (a git-pinned older version, presumably installed at workspace-bootstrap time months ago). The `0.2.0` version doesn't have `pbg_superpowers/dashboard.py`. Symptom:

```
$ .venv/bin/python -m pbg_superpowers.dashboard start --workspace .
.venv/bin/python: No module named pbg_superpowers.dashboard
```

But:

```
$ python -m pbg_superpowers.dashboard start --workspace .   # which resolves to the shared venv
{"action": "started", ...}    # works
```

The error message doesn't hint that two installs exist. I had to compare `pbg_superpowers.__file__` from both Pythons to figure it out.

**Recommendation:** When `pbg-dashboard start` (which runs from the SKILL host venv) detects that the WORKSPACE `.venv/` has a different pbg_superpowers version, print a one-line warning. Better: `pbg-workspace --in-place` and the bootstrap path should `pip install -U pbg-superpowers` in the workspace venv at register time.

## 15. Composite discovery is file-glob only — programmatic factories are invisible

The workspace package had `build_document(barrier_kind=..., ...)` — a Python factory producing the full composite state dict programmatically. The dashboard's **Composites tab discovered nothing from this**, because `pbg_superpowers.composite_discovery` walks `*.composite.yaml` and `*.composite.json` files only. Factory functions in `__init__.py` are not enumerated.

To get the three boundary-condition rungs to show up I had to generate three `*.composite.yaml` files by serializing `build_document(barrier_kind=k)` output:

```python
state = build_document(**kwargs)
spec = {"name": ..., "description": ..., "tags": [...], "state": state}
path.write_text(yaml.safe_dump(spec, sort_keys=False))
```

This works but is brittle: every change to `build_document` requires regenerating the YAML files. The hand-coded factory and the discovered YAML are now two sources of truth that can drift.

**Recommendation:** Support a third spec form alongside `state:` — a `factory:` key (e.g. `factory: pbg_membrane_actin_composite.document.build_document`) that the dashboard calls at discovery/render time. Many model packages will already have a hand-coded factory; forcing them to also emit static YAML is duplicative.

Alternative: provide a `scripts/regen-composites.py` helper that re-runs the serialization step. Even just documenting the pattern in the pbg-workspace skill would help.

## 16. `composite:` regex rejects hyphens; mem3dg's own composites would fail it

The study schema requires:

```regex
^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$
```

for `baseline[].composite`. But the canonical composite file stem in
the wild is **kebab-case** — e.g. `pbg_mem3dg/composites/membrane-demo.composite.yaml`
discovered as `pbg_mem3dg.composites.membrane-demo`. The HYPHEN in
`membrane-demo` violates the regex. A study can't reference it as
`pbg_mem3dg.composites.membrane-demo`.

I renamed the workspace's composite files from `rung1-fixed-boundary.composite.yaml` to `rung1_fixed_boundary.composite.yaml` to work around this. That works, but the **convention drift** is real: composite specs commonly use hyphens, study references can't.

**Recommendation:** Either widen the study schema regex to allow hyphens in the last segment, or change the discovery to normalize hyphens to underscores in composite IDs, or update the composite-spec convention docs to recommend underscored stems. The current state means cross-package references randomly fail.

## 17. `lint-workspace.py` distinguishes "schema ✓" and "dashboard ✓" but mixes their warnings

After writing six studies with `expected_behavior` entries that lacked
`measure.kind`, the lint output had:

```
WARN study … fails dashboard load: expected_behavior[0].measure.kind is required
…
workspace lint: OK
  6 studies: …  (validated: schema ✓, dashboard ✓)
```

The summary at the end says `dashboard ✓` but the body said
`fails dashboard load`. I had to read the WARN lines to know which
fields were broken — but only AFTER the summary suggested everything
was fine.

**Recommendation:** If any study fails dashboard load, the summary line should say `dashboard ✗ (N studies)`, not ✓. The summary is the headline; warnings are the body. They should agree.

## 18. Investigations don't validate that their study slugs exist

A `boundary-condition-staircase` investigation listed `studies: [fixed-boundary, ...]`. The studies directory was empty. Lint passed. The dashboard 404'd at runtime ("Study not found").

The investigation schema doesn't require referenced studies to exist on disk — `studies[]` is just a list of slug strings. The dashboard is the first thing that notices the slug is dangling.

**Recommendation:** Add a `lint-workspace.py` cross-reference check: for every investigation, every `studies[i]` slug must correspond to `studies/<slug>/study.yaml`. Same for `acceptance_criteria[].study`. This is the single biggest "I scaffolded a planning frame and the dashboard 404'd" friction.

## 19. `render-dashboard.py` output is opaque

```
$ .venv/bin/python scripts/render-dashboard.py
rendered /Users/eranagmon/code/pbg-membrane-actin-composite/reports/index.html
```

That's all it says. No "embedded 2 investigations, 6 studies, 10 composites, 3 visualizations." After running this I had to grep the rendered HTML to confirm the studies were embedded (they weren't — they're fetched client-side via /api). For someone who just spent 20 minutes wiring up YAMLs, that summary would be the difference between "shipped" and "not sure."

**Recommendation:** `render-dashboard.py` should print a one-line summary of what got embedded + a hint at which client-side endpoints feed the rest.

## 20. The skill text for /pbg-dashboard doesn't mention the render step

The `/pbg-dashboard start` skill description says it "wraps `vivarium-dashboard serve` so the dashboard runs detached." It doesn't say "first ensure `reports/index.html` is a freshly-rendered SPA, not the bootstrap placeholder."

If the user runs `/pbg-dashboard start` on a fresh workspace, they see the placeholder. The skill doesn't warn that this is expected and that they need `/pbg-report` next. Onboarding double-tap.

**Recommendation:** `/pbg-dashboard start` should call `render_dashboard()` first. If that's not architecturally clean (separation of concerns: dashboard skill ≠ report skill), then at minimum the skill should detect "placeholder body in reports/index.html" and exit with `run /pbg-report first, then re-run /pbg-dashboard start`.

## What worked well (so the next agent doesn't break it)

- Once `render-dashboard.py` ran, the SPA picked up everything correctly: 6 studies, 3 workspace composites, 5 mem3dg composites, 2 readdy composites, 1 expert doc, 1 BibTeX reference. No second-pass needed.
- Composite discovery picking up `*.composite.yaml` files via `importlib.metadata.distributions()` + `bigraph-schema` dependency-graph filter is robust. New packages dropped into the workspace venv get picked up on next process restart without config changes.
- The `/api/composites` endpoint is JSON and well-shaped — easy to verify with `curl | python -c "json.load"` what the dashboard sees.

## Summary recommendations, ranked

1. **`pbg-dashboard start` should auto-render** (or refuse to start with a clear message). The placeholder-served-as-dashboard is the worst first impression possible.
2. **Refuse to fall through to a sibling venv** in binary resolution. Either the workspace venv has vivarium-dashboard or the skill errors out clearly.
3. **Add a cross-reference lint** for investigation → study slug existence.
4. **Support `factory:` in composite specs**, or document the regen pattern, so factory-based model packages don't have to dual-maintain.
5. **Reconcile hyphens-vs-underscores** in composite stems / study `composite:` regex.
6. **Lint summary must agree with WARN lines** — no ✓ in the summary if any study fails dashboard load.
7. **`render-dashboard.py` should print what it embedded.**
