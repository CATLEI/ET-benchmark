"""Unit tests for DeepDeWedge subtomo sizing helpers (no hyperspy/ddw required)."""

from __future__ import annotations

import math

from et_dflow.infrastructure.algorithms.native_deepdewedge import (
    _ddw_enlarged_subtomo_size,
    _extract_larger_subtomos_for_volume,
    _subtomo_grid_count,
    _subtomo_size_for_volume,
)


def test_enlarged_subtomo_size_matches_ddw_sqrt2_even_ceil():
    # Official enlarge path: ceil_even(sqrt(2) * 64) == 92
    assert _ddw_enlarged_subtomo_size(64) == 92
    assert _ddw_enlarged_subtomo_size(96) == int(
        math.ceil((math.sqrt(2) * 96) / 2.0) * 2
    )


def test_vesicle_64_clamps_and_disables_enlarge():
    shape = (64, 64, 64)
    size = _subtomo_size_for_volume(shape, {})
    assert size == 64
    assert _extract_larger_subtomos_for_volume(shape, size, {}) is False
    assert _subtomo_grid_count(shape, size, size) == 1


def test_sm70_keeps_enlarge_for_default_96():
    shape = (512, 512, 512)
    size = _subtomo_size_for_volume(shape, {})
    assert size == 96
    assert _ddw_enlarged_subtomo_size(size) <= 512
    assert _extract_larger_subtomos_for_volume(shape, size, {}) is True


def test_extract_larger_override():
    shape = (64, 64, 64)
    assert (
        _extract_larger_subtomos_for_volume(
            shape, 64, {"ddw_extract_larger_subtomos_for_rotating": True}
        )
        is True
    )
