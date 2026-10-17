"""Axis layout between tilt series and ASTRA parallel3d projection data."""

import numpy as np

from et_dflow.infrastructure.algorithms.native_astra import (
    apply_parallel_fbp_filter,
    tilt_series_to_astra_sino,
)


def test_tilt_series_to_astra_sino_moves_angles_to_axis_1():
    proj = np.arange(8 * 16 * 16, dtype=np.float32).reshape(8, 16, 16)
    sino = tilt_series_to_astra_sino(proj)
    assert sino.shape == (16, 8, 16)
    assert sino.flags.c_contiguous
    np.testing.assert_array_equal(sino[:, 3, :], proj[3])


def test_ramp_filter_keeps_shape_and_zeros():
    zeros = np.zeros((2, 4, 8), dtype=np.float32)
    out = apply_parallel_fbp_filter(zeros, "ram-lak")
    assert out.shape == zeros.shape
    assert out.flags.c_contiguous
    assert np.max(np.abs(out)) < 1e-6
    ones = np.ones_like(zeros)
    filtered = apply_parallel_fbp_filter(ones, "ramp")
    assert filtered.shape == ones.shape
    assert not np.allclose(filtered, ones)
