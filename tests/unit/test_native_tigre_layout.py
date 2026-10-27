"""Detector axis layout for TIGRE parallel-beam adapter."""

import numpy as np

from et_dflow.infrastructure.algorithms.native_tigre import tigre_n_detector_from_proj_hw


def test_n_detector_matches_proj_hw_for_ax_broadcast():
    # Non-square SM70-like frames: (n_tilts, H=512, W=513)
    n_det = tigre_n_detector_from_proj_hw(512, 513)
    assert n_det.tolist() == [512, 513]
    # Simulated Ax layout (n_angles, nDetector[0], nDetector[1])
    ax_shape = (141, int(n_det[0]), int(n_det[1]))
    proj_shape = (141, 512, 513)
    assert ax_shape == proj_shape


def test_n_detector_dtype():
    n_det = tigre_n_detector_from_proj_hw(16, 32)
    assert n_det.dtype == np.int32
    assert n_det.shape == (2,)
