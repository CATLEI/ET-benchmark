"""Unit tests for protocol bypass metrics (not wired into chain)."""

from __future__ import annotations

import numpy as np

from et_dflow.domain.evaluation.metrics.protocol_bypass import (
    affine_aligned_ssim_cc,
    affine_intensity_align,
    compute_protocol_metrics,
    fsc_curve_protocol,
    missing_wedge_mask,
    pearson_cc,
    wedge_in_out_cc,
)


def test_affine_align_recovers_scale_offset():
    rng = np.random.default_rng(0)
    gt = rng.normal(size=(16, 16, 16))
    recon = 2.5 * gt - 7.0
    aligned, a, b = affine_intensity_align(recon, gt)
    assert abs(a - 0.4) < 1e-6  # inverse of 2.5
    assert abs(b - 2.8) < 1e-5  # 7/2.5
    assert pearson_cc(aligned, gt) > 0.999


def test_affine_aligned_keys_on_identical():
    vol = np.ones((12, 12, 12), dtype=np.float64)
    vol[4:8, 4:8, 4:8] = 2.0
    out = affine_aligned_ssim_cc(vol, vol)
    assert out["protocol_affine_cc"] > 0.999
    assert "protocol_affine_ssim" in out


def test_missing_wedge_mask_has_interior():
    mask = missing_wedge_mask((32, 32, 32), -70.0, 70.0, tilt_axis="y")
    assert mask.dtype == bool
    assert mask.any()
    assert (~mask).any()


def test_wedge_in_out_cc_perfect_match():
    rng = np.random.default_rng(1)
    gt = rng.normal(size=(24, 24, 24))
    metrics = wedge_in_out_cc(gt, gt, -70.0, 70.0)
    assert metrics["protocol_wedge_out_cc"] > 0.99
    assert metrics["protocol_wedge_in_cc"] > 0.99
    assert abs(metrics["protocol_missing_wedge_deg"] - 40.0) < 1e-9


def test_fsc_curve_has_shells_and_thresholds():
    rng = np.random.default_rng(2)
    gt = rng.normal(size=(20, 20, 20))
    noisy = gt + 0.01 * rng.normal(size=gt.shape)
    out = fsc_curve_protocol(noisy, gt, n_shells=16, pixel_size_nm=0.1)
    curve = out["protocol_fsc_curve"]
    assert len(curve["fsc"]) >= 1
    assert "protocol_fsc_res_0p5_px" in out
    assert out["protocol_pixel_size_nm"] == 0.1


def test_compute_protocol_metrics_aggregate():
    rng = np.random.default_rng(3)
    gt = rng.normal(size=(16, 16, 16))
    recon = 0.8 * gt + 1.0
    m = compute_protocol_metrics(recon, gt, -60.0, 60.0)
    assert "protocol_affine_cc" in m
    assert "protocol_wedge_out_cc" in m
    assert "protocol_fsc_curve" in m
