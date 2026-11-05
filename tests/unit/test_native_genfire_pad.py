"""Unit tests for GENFIRE square/even projection padding."""

import numpy as np

from et_dflow.infrastructure.algorithms.native_genfire import (
    _coerce_oversampling_ratio,
    _pad_square_projections,
)


def test_pad_square_forces_even_side_for_odd_detector():
    # sm70-like: (n_tilts, 512, 513) → must become even square (514, 514, n)
    stack = np.ones((3, 512, 513), dtype=np.float32)
    out = _pad_square_projections(stack)
    assert out.shape == (514, 514, 3)
    assert out.dtype == np.float32
    # Center-placed content preserved
    assert float(out[1:513, 0:513, 0].sum()) == float(stack[0].sum())


def test_pad_square_keeps_even_side():
    stack = np.ones((2, 64, 64), dtype=np.float32)
    out = _pad_square_projections(stack)
    assert out.shape == (64, 64, 2)


def test_coerce_oversampling_ratio_int_for_whole_numbers():
    assert _coerce_oversampling_ratio(1) == 1
    assert _coerce_oversampling_ratio(1.0) == 1
    assert isinstance(_coerce_oversampling_ratio(2), int)


def test_coerce_oversampling_ratio_int_pad_for_fractional():
    ratio = _coerce_oversampling_ratio(1.5)
    # Mimic GENFIRE: paddedDim = dims[0] * oversamplingRatio
    assert 512 * ratio == 768
    assert np.int64(512) * ratio == 768
    assert isinstance(512 * ratio, int)
    nc_big = (512 * ratio) // 2
    assert isinstance(nc_big, int)
    assert nc_big == 384
