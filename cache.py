import threading
import time
from typing import Any, Dict, Optional, TypedDict


class CacheStats(TypedDict):
    """Type definition for cache statistics."""
    hits: int
    misses: int
    hit_rate: float
    total_requests: int
    current_size: int
    evictions: int
    expired_removals: int


class CacheNode:
    """Node in the doubly linked list for LRU tracking."""
    def __init__(self, key: str, value: Any, expiry: float = 0):
        self.key = key
        self.value = value
        self.expiry = expiry  # Timestamp when this entry expires (0 means no expiration)
        self.prev = None
        self.next = None


class ThreadSafeCache:
    """A thread-safe in-memory cache with LRU eviction and TTL support."""
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = None):
        """Initialize the cache.
        
        Args:
            max_size: Maximum number of entries in the cache
            default_ttl: Default time-to-live in seconds (None means no expiration)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        
        # Core data structures
        self.cache: Dict[str, CacheNode] = {}  # Key-value store
        self.head = CacheNode("", None)  # Dummy head for the doubly linked list
        self.tail = CacheNode("", None)  # Dummy tail for the doubly linked list
        self.head.next = self.tail
        self.tail.prev = self.head
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expired_removals = 0
        
        # Thread safety
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        
        # Background cleanup thread
        self.cleanup_interval = 60  # Cleanup every 60 seconds
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.running = True
        self.cleanup_thread.start()
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Insert a key-value pair with optional TTL.
        
        Args:
            key: The key to store
            value: The value to store
            ttl: Time-to-live in seconds (None means use default_ttl)
        """
        if key is None or key == "":
            raise ValueError("Key cannot be None or empty")
        
        with self.lock:
            # Calculate expiry time
            expiry = 0
            if ttl is not None:
                expiry = time.time() + ttl
            elif self.default_ttl is not None:
                expiry = time.time() + self.default_ttl
            
            # Check if key already exists
            if key in self.cache:
                # Update existing entry
                node = self.cache[key]
                node.value = value
                node.expiry = expiry
                # Move to front (most recently used)
                self._remove_node(node)
                self._add_to_front(node)
            else:
                # Create new entry
                node = CacheNode(key, value, expiry)
                self.cache[key] = node
                self._add_to_front(node)
                
                # Check if we need to evict
                if len(self.cache) > self.max_size:
                    self._evict_lru()
    
    def get(self, key: str) -> Any:
        """Retrieve a value by key and update access order.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The value or None if not found or expired
        """
        with self.lock:
            if key in self.cache:
                node = self.cache[key]
                
                # Check if expired
                if self._is_expired(node):
                    self._remove_node(node)
                    del self.cache[key]
                    self.expired_removals += 1
                    self.misses += 1
                    return None
                
                # Move to front (most recently used)
                self._remove_node(node)
                self._add_to_front(node)
                
                self.hits += 1
                return node.value
            else:
                self.misses += 1
                return None
    
    def delete(self, key: str) -> bool:
        """Remove a specific key from the cache.
        
        Args:
            key: The key to delete
            
        Returns:
            True if the key was found and deleted, False otherwise
        """
        with self.lock:
            if key in self.cache:
                node = self.cache[key]
                self._remove_node(node)
                del self.cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Empty the entire cache."""
        with self.lock:
            self.cache.clear()
            # Reset the linked list
            self.head.next = self.tail
            self.tail.prev = self.head
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics.
        
        Returns:
            A dictionary with cache statistics
        """
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0
            
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "total_requests": total_requests,
                "current_size": len(self.cache),
                "evictions": self.evictions,
                "expired_removals": self.expired_removals
            }
    
    def _add_to_front(self, node: CacheNode) -> None:
        """Add a node to the front of the doubly linked list (most recently used)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node
    
    def _remove_node(self, node: CacheNode) -> None:
        """Remove a node from the doubly linked list."""
        node.prev.next = node.next
        node.next.prev = node.prev
    
    def _evict_lru(self) -> None:
        """Evict the least recently used item from the cache."""
        if not self.cache:  # Safety check
            return
        
        # The LRU node is at the end of the list (just before tail)
        lru_node = self.tail.prev
        if lru_node == self.head:  # Safety check
            return
        
        # Remove from linked list and dictionary
        self._remove_node(lru_node)
        del self.cache[lru_node.key]
        self.evictions += 1
    
    def _is_expired(self, node: CacheNode) -> bool:
        """Check if a cache entry has expired.
        
        Args:
            node: The cache node to check
            
        Returns:
            True if expired, False otherwise
        """
        return node.expiry > 0 and time.time() > node.expiry
    
    def _cleanup_worker(self) -> None:
        """Background worker that periodically removes expired entries."""
        while self.running:
            time.sleep(self.cleanup_interval)
            self._cleanup_expired()
    
    def _cleanup_expired(self) -> None:
        """Remove all expired entries from the cache."""
        with self.lock:
            # Create a list of expired keys to avoid modifying the dictionary during iteration
            expired_keys = []
            current_time = time.time()
            
            for key, node in self.cache.items():
                if node.expiry > 0 and current_time > node.expiry:
                    expired_keys.append(key)
            
            # Remove expired entries
            for key in expired_keys:
                node = self.cache[key]
                self._remove_node(node)
                del self.cache[key]
                self.expired_removals += 1
    
    def shutdown(self) -> None:
        """Shutdown the cache and stop the cleanup thread."""
        self.running = False
        if self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=1.0)


def create_cache(max_size: int = 1000, default_ttl: Optional[int] = None) -> ThreadSafeCache:
    """Factory function to create a new cache instance.
    
    Args:
        max_size: Maximum number of entries in the cache
        default_ttl: Default time-to-live in seconds (None means no expiration)
        
    Returns:
        A new ThreadSafeCache instance
    """
    return ThreadSafeCache(max_size, default_ttl)