"""
Adapters: (signal, params) -> signal for pipeline integration.

Hyperspy tilt series signal.data is (N, H, W). User functions use (H, W, N) or (N, H, W).
"""

from typing import Dict, Any
import numpy as np


def _signal_to_hwn(signal):
    """(N, H, W) -> (H, W, N)."""
    data = np.asarray(signal.data)
    if data.ndim != 3:
        raise ValueError(f"Expected 3D tilt series, got shape {data.shape}")
    return np.transpose(data, (1, 2, 0))


def _hwn_to_signal(signal, data_hwn):
    """(H, W, N) -> (N, H, W) and set signal.data."""
    data_nhw = np.transpose(np.asarray(data_hwn), (2, 0, 1))
    out = signal.deepcopy()
    out.data = data_nhw
    return out


def _get_tilt_angles(signal, params):
    """Extract tilt angles from signal metadata or params."""
    angles = params.get("tilt_angles")
    if angles is not None:
        return np.asarray(angles)
    if hasattr(signal, "axes_manager") and signal.axes_manager is not None:
        nav = signal.axes_manager.navigation_axes
        if len(nav) >= 1 and hasattr(nav[0], "axis"):
            return np.array(nav[0].axis)
    return None


def align_cross_correlation(signal, params: Dict[str, Any]):
    from et_dflow.infrastructure.data.preprocessing.steps.alignment.cross_correlation import (
        cross_correlation_align,
    )
    data_hwn = _signal_to_hwn(signal)
    tilt_angles = _get_tilt_angles(signal, params)
    result, _offsets, _ref = cross_correlation_align(data_hwn, tilt_angles)
    return _hwn_to_signal(signal, result)


def align_center_of_mass(signal, params: Dict[str, Any]):
    from et_dflow.infrastructure.data.preprocessing.steps.alignment.center_of_mass import (
        center_of_mass_align,
    )
    data_hwn = _signal_to_hwn(signal)
    result, _offsets = center_of_mass_align(data_hwn)
    return _hwn_to_signal(signal, result)


def align_axis_shift(signal, params: Dict[str, Any]):
    from et_dflow.infrastructure.data.preprocessing.steps.alignment.axis_shift import (
        axis_shift_align,
    )
    data = np.asarray(signal.data)  # (N, H, W)
    angles = _get_tilt_angles(signal, params)
    if angles is None:
        angles = np.linspace(0, 180, data.shape[0])
    shift_range = params.get("shift_range", 20)
    num_slices = params.get("numberOfSlices", params.get("num_slices", 5))
    result, _best_shift = axis_shift_align(
        data, angles, shift_range=shift_range, numberOfSlices=num_slices, show=False
    )
    out = signal.deepcopy()
    out.data = np.asarray(result)
    return out


def align_tilts_rotation(signal, params: Dict[str, Any]):
    from et_dflow.infrastructure.data.preprocessing.steps.alignment.tilts_rotation import (
        tilt_axis_rotation_align,
    )
    data_hwn = _signal_to_hwn(signal)
    result, _rot_ang = tilt_axis_rotation_align(data_hwn)
    return _hwn_to_signal(signal, result)
