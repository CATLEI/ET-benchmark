"""
Algorithm domain logic.

Contains algorithm base classes, strategy pattern, and registry.
"""

from et_dflow.domain.algorithms.wbp import WBPAlgorithm
from et_dflow.domain.algorithms.registry import get_algorithm_registry

# Register algorithms
_registry = get_algorithm_registry()
_registry.register("wbp", WBPAlgorithm)

