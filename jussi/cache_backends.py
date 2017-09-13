# -*- coding: utf-8 -*-
import logging

from aiocache import SimpleMemoryCache

# pylint: disable=no-name-in-module
from lru import LRU

logger = logging.getLogger(__name__)

MEMORY_CACHE_ITEMS_LIMIT = 1000


class SimpleLRUMemoryCache(SimpleMemoryCache):
    def __init__(self, max_items=MEMORY_CACHE_ITEMS_LIMIT, **kwargs):
        self.max_items = max_items
        super().__init__(**kwargs)
        self._cache = LRU(self.max_items)
