"""
Configuration wizard for interactive configuration generation.

Provides interactive wizard for generating configuration files.
"""

import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from et_dflow.core.exceptions import ConfigurationError


class ConfigWizard:
    """
    Interactive configuration wizard.
    
    Guides users through configuration generation process.
    """
    
    def __init__(self):
        """Initialize configuration wizard."""
        pass
    
    def create_config(self, output_path: str = "config.yaml") -> Dict[str, Any]:
        """
        Create configuration interactively.
        
        Args:
            output_path: Path to save configuration file
        
        Returns:
            Configuration dictionary
        """
        config = {}
        
        # Basic settings
        config["algorithms"] = self._configure_algorithms()
        config["datasets"] = self._configure_datasets()
        config["workflow"] = self._configure_workflow()
        
        # Save configuration
        with open(output_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config
    
    def _configure_algorithms(self) -> Dict[str, Any]:
        """Configure algorithms interactively."""
        # Simplified - would use actual interactive prompts
        algorithms = {
            "wbp": {
                "enabled": True,
                "docker_image": "et-dflow/wbp:latest",
            },
            "sirt": {
                "enabled": True,
                "docker_image": "et-dflow/sirt:latest",
            },
        }
        return algorithms
    
    def _configure_datasets(self) -> Dict[str, Any]:
        """Configure datasets interactively."""
        # Simplified - would use actual interactive prompts
        datasets = {
            "default": {
                "path": "./data",
                "format": "hyperspy",
            },
        }
        return datasets
    
    def _configure_workflow(self) -> Dict[str, Any]:
        """Configure workflow interactively."""
        # Simplified - would use actual interactive prompts
        workflow = {
            "type": "benchmark",
            "output_dir": "./results",
        }
        return workflow


class SimpleMode:
    """
    Simple configuration mode.
    
    Provides minimal configuration for quick setup.
    """
    
    @staticmethod
    def create_simple_config(
        dataset_path: str,
        algorithm: str = "wbp",
        output_dir: str = "./results"
    ) -> Dict[str, Any]:
        """
        Create simple configuration.
        
        Args:
            dataset_path: Path to dataset
            algorithm: Algorithm name
            output_dir: Output directory
        
        Returns:
            Configuration dictionary
        """
        return {
            "datasets": {
                "test_dataset": {
                    "path": dataset_path,
                    "format": "hyperspy",
                    "has_ground_truth": False,
                }
            },
            "algorithms": {
                algorithm: {
                    "enabled": True,
                }
            },
            "workflow": {
                "type": "baseline_benchmark",
                "output_dir": output_dir,
            },
            "evaluation": {
                "metrics": ["psnr", "ssim", "mse"],
            },
        }


class ConfigValidator:
    """
    Configuration validator.
    
    Validates configuration files and provides suggestions.
    """
    
    def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate configuration.
        
        Args:
            config: Configuration dictionary
        
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        suggestions = []
        
        # Validate required fields
        if "algorithms" not in config:
            errors.append("Missing required field: algorithms")
        
        if "datasets" not in config:
            errors.append("Missing required field: datasets")
        
        # Validate algorithms
        if "algorithms" in config:
            for alg_name, alg_config in config["algorithms"].items():
                if "docker_image" not in alg_config:
                    warnings.append(f"Algorithm {alg_name} missing docker_image")
        
        # Validate datasets
        if "datasets" in config:
            for ds_name, ds_config in config["datasets"].items():
                if "path" not in ds_config:
                    errors.append(f"Dataset {ds_name} missing path")

        self._validate_runtime_strategy(config, errors, warnings, suggestions)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
        }

    @staticmethod
    def _validate_runtime_strategy(
        config: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
        suggestions: List[str],
    ) -> None:
        runtime_profiles = config.get("runtime_profiles") or {}
        dataset_profiles = config.get("dataset_profiles") or {}
        policy = config.get("policy") or {}

        if runtime_profiles and not isinstance(runtime_profiles, dict):
            errors.append("runtime_profiles must be a mapping of profile_name -> profile_config")
            return
        if dataset_profiles and not isinstance(dataset_profiles, dict):
            errors.append("dataset_profiles must be a mapping of class_name -> profile selector")
            return
        if policy and not isinstance(policy, dict):
            errors.append("policy must be a mapping")
            return

        allowed_backends = {"cpu_sirt", "astra_gpu_sirt"}
        for alg_name, alg_cfg in (config.get("algorithms") or {}).items():
            if not isinstance(alg_cfg, dict):
                continue
            params = alg_cfg.get("parameters") or {}
            if not isinstance(params, dict):
                errors.append(f"Algorithm {alg_name} parameters must be a mapping")
                continue
            backend = params.get("backend")
            if backend is not None and backend not in allowed_backends:
                errors.append(
                    f"Algorithm {alg_name} has invalid parameters.backend={backend!r}; "
                    f"allowed: {sorted(allowed_backends)}"
                )
            dtype = params.get("dtype")
            if dtype is not None and dtype not in {"float32", "float64"}:
                errors.append(
                    f"Algorithm {alg_name} has invalid parameters.dtype={dtype!r}; "
                    "allowed: 'float32' or 'float64'"
                )
            iterations = params.get("iterations")
            if iterations is not None:
                try:
                    it_n = int(iterations)
                    if it_n <= 0:
                        errors.append(f"Algorithm {alg_name} parameters.iterations must be > 0")
                except (TypeError, ValueError):
                    errors.append(f"Algorithm {alg_name} parameters.iterations must be an integer")

        for profile_name, profile_cfg in runtime_profiles.items():
            if not isinstance(profile_cfg, dict):
                errors.append(f"runtime_profiles.{profile_name} must be a mapping")
                continue
            backend = profile_cfg.get("backend")
            if backend is not None and backend not in allowed_backends:
                errors.append(
                    f"runtime_profiles.{profile_name}.backend={backend!r} not in {sorted(allowed_backends)}"
                )
            for key in ("threads", "iterations", "ram_limit_gb", "gpu_count", "vram_min_gb", "chunk_size"):
                if key not in profile_cfg:
                    continue
                try:
                    val = int(profile_cfg[key])
                    if val <= 0:
                        errors.append(f"runtime_profiles.{profile_name}.{key} must be > 0")
                except (TypeError, ValueError):
                    errors.append(f"runtime_profiles.{profile_name}.{key} must be an integer")
            dtype = profile_cfg.get("dtype")
            if dtype is not None and dtype not in {"float32", "float64"}:
                errors.append(
                    f"runtime_profiles.{profile_name}.dtype={dtype!r} must be 'float32' or 'float64'"
                )

        for size_class, ds_profile in dataset_profiles.items():
            if not isinstance(ds_profile, dict):
                errors.append(f"dataset_profiles.{size_class} must be a mapping")
                continue
            candidate = ds_profile.get("runtime_profile")
            if candidate and candidate not in runtime_profiles:
                warnings.append(
                    f"dataset_profiles.{size_class}.runtime_profile={candidate!r} "
                    "is not defined in runtime_profiles"
                )

        policy_profile = policy.get("default_runtime_profile")
        if policy_profile and policy_profile not in runtime_profiles:
            warnings.append(
                f"policy.default_runtime_profile={policy_profile!r} not found in runtime_profiles"
            )
        if not runtime_profiles:
            suggestions.append(
                "Add runtime_profiles/dataset_profiles/policy to enable automatic SIRT resource tiering."
            )

