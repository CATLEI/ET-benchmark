"""
Preprocessing step registry.

Maps step_name (and optional method) to callable (signal, params) -> signal.
Supports steps with a single implementation (e.g. downsample) or multiple
methods (e.g. alignment: cross_correlation, centroid, tilt_axis).
"""

from typing import Dict, Any, Callable, Optional

# step_name -> callable (no method) or step_name -> {method -> callable}
_REGISTRY: Dict[str, Any] = {}
_DEFAULT_METHODS: Dict[str, str] = {}  # step_name -> default method name


def register(
    step_name: str,
    step_fn: Callable,
    method: Optional[str] = None,
    default: bool = False,
) -> None:
    """
    Register a preprocessing step.

    Args:
        step_name: Step identifier (e.g. 'alignment', 'downsample').
        step_fn: Callable(signal, params) -> signal.
        method: Method name for this step (e.g. 'cross_correlation').
                 If None, step has a single implementation.
        default: If True, set as default method when step_name has multiple methods.
    """
    if method is None:
        _REGISTRY[step_name] = step_fn
        return
    if step_name not in _REGISTRY:
        _REGISTRY[step_name] = {}
    _REGISTRY[step_name][method] = step_fn
    if default:
        _DEFAULT_METHODS[step_name] = method


def get(
    step_name: str,
    method: Optional[str] = None,
) -> Optional[Callable]:
    """
    Get step implementation.

    Args:
        step_name: Step identifier.
        method: Method name. If step has multiple methods and method is None,
                use default for that step.

    Returns:
        Callable(signal, params) -> signal, or None if not found.
    """
    impl = _REGISTRY.get(step_name)
    if impl is None:
        return None
    if callable(impl):
        return impl
    if isinstance(impl, dict):
        m = method or _DEFAULT_METHODS.get(step_name)
        if m is None and impl:
            m = next(iter(impl.keys()))
        return impl.get(m) if m else None
    return None


def has_step(step_name: str, method: Optional[str] = None) -> bool:
    """Return True if step_name (and optional method) is registered."""
    return get(step_name, method) is not None


def list_steps() -> Dict[str, Any]:
    """Return copy of registry (step_name -> callable or {method -> callable})."""
    return dict(_REGISTRY)
