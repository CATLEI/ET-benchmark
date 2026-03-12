"""
Data models for ET-dflow Benchmark Framework.

All data models use Pydantic for validation and serialization.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
import hyperspy.api as hs
import numpy as np


class AlgorithmResult(BaseModel):
    """
    Result from algorithm execution.
    
    Contains reconstruction result and execution metadata.
    """
    
    reconstruction: Any = Field(
        ...,
        description="3D reconstruction as hyperspy Signal"
    )
    execution_time: float = Field(
        ...,
        ge=0,
        description="Execution time in seconds"
    )
    memory_usage: float = Field(
        ...,
        ge=0,
        description="Memory usage in bytes"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Algorithm-specific metadata"
    )
    algorithm_name: str = Field(
        ...,
        description="Name of the algorithm that produced this result"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when result was generated"
    )
    
    class Config:
        arbitrary_types_allowed = True
    
    def save_hyperspy(self, output_path: str):
        """
        Save reconstruction as hyperspy file.
        
        Args:
            output_path: Path to save file
        """
        if hasattr(self.reconstruction, 'save'):
            self.reconstruction.save(output_path)
        else:
            raise ValueError("Reconstruction is not a hyperspy Signal")
    
    def save_numpy(self, output_path: str):
        """
        Save reconstruction as numpy array (.npy file).
        
        Args:
            output_path: Path to save .npy file
        """
        if hasattr(self.reconstruction, 'data'):
            np.save(output_path, self.reconstruction.data)
        else:
            raise ValueError("Reconstruction does not have data attribute")


class EvaluationResult(BaseModel):
    """
    Result from evaluation metrics.
    
    Contains evaluation metrics and metadata.
    """
    
    metrics: Dict[str, Any] = Field(
        ...,
        description="Dictionary of metric names and values"
    )
    algorithm_name: str = Field(
        ...,
        description="Name of evaluated algorithm"
    )
    dataset_name: Optional[str] = Field(
        None,
        description="Name of dataset used"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when evaluation was performed"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Evaluation-specific metadata"
    )


class Dataset(BaseModel):
    """
    Dataset information model.
    
    Contains dataset metadata and configuration.
    Note: Complexity field has been removed. Use quality_metrics from metadata instead.
    """
    
    name: str = Field(..., description="Dataset name")
    type: str = Field(..., description="Dataset type: 'simulated' or 'experimental'")
    version: Optional[str] = Field(None, description="Dataset version (e.g., '1.0')")
    has_ground_truth: bool = Field(..., description="Whether dataset has ground truth")
    path: Optional[str] = Field(None, description="Path to dataset files")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dataset metadata (EMDB standard)"
    )
    description: Optional[str] = Field(None, description="Dataset description")
    quality_indicators: Optional[Dict[str, Any]] = Field(
        None,
        description="Quality indicators (SNR, missing_wedge_angle, etc.) - auto-read from metadata.yaml"
    )


class AlgorithmConfig(BaseModel):
    """
    Algorithm configuration model.
    
    Contains algorithm-specific configuration parameters.
    """
    
    name: str = Field(..., description="Algorithm name")
    docker_image: str = Field(..., description="Docker image name")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Algorithm-specific parameters"
    )
    resources: Dict[str, Any] = Field(
        default_factory=dict,
        description="Resource requirements"
    )


class WorkflowConfig(BaseModel):
    """
    Workflow configuration model.
    
    Contains configuration for benchmark workflows.
    """
    
    dataset: str = Field(..., description="Dataset name")
    algorithms: List[str] = Field(..., description="List of algorithm names")
    task: str = Field(
        ...,
        description="Evaluation task: 'baseline', 'missing_wedge', 'experimental'"
    )
    output_path: str = Field(
        default="./output",
        description="Output directory path"
    )
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional workflow configuration"
    )

