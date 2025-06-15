import time
import threading
from cache import create_cache


def basic_operations_demo():
    """Demonstrate basic cache operations."""
    print("\n=== Basic Operations Demo ===")
    cache = create_cache(max_size=1000, default_ttl=300)
    
    # Put and get operations
    print("Adding items to cache...")
    cache.put("config:db_host", "localhost:5432")
    cache.put("config:api_key", "abc123", ttl=60)
    
    print(f"Retrieved db_host: {cache.get('config:db_host')}")
    print(f"Retrieved api_key: {cache.get('config:api_key')}")
    
    # Delete operation
    print("\nDeleting an item...")
    cache.delete("config:db_host")
    print(f"After deletion, db_host: {cache.get('config:db_host')}")
    
    # Clear operation
    print("\nClearing the cache...")
    cache.put("temp_key", "temp_value")
    cache.clear()
    print(f"After clearing, temp_key: {cache.get('temp_key')}")
    
    # Cleanup
    cache.shutdown()


def eviction_demo():
    """Demonstrate LRU eviction when cache is full."""
    print("\n=== LRU Eviction Demo ===")
    cache = create_cache(max_size=10)
    
    print("Adding 10 items to fill the cache...")
    for i in range(10):
        cache.put(f"key{i}", f"value{i}")
        print(f"Added key{i}")
    
    print("\nAccessing first 3 items to update LRU order...")
    for i in range(3):
        print(f"Accessed key{i}: {cache.get(f'key{i}')}")
    
    print("\nAdding a new item to trigger eviction...")
    cache.put("new_key", "new_value")
    
    print("\nChecking which item was evicted (should be key3)...")
    for i in range(10):
        value = cache.get(f"key{i}")
        print(f"key{i}: {'Present' if value else 'Evicted'}")
    
    print(f"new_key: {'Present' if cache.get('new_key') else 'Evicted'}")
    
    print("\nCache statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Cleanup
    cache.shutdown()


def expiration_demo():
    """Demonstrate TTL expiration."""
    print("\n=== TTL Expiration Demo ===")
    cache = create_cache()
    
    print("Adding item with 2-second TTL...")
    cache.put("temp_data", "expires_soon", ttl=2)
    
    print(f"Immediately after: {cache.get('temp_data')}")
    
    print("Waiting 3 seconds for expiration...")
    time.sleep(3)
    
    print(f"After waiting: {cache.get('temp_data')}")
    
    print("\nCache statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Cleanup
    cache.shutdown()


def concurrent_access_demo():
    """Demonstrate concurrent access to the cache."""
    print("\n=== Concurrent Access Demo ===")
    cache = create_cache(max_size=1000)
    
    def worker(thread_id):
        for i in range(100):
            cache.put(f"thread_{thread_id}:item_{i}", f"data_{i}")
            cache.get(f"thread_{thread_id}:item_{i//2}")
    
    print("Starting 5 worker threads...")
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    print("All threads completed")
    
    print("\nCache statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Cleanup
    cache.shutdown()


def main():
    print("Thread-Safe Cache System Demo")
    print("============================")
    
    basic_operations_demo()
    eviction_demo()
    expiration_demo()
    concurrent_access_demo()


if __name__ == "__main__":
    main()