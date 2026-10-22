"""Tests for reconstruction-to-GT volume alignment."""

import numpy as np
import pytest

from et_dflow.domain.evaluation.volume_alignment import (
    apply_fixed_geometry,
    center_embed,
    find_best_shift,
    ncc,
    shift_volume,
    trim_to_shape,
    align_reconstruction_to_ground_truth,
)


def test_trim_leading_vs_center_differ():
    src = np.arange(5 * 3 * 3, dtype=np.float32).reshape(5, 3, 3)
    leading = trim_to_shape(src, (4, 3, 3), mode="leading")
    center = trim_to_shape(src, (4, 3, 3), mode="center")
    trailing = trim_to_shape(src, (4, 3, 3), mode="trailing")
    assert leading.shape == (4, 3, 3)
    assert not np.allclose(leading, center)
    assert not np.allclose(leading, trailing)
    # leading drops index 0, keeps 1..4
    np.testing.assert_array_equal(leading, src[1:5])
    np.testing.assert_array_equal(trailing, src[0:4])


def test_center_embed_513_style():
    src = np.ones((4, 5, 5), dtype=np.float32)
    out = center_embed(src, (4, 4, 4))
    assert out.shape == (4, 4, 4)
    assert out.sum() == 4 * 4 * 4  # fully filled from crop


def test_apply_fixed_geometry_transpose_flip_trim():
    # Mark a unique voxel at (0, 1, 2) so we can track axes_order.
    vol = np.zeros((3, 4, 5), dtype=np.float32)
    vol[0, 1, 2] = 7.0
    # axes_order [1,2,0] -> (Y,X,Z) = (4,5,3); value at (1,2,0)
    out = apply_fixed_geometry(
        vol,
        target_shape=(4, 5, 3),
        axes_order=(1, 2, 0),
        flip_axes=[],
        trim="trailing",
    )
    assert out.shape == (4, 5, 3)
    assert out[1, 2, 0] == 7.0


def test_shift_volume_zero_pad_not_wrap():
    vol = np.zeros((5, 5, 5), dtype=np.float32)
    vol[2, 2, 2] = 1.0
    moved = shift_volume(vol, (0, 0, 2))
    assert moved[2, 2, 4] == 1.0
    # No wrap: original corner stays zero (would be 1 if roll wrapped from center).
    assert moved[2, 2, 0] == 0.0
    assert moved[2, 2, 1] == 0.0


def test_find_best_shift_recovers_known_offset():
    rng = np.random.default_rng(0)
    gt = rng.standard_normal((32, 32, 32)).astype(np.float32)
    true_shift = (2, -1, 1)
    moving = shift_volume(gt, true_shift)
    # Recover by shifting moving back toward gt: expected ≈ -true_shift
    found, score = find_best_shift(gt, moving, max_shift=4, downsample_target=32)
    assert score > 0.9
    assert found == (-true_shift[0], -true_shift[1], -true_shift[2])


def test_max_shift_fullres_clipped():
    rng = np.random.default_rng(1)
    gt = rng.standard_normal((32, 32, 32)).astype(np.float32)
    moving = shift_volume(gt, (3, 0, 0))
    found, _ = find_best_shift(gt, moving, max_shift=2, downsample_target=32)
    assert abs(found[0]) <= 2
    assert abs(found[1]) <= 2
    assert abs(found[2]) <= 2


def test_align_strategy_fixed_and_center():
    gt = np.zeros((8, 8, 8), dtype=np.float32)
    gt[2:6, 2:6, 2:6] = 1.0
    # Oversized recon: same content with an extra leading slice of zeros on Z.
    recon = np.zeros((9, 8, 8), dtype=np.float32)
    recon[1:9, :, :] = gt

    aligned_fixed, meta_f = align_reconstruction_to_ground_truth(
        recon,
        gt,
        target_shape=(8, 8, 8),
        strategy="fixed",
        align_fixed={"axes_order": [0, 1, 2], "flip_axes": [], "trim": "leading"},
        max_shift=0,
    )
    assert meta_f["strategy"] == "fixed"
    assert aligned_fixed.shape == (8, 8, 8)
    assert ncc(aligned_fixed, gt) > 0.99

    aligned_c, meta_c = align_reconstruction_to_ground_truth(
        recon, gt, target_shape=(8, 8, 8), strategy="center", max_shift=0
    )
    assert meta_c["strategy"] == "center"
    assert aligned_c.shape == (8, 8, 8)


def test_align_strategy_ncc_metadata():
    rng = np.random.default_rng(2)
    gt = rng.standard_normal((24, 24, 24)).astype(np.float32)
    recon = shift_volume(gt, (1, 0, -1))
    aligned, meta = align_reconstruction_to_ground_truth(
        recon,
        gt,
        target_shape=(24, 24, 24),
        strategy="ncc",
        max_shift=3,
        refine_max_shift=2,
    )
    assert meta["strategy"] == "ncc"
    assert meta["shift_mode"] == "zero_pad"
    assert "ncc_approx" in meta
    assert "ncc_refine" in meta
    assert aligned.shape == (24, 24, 24)
    assert ncc(aligned, gt) > 0.85


def test_unknown_strategy_raises():
    vol = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="Unknown align strategy"):
        align_reconstruction_to_ground_truth(vol, vol, strategy="nope")


def test_apply_output_to_gt_array_and_disabled():
    from et_dflow.domain.evaluation.volume_alignment import (
        apply_output_to_gt_array,
        output_to_gt_enabled,
    )

    vol = np.arange(2 * 3 * 3, dtype=np.float32).reshape(2, 3, 3)
    geom = {
        "axes_order": [0, 1, 2],
        "flip_axes": [],
        "trim": "leading",
        "target_shape": [1, 3, 3],
    }
    out, meta = apply_output_to_gt_array(vol, geom)
    assert meta["applied"] is True
    assert out.shape == (1, 3, 3)
    np.testing.assert_array_equal(out, vol[1:2])

    assert output_to_gt_enabled({"enabled": False}) is False
    out2, meta2 = apply_output_to_gt_array(vol, {"enabled": False})
    assert meta2["applied"] is False
    assert out2.shape == vol.shape


def test_apply_output_to_gt_file_backup_and_replay(tmp_path):
    from et_dflow.domain.evaluation.volume_alignment import apply_output_to_gt_file

    # Use .npy to avoid slow/hanging HyperSpy IO in unit tests.
    vol = np.zeros((5, 4, 4), dtype=np.float32)
    vol[1:, :, :] = 1.0
    path = tmp_path / "reconstruction.npy"
    np.save(str(path), vol)

    geom = {
        "axes_order": [0, 1, 2],
        "flip_axes": [],
        "trim": "leading",
        "target_shape": [4, 4, 4],
    }
    meta = apply_output_to_gt_file(
        path,
        geom,
        force_from_native=True,
        native_backup_name="reconstruction_native.npy",
    )
    assert meta["applied"] is True
    native = tmp_path / "reconstruction_native.npy"
    assert native.is_file()
    assert np.load(str(path)).shape == (4, 4, 4)

    meta2 = apply_output_to_gt_file(
        path,
        geom,
        force_from_native=True,
        native_backup_name="reconstruction_native.npy",
    )
    assert meta2["applied"] is True
    assert native.is_file()


def test_resolve_algorithm_output_to_gt():
    from et_dflow.domain.evaluation.volume_alignment import resolve_algorithm_output_to_gt

    cfg = {
        "algorithms": {
            "wbp": {
                "parameters": {
                    "output_to_gt": {
                        "axes_order": [1, 2, 0],
                        "flip_axes": [2],
                        "trim": "leading",
                        "target_shape": [512, 512, 512],
                    }
                }
            }
        }
    }
    geom = resolve_algorithm_output_to_gt(cfg, "wbp")
    assert geom["axes_order"] == [1, 2, 0]
    assert resolve_algorithm_output_to_gt(cfg, "missing") is None
