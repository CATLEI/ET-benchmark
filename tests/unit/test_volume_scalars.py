"""Unit tests for volume scalar metrics and chain registration."""

import numpy as np
import hyperspy.api as hs
import pytest

from et_dflow.core.models import AlgorithmResult
from et_dflow.domain.evaluation.chain import build_evaluation_chain
from et_dflow.domain.evaluation.metrics.fsc import fsc_resolution_pixels
from et_dflow.domain.evaluation.metrics.volume_scalars import (
    edge_rise_pixels,
    elongation_ratio,
    pearson_r2,
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


def test_elongation_z_stretched_above_one():
    shape = (64, 64, 64)
    center = (32, 32, 32)
    gt = _ball(shape, center, 8).astype(np.float64)
    recon = _ellipsoid(shape, center, (16, 8, 8)).astype(np.float64)
    value = elongation_ratio(recon, gt)
    assert value is not None
    assert value > 1.0


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
        ["psnr", "ssim", "mse", "r2", "elongation", "fsc_resolution_px", "edge_rise_px"]
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
