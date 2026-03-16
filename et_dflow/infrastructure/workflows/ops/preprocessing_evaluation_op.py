"""
dflow OP for preprocessing quality evaluation.

Evaluates alignment and/or denoising results (tilt series) and outputs metrics JSON.
"""

import json
import os
from typing import Dict, Any

from dflow.python import OP, OPIO, Parameter, Artifact
from et_dflow.domain.evaluation.preprocessing_metrics import (
    compute_alignment_metrics,
    compute_denoising_metrics,
)


class PreprocessingEvaluationOP(OP):
    """
    Evaluates alignment and denoising outputs from data preparation.
    """

    @classmethod
    def get_input_sign(cls):
        return OPIO({
            "alignment_output": Artifact(str, optional=True),
            "denoising_output": Artifact(str, optional=True),
            "before_alignment": Artifact(str, optional=True),
            "before_denoising": Artifact(str, optional=True),
            "alignment_metrics": Parameter(list, default=["shift_stability", "cross_correlation_peak"]),
            "denoising_metrics": Parameter(list, default=["snr_estimate", "local_variance"]),
            "metrics_output": Parameter(str, default="/tmp/preprocessing_metrics.json"),
        })

    @classmethod
    def get_output_sign(cls):
        return OPIO({
            "preprocessing_metrics_file": Artifact(str),
        })

    @OP.exec_sign_check
    def execute(self, op_in: OPIO) -> OPIO:
        alignment_path = op_in.get("alignment_output")
        denoising_path = op_in.get("denoising_output")
        alignment_metrics = op_in.get("alignment_metrics", ["shift_stability", "cross_correlation_peak"])
        denoising_metrics = op_in.get("denoising_metrics", ["snr_estimate", "local_variance"])
        metrics_output = str(op_in.get("metrics_output", "/tmp/preprocessing_metrics.json"))

        report = {}

        if alignment_path and os.path.exists(alignment_path):
            report["alignment"] = compute_alignment_metrics(
                alignment_path,
                alignment_metrics=alignment_metrics,
                before_alignment_path=op_in.get("before_alignment"),
            )

        if denoising_path and os.path.exists(denoising_path):
            report["denoising"] = compute_denoising_metrics(
                denoising_path,
                denoising_metrics=denoising_metrics,
                before_denoising_path=op_in.get("before_denoising"),
            )

        os.makedirs(os.path.dirname(metrics_output) or ".", exist_ok=True)
        with open(metrics_output, "w") as f:
            json.dump(report, f, indent=2, default=str)

        return OPIO({
            "preprocessing_metrics_file": metrics_output,
        })
