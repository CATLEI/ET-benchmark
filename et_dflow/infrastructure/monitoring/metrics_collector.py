"""
Metrics collection for monitoring.

Collects Prometheus-style metrics for workflow monitoring.
"""

from typing import Dict, Any, Optional
from collections import defaultdict
import time
from datetime import datetime


class MetricsCollector:
    """
    Collects metrics for monitoring.
    
    Provides Prometheus-style metrics collection.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, Any] = defaultdict(list)
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, list] = defaultdict(list)
    
    def increment_counter(self, name: str, labels: Optional[Dict[str, str]] = None):
        """
        Increment counter metric.
        
        Args:
            name: Metric name
            labels: Optional labels
        """
        key = self._make_key(name, labels)
        self.counters[key] += 1
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Set gauge metric.
        
        Args:
            name: Metric name
            value: Gauge value
            labels: Optional labels
        """
        key = self._make_key(name, labels)
        self.gauges[key] = value
    
    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Observe histogram value.
        
        Args:
            name: Metric name
            value: Observed value
            labels: Optional labels
        """
        key = self._make_key(name, labels)
        self.histograms[key].append(value)
    
    def record_execution_time(
        self,
        operation: str,
        duration: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """
        Record operation execution time.
        
        Args:
            operation: Operation name
            duration: Duration in seconds
            labels: Optional labels
        """
        self.observe_histogram(f"{operation}_duration_seconds", duration, labels)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.
        
        Returns:
            Dictionary with all metrics
        """
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {
                k: {
                    "count": len(v),
                    "sum": sum(v),
                    "mean": sum(v) / len(v) if v else 0,
                    "min": min(v) if v else 0,
                    "max": max(v) if v else 0,
                }
                for k, v in self.histograms.items()
            },
        }
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Make metric key from name and labels."""
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name

