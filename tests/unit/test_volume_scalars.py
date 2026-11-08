"""Unit tests for volume scalar metrics and chain registration."""

import numpy as np
import hyperspy.api as hs
import pytest

from et_dflow.core.models import AlgorithmResult
from et_dflow.domain.evaluation.chain import build_evaluation_chain
from et_dflow.domain.evaluation.metrics.fsc import fsc_resolution_pixels
from et_dflow.domain.evaluation.metrics.volume_scalars import (
    dice_coefficient,
    edge_rise_pixels,
    elongation_ratio,
    hausdorff95_px,
    pearson_r2,
    percolation_mismatch,
    porosity_abs_error,
    psd_wasserstein_px,
    ssa_rel_error,
    void_cc_fraction_abs_error,
)


def _ball(shape, center, radius):
    zz, yy, xx = np.ogrid[: shape[0], : shape[1], : shape[2]]
    return ((zz - center[0]) ** 2 + (yy - center[1]) ** 2 + (xx - center[2]) ** 2) <= radius**2


def _ellipsoid(shape, center, radii):
    zz, yy, xx = np.ogrid[: shape[0], : shape[1], : shape[2]]
    return (
        ((zz - center[0]) / radii[0]) ** 2
        + ((yy - center[1]) / radii[1]) ** 2
        + ((xx - center[2]) / radii[2]) ** 2
    ) <= 1.0


def test_pearson_r2_identical_is_one():
    gt = np.random.default_rng(0).normal(size=(16, 16, 16))
    assert pearson_r2(gt, gt) == pytest.approx(1.0)


def test_pearson_r2_affine_invariant():
    gt = np.random.default_rng(1).normal(size=(12, 12, 12))
    recon = 2.5 * gt + 7.0
    assert pearson_r2(recon, gt) == pytest.approx(1.0)


def test_pearson_r2_constant_returns_none():
    gt = np.random.default_rng(2).normal(size=(8, 8, 8))
    assert pearson_r2(np.ones_like(gt), gt) is None


def test_pearson_r2_shape_mismatch_returns_none():
    assert pearson_r2(np.zeros((4, 4, 4)), np.zeros((5, 5, 5))) is None


def test_elongation_identical_is_one():
    shape = (48, 48, 48)
    center = (24, 24, 24)
    vol = _ball(shape, center, 10).astype(np.float64)
    assert elongation_ratio(vol, vol) == pytest.approx(1.0, abs=1e-6)


def test_elongation_binary_plateau_is_finite():
    """Simulated porous GT is often 0/255; percentile-90 masks used to be empty."""
    shape = (32, 32, 32)
    gt = np.zeros(shape, dtype=np.float64)
    gt[8:24, 8:24, 8:24] = 255.0
    assert elongation_ratio(gt, gt) == pytest.approx(1.0, abs=1e-6)


def test_elongation_z_stretched_above_one():
    shape = (64, 64, 64)
    center = (32, 32, 32)
    gt = _ball(shape, center, 8).astype(np.float64)
    recon = _ellipsoid(shape, center, (16, 8, 8)).astype(np.float64)
    value = elongation_ratio(recon, gt)
    assert value is not None
    assert value > 1.0


def test_dice_identical_is_one():
    shape = (24, 24, 24)
    gt = _ball(shape, (12, 12, 12), 6).astype(np.float64) * 255.0
    assert dice_coefficient(gt, gt) == pytest.approx(1.0)


def test_dice_disjoint_near_zero():
    shape = (32, 32, 32)
    gt = _ball(shape, (8, 8, 8), 4).astype(np.float64) * 255.0
    recon = _ball(shape, (24, 24, 24), 4).astype(np.float64) * 255.0
    assert dice_coefficient(recon, gt) == pytest.approx(0.0)


def test_hausdorff95_identical_is_zero():
    shape = (24, 24, 24)
    gt = _ball(shape, (12, 12, 12), 5).astype(np.float64) * 255.0
    assert hausdorff95_px(gt, gt) == pytest.approx(0.0, abs=1e-6)


def test_porosity_abs_error_identical_is_zero():
    shape = (20, 20, 20)
    gt = _ball(shape, (10, 10, 10), 5).astype(np.float64) * 255.0
    assert porosity_abs_error(gt, gt) == pytest.approx(0.0)


def _porous_slab(shape, pore_radius):
    """Solid fill with a spherical pore (void) in the center."""
    vol = np.ones(shape, dtype=np.float64) * 255.0
    center = tuple(s // 2 for s in shape)
    vol[_ball(shape, center, pore_radius)] = 0.0
    return vol


def test_psd_wasserstein_identical_is_zero():
    gt = _porous_slab((32, 32, 32), 6)
    assert psd_wasserstein_px(gt, gt) == pytest.approx(0.0, abs=1e-9)


def test_psd_wasserstein_larger_pore_is_positive():
    gt = _porous_slab((40, 40, 40), 5)
    recon = _porous_slab((40, 40, 40), 10)
    value = psd_wasserstein_px(recon, gt)
    assert value is not None
    assert value > 0.0


def test_ssa_rel_error_identical_is_zero():
    gt = _porous_slab((28, 28, 28), 5)
    assert ssa_rel_error(gt, gt) == pytest.approx(0.0)


def test_void_cc_fraction_identical_is_zero():
    gt = _porous_slab((28, 28, 28), 5)
    assert void_cc_fraction_abs_error(gt, gt) == pytest.approx(0.0)


def test_percolation_mismatch_identical_is_zero():
    # Open channel along z through a solid volume.
    shape = (24, 24, 24)
    gt = np.ones(shape, dtype=np.float64) * 255.0
    gt[:, 10:14, 10:14] = 0.0
    assert percolation_mismatch(gt, gt) == pytest.approx(0.0)


def test_percolation_mismatch_blocked_channel():
    shape = (24, 24, 24)
    gt = np.ones(shape, dtype=np.float64) * 255.0
    gt[:, 10:14, 10:14] = 0.0
    recon = gt.copy()
    recon[12, 10:14, 10:14] = 255.0  # plug the channel
    value = percolation_mismatch(recon, gt)
    assert value is not None
    assert value > 0.0


def test_edge_rise_px_matches_constructed_width():
    # 1D-like ramp along x through a 3D slab: intensity goes 0 -> 1 over 10 voxels.
    size = 64
    x = np.arange(size, dtype=np.float64)
    ramp = np.clip((x - 20.0) / 10.0, 0.0, 1.0)
    volume = np.broadcast_to(ramp, (16, 16, size)).copy()
    # Ground truth has a sharp step so the steepest gradient sits at the ramp center.
    gt = np.zeros_like(volume)
    gt[..., 25:] = 1.0
    rise = edge_rise_pixels(volume, gt)
    assert rise is not None
    assert rise == pytest.approx(8.0, abs=1.5)


def test_fsc_resolution_px_identical_is_finite_positive():
    rng = np.random.default_rng(3)
    vol = rng.normal(size=(24, 24, 24))
    value = fsc_resolution_pixels(vol, vol)
    assert value is not None
    assert value > 0.0
    assert np.isfinite(value)


def test_chain_registers_new_metrics():
    shape = (32, 32, 32)
    center = (16, 16, 16)
    gt_arr = _ball(shape, center, 6).astype(np.float64)
    recon_arr = gt_arr.copy()
    gt = hs.signals.Signal2D(gt_arr)
    recon = hs.signals.Signal2D(recon_arr)
    result = AlgorithmResult(
        reconstruction=recon,
        execution_time=0.0,
        memory_usage=0.0,
        metadata={},
        algorithm_name="test",
    )
    chain = build_evaluation_chain(
        [
            "psnr",
            "ssim",
            "mse",
            "r2",
            "elongation",
            "fsc_resolution_px",
            "edge_rise_px",
            "dice",
            "hausdorff95_px",
            "porosity_abs_error",
            "psd_wasserstein_px",
            "ssa_rel_error",
            "void_cc_fraction_abs_error",
            "percolation_mismatch",
        ]
    )
    assert chain is not None
    metrics = chain.process(result, gt)
    assert "r2" in metrics
    assert metrics["r2"] == pytest.approx(1.0)
    assert "elongation" in metrics
    assert metrics["elongation"] == pytest.approx(1.0, abs=1e-6)
    assert "fsc_resolution_px" in metrics
    assert metrics["fsc_resolution_px"] > 0.0
    # Identical sharp ball may not produce a 10–90 rise; key may be absent.
    assert "edge_rise_px" not in metrics or metrics["edge_rise_px"] > 0.0
    assert metrics["dice"] == pytest.approx(1.0)
    assert metrics["hausdorff95_px"] == pytest.approx(0.0, abs=1e-6)
    assert metrics["porosity_abs_error"] == pytest.approx(0.0)
    assert metrics["psd_wasserstein_px"] == pytest.approx(0.0, abs=1e-9)
    assert metrics["ssa_rel_error"] == pytest.approx(0.0)
    assert metrics["void_cc_fraction_abs_error"] == pytest.approx(0.0)
    assert metrics["percolation_mismatch"] == pytest.approx(0.0)
