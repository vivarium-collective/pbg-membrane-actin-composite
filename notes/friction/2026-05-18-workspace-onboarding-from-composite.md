# Friction log — promoting an existing composite repo into a pbg-superpowers workspace

**Date:** 2026-05-18
**Agent:** Claude Code (Opus 4.7)
**Task:** Convert `pbg-membrane-actin-composite` (a standalone composite-package
repo combining pbg-mem3dg + pbg-readdy) into a pbg-template-style workspace
branch so investigations could be planned from the vivarium-dashboard.
**Outcome:** Succeeded on branch `membrane-actin-workspace`. Lint passes,
investigation seed file validates, workspace registered in `~/.pbg/workspaces.json`.

These notes are intentionally concrete — file paths, exact commands that
failed, schema mismatches — so the next agent improving onboarding has
something diffable rather than vibes.

---

## 1. The biggest single friction: `--in-place` is documented but unimplemented

`python -m pbg_superpowers.scaffold workspace --in-place …` is exposed as a
CLI flag in `scaffold workspace --help`, but invoking it prints:

> `Error: --in-place bootstrap not yet implemented in scaffold.py. Follow the manual steps in skills/pbg-workspace/SKILL.md ('In-place mode') until this is implemented.`

The SKILL.md "In-place mode" section is correct but asks the operator to
mentally execute what's effectively a small build script:

1. Copy a subset of template directories.
2. Copy a subset of template .j2 files (skipping the ones that conflict with
   the existing repo — README.md.j2, pyproject.toml.j2).
3. Render the remaining .j2 files with sed substitution of four variables
   (`workspace_name`, `package_path`, `today`, `plugin_version`).
4. Merge new lines into the existing pyproject.toml and .gitignore.
5. Commit + register in the workspace catalog.

**Recommendation:** Implement `--in-place` in scaffold.py. The logic is
~30 lines of Python and the manual ritual is the single biggest onboarding
tax. Until then, the SKILL.md should explicitly list **the conflict set**
(files that would overwrite existing repo contents) instead of saying
"SKIP files that already exist" generically — see §5 below.

## 2. Decision tree at the top of the skill would save a turn

The skill markdown lists three modes (upstream-branch, standalone, in-place)
as sibling sections. With an existing checkout, "in-place" is the right
answer — but the skill doesn't say *"if you already have a checkout, jump
to In-place mode."* I had to surface this to the user as a 3-option choice.

**Recommendation:** Add a 5-line decision tree at the top of SKILL.md:

```
- No directory yet, no upstream model repo  → standalone
- No directory yet, want to branch off existing repo  → upstream-branch
- Already inside a checkout you want to promote  → in-place
```

## 3. Hidden CWD-persistence pitfall when reading the template

I `cd`'d into `/Users/eranagmon/code/pbg-template/template/` to inspect
files, then continued running shell commands assuming I was back in the
workspace. The Bash tool persists CWD across invocations, so my next
`ls -la` showed template content and briefly confused me about the
workspace's state. This is generic to Claude Code's Bash tool — but a note
in the skill ("prefer absolute paths when inspecting `pbg-template/`")
would prevent the mistake.

## 4. The `plugin_version` variable has no obvious source of truth

`template-init.sh` hardcodes `PLUGIN_VERSION="0.4.16"`. When doing the
in-place manual steps, I had to grep for this — it's not in `workspace.yaml.j2`,
not in `pbg_superpowers.__version__`, not in env. Picking the right value
matters because the dashboard reads it.

**Recommendation:** Have the scaffolder import
`pbg_superpowers.__version__` (or similar). Eliminate the hardcoded literal
in `template-init.sh`. For in-place mode, the operator should run a single
command that emits the value, not copy a constant from a different script.

## 5. The conflict set when in-place overlaying pbg-template

For a composite repo like this one (already has README, pyproject, package,
tests, docs), copying the entire template tree would overwrite the
following files. **Skip / don't copy:**

| Template file | Why skip |
|---|---|
| `README.md.j2` | Composite has a richer README describing the model. |
| `pyproject.toml.j2` | Composite already has deps; need to **merge**, not replace. |
| `.gitignore` | Composite has model-specific entries; **append** template's. |
| `docs/README.md`, `docs/decisions.yaml` | Composite's `docs/spec.md` would be sibling but `docs/README.md` would clobber. (In this case `docs/` only had `spec.md` so it was safe.) |

**Files / dirs to copy unchanged:**
`datasets/`, `experiments/`, `notes/`, `references/`, `reports/`,
`scripts/`, `.pbg/`, `.claude/settings.json`,
`.github/workflows/workspace-ci.yml.j2`, `workspace.yaml.j2`,
`NEXT_STEPS.md.j2`.

**Files to merge (not replace):**
- `pyproject.toml` — add `pyyaml`, `jsonschema[format-nongpl]`, `jinja2`,
  `pypdf`, `vivarium-dashboard` to `dependencies`.
- `.gitignore` — add the workspace runtime entries (`.pbg/server/`,
  `.pbg/state.json`, `investigations/*/runs.db`, `reports/assets/*`, etc.).

The skill's "skip files that already exist" guidance is correct in spirit
but ambiguous in practice: it doesn't say which files need *merge* vs
*skip-entirely*. A scaffolder should encode this table.

## 6. `vivarium-dashboard` isn't on PyPI; in-place mode misses the auto-pin

`template-init.sh` has logic to detect a sibling `../vivarium-dashboard/`
checkout and inject a `[tool.uv.sources]` block into pyproject.toml. The
in-place workflow doesn't run `template-init.sh` and therefore skips this
step. The first time the user runs `uv pip install -e ".[dev]"`, they'll
hit:

> `vivarium-dashboard was not found in the package registry`

**Recommendation:** The in-place scaffolder must run the same auto-pin
logic (or print a clear warning) when adding vivarium-dashboard to deps.
Otherwise the very next user action after this scaffolding (`bash
scripts/serve.sh`) silently fails because the venv install never
completed.

## 7. Investigation vs Study schema asymmetry isn't surfaced

The user said "plan investigations with the vivarium-dashboard." The
right artifact to seed for *planning* is an **investigation**
(`name`, `title` required; everything else optional — see
`.pbg/schemas/investigation.schema.json`). A **study** has 8 canonical
sections and requires `baseline[]` with at least one `composite`-bound
entry — way too heavy to seed at planning time.

This distinction is implied in NEXT_STEPS.md §4 ("a study is one research
question … an investigation groups related studies … as a DAG") but isn't
called out as: **investigations are lightweight planning frames; studies
are filled in later from the dashboard.**

**Recommendation:** Add a one-line hint to NEXT_STEPS.md and/or the
investigation schema: "Start here for planning. Seed studies with
`/pbg-study` once the simulation set is concrete."

## 8. Lint summary doesn't mention investigations

After seeding `investigations/boundary-condition-staircase/`, `python3
scripts/lint-workspace.py` prints:

```
workspace lint: OK
  workspace: pbg-membrane-actin-composite  (package: pbg_membrane_actin_composite)
  0 expert_docs, 0 bib keys, 0 claims
  0 studies
  0 active runs, 0 completed runs
```

No mention of the investigation I just created. I had to grep the schema
to confirm it was even being validated. This is a minor but real
"is anything happening?" moment.

**Recommendation:** Add `N investigations` (and ideally a per-investigation
validity check) to the lint summary.

## 9. `workspace.yaml.j2` has no inline hints

The rendered workspace.yaml looks like:

```yaml
observables: []
visualizations: []
simulations: []
datasets: []
```

Four empty arrays, no comment hinting that these are populated by the
dashboard (Registry → Install, Investigations tab → Add observable, etc.).
A new operator opening workspace.yaml sees an empty config and doesn't
know whether to hand-edit or let the dashboard write to it.

**Recommendation:** Either inline `# populated by the dashboard's <tab>
tab` comments per field, or have NEXT_STEPS.md cross-reference the
workspace.yaml schema. Right now there's no on-ramp from "blank config"
to "first useful entry."

## 10. The user's framing — "pbg-superpowers style repo" — was ambiguous

The user said "make this into a pbg-superpowers style repo." Even with
strong domain context, that phrase had at least three plausible reads:

1. Overlay workspace files on this repo (in-place).
2. Make a sibling workspace repo that depends on this one (upstream).
3. Add the superpowers skills to this repo.

I asked the user to disambiguate. **A clearer vocabulary in the
pbg-superpowers README ("workspace" = the dashboard-driveable thing;
"composite" = the model-code package; a workspace can wrap or live
beside one or more composites) would have made the question
self-answering.** The README does mention "workspace" but doesn't
contrast it with "composite-only repos like pbg-mem3dg" — and that
contrast is precisely where new users land.

## 11. The pre-existing `.github/` and `.claude/` directories were empty stubs

The composite repo had `.github/` and (no `.claude/`) on disk but
`git ls-files .github/` returned empty — the dir was untracked.
Useful to verify with `git ls-files` before assuming "this dir already
has content."

## What worked well (so the next agent doesn't break it)

- The sed-based rendering loop from `template-init.sh` is portable and
  obvious. Variable list is small (4 vars). Easy to copy into an
  in-place implementation.
- `.pbg/schemas/` JSON-schemas are well-structured and the lint catches
  shape errors immediately. The investigation I wrote validated on the
  first try because the schema docstrings were precise.
- `python -m pbg_superpowers.workspace_catalog add …` is idempotent and
  outputs a single JSON line — trivially scriptable.
- `python3 scripts/lint-workspace.py` printing `workspace lint: OK` is a
  great single-line signal of "you're done."

## Summary recommendations, ranked

1. **Implement `scaffold.py --in-place`** so this whole document becomes
   obsolete except for the conflict-set table.
2. **Add a decision tree** to the top of `/pbg-workspace` SKILL.md
   (standalone / upstream-branch / in-place).
3. **Encode the merge-vs-skip-vs-copy table** (§5 above) into the
   scaffolder, not into prose.
4. **Wire vivarium-dashboard auto-pin** into the in-place path.
5. **Lint summary should mention investigations.**
6. **Inline comments in `workspace.yaml.j2`** pointing at dashboard tabs.
7. **README contrast** between "workspace" and "composite-only" repos.
