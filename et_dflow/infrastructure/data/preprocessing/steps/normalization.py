import numpy as np
from typing import Dict, Any

def normalize(signal, params):
    data = signal.data.copy()
    out_data = np.zeros_like(data)
    for i in range(data.shape[0]):
        img = data[i]
        lo, hi = img.min(), img.max()
        if hi > lo:
            out_data[i] = (img - lo) / (hi - lo)
        else:
            out_data[i] = img
    out = signal.deepcopy()
    out.data = out_data
    return out
