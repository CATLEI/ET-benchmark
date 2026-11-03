"""Unit tests for GENFIRE square/even projection padding."""

import numpy as np

from et_dflow.infrastructure.algorithms.native_genfire import _pad_square_projections


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
