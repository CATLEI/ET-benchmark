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
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
        }

