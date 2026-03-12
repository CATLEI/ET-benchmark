"""
dflow OP implementations.

Contains OP classes for data preparation, algorithm execution, and evaluation.
"""

from et_dflow.infrastructure.workflows.ops.data_preparation_op import DataPreparationOP
from et_dflow.infrastructure.workflows.ops.algorithm_execution_op import AlgorithmExecutionOP
from et_dflow.infrastructure.workflows.ops.evaluation_op import EvaluationOP
from et_dflow.infrastructure.workflows.ops.comparison_op import ComparisonOP

__all__ = [
    "DataPreparationOP",
    "AlgorithmExecutionOP",
    "EvaluationOP",
    "ComparisonOP",
]
