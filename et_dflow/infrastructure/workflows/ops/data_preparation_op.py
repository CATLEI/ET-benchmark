"""
dflow OP for data preparation.

Handles data loading, preprocessing, and metadata enrichment.
"""

from typing import Dict, Any
from dflow.python import OP, OPIO, Parameter, Artifact
from et_dflow.infrastructure.data.factory import get_data_loader_factory
from et_dflow.infrastructure.data.preprocessors import DataPreprocessor
from et_dflow.infrastructure.data.converters.format_converter import FormatConverter
from et_dflow.core.exceptions import DataError


class DataPreparationOP(OP):
    """
    dflow OP for data preparation.
    
    Loads data, applies preprocessing, and enriches metadata.
    """
    
    def __init__(self):
        """Initialize data preparation OP."""
        self.factory = get_data_loader_factory()
        self.preprocessor = DataPreprocessor()
    
    @classmethod
    def get_input_sign(cls):
        """Get input signature."""
        return OPIO({
            "dataset_path": Artifact(str),
            "dataset_format": Parameter(str, default="hyperspy"),
            "ground_truth_path": Artifact(str, optional=True),
            "preprocessing_config": Artifact(str, optional=True),
            "preprocessing_steps": Parameter(list, default=None),
            "preprocessing_evaluation_config": Parameter(dict, default=None),
            "metadata": Parameter(dict, default={}),
            "prepared_data": Parameter(str, default="/tmp/prepared_data.hspy"),
        })
    
    @classmethod
    def get_output_sign(cls):
        """Get output signature (use dflow.python.Artifact with type for OPIO)."""
        return OPIO({
            "prepared_data": Artifact(str),
            "ground_truth": Artifact(str, optional=True),
            "alignment_output": Artifact(str, optional=True),
            "denoising_output": Artifact(str, optional=True),
            "metadata": Parameter(dict),
        })
    
    @OP.exec_sign_check
    def execute(self, op_in: OPIO) -> OPIO:
        """
        Execute data preparation.
        
        Args:
            op_in: Input OPIO
        
        Returns:
            Output OPIO with prepared data
        """
        import hyperspy.api as hs
        import os
        import time
        from pathlib import Path
        
        dataset_path = op_in["dataset_path"]
        dataset_format = op_in.get("dataset_format", "hyperspy")
        ground_truth_path = op_in.get("ground_truth_path")
        metadata = op_in.get("metadata", {})
        preprocessing_steps = op_in.get("preprocessing_steps")
        preprocessing_evaluation_config = op_in.get("preprocessing_evaluation_config") or {}
        config_path = op_in.get("preprocessing_config")
        if config_path and os.path.exists(config_path):
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            preprocessing_steps = cfg.get("preprocessing_steps", preprocessing_steps)
            preprocessing_evaluation_config = cfg.get("preprocessing_evaluation_config", preprocessing_evaluation_config)
        
        try:
            started_at = time.time()

            def _log_stage(message: str) -> None:
                elapsed = time.time() - started_at
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                print(
                    f"[et-dflow] [{timestamp}] DataPreparationOP {message} "
                    f"(elapsed={elapsed:.2f}s)",
                    flush=True,
                )

            # Initialize factory and preprocessor
            factory = get_data_loader_factory()
            preprocessor = DataPreprocessor()
            dataset_size = os.path.getsize(dataset_path) if os.path.exists(dataset_path) else None
            gt_size = os.path.getsize(ground_truth_path) if ground_truth_path and os.path.exists(ground_truth_path) else None
            _log_stage(
                "start: "
                f"dataset={dataset_path}, "
                f"dataset_format={dataset_format}, "
                f"dataset_size_bytes={dataset_size}, "
                f"ground_truth={'yes' if ground_truth_path else 'no'}, "
                f"ground_truth_size_bytes={gt_size}"
            )
            
            # Detect format and convert if necessary
            detected_format = factory._detect_format(dataset_path)
            _log_stage(f"detected input format: {detected_format} for {dataset_path}")
            
            if detected_format != "hspy":
                # Convert to hspy format
                _log_stage(f"converting input to hspy: {dataset_path}")
                converter = FormatConverter()
                cache_dir = Path("/tmp/data/cache/converted")
                cache_dir.mkdir(parents=True, exist_ok=True)
                converted_path = cache_dir / f"{Path(dataset_path).stem}_converted.hspy"
                signal = converter.convert_to_hyperspy(dataset_path, str(converted_path))
                # Update metadata to track original format
                signal.metadata.set_item("original_format", detected_format)
                signal.metadata.set_item("original_path", dataset_path)
            else:
                # Directly load hspy format
                _log_stage(f"loading hspy input: {dataset_path}")
                loader = factory.create_loader(dataset_path)
                signal = loader.load(dataset_path)
            _log_stage(
                "input loaded: "
                f"shape={getattr(getattr(signal, 'data', None), 'shape', None)}"
            )
            
            # Apply preprocessing (optionally save intermediates for evaluation)
            save_after_steps = (preprocessing_evaluation_config or {}).get("save_after_steps")
            save_dir = "/tmp/prep_intermediates" if save_after_steps else None
            if preprocessing_steps:
                _log_stage(f"running preprocessing steps: {preprocessing_steps}")
                result = preprocessor.preprocess(
                    signal,
                    preprocessing_steps,
                    save_after_steps=save_after_steps,
                    save_dir=save_dir,
                )
                if isinstance(result, tuple):
                    signal, intermediates = result
                else:
                    signal = result
                    intermediates = {}
            else:
                intermediates = {}
                _log_stage("no preprocessing steps configured")
            
            # Enrich metadata (Hyperspy metadata is DictionaryTreeBrowser, use set_item not update)
            for k, v in (metadata or {}).items():
                signal.metadata.set_item(k, v)
            
            # Save prepared data
            output_path = op_in.get("prepared_data")
            if not output_path:
                output_path = "/tmp/prepared_data.hspy"
            else:
                output_path = str(output_path)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            _log_stage(f"saving prepared data to: {output_path}")
            signal.save(output_path)
            _log_stage(f"prepared data saved: {output_path}")
            
            # Prepare output metadata
            output_metadata = {
                "original_path": dataset_path,
                "preprocessing_steps": preprocessing_steps or [],
                "data_shape": list(signal.data.shape),
            }
            
            # Handle ground truth if provided
            gt_output_path = None
            if ground_truth_path and os.path.exists(ground_truth_path):
                gt_detected_format = factory._detect_format(ground_truth_path)
                _log_stage(f"detected GT format: {gt_detected_format} for {ground_truth_path}")
                
                if gt_detected_format != "hspy":
                    # Convert ground truth to hspy format
                    _log_stage(f"converting GT to hspy: {ground_truth_path}")
                    converter = FormatConverter()
                    cache_dir = Path("/tmp/data/cache/converted")
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    gt_converted_path = cache_dir / f"{Path(ground_truth_path).stem}_gt_converted.hspy"
                    gt_signal = converter.convert_to_hyperspy(ground_truth_path, str(gt_converted_path))
                    gt_signal.metadata.set_item("original_format", gt_detected_format)
                    gt_signal.metadata.set_item("original_path", ground_truth_path)
                else:
                    # Directly load hspy format
                    _log_stage(f"loading GT hspy: {ground_truth_path}")
                    gt_loader = factory.create_loader(ground_truth_path)
                    gt_signal = gt_loader.load(ground_truth_path)
                    _log_stage(
                        "GT loaded: "
                        f"shape={getattr(getattr(gt_signal, 'data', None), 'shape', None)}"
                    )
                
                gt_output_path = output_path.replace(".hspy", "_ground_truth.hspy")
                _log_stage(f"saving GT copy to: {gt_output_path}")
                gt_signal.save(gt_output_path)
                _log_stage(f"GT copy saved: {gt_output_path}")
                output_metadata["ground_truth_path"] = gt_output_path
            
            out = {
                "prepared_data": output_path,
                "ground_truth": gt_output_path,
                "metadata": output_metadata,
            }
            if intermediates.get("alignment"):
                out["alignment_output"] = intermediates["alignment"]
            if intermediates.get("denoising"):
                out["denoising_output"] = intermediates["denoising"]
            return OPIO(out)
        except Exception as e:
            raise DataError(
                f"Data preparation failed: {e}",
                details={"dataset_path": dataset_path, "error": str(e)}
            ) from e

