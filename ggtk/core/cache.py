"""
Caching utilities for GGTK to improve performance.
"""

from typing import Any, Dict, Optional, Callable
import hashlib
import time
from functools import wraps


class LRUCache:
    """
    Simple LRU (Least Recently Used) cache implementation.
    
    Thread-safe for read operations; write operations should be 
    synchronized externally if needed.
    """
    
    def __init__(self, maxsize: int = 100):
        self._cache: Dict[str, Any] = {}
        self._access_order: list = []
        self._maxsize = maxsize
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache. Returns None if not found."""
        if key in self._cache:
            self._hits += 1
            # Move to end (most recently used)
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        self._misses += 1
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set item in cache, evicting LRU item if necessary."""
        if key in self._cache:
            # Update existing
            self._access_order.remove(key)
        elif len(self._cache) >= self._maxsize:
            # Evict least recently used
            oldest_key = self._access_order.pop(0)
            del self._cache[oldest_key]
        
        self._cache[key] = value
        self._access_order.append(key)
    
    def delete(self, key: str) -> bool:
        """Delete item from cache. Returns True if deleted."""
        if key in self._cache:
            del self._cache[key]
            self._access_order.remove(key)
            return True
        return False
    
    def clear(self) -> None:
        """Clear all items from cache."""
        self._cache.clear()
        self._access_order.clear()
        self._hits = 0
        self._misses = 0
    
    @property
    def size(self) -> int:
        """Current number of items in cache."""
        return len(self._cache)
    
    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'size': self.size,
            'maxsize': self._maxsize,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': self.hit_rate,
        }


class TTLCache:
    """
    Time-To-Live cache that expires items after a specified duration.
    """
    
    def __init__(self, ttl_seconds: int = 300, maxsize: int = 100):
        self._cache: Dict[str, tuple] = {}  # key -> (value, expiry_time)
        self._maxsize = maxsize
        self._ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        """Get item if not expired."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            else:
                # Expired
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set item with TTL."""
        if len(self._cache) >= self._maxsize:
            # Remove oldest expired items first
            now = time.time()
            expired = [k for k, (_, exp) in self._cache.items() if now >= exp]
            for k in expired:
                del self._cache[k]
            
            # If still full, remove arbitrary item
            if len(self._cache) >= self._maxsize:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
        
        expiry = time.time() + self._ttl
        self._cache[key] = (value, expiry)
    
    def clear(self) -> None:
        """Clear all items."""
        self._cache.clear()


def cache_result(cache: LRUCache, key_func: Callable = None):
    """
    Decorator to cache function results.
    
    Parameters
    ----------
    cache : LRUCache
        Cache instance to use
    key_func : callable, optional
        Function to generate cache key from arguments.
        Defaults to hashing all args and kwargs.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default: hash args and kwargs
                key_str = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
                key = hashlib.md5(key_str.encode()).hexdigest()
            
            # Try cache
            result = cache.get(key)
            if result is not None:
                return result
            
            # Compute and cache
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result
        
        # Attach cache to function for inspection/clearing
        wrapper.cache = cache
        return wrapper
    return decorator


# Module-level caches
grammar_cache = LRUCache(maxsize=10)
analysis_cache = LRUCache(maxsize=1000)
phonology_cache = LRUCache(maxsize=100)
