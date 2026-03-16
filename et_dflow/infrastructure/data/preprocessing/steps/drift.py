from typing import Dict, Any
from et_dflow.infrastructure.data.preprocessing.registry import get


def correct_drift(signal, params: Dict[str, Any]):
    """Drift correction by reusing alignment. (signal, params) -> signal."""
    method = params.get("method", "cross_correlation")
    align_fn = get("alignment", method)
    if align_fn:
        return align_fn(signal, params)
    return signal.deepcopy()
