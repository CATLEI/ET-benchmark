"""
Evaluation metrics chain implementation.

Implements Chain of Responsibility pattern for evaluation metrics.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.core.models import AlgorithmResult, EvaluationResult


class MetricHandler(ABC):
    """
    Base handler for evaluation metrics chain.
    
    Implements Chain of Responsibility pattern.
    Each handler processes one or more metrics and passes
    control to the next handler.
    
    Example:
        handler1 = PSNRMetricHandler()
        handler2 = SSIMMetricHandler(handler1)
        metrics = handler2.process(result, ground_truth)
    """
    
    def __init__(self, next_handler: Optional['MetricHandler'] = None):
        """
        Initialize metric handler.
        
        Args:
            next_handler: Next handler in the chain
        """
        self.next = next_handler
    
    @abstractmethod
    def handle(
        self,
        result: AlgorithmResult,
        ground_truth: Optional[Signal] = None
    ) -> Dict[str, Any]:
        """
        Handle evaluation metric calculation.
        
        Args:
            result: Algorithm result to evaluate
            ground_truth: Ground truth data (optional)
        
        Returns:
            Dictionary with metric name and value
        """
        pass
    
    def process(
        self,
        result: AlgorithmResult,
        ground_truth: Optional[Signal] = None
    ) -> Dict[str, Any]:
        """
        Process evaluation through chain.
        
        Args:
            result: Algorithm result to evaluate
            ground_truth: Ground truth data (optional)
        
        Returns:
            Combined dictionary of all metrics from chain
        """
        metrics = self.handle(result, ground_truth)
        
        if self.next:
            next_metrics = self.next.process(result, ground_truth)
            metrics.update(next_metrics)
        
        return metrics


class PSNRMetricHandler(MetricHandler):
    """PSNR metric handler."""
    
    def handle(
        self,
        result: AlgorithmResult,
        ground_truth: Optional[Signal] = None
    ) -> Dict[str, Any]:
        """
        Calculate PSNR metric.
        
        Args:
            result: Algorithm result
            ground_truth: Ground truth data
        
        Returns:
            Dictionary with 'psnr' key
        """
        if ground_truth is None:
            return {}
        
        # Convert to numpy arrays if needed
        recon_data = result.reconstruction.data
        gt_data = ground_truth.data
        if hasattr(recon_data, '__array__'):
            recon_data = np.asarray(recon_data)
        if hasattr(gt_data, '__array__'):
            gt_data = np.asarray(gt_data)
        
        psnr = self._calculate_psnr(recon_data, gt_data)
        
        return {"psnr": float(psnr)}
    
    @staticmethod
    def _calculate_psnr(reconstruction: Any, ground_truth: Any) -> float:
        """
        Calculate PSNR between reconstruction and ground truth.
        
        Args:
            reconstruction: Reconstructed data
            ground_truth: Ground truth data
        
        Returns:
            PSNR value in dB
        """
        import numpy as np
        
        # Convert to numpy arrays if needed
        if hasattr(reconstruction, "data"):
            recon_data = reconstruction.data
        else:
            recon_data = reconstruction
        
        if hasattr(ground_truth, "data"):
            gt_data = ground_truth.data
        else:
            gt_data = ground_truth
        
        # Ensure numpy arrays
        recon_data = np.asarray(recon_data)
        gt_data = np.asarray(gt_data)
        
        # Calculate MSE
        mse = np.mean((recon_data - gt_data) ** 2)
        
        if mse == 0:
            return float("inf")
        
        # Calculate PSNR
        max_val = gt_data.max()
        psnr = 20 * np.log10(max_val / np.sqrt(mse))
        
        return float(psnr)


class SSIMMetricHandler(MetricHandler):
    """SSIM metric handler."""
    
    def handle(
        self,
        result: AlgorithmResult,
        ground_truth: Optional[Signal] = None
    ) -> Dict[str, Any]:
        """
        Calculate SSIM metric.
        
        Args:
            result: Algorithm result
            ground_truth: Ground truth data
        
        Returns:
            Dictionary with 'ssim' key
        """
        if ground_truth is None:
            return {}
        
        # Convert to numpy arrays if needed
        recon_data = result.reconstruction.data
        gt_data = ground_truth.data
        if hasattr(recon_data, '__array__'):
            recon_data = np.asarray(recon_data)
        if hasattr(gt_data, '__array__'):
            gt_data = np.asarray(gt_data)
        
        ssim = self._calculate_ssim(recon_data, gt_data)
        
        return {"ssim": float(ssim)}
    
    @staticmethod
    def _calculate_ssim(reconstruction: Any, ground_truth: Any) -> float:
        """
        Calculate SSIM between reconstruction and ground truth.
        
        Simplified SSIM calculation.
        
        Args:
            reconstruction: Reconstructed data
            ground_truth: Ground truth data
        
        Returns:
            SSIM value (0-1)
        """
        import numpy as np
        
        # Convert to numpy arrays if needed
        if hasattr(reconstruction, "data"):
            recon_data = reconstruction.data
        else:
            recon_data = reconstruction
        
        if hasattr(ground_truth, "data"):
            gt_data = ground_truth.data
        else:
            gt_data = ground_truth
        
        # Ensure numpy arrays
        recon_data = np.asarray(recon_data)
        gt_data = np.asarray(gt_data)
        
        # Flatten for 3D comparison
        recon_flat = recon_data.flatten()
        gt_flat = gt_data.flatten()
        
        # Constants
        C1 = 0.01 ** 2
        C2 = 0.03 ** 2
        
        # Calculate means
        mu1 = np.mean(recon_flat)
        mu2 = np.mean(gt_flat)
        
        # Calculate variances and covariance
        sigma1_sq = np.var(recon_flat)
        sigma2_sq = np.var(gt_flat)
        sigma12 = np.mean((recon_flat - mu1) * (gt_flat - mu2))
        
        # Calculate SSIM
        numerator = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
        denominator = (mu1 ** 2 + mu2 ** 2 + C1) * (sigma1_sq + sigma2_sq + C2)
        
        ssim = numerator / denominator if denominator > 0 else 0.0
        
        return float(ssim)


class MSEMetricHandler(MetricHandler):
    """MSE metric handler."""
    
    def handle(
        self,
        result: AlgorithmResult,
        ground_truth: Optional[Signal] = None
    ) -> Dict[str, Any]:
        """
        Calculate MSE metric.
        
        Args:
            result: Algorithm result
            ground_truth: Ground truth data
        
        Returns:
            Dictionary with 'mse' key
        """
        if ground_truth is None:
            return {}
        
        # Convert to numpy arrays if needed
        recon_data = result.reconstruction.data
        gt_data = ground_truth.data
        if hasattr(recon_data, '__array__'):
            recon_data = np.asarray(recon_data)
        if hasattr(gt_data, '__array__'):
            gt_data = np.asarray(gt_data)
        
        mse = self._calculate_mse(recon_data, gt_data)
        
        return {"mse": float(mse)}
    
    @staticmethod
    def _calculate_mse(reconstruction: Any, ground_truth: Any) -> float:
        """
        Calculate MSE between reconstruction and ground truth.
        
        Args:
            reconstruction: Reconstructed data
            ground_truth: Ground truth data
        
        Returns:
            MSE value
        """
        import numpy as np
        
        # Convert to numpy arrays if needed
        if hasattr(reconstruction, "data"):
            recon_data = reconstruction.data
        else:
            recon_data = reconstruction
        
        if hasattr(ground_truth, "data"):
            gt_data = ground_truth.data
        else:
            gt_data = ground_truth
        
        # Ensure numpy arrays
        recon_data = np.asarray(recon_data)
        gt_data = np.asarray(gt_data)
        
        mse = np.mean((recon_data - gt_data) ** 2)
        
        return float(mse)


def build_evaluation_chain(metrics: List[str]) -> Optional[MetricHandler]:
    """
    Build evaluation metric chain.
    
    Args:
        metrics: List of metric names to include
    
    Returns:
        First handler in the chain, or None if no metrics
    
    Example:
        chain = build_evaluation_chain(['psnr', 'ssim', 'mse'])
        metrics = chain.process(result, ground_truth)
    """
    handlers = {
        "psnr": PSNRMetricHandler,
        "ssim": SSIMMetricHandler,
        "mse": MSEMetricHandler,
    }
    
    chain = None
    for metric in reversed(metrics):
        handler_class = handlers.get(metric.lower())
        if handler_class:
            chain = handler_class(chain)
    
    return chain

