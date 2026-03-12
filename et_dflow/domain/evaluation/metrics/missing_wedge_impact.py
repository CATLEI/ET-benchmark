"""
Missing wedge impact factor calculation.

Evaluates the impact of missing wedge on reconstruction quality.
"""

from typing import Dict, Any
import numpy as np
import hyperspy.api as hs
from et_dflow.core.exceptions import EvaluationError


def calculate_missing_wedge_impact(
    reconstruction: hs.signals.Signal1D,
    tilt_angles: np.ndarray,
    missing_wedge_angle: float
) -> Dict[str, Any]:
    """
    Calculate missing wedge impact factor.
    
    Args:
        reconstruction: Reconstructed volume
        tilt_angles: Tilt angles used
        missing_wedge_angle: Missing wedge angle in degrees
    
    Returns:
        Dictionary with impact metrics
    """
    # Calculate directional artifacts
    artifacts = _calculate_directional_artifacts(reconstruction.data, tilt_angles)
    
    # Calculate structural elongation
    elongation = _calculate_structural_elongation(reconstruction.data, tilt_angles)
    
    # Calculate impact factor
    impact_factor = _calculate_impact_factor(
        missing_wedge_angle, artifacts, elongation
    )
    
    return {
        "missing_wedge_angle": float(missing_wedge_angle),
        "directional_artifact_strength": float(artifacts["strength"]),
        "structural_elongation": float(elongation),
        "impact_factor": float(impact_factor),
        "impact_level": "high" if impact_factor > 0.7 else "medium" if impact_factor > 0.4 else "low",
    }


def _calculate_directional_artifacts(
    volume: np.ndarray,
    tilt_angles: np.ndarray
) -> Dict[str, Any]:
    """
    Calculate directional artifact strength.
    
    Args:
        volume: Volume data
        tilt_angles: Tilt angles
    
    Returns:
        Artifact information
    """
    # Simplified calculation
    # Full implementation would detect directional streaks and artifacts
    
    # Calculate variance in different directions
    # Missing wedge causes artifacts perpendicular to tilt axis
    
    # For now, return placeholder
    return {
        "strength": 0.5,  # 0 = no artifacts, 1 = severe artifacts
        "direction": [0, 0, 1],  # Tilt axis direction
    }


def _calculate_structural_elongation(
    volume: np.ndarray,
    tilt_angles: np.ndarray
) -> float:
    """
    Calculate structural elongation due to missing wedge.
    
    Args:
        volume: Volume data
        tilt_angles: Tilt angles
    
    Returns:
        Elongation factor (1.0 = no elongation)
    """
    # Simplified calculation
    # Full implementation would measure elongation along missing wedge direction
    
    # Calculate aspect ratio of volume
    # Missing wedge causes elongation perpendicular to tilt axis
    
    # For now, return placeholder
    return 1.2  # 20% elongation


def _calculate_impact_factor(
    missing_wedge_angle: float,
    artifacts: Dict[str, Any],
    elongation: float
) -> float:
    """
    Calculate overall impact factor.
    
    Args:
        missing_wedge_angle: Missing wedge angle
        artifacts: Artifact information
        elongation: Elongation factor
    
    Returns:
        Impact factor (0-1)
    """
    # Combine factors
    angle_factor = missing_wedge_angle / 90.0  # Normalize to [0, 1]
    artifact_factor = artifacts["strength"]
    elongation_factor = (elongation - 1.0) / 2.0  # Normalize elongation
    
    # Weighted combination
    impact = 0.4 * angle_factor + 0.3 * artifact_factor + 0.3 * elongation_factor
    
    return float(np.clip(impact, 0, 1))


