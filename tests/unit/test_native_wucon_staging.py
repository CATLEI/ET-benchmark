"""Staging / patch helpers for WUCon automation (no GPU / no upstream train)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

# adapter_common imports hyperspy at module load; stub if missing (CI/local lean envs).
try:
    import hyperspy.api  # noqa: F401
except ImportError:
    sys.modules.setdefault("hyperspy", MagicMock())
    sys.modules.setdefault("hyperspy.api", MagicMock())

from et_dflow.infrastructure.algorithms.native_wucon import (
    ensure_even_height,
    patch_parser_choices,
    prepare_wucon_src_copy,
    resolve_wucon_src_dir,
    stage_wucon_inputs,
    write_mrc,
    write_tlt,
    _render_constants_py,
)


def _fake_wucon_src(tmp_path: Path) -> Path:
    src = tmp_path / "upstream_src"
    src.mkdir()
    for name in (
        "recon_chunk.py",
        "constants.py",
        "parser.py",
        "dataset.py",
    ):
        (src / name).write_text("# stub %s\n" % name, encoding="utf-8")
    # Minimal parser snippet with choices list
    (src / "parser.py").write_text(
        "p.add_argument('--dataset', type=str, required=True,\n"
        "               choices=['sph', 'geo', 'p2s'], help='cryoet dataset')\n",
        encoding="utf-8",
    )
    return src


def test_ensure_even_height_crops_odd():
    odd = np.zeros((4, 33, 16), dtype=np.float32)
    out = ensure_even_height(odd)
    assert out.shape == (4, 32, 16)


def test_ensure_even_height_keeps_even():
    even = np.zeros((4, 32, 16), dtype=np.float32)
    out = ensure_even_height(even)
    assert out.shape == (4, 32, 16)


def test_resolve_wucon_src_dir_from_config(tmp_path):
    src = _fake_wucon_src(tmp_path)
    found = resolve_wucon_src_dir({"wucon_src_dir": str(src)})
    assert found == src.resolve()


def test_resolve_wucon_src_dir_from_env(tmp_path, monkeypatch):
    src = _fake_wucon_src(tmp_path)
    monkeypatch.delenv("WUCON_SRC", raising=False)
    monkeypatch.setenv("WUCON_SRC", str(src))
    found = resolve_wucon_src_dir({})
    assert found == src.resolve()


def test_resolve_wucon_src_dir_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("WUCON_SRC", raising=False)
    with pytest.raises(FileNotFoundError):
        resolve_wucon_src_dir({"wucon_src_dir": str(tmp_path / "nope")})


class _FakeTiltSeries:
    """Minimal stand-in for HyperSpy Signal2D (staging only needs .data)."""

    def __init__(self, data: np.ndarray):
        self.data = data
        self.metadata = type("Meta", (), {})()


def test_stage_and_patch(tmp_path):
    pytest.importorskip("mrcfile")
    stack = np.random.randn(8, 32, 32).astype(np.float32)
    sig = _FakeTiltSeries(stack)
    work = tmp_path / "work"
    work.mkdir()
    src = _fake_wucon_src(tmp_path)

    staged = stage_wucon_inputs(
        sig,
        {"tilt_range": [-60, 60]},
        work,
    )
    assert staged["n_tilts"] == 8
    assert staged["prj_size_load"] == (32, 32)
    assert staged["img_size_load"] == (32, 32, 32)
    assert staged["prj_path"].is_file()
    assert staged["tlt_path"].is_file()
    tlt_lines = staged["tlt_path"].read_text(encoding="utf-8").strip().splitlines()
    assert len(tlt_lines) == 8

    dest = prepare_wucon_src_copy(
        src,
        work,
        staged=staged,
        n_epochs_mid=5,
        n_epochs_all=3,
        case_id=90,
    )
    constants = (dest / "constants.py").read_text(encoding="utf-8")
    assert "DIR_PROJECT" in constants
    assert "'etbench'" in constants
    assert "N_EPOCHS_MID = 5" in constants
    assert "n_sparse_prj': 8" in constants
    parser = (dest / "parser.py").read_text(encoding="utf-8")
    assert "etbench" in parser


def test_patch_parser_choices_inserts_etbench():
    text = "choices=['sph', 'geo', 'p2s'], help='x'"
    out = patch_parser_choices(text)
    assert "etbench" in out


def test_render_constants_contains_paths(tmp_path):
    text = _render_constants_py(
        dir_project=tmp_path,
        dir_data=tmp_path / "data",
        img_size_load=(16, 32, 16),
        prj_size_load=(16, 32),
        n_tilts=8,
        n_epochs_mid=5,
        n_epochs_all=3,
        case_id=90,
    )
    assert str(tmp_path) in text
    assert "N_EPOCHS_MID = 5" in text
    assert "90: {}" in text


def test_write_mrc_and_tlt(tmp_path):
    mrc_path = tmp_path / "a.mrc"
    tlt_path = tmp_path / "a.tlt"
    write_mrc(mrc_path, np.ones((2, 4, 4), dtype=np.float32))
    write_tlt(tlt_path, np.array([-10.0, 10.0]))
    assert mrc_path.is_file()
    assert tlt_path.read_text(encoding="utf-8").splitlines() == ["-10.0", "10.0"]


@pytest.mark.skipif(
    not os.environ.get("WUCON_SRC")
    or not Path(os.environ.get("WUCON_SRC", "")).is_dir(),
    reason="Set WUCON_SRC to upstream src for GPU smoke",
)
def test_gpu_smoke_mid_assemble():
    """Optional: mid chunk + assemble when CUDA + WUCON_SRC are available."""
    torch = pytest.importorskip("torch")
    if torch.cuda.device_count() < 1:
        pytest.skip("CUDA required for WUCON smoke")
    hs = pytest.importorskip("hyperspy.api")
    from et_dflow.infrastructure.algorithms.native_wucon import (
        run_wucon_reconstruction,
    )
    import time

    stack = (np.random.randn(8, 32, 32).astype(np.float32) * 0.1) + 0.5
    sig = hs.signals.Signal2D(stack)
    cfg = {
        "wucon_pipeline": True,
        "wucon_recon_subset": True,
        "wucon_n_epochs_mid": 5,
        "wucon_n_epochs_all": 3,
        "wucon_case_id": 90,
        "tilt_range": [-40, 40],
    }
    result = run_wucon_reconstruction(sig, cfg, start_time=time.time())
    assert result.reconstruction is not None
    assert np.asarray(result.reconstruction.data).ndim == 3
