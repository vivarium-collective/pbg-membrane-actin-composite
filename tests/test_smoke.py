"""Backend-free smoke check: the workspace manifest is present and parseable.

Guarantees workspace-ci collects at least one test even when the heavy compiled
backend (pymem3dg/readdy) is absent and the solver tests are skipped.
"""
from pathlib import Path


def test_workspace_manifest_present():
    root = Path(__file__).resolve().parent.parent
    assert (root / "workspace.yaml").is_file(), "workspace.yaml missing at repo root"
