import numpy as np
from scipy import ndimage
from typing import Dict, Any


def remove_bad_pixels(signal, params: Dict[str, Any]):
    """Remove bad pixels (median filter). (signal, params) -> signal."""
    method = params.get("method", "median_filter")
    data = np.asarray(signal.data).copy()
    if method == "median_filter":
        size = params.get("size", 3)
        for i in range(data.shape[0]):
            data[i] = ndimage.median_filter(data[i], size=size)
    out = signal.deepcopy()
    out.data = data
    return out
