# Friction log — 3D viz, run-queue, browser UX, PR flow

**Date:** 2026-05-18 (continuing the same session as the three earlier logs).
**Tasks in this segment, in order:** add 3D Three.js visualizations like
the demo report; populate observables; fix the staircase investigation
queue; trigger PR creation from the dashboard. Each surfaced its own
class of friction.

Companion to:

- `2026-05-18-workspace-onboarding-from-composite.md` (scaffold-time)
- `2026-05-18-dashboard-first-render.md` (first-render-time)
- `2026-05-18-running-the-full-investigation.md` (run-time)

This log: **viz-time, browser-UX, and PR-flow**.

---

## 29. `@composite_generator(visualizations=...)` defaults also need `address:`

Earlier (friction #26) I documented that **study.yaml** visualizations[]
entries need an `address:` field or the dashboard `KeyError`s. What I
missed: the same is true for the `visualizations=[...]` list passed to
`@composite_generator`. When the dashboard's `_render_study_visualizations`
**merges** generator-default vizzes with study-declared vizzes, the
unaddressed defaults silently win on name collision (or appear when the
study declares fewer entries). The error message is identical to the
study-level one:

> Failed to render `barrier-kinematics`: KeyError: 'address'

Two sources of truth (study yaml + generator decorator), both need to
agree on the address contract.

**Recommendation:** Default `address:` from the workspace.yaml
`visualizations[].class` field when missing, in BOTH merge sources.
This single piece of state already exists; both halves should resolve
through it.

## 30. The dashboard's typed wire truncates 3-level-nested data — there's no working port type for positions

Tried to render REAL `actin_positions` (per-step `list[points][3]`) and
`membrane_vertex_positions` (per-step `list[vertices][3]`) in a Three.js
viewer. The dashboard's `build_viz_composite` dispatches `inputs_store`
by **declared port type**:

| Declared type            | Behaviour with positions data |
|--------------------------|------------------------------|
| `'list[float]'`          | schema engine coerces inner lists to scalars → ends up empty |
| `'list[list[float]]'`    | passes the outer list-of-runs, but inner per-frame structure is truncated to flat — actin/membrane arrays in the rendered viz are `[]` |
| `'any'`                  | not a recognized process-bigraph type — fails composite init with `'str' object does not support item assignment` |
| (any other type name)    | same as `'any'` — fails init |

So for 3-level-nested coordinate data, **there is no declared input
type that gets the full structure through**. The platform has typed
wires for time-series scalars but no convention for per-step nested
arrays.

Workarounds I considered but didn't ship:

1. Flatten to `list[float]` (length = 3 · N · T) on the Python side,
   reshape in JS. Loses the per-frame N count if N varies (it does
   for actin — particles get added during polymerization).
2. Have the viz read directly from `runs.db` via Python, bypassing
   the typed wire. Breaks the platform's wire contract.
3. Render the scene server-side as a static `<svg>` or as embedded
   base64 frames. Heavyweight.

`SchematicVesicle3D` (scalar-driven schematic — vesicle radius from
`membrane_volume`, actin "puck" position from `actin_max_z`) works
end-to-end because all its inputs are scalar-per-step series. The
schematic does the user's job-to-be-done for "see the dynamics" but
not for "see the real particle field." For the latter to work, the
platform needs a position-typed wire convention.

**Recommendation:** Add a `'positions'` (or `'list[vec3]'`) primitive
to the workspace.schema type vocabulary, and a matching dispatch
branch in `build_viz_composite` that passes the full nested structure
through unchanged. Until that exists, document the limitation in
`docs/concepts/visualizations.md` so the next viz author doesn't
spend an hour rediscovering it.

## 31. JS embedded in a Python module — double-brace escape footgun

`SchematicVesicle3D.update()` returns an HTML string that includes a
self-contained JavaScript body. My first draft was an f-string, so
all `{` and `}` in the JS were `{{` and `}}`. I refactored to a
non-f-string but forgot to unescape. The browser parsed
`(function() {{` as invalid JS and the Three.js scene silently never
ran — no error, just an empty `<div>` where the viewer should be.

Python catches f-string syntax errors at parse time. Plain-string JS
errors only surface when a browser tries to run the output. Took a
"why are the 3D viz not in the report?" user message + an in-browser
inspection to find.

**Recommendation:** If a Python module embeds JS, run a syntax pass
on the rendered HTML in tests. `nodejs --check` against the script
body would catch this in seconds. Or just keep JS in `.js` files
and template via `str.replace`, which is what I ended up doing.

## 32. Dashboard `start` opens a browser tab on every restart, and the port shifts

The `/pbg-dashboard` skill defaults to `--browser` (auto-open) and
picks a free port each time. macOS keeps just-closed ports in
`TIME_WAIT` for ~60 seconds, so consecutive `restart` calls almost
always pick a *different* port. Net effect for the user: every
restart opens a new browser tab, and the URL changes, so the user's
existing tab dies.

Workaround I landed on: pass `--port 8766 --no-browser` to pin a
specific port for this workspace AND skip the auto-open. The user
keeps a single tab at `http://localhost:8766/` and just reloads it.
But this only works if I remember to pass both flags every time.

The default behavior burned ~20 minutes of frustration for the user
before they explicitly asked me to stop opening tabs.

**Recommendation:** Either:

1. Default `start` to `--no-browser` and only open when the user
   passes `--browser`. The agent-driven case is the more common
   one in a Claude Code session — the user is already on a tab.
2. Persist the last-chosen port in `~/.pbg/dashboard-info.json` so
   `restart` reuses it.
3. Document the `--port <N> --no-browser` idiom in the skill's
   "How to invoke" section as the recommended Claude-Code invocation.

I'd take any of those; option 1 is cheapest.

## 33. Default port 8765 collides across workspaces

The first workspace to launch grabs port 8765; every subsequent
workspace's dashboard falls back to a random port. So:

- `v2ecoli`'s dashboard had 8765.
- This workspace's dashboard tried 8765, failed, picked a system
  port (e.g., 56324, 57597, ...).
- The user can't bookmark a stable URL because the port shifts on
  every restart (per §32).

I picked **8766** for this workspace by convention.

**Recommendation:** The skill should advise "if 8765 is taken, pick
the lowest free port in 8766-8799 and remember it for this
workspace." Persisted in `<workspace>/.pbg/dashboard/preferred-port`.

## 34. "Failed to queue: no unblocked variants to run" — root cause unknown

The Investigations page's **Run unblocked** button returned this error
after I'd already run every member study's baseline at the study level.
The dashboard's `enumerate_unblocked` (in
`vivarium_dashboard/lib/run_jobs.py:138`) determines runnability per
study; nothing in my member study yamls indicated they were "blocked,"
but every entry must have come back as something other than `queued`.

I didn't fully trace why. Two plausible causes:

- The dashboard considers a study "already done" once its `runs.db`
  has a completed row for its baseline. The investigation-level
  runner then has nothing left to queue.
- The investigation's `acceptance_criteria` reference
  `expected_behavior` names whose `status: stub` blocks them from
  being run automatically.

**Recommendation:** When `Run unblocked` returns an empty queue, the
UI should explain *why* (per-study reason: done, blocked-by, no
variants declared, etc.). Right now it's an unactionable error.
Make the API response items[] visible in the UI tooltip.

## 35. The dashboard's "Push" button is missing for unpushed branches

I trusted the dashboard's error message — *"PR create failed: push
to origin first (Push button)"* — and assumed the **GitHub Branches**
tab had a Push button I could point the user at. The user's reply
was:

> "i did not have the option to do this from the dashboard"

So the error message refers to a UI element that doesn't appear in
the current dashboard build for this state (branch not yet pushed),
OR the button is hidden behind another tab/menu, OR the message text
is stale w.r.t. the actual UI.

I worked around by running `git push -u origin
membrane-actin-workspace` from the terminal — but that's the exact
manual step the dashboard claims to automate.

**Recommendation:** Either ship the Push button on the
GitHub-Branches row for unpushed branches, or update the error text
to point at the actual workflow (e.g., "run `git push` in this
workspace first; the dashboard will show the branch after the next
refresh"). The current text directs users at UI that isn't there.

## 36. The Run-button cluster has too many "actions" without explanation

The screenshot the user sent (boundary-condition-staircase Investigation
page) showed: `Running`, `Refresh`, `Run unblocked`, `Generate report`,
`Clone` — five tightly-packed actions next to a `Failed to queue` error.
There's no UI affordance to hover/explain what each does, what an
"unblocked" variant means, or what a successful "Generate report"
produces.

This isn't a bug — it's a discoverability gap. Documented here so the
next round of dashboard polish can prioritize it.

**Recommendation:** Each action button should have a one-sentence
tooltip ("Queue every study baseline + variant that has no unsatisfied
prerequisites and hasn't run yet") or a small `?` info-icon next to
the cluster.

## What worked well

- Once the address-on-defaults bug was fixed, the dashboard's
  per-viz iframe pattern made it easy to see exactly which viz failed
  and why — error stubs landed cleanly in each iframe without
  contaminating the rest of the page.
- The post-run `studies/<slug>/viz/*.html` artifacts are stable
  enough to inspect via plain `cat` / `head` / `grep` from a terminal.
  Made diagnosing brace-escape and empty-data issues straightforward.
- `--port <N> --no-browser` works reliably once you know to use it.
  Stable URL = stable user experience.
- The git push → dashboard refresh roundtrip is well-defined; the
  branch shows up correctly on the GitHub Branches tab once pushed.

## Cross-cutting themes

1. **Type contracts at the dashboard's wires are load-bearing AND
   under-specified.** Every viz had to discover empirically which
   port types pass which data shape (see #25, #30). A short
   reference table in `docs/concepts/visualizations.md` would save
   every new viz author the same exploration.

2. **Default to "agentic" mode.** Auto-opening a browser tab on every
   restart and using random ports is fine for a human running
   `pbg-dashboard start` once. It is friction-by-default for an
   AI agent that restarts the dashboard 10 times in a debugging session.
   The dashboard skill is presumably used MORE by agents than by humans;
   pick defaults accordingly.

3. **Error messages should point at UI affordances that exist.**
   #35 (Push button) is the canonical example. A message that says
   "click X" is a contract — if X isn't there, the user is stuck.

4. **3D viz needs a position-aware wire.** This isn't a niche concern
   — every spatial simulator (Mem3DG, ReaDDy, Cytosim, COMSOL ports)
   produces nested coordinate arrays. The platform should support
   them as a first-class observable type.
