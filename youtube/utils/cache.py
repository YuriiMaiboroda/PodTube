
import datetime
from typing import Callable

class CacheItem:
    """
    Represents a cache item with an expiration time.
    """

    def __init__(self, expire: datetime.datetime, name: str = None):
        self.__expire = expire
        self.__name = name

    @property
    def name(self) -> str:
        """
        Returns the name of the cache item.
        
        Returns:
            str: The name of the cache item.
        """
        return self.__name
    
    @name.setter
    def name(self, value: str):
        """
        Sets the name of the cache item.
        
        Args:
            value (str): The name to set for the cache item.
        """
        self.__name = value
    
    @property
    def expire(self) -> datetime.datetime:
        """
        Returns the expiration time of the cache item.
        
        Returns:
            datetime.datetime: The expiration time of the cache item.
        """
        return self.__expire
    
    def clear(self):
        """
        Clears the cache item.
        This method can be overridden in subclasses to implement specific clearing logic.
        """
        pass

class CacheManager:
    """
    A simple cache manager that allows storing, retrieving, and managing cache items.
    """
    def __init__(self):
        self.__cache:dict[str, dict[str, CacheItem]] = {}


    def get(self, cache_name: str, item_name: str) -> CacheItem | None:
        """
        Retrieves a cache item by its name from the specified cache.

        Args:
            cache_name (str): The name of the cache.
            item_name (str): The name of the item to retrieve.

        Returns:
            CacheItem | None: The cache item if found, otherwise None.
        """
        return self.__cache.get(cache_name, {}).get(item_name, None)

    def set(self, cache_name: str, item_name: str, item: CacheItem):
        """
        Sets a cache item in the specified cache.
        Args:
            cache_name (str): The name of the cache.
            item_name (str): The name of the item to set.
            item (CacheItem): The cache item to set.
        """
        if cache_name not in self.__cache:
            self.__cache[cache_name] = {}
        self.__cache[cache_name][item_name] = item

    def has(self, cache_name: str, item_name: str) -> bool:
        """
        Checks if a cache item exists in the specified cache.
        
        Args:
            cache_name (str): The name of the cache.
            item_name (str): The name of the item to check.
        
        Returns:
            bool: True if the item exists, False otherwise.
        """
        return cache_name in self.__cache and item_name in self.__cache[cache_name]

    def add_if_not_exists(self, cache_name: str, item_name: str, item: CacheItem|Callable[[], CacheItem]) -> bool:
        """
        Adds a cache item to the specified cache if it does not already exist.
        
        Args:
            cache_name (str): The name of the cache.
            item_name (str): The name of the item to add.
            item (CacheItem): The cache item to add.
        
        Returns:
            bool: True if the item was added, False if it already exists.
        """
        if not self.has(cache_name, item_name):
            if callable(item):
                item = item()
            self.set(cache_name, item_name, item)
            return True
        return False
    
    def get_or_add(self, cache_name: str, item_name: str, item: CacheItem|Callable[[], CacheItem]) -> CacheItem:
        """
        Retrieves a cache item by its name from the specified cache, or adds it if it does not exist.
        
        Args:
            cache_name (str): The name of the cache.
            item_name (str): The name of the item to retrieve or add.
            item (CacheItem): The cache item to add if it does not exist.
        
        Returns:
            CacheItem: The retrieved or added cache item.
        """
        self.add_if_not_exists(cache_name, item_name, item)
        return self.get(cache_name, item_name)

    def remove_cache_item(self, cache_name: str, item_name: str):
        """
        Removes a cache item by its name from the specified cache.
        Args:
            cache_name (str): The name of the cache.
            item_name (str): The name of the item to remove.
        """
        if cache_name in self.__cache and item_name in self.__cache[cache_name]:
            del self.__cache[cache_name][item_name]
            # if not self.__cache[cache_name]:  # Remove the cache if it's empty
            #     del self.__cache[cache_name]

    def clear_cache(self, cache_name: str):
        """
        Clears all items from the specified cache.
        
        Args:
            cache_name (str): The name of the cache to clear.
        """
        if cache_name in self.self.__cache:
            del self.__cache[cache_name]

    def clear_all_caches(self):
        """
        Clears all caches.
        """
        self.__cache = {}

    def get_cache_names(self) -> list[str]:
        """
        Retrieves the names of all caches.
        Returns:
            list[str]: A list of cache names.
        """
        return list(self.__cache.keys())

    def get_cache_items(self, cache_name: str) -> dict[str, CacheItem]:
        """
        Retrieves all items from the specified cache.
        Args:
            cache_name (str): The name of the cache.
        Returns:
            dict[str, CacheItem]: A dictionary of cache items.
        """
        return self.__cache.get(cache_name, {}).copy()  # Return a copy to avoid external modifications

    def get_all_cache_items(self) -> dict[str, dict[str, CacheItem]]:
        """
        Retrieves all cache items from all caches.
        Returns:
            dict[str, dict[str, CacheItem]]: A dictionary of all cache items.
        """
        return {cache_name: items.copy() for cache_name, items in self.__cache.items()}  # Return copies to avoid external modifications

    def cleanup_cache(self, cache_name: str, item_name:str|None = None) -> int:
        """
        Cleans up a specific cache or a specific item in a cache.
        Args:
            cache_name (str): The name of the cache to clean up.
            item_name (str|None): The name of the item to clean up. If None, cleans the entire cache.
        Returns:
            int: The number of items removed from the cache. If item_name is specified, returns 1 if the item was removed, otherwise 0.
        """
        if cache_name not in self.__cache:
            return 0

        old_count = len(self.__cache[cache_name])
        items = self.__cache[cache_name]
        items_to_remove = list(items.items()) if item_name is None else [(item_name, items.get(item_name, None))]

        for item_name, item in items_to_remove:
            if item is None:
                continue
            item.clear()
            del items[item_name]
        if not items:
            del self.__cache[cache_name]

        new_count = len(items)
        return old_count - new_count

    def cleanup_expired_items(self) -> dict[str, int]:
        """
        Cleans up expired items from all caches.
        Returns:
            dict[str, int]: A dictionary with cache names as keys and the number of removed items as values.
        """
        now = datetime.datetime.now()
        removed_items_count:dict[str, int] = {}
        for cache_name in list(self.__cache.keys()):
            items = self.__cache[cache_name]
            old_count = len(items)

            expired_items = [(item_name, item) for item_name, item in items.items() if item.expire < now]
            for (item_name, item) in expired_items:
                item.clear()
                del items[item_name]
            if not items:
                del self.__cache[cache_name]
            
            new_count = len(items)
            removed_count = old_count - new_count
            if removed_count > 0:
                removed_items_count[cache_name] = removed_count
        return removed_items_count
        