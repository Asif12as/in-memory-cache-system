import unittest
import time
import threading
from cache import create_cache


class TestThreadSafeCache(unittest.TestCase):
    def setUp(self):
        # Create a new cache for each test
        self.cache = create_cache(max_size=10, default_ttl=60)
    
    def tearDown(self):
        # Ensure cleanup thread is stopped
        self.cache.shutdown()
    
    def test_basic_operations(self):
        """Test basic put, get, delete operations."""
        # Put and get
        self.cache.put("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")
        
        # Update existing key
        self.cache.put("key1", "updated_value")
        self.assertEqual(self.cache.get("key1"), "updated_value")
        
        # Get non-existent key
        self.assertIsNone(self.cache.get("non_existent_key"))
        
        # Delete
        self.assertTrue(self.cache.delete("key1"))
        self.assertIsNone(self.cache.get("key1"))
        
        # Delete non-existent key
        self.assertFalse(self.cache.delete("non_existent_key"))
        
        # Clear
        self.cache.put("key2", "value2")
        self.cache.clear()
        self.assertIsNone(self.cache.get("key2"))
    
    def test_ttl_expiration(self):
        """Test that entries expire after their TTL."""
        # Put with short TTL
        self.cache.put("temp_key", "temp_value", ttl=1)
        
        # Should be available immediately
        self.assertEqual(self.cache.get("temp_key"), "temp_value")
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired now
        self.assertIsNone(self.cache.get("temp_key"))
        
        # Test with default TTL
        cache_with_short_ttl = create_cache(max_size=10, default_ttl=1)
        cache_with_short_ttl.put("another_key", "another_value")
        
        # Should be available immediately
        self.assertEqual(cache_with_short_ttl.get("another_key"), "another_value")
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired now
        self.assertIsNone(cache_with_short_ttl.get("another_key"))
        
        # Cleanup
        cache_with_short_ttl.shutdown()
    
    def test_lru_eviction(self):
        """Test that least recently used items are evicted when cache is full."""
        # Fill the cache to capacity (max_size=10)
        for i in range(10):
            self.cache.put(f"key{i}", f"value{i}")
        
        # Verify all items are in the cache
        for i in range(10):
            self.assertEqual(self.cache.get(f"key{i}"), f"value{i}")
        
        # Access some items to change LRU order
        # key0, key1, key2 are now most recently used
        for i in range(3):
            self.cache.get(f"key{i}")
        
        # Add a new item to trigger eviction
        self.cache.put("new_key", "new_value")
        
        # Verify the least recently used item (key3) was evicted
        self.assertIsNone(self.cache.get("key3"))
        
        # Verify other items are still in the cache
        for i in range(3):
            self.assertEqual(self.cache.get(f"key{i}"), f"value{i}")
        for i in range(4, 10):
            self.assertEqual(self.cache.get(f"key{i}"), f"value{i}")
        self.assertEqual(self.cache.get("new_key"), "new_value")
    
    def test_statistics(self):
        """Test that cache statistics are tracked correctly."""
        # Initial stats
        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["current_size"], 0)
        
        # Add some hits and misses
        self.cache.put("key1", "value1")
        self.cache.get("key1")  # Hit
        self.cache.get("key1")  # Hit
        self.cache.get("missing")  # Miss
        
        # Check updated stats
        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["current_size"], 1)
        self.assertEqual(stats["total_requests"], 3)
        self.assertAlmostEqual(stats["hit_rate"], 2/3)
        
        # Test eviction stats
        cache_for_eviction = create_cache(max_size=3)
        for i in range(5):  # This should cause 2 evictions
            cache_for_eviction.put(f"key{i}", f"value{i}")
        
        stats = cache_for_eviction.get_stats()
        self.assertEqual(stats["evictions"], 2)
        self.assertEqual(stats["current_size"], 3)
        
        # Cleanup
        cache_for_eviction.shutdown()
        
        # Test expiration stats
        cache_for_expiration = create_cache(default_ttl=1)
        cache_for_expiration.put("temp1", "value1")
        cache_for_expiration.put("temp2", "value2")
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Trigger expiration check
        cache_for_expiration.get("temp1")
        cache_for_expiration.get("temp2")
        
        stats = cache_for_expiration.get_stats()
        self.assertEqual(stats["expired_removals"], 2)
        
        # Cleanup
        cache_for_expiration.shutdown()
    
    def test_concurrent_access(self):
        """Test that the cache handles concurrent access correctly."""
        # Create a larger cache for concurrent testing
        concurrent_cache = create_cache(max_size=1000)
        
        def worker(thread_id):
            for i in range(100):
                # Put operation
                concurrent_cache.put(f"thread_{thread_id}:item_{i}", f"data_{i}")
                # Get operation (half of the items)
                concurrent_cache.get(f"thread_{thread_id}:item_{i//2}")
        
        # Create and start multiple threads
        threads = []
        for i in range(10):  # 10 threads
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify that the cache contains the expected items
        # Each thread adds 100 items, but due to the cache size limit and LRU eviction,
        # we expect the cache to contain items from the most recent operations
        stats = concurrent_cache.get_stats()
        self.assertEqual(stats["current_size"], 1000)  # Cache should be full
        
        # Cleanup
        concurrent_cache.shutdown()
    
    def test_invalid_keys(self):
        """Test handling of invalid keys."""
        with self.assertRaises(ValueError):
            self.cache.put(None, "value")
        
        with self.assertRaises(ValueError):
            self.cache.put("", "value")


if __name__ == "__main__":
    unittest.main()