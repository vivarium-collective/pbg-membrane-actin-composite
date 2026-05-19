"""pbg-membrane-actin-composite: Brownian-ratchet coupling of pbg-mem3dg + pbg-readdy."""

from .core import build_core
from .document import build_document
from .processes import BrownianRatchetCoupler

# Eagerly import composites and visualizations subpackages so their
# @composite_generator decorators and Visualization classes register
# at top-level import time. The dashboard imports this top-level
# package via importlib.import_module(pkg); without these imports,
# the decorators never fire and the registry stays empty.
from . import composites  # noqa: F401  — side-effect: @composite_generator registration
from . import visualizations  # noqa: F401  — side-effect: Visualization subclass registration

__all__ = ['BrownianRatchetCoupler', 'build_core', 'build_document']
