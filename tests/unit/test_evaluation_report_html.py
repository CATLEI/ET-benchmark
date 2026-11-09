"""Tests for categorized comparison HTML reports."""

from pathlib import Path

from et_dflow.infrastructure.visualization.evaluation_visualizer import (
    EvaluationVisualizer,
    _best_algorithms_for_metric,
    _grouped_metric_keys,
    collect_sample_info,
)


def test_grouped_metric_keys_orders_known_categories():
    groups = _grouped_metric_keys(
        ["psnr", "dice", "psd_wasserstein_px", "custom_metric", "ssim"]
    )
    titles = [g["title"] for g in groups]
    assert titles[0] == "Intensity fidelity"
    assert "psnr" in groups[0]["metrics"]
    assert "ssim" in groups[0]["metrics"]
    assert any(g["id"] == "morphology" and "dice" in g["metrics"] for g in groups)
    assert any(
        g["id"] == "porous" and "psd_wasserstein_px" in g["metrics"] for g in groups
    )
    assert any(g["id"] == "other" and "custom_metric" in g["metrics"] for g in groups)


def test_best_algorithms_respect_direction():
    data = {
        "a": {"metrics": {"psnr": 10.0, "mse": 5.0, "elongation": 1.2}},
        "b": {"metrics": {"psnr": 12.0, "mse": 8.0, "elongation": 1.05}},
        "c": {"metrics": {"psnr": 11.0, "mse": 3.0, "elongation": 0.9}},
    }
    assert _best_algorithms_for_metric(data, "psnr") == {"b"}
    assert _best_algorithms_for_metric(data, "mse") == {"c"}
    assert _best_algorithms_for_metric(data, "elongation") == {"b"}


def test_html_report_is_grouped_and_marks_best(tmp_path):
    visualizer = EvaluationVisualizer(str(tmp_path))
    data = {
        "wbp": {"metrics": {"psnr": 14.0, "ssim": 0.88, "mse": 2000.0, "dice": 0.96}},
        "astra_sirt": {
            "metrics": {"psnr": 15.0, "ssim": 0.87, "mse": 1900.0, "dice": 0.93}
        },
    }
    sample_info = {
        "dataset_key": "aligned_model_sm70",
        "variant": "sm70",
        "tilt_range": [-70, 70],
        "missing_wedge_angle": 70,
        "gt_shape": [512, 512, 512],
    }
    html = visualizer._generate_html_report(
        data, None, None, sample_info=sample_info
    )
    assert "Evaluation Report — aligned_model_sm70" in html
    assert "Sample" in html
    assert "sm70" in html
    assert "[-70°, 70°]" in html
    assert "512 × 512 × 512" in html
    assert "Intensity fidelity" in html
    assert "Solid–void morphology" in html
    assert "Best algorithm per metric" in html
    assert "best-tag" in html
    assert html.count("best</span>") >= 4
    out = Path(tmp_path) / "probe.html"
    out.write_text(html, encoding="utf-8")
    assert out.exists()


def test_collect_sample_info_from_evaluation_payloads():
    payloads = [
        {
            "dataset_name": "aligned_model_sm70",
            "metadata": {
                "dataset_key": "aligned_model_sm70",
                "variant": "sm70",
                "tilt_range": [-70, 70],
                "missing_wedge_angle": 70,
                "gt_shape": [512, 512, 512],
                "source_root": "/personal/ET/data/Aligned_data/model/",
            },
        }
    ]
    info = collect_sample_info(payloads, algorithm_names=["wbp", "astra_fbp"])
    assert info["dataset_key"] == "aligned_model_sm70"
    assert info["variant"] == "sm70"
    assert info["tilt_range"] == [-70, 70]
    assert info["algorithms"] == "wbp, astra_fbp"
    assert "generated_at" in info
