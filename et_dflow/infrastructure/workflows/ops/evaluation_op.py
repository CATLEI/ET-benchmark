"""
dflow OP for evaluation.

Calculates evaluation metrics on algorithm results.
"""

from typing import Any, Dict, List, Optional, Tuple
from dflow.python import OP, OPIO, Parameter, Artifact
from et_dflow.domain.evaluation.chain import build_evaluation_chain
from et_dflow.domain.evaluation.volume_alignment import align_reconstruction_signal
from et_dflow.core.models import AlgorithmResult, EvaluationResult
from et_dflow.core.exceptions import EvaluationError


class EvaluationOP(OP):
    """
    dflow OP for evaluation.
    
    Calculates evaluation metrics on algorithm results.
    """
    
    def __init__(self):
        """Initialize evaluation OP."""
        pass
    
    @classmethod
    def get_input_sign(cls):
        """Get input signature (use dflow.python.Artifact with type for OPIO)."""
        return OPIO({
            "reconstruction": Artifact(str),
            "ground_truth": Artifact(str, optional=True),
            "metrics": Parameter(list, default=["psnr", "ssim", "mse"]),
            "algorithm_name": Parameter(str),
            "metrics_file": Parameter(str),  # output path for metrics JSON
            "dataset_key": Parameter(str, default=""),
            "suite_metadata": Parameter(dict, default={}),
            "evaluation_config": Parameter(dict, default={}),
        })
    
    @classmethod
    def get_output_sign(cls):
        """Get output signature (use dflow.python.Artifact with type for OPIO)."""
        return OPIO({
            "evaluation_results": Artifact(str),
            "metrics_file": Artifact(str),
        })
    
    @OP.exec_sign_check
    def execute(self, op_in: OPIO) -> OPIO:
        """
        Execute evaluation.
        
        Args:
            op_in: Input OPIO
        
        Returns:
            Output OPIO with evaluation results
        """
        import hyperspy.api as hs
        import json
        import os
        from pathlib import Path
        
        reconstruction_path = op_in["reconstruction"]
        ground_truth_path = op_in.get("ground_truth")
        metrics = op_in.get("metrics", ["psnr", "ssim", "mse"])
        algorithm_name = op_in["algorithm_name"]
        dataset_key = (op_in.get("dataset_key") or "").strip()
        suite_metadata = dict(op_in.get("suite_metadata") or {})
        evaluation_config = dict(op_in.get("evaluation_config") or {})

        def _target_shape(cfg: Dict[str, Any], gt_signal: Any) -> Tuple[int, int, int]:
            raw = cfg.get("align_target_shape")
            if raw and len(raw) == 3:
                return (int(raw[0]), int(raw[1]), int(raw[2]))
            return tuple(int(x) for x in gt_signal.data.shape)

        try:
            # Load reconstruction
            reconstruction = hs.load(reconstruction_path)
            if isinstance(reconstruction, list):
                reconstruction = reconstruction[0]

            # Load ground truth if available
            ground_truth = None
            if ground_truth_path:
                ground_truth = hs.load(ground_truth_path)
                if isinstance(ground_truth, list):
                    ground_truth = ground_truth[0]

            align_meta: Optional[Dict[str, Any]] = None
            recon_for_metrics = reconstruction
            if (
                ground_truth is not None
                and evaluation_config.get("align_reconstruction", False)
            ):
                max_shift = int(evaluation_config.get("align_max_shift", 8))
                target_shape = _target_shape(evaluation_config, ground_truth)
                recon_for_metrics, align_meta = align_reconstruction_signal(
                    reconstruction,
                    ground_truth,
                    target_shape=target_shape,
                    max_shift=max_shift,
                )
                metrics_dir = Path(str(op_in["metrics_file"])).parent
                aligned_path = metrics_dir / "reconstruction_aligned.hspy"
                recon_for_metrics.save(str(aligned_path))
                meta_path = metrics_dir / "reconstruction_align_meta.json"
                with open(meta_path, "w", encoding="utf-8") as mf:
                    json.dump(align_meta, mf, indent=2)

            # Create AlgorithmResult placeholder
            algorithm_result = AlgorithmResult(
                reconstruction=recon_for_metrics,
                execution_time=0.0,
                memory_usage=0.0,
                metadata={},
                algorithm_name=algorithm_name,
            )

            # Build evaluation chain
            chain = build_evaluation_chain(metrics)

            if chain:
                metrics_dict = chain.process(algorithm_result, ground_truth)
            else:
                metrics_dict = {}

            meta_out = {
                **suite_metadata,
                "dataset_key": dataset_key or None,
                "track": suite_metadata.get("track"),
                "variant": suite_metadata.get("variant"),
            }
            if align_meta is not None:
                meta_out["reconstruction_alignment"] = align_meta
            # Create evaluation result
            evaluation_result = EvaluationResult(
                metrics=metrics_dict,
                algorithm_name=algorithm_name,
                dataset_name=dataset_key or None,
                metadata={k: v for k, v in meta_out.items() if v is not None},
            )
            
            # Save results
            results_dict = evaluation_result.dict()
            metrics_file = str(op_in["metrics_file"])
            os.makedirs(os.path.dirname(metrics_file), exist_ok=True)
            with open(metrics_file, "w") as f:
                json.dump(results_dict, f, indent=2, default=str)
            
            return OPIO({
                "evaluation_results": metrics_file,  # Path to JSON (Artifact expects str)
                "metrics_file": metrics_file,
            })
        except Exception as e:
            raise EvaluationError(
                f"Evaluation failed: {e}",
                details={
                    "algorithm": algorithm_name,
                    "error": str(e)
                }
            ) from e

