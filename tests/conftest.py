"""Skip mem3dg/readdy-backend tests when the compiled backend is unavailable.

viva-membrane-actin wraps pymem3dg (needs system netcdf-cxx4) and readdy — heavy
compiled backends a vanilla GitHub runner cannot build, so they live in the
optional `sim` extra and CI does not install them. Skip the tests that need them
(they run in the repo's Docker image) with a clear notice, instead of failing.
"""
from __future__ import annotations
try:
    import pymem3dg  # noqa: F401 — mem3dg C++ backend
    _HAVE_BACKEND = True
except Exception:  # noqa: BLE001
    _HAVE_BACKEND = False
_BACKEND_TEST_MODULES = ["test_adapters.py", "test_assembly.py", "test_run.py"]
collect_ignore = [] if _HAVE_BACKEND else list(_BACKEND_TEST_MODULES)
def pytest_configure(config):
    if not _HAVE_BACKEND:
        config.issue_config_time_warning(
            __import__("pytest").PytestConfigWarning(
                "pymem3dg/readdy backend unavailable — skipping "
                f"{len(_BACKEND_TEST_MODULES)} backend test module(s); run them "
                "in the repo's Docker image. Backend-free checks still run."),
            stacklevel=1)
