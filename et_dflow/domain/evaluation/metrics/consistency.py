"""
Structural consistency evaluation.

Evaluates consistency between multiple reconstructions or regions.
"""

from typing import List, Dict, Any
import numpy as np
import hyperspy.api as hs
from et_dflow.core.exceptions import EvaluationError


def calculate_consistency(
    reconstructions: List[hs.signals.Signal1D],
    method: str = "pairwise"
) -> Dict[str, Any]:
    """
    Calculate structural consistency between reconstructions.
    
    Args:
        reconstructions: List of reconstructions to compare
        method: Consistency calculation method
    
    Returns:
        Dictionary with consistency metrics
    """
    if len(reconstructions) < 2:
        raise EvaluationError(
            "Need at least 2 reconstructions for consistency calculation",
            details={"n_reconstructions": len(reconstructions)}
        )
    
    if method == "pairwise":
        return _calculate_pairwise_consistency(reconstructions)
    else:
        raise EvaluationError(
            f"Unknown consistency method: {method}",
            details={"method": method}
        )


def _calculate_pairwise_consistency(
    reconstructions: List[hs.signals.Signal1D]
) -> Dict[str, Any]:
    """
    Calculate pairwise consistency matrix.
    
    Args:
        reconstructions: List of reconstructions
    
    Returns:
        Dictionary with pairwise similarity matrix and consistency metrics
    """
    n = len(reconstructions)
    similarity_matrix = np.zeros((n, n))
    
    # Calculate pairwise similarities
    for i in range(n):
        for j in range(i + 1, n):
            # Calculate correlation coefficient
            data1 = reconstructions[i].data.flatten()
            data2 = reconstructions[j].data.flatten()
            
            # Normalize
            data1 = (data1 - data1.mean()) / (data1.std() + 1e-10)
            data2 = (data2 - data2.mean()) / (data2.std() + 1e-10)
            
            # Correlation
            correlation = np.corrcoef(data1, data2)[0, 1]
            similarity_matrix[i, j] = correlation
            similarity_matrix[j, i] = correlation
    
    # Diagonal is 1.0 (self-similarity)
    np.fill_diagonal(similarity_matrix, 1.0)
    
    # Calculate average consistency
    # Exclude diagonal
    mask = ~np.eye(n, dtype=bool)
    average_consistency = float(np.mean(similarity_matrix[mask]))
    
    # Identify consistent regions
    # Regions with high consistency across all pairs
    consistency_regions = _identify_consistent_regions(reconstructions)
    
    return {
        "similarity_matrix": similarity_matrix.tolist(),
        "average_consistency": average_consistency,
        "min_consistency": float(np.min(similarity_matrix[mask])),
        "max_consistency": float(np.max(similarity_matrix[mask])),
        "consistency_regions": consistency_regions,
    }


def _identify_consistent_regions(
    reconstructions: List[hs.signals.Signal1D]
) -> List[Dict[str, Any]]:
    """
    Identify regions with high consistency.
    
    Args:
        reconstructions: List of reconstructions
    
    Returns:
        List of consistent regions
    """
    # Simplified implementation
    # Full implementation would identify spatial regions with high consistency
    
    # For now, return placeholder
    return [
        {
            "region": "center",
            "consistency": 0.9,
            "coordinates": None,  # Would contain actual coordinates
        }
    ]


