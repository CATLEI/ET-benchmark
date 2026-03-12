"""
dflow OP for evaluation.

Calculates evaluation metrics on algorithm results.
"""

from typing import Dict, Any, Optional
from dflow.python import OP, OPIO, Parameter, Artifact
from et_dflow.domain.evaluation.chain import build_evaluation_chain
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
        
        reconstruction_path = op_in["reconstruction"]
        ground_truth_path = op_in.get("ground_truth")
        metrics = op_in.get("metrics", ["psnr", "ssim", "mse"])
        algorithm_name = op_in["algorithm_name"]
        
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
            
            # Create AlgorithmResult placeholder
            # In real implementation, this would come from algorithm execution
            algorithm_result = AlgorithmResult(
                reconstruction=reconstruction,
                execution_time=0.0,
                memory_usage=0.0,
                metadata={},
                algorithm_name=algorithm_name,
            )
            
            # Build evaluation chain
            chain = build_evaluation_chain(metrics)
            
            if chain:
                # Calculate metrics
                metrics_dict = chain.process(algorithm_result, ground_truth)
            else:
                metrics_dict = {}
            
            # Create evaluation result
            evaluation_result = EvaluationResult(
                metrics=metrics_dict,
                algorithm_name=algorithm_name,
                metadata={},
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

