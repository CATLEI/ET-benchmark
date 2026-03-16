"""
Data preprocessing implementation.

Provides comprehensive data preprocessing for ET tilt series.
"""

import os
from typing import List, Optional, Tuple, Dict, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.core.interfaces import IPreprocessor
from et_dflow.core.exceptions import DataError

# Populate registry with all step implementations
def _ensure_registry_loaded():
    try:
        from et_dflow.infrastructure.data.preprocessing import steps  # noqa: F401
    except Exception:
        pass


def _run_step(step_name: str, step_params: Dict[str, Any], signal: Signal) -> Signal:
    """Execute a single step via registry or legacy fallback."""
    _ensure_registry_loaded()
    from et_dflow.infrastructure.data.preprocessing.registry import get
    methods = step_params.get("methods")
    if isinstance(methods, list):
        current = signal
        for m in methods:
            method = m if isinstance(m, str) else str(m)
            fn = get(step_name, method=method)
            if fn is None:
                raise DataError(
                    f"Unknown method '{method}' for step '{step_name}'",
                    details={"step": step_name, "method": method}
                )
            current = fn(current, step_params)
        return current
    method = step_params.get("method")
    fn = get(step_name, method=method)
    if fn is not None:
        return fn(signal, step_params)
    raise DataError(
        f"Unknown preprocessing step: {step_name}",
        details={"step": step_name}
    )


def normalize_preprocessing_steps(
    steps: Optional[List[Union[str, Dict[str, Any]]]]
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Normalize preprocessing steps to a list of (name, params).

    Accepts:
        - List of strings: ["alignment", "normalization"] -> [("alignment", {}), ...]
        - List of dicts: [{"name": "alignment", "params": {"method": "cc"}}] or
          [{"name": "alignment", "method": "cc"}] (kwargs merged into params)

    Returns:
        List of (step_name, step_params).
    """
    if not steps:
        return []
    result = []
    for item in steps:
        if isinstance(item, str):
            result.append((item, {}))
        elif isinstance(item, dict):
            name = item.get("name")
            if not name:
                raise DataError(
                    "Preprocessing step dict must have 'name'",
                    details={"item": item}
                )
            params = dict(item.get("params", {}))
            for k, v in item.items():
                if k not in ("name", "params"):
                    params[k] = v
            result.append((name, params))
        else:
            raise DataError(
                f"Preprocessing step must be str or dict, got {type(item)}",
                details={"item": item}
            )
    return result


class DataPreprocessor(IPreprocessor):
    """
    Comprehensive data preprocessing for ET data.
    
    Handles:
    - Alignment
    - Contrast normalization
    - Bad pixel removal
    - Drift correction
    """
    
    def preprocess(
        self,
        tilt_series: Signal,
        steps: Optional[List[Union[str, Dict[str, Any]]]] = None,
        save_after_steps: Optional[List[str]] = None,
        save_dir: Optional[str] = None,
    ):
        """
        Apply preprocessing steps.

        Args:
            tilt_series: Input tilt series
            steps: List of step names (str) or step descriptors (dict with
                   'name' and optional 'params' / kwargs). If None, apply
                   default steps.
            save_after_steps: If set, save signal after each of these step names.
            save_dir: Directory to write intermediate artifacts (required if save_after_steps).

        Returns:
            If save_after_steps is None: processed Signal.
            Else: (processed_signal, intermediates_dict) where intermediates_dict
                  maps step_name -> path to saved .hspy file.
        """
        if steps is None:
            steps = ["alignment", "normalization", "bad_pixels", "drift"]
        normalized = normalize_preprocessing_steps(steps)
        save_after = (save_after_steps or []) if save_after_steps else []
        intermediates: Dict[str, str] = {}
        if save_after and save_dir:
            os.makedirs(save_dir, exist_ok=True)

        processed = tilt_series.deepcopy()

        try:
            for step_name, step_params in normalized:
                processed = _run_step(step_name, step_params, processed)
                if step_name in save_after and save_dir:
                    path = os.path.join(save_dir, f"after_{step_name}.hspy")
                    processed.save(path)
                    intermediates[step_name] = path

            processed.metadata.set_item(
                "preprocessing_steps",
                [name for name, _ in normalized]
            )
            if save_after and save_dir:
                return processed, intermediates
            return processed
        except DataError:
            raise
        except Exception as e:
            raise DataError(
                f"Error during preprocessing: {e}",
                details={"error": str(e), "steps": normalized}
            ) from e

