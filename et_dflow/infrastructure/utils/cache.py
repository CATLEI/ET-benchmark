"""
Result caching implementation.

Provides caching mechanism for algorithm results and evaluations.
"""

import hashlib
import json
import time
from typing import Any, Optional, Callable, Dict
from pathlib import Path
from functools import wraps


class ResultCache:
    """
    Cache for algorithm results and evaluations.
    
    Uses hash-based keys and supports TTL (time-to-live).
    """
    
    def __init__(self, cache_dir: Optional[Path] = None, default_ttl: float = 3600.0):
        """
        Initialize result cache.
        
        Args:
            cache_dir: Directory for cache files
            default_ttl: Default TTL in seconds
        """
        self.cache_dir = cache_dir or Path(".cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def _generate_key(self, *args, **kwargs) -> str:
        """
        Generate cache key from arguments.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Cache key (hash string)
        """
        # Create hash from arguments
        key_data = {
            "args": args,
            "kwargs": kwargs,
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return key_hash
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        # Check TTL
        if time.time() > entry["expires_at"]:
            # Expired
            del self._cache[key]
            return None
        
        return entry["value"]
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        ttl = ttl or self.default_ttl
        expires_at = time.time() + ttl
        
        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": time.time(),
        }
    
    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()


def cached(ttl: Optional[float] = None):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time-to-live in seconds
    
    Returns:
        Decorated function
    """
    cache = ResultCache(default_ttl=ttl or 3600.0)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache._generate_key(*args, **kwargs)
            
            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(key, result, ttl=ttl)
            
            return result
        
        return wrapper
    
    return decorator

