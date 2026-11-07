"""CPU checks for DART and TVR-DART helpers. No ASTRA or TIGRE import."""

import numpy as np
import pytest

from et_dflow.infrastructure.algorithms.native_dart import (
    boundary_mask,
    free_pixel_mask,
    segment_nearest,
    sirt_run_count,
    slice_sinograms,
    stack_slices,
    validate_gray_levels,
)
from et_dflow.infrastructure.algorithms.native_tvm import asd_pocs_call_args
from et_dflow.infrastructure.algorithms.native_tvr_dart import (
    estimate_row_range,
    huber_grad,
    huber_value,
    soft_segment,
    soft_segment_dx,
    validate_n_gray,
)


def test_sirt_run_count_matches_astra_sweep_semantics():
    assert sirt_run_count("SIRT_CUDA", sweeps=5, n_angles=141) == 5
    assert sirt_run_count("SART_CUDA", sweeps=5, n_angles=141) == 5 * 141


def test_sirt_run_count_rejects_unknown_method():
    with pytest.raises(ValueError):
        sirt_run_count("CGLS_CUDA", sweeps=1, n_angles=4)


def test_gray_levels_are_required_unique_and_sorted():
    levels = validate_gray_levels({"dart_gray_levels": [2.0, 0.0, 1.0]})
    assert levels.tolist() == [0.0, 1.0, 2.0]
    with pytest.raises(ValueError):
        validate_gray_levels({})
    with pytest.raises(ValueError):
        validate_gray_levels({"dart_gray_levels": []})
    with pytest.raises(ValueError):
        validate_gray_levels({"dart_gray_levels": [1.0]})
    with pytest.raises(ValueError):
        validate_gray_levels({"dart_gray_levels": [1.0, 1.0]})


def test_segment_nearest_uses_midpoint_thresholds():
    image = np.array([[0.1, 0.49], [0.51, 2.0]])
    labels = segment_nearest(image, np.array([0.0, 1.0]))
    assert labels.tolist() == [[0.0, 0.0], [1.0, 1.0]]


def test_boundary_is_eight_connected_by_default():
    labels = np.zeros((3, 3))
    labels[1, 1] = 1.0
    edges = boundary_mask(labels, connectivity=8)
    assert edges.all()
    cross = boundary_mask(labels, connectivity=4)
    assert cross[1, 1] and cross[0, 1] and cross[1, 0]
    assert not cross[0, 0]


def test_random_zero_frees_only_the_boundary_and_seed_is_stable():
    labels = np.zeros((16, 16))
    labels[:, 8:] = 1.0
    boundary = boundary_mask(labels, connectivity=8)
    free = free_pixel_mask(labels, random_fraction=0.0, seed=0, connectivity=8)
    assert np.array_equal(free, boundary)
    again = free_pixel_mask(labels, random_fraction=0.4, seed=3, connectivity=8)
    same = free_pixel_mask(labels, random_fraction=0.4, seed=3, connectivity=8)
    assert np.array_equal(again, same)
    other = free_pixel_mask(labels, random_fraction=0.4, seed=4, connectivity=8)
    assert not np.array_equal(again, other)


def test_slice_layout_matches_astra_sirt_volume():
    proj = np.zeros((141, 512, 513))
    rows = slice_sinograms(proj)
    assert rows.shape == (512, 141, 513)
    volume = stack_slices([np.zeros((513, 513)) for _ in range(512)])
    assert volume.shape == (512, 513, 513)


def test_asd_pocs_kwargs_omit_ossart_tvlambda():
    niter, kwargs = asd_pocs_call_args({})
    assert niter == 50
    assert kwargs == {"tviter": 20}
    assert "tvlambda" not in kwargs
    niter, kwargs = asd_pocs_call_args({"tvm_niter": 3, "tvm_alpha": 0.01})
    assert niter == 3
    assert kwargs["alpha"] == 0.01
    assert "maxl2err" not in kwargs


def test_n_gray_is_required():
    assert validate_n_gray({"tvr_n_gray": 3}) == 3
    with pytest.raises(ValueError):
        validate_n_gray({})
    with pytest.raises(ValueError):
        validate_n_gray({"tvr_n_gray": 1})


def test_soft_segment_derivative_matches_central_differences():
    rho = [0.0, 0.4, 1.0]
    gain = [4.0, 6.0]
    latent = np.linspace(-0.2, 1.2, 9).reshape(3, 3)
    analytic = soft_segment_dx(latent, rho, gain)
    step = 1e-6
    numeric = (
        soft_segment(latent + step, rho, gain) - soft_segment(latent - step, rho, gain)
    ) / (2.0 * step)
    scale = max(float(np.max(np.abs(analytic))), 1e-8)
    assert float(np.max(np.abs(numeric - analytic))) / scale < 1e-4


def test_huber_scalar_and_gradient():
    epsilon = 1e-4
    # One row, so the only nonzero forward difference is horizontal.
    small = np.zeros((1, 2))
    small[0, 1] = 1e-5
    magnitude = 1e-5
    assert huber_value(small, epsilon) == pytest.approx(magnitude**2 / (2.0 * epsilon))

    large = np.zeros((1, 2))
    large[0, 1] = 1.0
    assert huber_value(large, epsilon) == pytest.approx(1.0 - epsilon / 2.0)

    image = np.array(
        [[0.0, 0.2, -0.1], [0.05, 1.0, 0.0], [-0.3, 0.4, 0.7]], dtype=np.float64
    )
    analytic = huber_grad(image, epsilon)
    step = 1e-6
    numeric = np.zeros_like(image)
    for index in np.ndindex(image.shape):
        plus = image.copy()
        minus = image.copy()
        plus[index] += step
        minus[index] -= step
        numeric[index] = (huber_value(plus, epsilon) - huber_value(minus, epsilon)) / (
            2.0 * step
        )
    scale = max(float(np.max(np.abs(analytic))), 1e-8)
    assert float(np.max(np.abs(numeric - analytic))) / scale < 1e-4


def test_estimate_rows_follow_the_peak_and_an_override():
    volume = np.zeros((5, 2, 2))
    volume[0] = 1.0
    assert estimate_row_range(volume) == (0, 1)
    volume[3] = 4.0
    assert estimate_row_range(volume) == (2, 4)
    assert estimate_row_range(volume, [4, 1]) == (1, 4)
