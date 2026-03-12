"""
Memory management utilities.

Monitors memory usage and provides memory-efficient data processing.
"""

import psutil
import os
from typing import Optional, Callable, Any, Dict
import numpy as np


class MemoryManager:
    """
    Memory usage monitoring and management.
    
    Tracks memory usage and provides utilities for memory-efficient processing.
    """
    
    def __init__(self, warning_threshold: float = 0.8, critical_threshold: float = 0.9):
        """
        Initialize memory manager.
        
        Args:
            warning_threshold: Memory usage warning threshold (0-1)
            critical_threshold: Memory usage critical threshold (0-1)
        """
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
    
    def get_memory_usage(self) -> Dict[str, float]:
        """
        Get current memory usage.
        
        Returns:
            Dictionary with memory usage information
        """
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        
        system_mem = psutil.virtual_memory()
        
        return {
            "process_rss": float(mem_info.rss),  # Resident Set Size
            "process_vms": float(mem_info.vms),  # Virtual Memory Size
            "system_total": float(system_mem.total),
            "system_available": float(system_mem.available),
            "system_percent": float(system_mem.percent),
        }
    
    def check_memory_status(self) -> str:
        """
        Check current memory status.
        
        Returns:
            Status: 'ok', 'warning', or 'critical'
        """
        usage = self.get_memory_usage()
        percent = usage["system_percent"] / 100.0
        
        if percent >= self.critical_threshold:
            return "critical"
        elif percent >= self.warning_threshold:
            return "warning"
        else:
            return "ok"
    
    def process_in_chunks(
        self,
        data: np.ndarray,
        chunk_size: int,
        process_func: Callable[[np.ndarray], Any]
    ) -> Any:
        """
        Process large data in chunks to reduce memory usage.
        
        Args:
            data: Data array to process
            chunk_size: Size of each chunk
            process_func: Function to process each chunk
        
        Returns:
            Processed result
        """
        results = []
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            result = process_func(chunk)
            results.append(result)
        
        # Combine results (simplified - would need proper combination logic)
        return results

