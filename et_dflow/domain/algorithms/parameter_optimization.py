"""
Parameter optimization framework.

Implements multiple strategies for optimizing algorithm parameters
to ensure fair comparison.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from et_dflow.domain.algorithms.base import Algorithm
from et_dflow.core.models import AlgorithmResult, EvaluationResult
from et_dflow.core.exceptions import AlgorithmError


class ParameterOptimizationFramework:
    """
    Framework for optimizing algorithm parameters.
    
    Supports multiple optimization strategies:
    - Literature-based parameters
    - Grid search
    - Cross-validation
    - Bayesian optimization
    """
    
    def __init__(self):
        """Initialize parameter optimization framework."""
        self.literature_params = self._load_literature_parameters()
    
    def optimize_parameters(
        self,
        algorithm: Algorithm,
        dataset: Any,  # Dataset or tilt series
        strategy: str = "literature_based",
        metric: str = "psnr",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Optimize algorithm parameters.
        
        Args:
            algorithm: Algorithm instance
            dataset: Dataset or tilt series for optimization
            strategy: Optimization strategy
            metric: Metric to optimize
            **kwargs: Strategy-specific parameters
        
        Returns:
            Dictionary with optimized parameters and results
        """
        if strategy == "literature_based":
            return self._use_literature_parameters(algorithm.name)
        elif strategy == "grid_search":
            return self._grid_search(algorithm, dataset, metric, **kwargs)
        elif strategy == "cross_validation":
            return self._cross_validation_optimization(algorithm, dataset, metric, **kwargs)
        elif strategy == "bayesian":
            return self._bayesian_optimization(algorithm, dataset, metric, **kwargs)
        else:
            raise AlgorithmError(
                f"Unknown optimization strategy: {strategy}",
                details={"strategy": strategy, "available": [
                    "literature_based", "grid_search", "cross_validation", "bayesian"
                ]}
            )
    
    def _load_literature_parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        Load literature-based parameters for algorithms.
        
        Returns:
            Dictionary mapping algorithm names to parameter sets
        """
        # Literature parameters database
        # In real implementation, would load from config file or database
        return {
            "wbp": {
                "filter_type": "ramp",
                "filter_cutoff": 1.0,
            },
            "sirt": {
                "iterations": 30,
                "relaxation_factor": 0.5,
            },
            "genfire": {
                "iterations": 100,
                "oversampling_ratio": 1.5,
            },
            "resire": {
                "iterations": 50,
                "oversampling_ratio": 2.0,
            },
        }
    
    def _use_literature_parameters(self, algorithm_name: str) -> Dict[str, Any]:
        """
        Use literature-based parameters.
        
        Args:
            algorithm_name: Name of algorithm
        
        Returns:
            Dictionary with parameters
        """
        params = self.literature_params.get(algorithm_name, {})
        
        return {
            "parameters": params,
            "strategy": "literature_based",
            "optimization_time": 0.0,
        }
    
    def _grid_search(
        self,
        algorithm: Algorithm,
        dataset: Any,
        metric: str,
        param_grid: Optional[Dict[str, List]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Grid search for parameter optimization.
        
        Args:
            algorithm: Algorithm instance
            dataset: Dataset for optimization
            metric: Metric to optimize
            param_grid: Parameter grid to search
        
        Returns:
            Dictionary with best parameters and results
        """
        if param_grid is None:
            # Use default grid based on algorithm
            param_grid = self._get_default_param_grid(algorithm.name)
        
        best_params = None
        best_score = float('-inf')
        results = []
        
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        from itertools import product
        for param_combo in product(*param_values):
            params = dict(zip(param_names, param_combo))
            
            # Run algorithm with these parameters
            try:
                result = algorithm.run(dataset, config=params)
                # Evaluate (simplified - would use actual evaluation)
                score = self._evaluate_result(result, metric, dataset)
                
                results.append({
                    "parameters": params,
                    "score": score,
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params
            except Exception:
                continue  # Skip failed parameter sets
        
        return {
            "parameters": best_params,
            "best_score": best_score,
            "all_results": results,
            "strategy": "grid_search",
        }
    
    def _cross_validation_optimization(
        self,
        algorithm: Algorithm,
        dataset: Any,
        metric: str,
        n_folds: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Cross-validation based parameter optimization.
        
        Args:
            algorithm: Algorithm instance
            dataset: Dataset for optimization
            metric: Metric to optimize
            n_folds: Number of cross-validation folds
        
        Returns:
            Dictionary with optimized parameters
        """
        # Simplified cross-validation
        # In full implementation, would properly split data
        
        # For now, use grid search with cross-validation
        param_grid = self._get_default_param_grid(algorithm.name)
        
        # Average scores across folds
        param_scores = {}
        
        from itertools import product
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        for param_combo in product(*param_values):
            params = dict(zip(param_names, param_combo))
            scores = []
            
            # Cross-validation (simplified)
            for fold in range(n_folds):
                try:
                    result = algorithm.run(dataset, config=params)
                    score = self._evaluate_result(result, metric, dataset)
                    scores.append(score)
                except Exception:
                    continue
            
            if scores:
                param_scores[tuple(params.items())] = np.mean(scores)
        
        # Find best parameters
        if param_scores:
            best_params_tuple = max(param_scores.items(), key=lambda x: x[1])
            best_params = dict(best_params_tuple[0])
            best_score = best_params_tuple[1]
        else:
            best_params = {}
            best_score = 0.0
        
        return {
            "parameters": best_params,
            "best_score": best_score,
            "strategy": "cross_validation",
            "n_folds": n_folds,
        }
    
    def _bayesian_optimization(
        self,
        algorithm: Algorithm,
        dataset: Any,
        metric: str,
        n_iterations: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Bayesian optimization for parameters.
        
        Args:
            algorithm: Algorithm instance
            dataset: Dataset for optimization
            metric: Metric to optimize
            n_iterations: Number of optimization iterations
        
        Returns:
            Dictionary with optimized parameters
        """
        # Simplified Bayesian optimization
        # In full implementation, would use proper Bayesian optimization library
        
        # For now, use random search as placeholder
        param_ranges = self._get_param_ranges(algorithm.name)
        
        best_params = None
        best_score = float('-inf')
        
        np.random.seed(42)
        for i in range(n_iterations):
            # Sample random parameters
            params = {}
            for param_name, param_range in param_ranges.items():
                if isinstance(param_range, list):
                    params[param_name] = np.random.choice(param_range)
                elif isinstance(param_range, tuple):
                    if len(param_range) == 2:
                        params[param_name] = np.random.uniform(param_range[0], param_range[1])
            
            # Evaluate
            try:
                result = algorithm.run(dataset, config=params)
                score = self._evaluate_result(result, metric, dataset)
                
                if score > best_score:
                    best_score = score
                    best_params = params
            except Exception:
                continue
        
        return {
            "parameters": best_params or {},
            "best_score": best_score,
            "strategy": "bayesian",
            "n_iterations": n_iterations,
        }
    
    def _get_default_param_grid(self, algorithm_name: str) -> Dict[str, List]:
        """Get default parameter grid for algorithm."""
        grids = {
            "sirt": {
                "iterations": [10, 20, 30, 50],
                "relaxation_factor": [0.3, 0.5, 0.7],
            },
            "genfire": {
                "iterations": [50, 100, 150],
                "oversampling_ratio": [1.0, 1.5, 2.0],
            },
        }
        return grids.get(algorithm_name, {})
    
    def _get_param_ranges(self, algorithm_name: str) -> Dict[str, Any]:
        """Get parameter ranges for Bayesian optimization."""
        ranges = {
            "sirt": {
                "iterations": (10, 100),
                "relaxation_factor": (0.1, 1.0),
            },
            "genfire": {
                "iterations": (50, 200),
                "oversampling_ratio": (1.0, 3.0),
            },
        }
        return ranges.get(algorithm_name, {})
    
    def _evaluate_result(
        self,
        result: AlgorithmResult,
        metric: str,
        dataset: Any
    ) -> float:
        """
        Evaluate algorithm result with given metric.
        
        Args:
            result: Algorithm result
            metric: Metric name
            dataset: Dataset (may contain ground truth)
        
        Returns:
            Metric value
        """
        # Simplified evaluation
        # In full implementation, would use proper evaluation framework
        
        # Placeholder: return execution time inverse as score
        # (faster is better)
        if metric == "execution_time":
            return 1.0 / (result.execution_time + 1e-6)
        else:
            # Default score
            return 1.0


