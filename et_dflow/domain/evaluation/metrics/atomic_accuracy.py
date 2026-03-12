"""
Atomic position and bond accuracy evaluation.

Evaluates accuracy of atomic positions, bond lengths, and bond angles.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from scipy.spatial.distance import cdist
import hyperspy.api as hs
from et_dflow.core.exceptions import EvaluationError


def calculate_atomic_position_accuracy(
    reconstruction: hs.signals.Signal1D,
    ground_truth: hs.signals.Signal1D,
    detected_positions: List[Tuple[float, float, float]],
    gt_positions: List[Tuple[float, float, float]]
) -> Dict[str, Any]:
    """
    Calculate atomic position accuracy.
    
    Args:
        reconstruction: Reconstructed volume
        detected_positions: Detected atomic positions
        ground_truth: Ground truth volume
        gt_positions: Ground truth atomic positions
    
    Returns:
        Dictionary with position accuracy metrics
    """
    if len(detected_positions) == 0 or len(gt_positions) == 0:
        return {
            "mean_error": float('inf'),
            "rmse": float('inf'),
            "max_error": float('inf'),
            "n_matched": 0,
        }
    
    # Match detected positions to ground truth
    detected_array = np.array(detected_positions)
    gt_array = np.array(gt_positions)
    
    # Calculate distance matrix
    distances = cdist(detected_array, gt_array)
    
    # Find best matches (Hungarian algorithm simplified - greedy matching)
    matched_pairs = []
    used_gt = set()
    used_detected = set()
    
    # Greedy matching: find closest pairs
    while len(matched_pairs) < min(len(detected_positions), len(gt_positions)):
        min_dist = float('inf')
        best_pair = None
        
        for i, det_pos in enumerate(detected_positions):
            if i in used_detected:
                continue
            for j, gt_pos in enumerate(gt_positions):
                if j in used_gt:
                    continue
                dist = distances[i, j]
                if dist < min_dist:
                    min_dist = dist
                    best_pair = (i, j)
        
        if best_pair is None:
            break
        
        matched_pairs.append(best_pair)
        used_detected.add(best_pair[0])
        used_gt.add(best_pair[1])
    
    # Calculate errors for matched pairs
    errors = []
    for det_idx, gt_idx in matched_pairs:
        error = distances[det_idx, gt_idx]
        errors.append(error)
    
    if len(errors) == 0:
        return {
            "mean_error": float('inf'),
            "rmse": float('inf'),
            "max_error": float('inf'),
            "n_matched": 0,
        }
    
    errors = np.array(errors)
    
    return {
        "mean_error": float(np.mean(errors)),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "max_error": float(np.max(errors)),
        "median_error": float(np.median(errors)),
        "n_matched": len(matched_pairs),
        "n_detected": len(detected_positions),
        "n_ground_truth": len(gt_positions),
    }


def calculate_bond_accuracy(
    reconstruction: hs.signals.Signal1D,
    ground_truth: hs.signals.Signal1D,
    detected_positions: List[Tuple[float, float, float]],
    gt_positions: List[Tuple[float, float, float]],
    max_bond_length: float = 3.0
) -> Dict[str, Any]:
    """
    Calculate bond length and angle accuracy.
    
    Args:
        reconstruction: Reconstructed volume
        ground_truth: Ground truth volume
        detected_positions: Detected atomic positions
        gt_positions: Ground truth atomic positions
        max_bond_length: Maximum bond length to consider
    
    Returns:
        Dictionary with bond accuracy metrics
    """
    # Calculate bond lengths in detected and ground truth
    detected_bonds = _calculate_bond_lengths(detected_positions, max_bond_length)
    gt_bonds = _calculate_bond_lengths(gt_positions, max_bond_length)
    
    # Match bonds (simplified)
    # In full implementation, would properly match bonds based on atomic connectivity
    
    # Calculate bond length errors
    bond_length_errors = []
    if len(detected_bonds) > 0 and len(gt_bonds) > 0:
        # Simple comparison (would need proper matching)
        detected_lengths = [b["length"] for b in detected_bonds]
        gt_lengths = [b["length"] for b in gt_bonds]
        
        # Match closest lengths
        for det_len in detected_lengths[:min(len(detected_lengths), len(gt_lengths))]:
            closest_gt = min(gt_lengths, key=lambda x: abs(x - det_len))
            error = abs(det_len - closest_gt)
            bond_length_errors.append(error)
    
    # Calculate bond angles (simplified)
    detected_angles = _calculate_bond_angles(detected_positions, max_bond_length)
    gt_angles = _calculate_bond_angles(gt_positions, max_bond_length)
    
    bond_angle_errors = []
    if len(detected_angles) > 0 and len(gt_angles) > 0:
        detected_angle_values = [a["angle"] for a in detected_angles]
        gt_angle_values = [a["angle"] for a in gt_angles]
        
        for det_angle in detected_angle_values[:min(len(detected_angle_values), len(gt_angle_values))]:
            closest_gt = min(gt_angle_values, key=lambda x: abs(x - det_angle))
            error = abs(det_angle - closest_gt)
            bond_angle_errors.append(error)
    
    return {
        "bond_length_mean_error": float(np.mean(bond_length_errors)) if bond_length_errors else float('inf'),
        "bond_length_rmse": float(np.sqrt(np.mean(np.array(bond_length_errors)**2))) if bond_length_errors else float('inf'),
        "bond_angle_mean_error": float(np.mean(bond_angle_errors)) if bond_angle_errors else float('inf'),
        "bond_angle_rmse": float(np.sqrt(np.mean(np.array(bond_angle_errors)**2))) if bond_angle_errors else float('inf'),
        "n_bonds_detected": len(detected_bonds),
        "n_bonds_gt": len(gt_bonds),
        "n_angles_detected": len(detected_angles),
        "n_angles_gt": len(gt_angles),
    }


def _calculate_bond_lengths(
    positions: List[Tuple[float, float, float]],
    max_length: float
) -> List[Dict[str, Any]]:
    """
    Calculate bond lengths between atoms.
    
    Args:
        positions: Atomic positions
        max_length: Maximum bond length
    
    Returns:
        List of bond dictionaries
    """
    bonds = []
    positions_array = np.array(positions)
    
    # Calculate pairwise distances
    distances = cdist(positions_array, positions_array)
    
    # Find bonds (distances < max_length, excluding self)
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            dist = distances[i, j]
            if dist <= max_length:
                bonds.append({
                    "atom1": i,
                    "atom2": j,
                    "length": float(dist),
                })
    
    return bonds


def _calculate_bond_angles(
    positions: List[Tuple[float, float, float]],
    max_length: float
) -> List[Dict[str, Any]]:
    """
    Calculate bond angles.
    
    Args:
        positions: Atomic positions
        max_length: Maximum bond length
    
    Returns:
        List of angle dictionaries
    """
    angles = []
    positions_array = np.array(positions)
    
    # Find triplets of atoms forming angles
    # For each atom, find its neighbors
    distances = cdist(positions_array, positions_array)
    
    for center_idx in range(len(positions)):
        # Find neighbors
        neighbors = [i for i in range(len(positions)) 
                    if i != center_idx and distances[center_idx, i] <= max_length]
        
        # Calculate angles between neighbor pairs
        for i, neighbor1 in enumerate(neighbors):
            for neighbor2 in neighbors[i+1:]:
                # Calculate angle at center
                vec1 = positions_array[neighbor1] - positions_array[center_idx]
                vec2 = positions_array[neighbor2] - positions_array[center_idx]
                
                # Normalize
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)
                
                if norm1 > 0 and norm2 > 0:
                    cos_angle = np.dot(vec1, vec2) / (norm1 * norm2)
                    cos_angle = np.clip(cos_angle, -1, 1)
                    angle = np.degrees(np.arccos(cos_angle))
                    
                    angles.append({
                        "center": center_idx,
                        "atom1": neighbor1,
                        "atom2": neighbor2,
                        "angle": float(angle),
                    })
    
    return angles


