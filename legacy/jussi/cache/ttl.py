# -*- coding: utf-8 -*-
"""
Method Settings
---------------
- Each tuple in the METHOD_SETTING's list of tuples is a setting
- Each setting is a two-tuple of `prefix` and `ttl`, eg, ('steemd.database_api.get_block',1)
- Settings are stored in a trie structure, the longest matching prefix for a method is it's setting
- TTL is an integer value in seconds. Integers <= 0 have special meaning
  - A TTL of `0` won't expire
  - A TTL of `-1` wont be cached
  - A TTL of `-2` will be cached with default expiration only if it is 'irreversible' in terms of blockchain consesus
- For readabilty/writabilty, there are shorthand variables for these 'special' TTL values:
   - `NO_EXPIRE` == 0
   - `NO_CACHE` == -1
   - `DEFAULT_EXPIRE_IF_IRREVERSIBLE` == -2

"""

from enum import Enum


class TTL(Enum):
    DEFAULT_TTL = 3
    NO_EXPIRE = None
    NO_CACHE = -1
    DEFAULT_EXPIRE_IF_IRREVERSIBLE = -2

    # pylint: disable=no-else-return
    def __eq__(self, other: int) -> bool:
        if isinstance(other, (int, type(None))):
            return self.value == other
        else:
            return super().__eq__(other)

    def __lt__(self, other)-> bool:
        if isinstance(other, int):
            return self.value < other
        else:
            return super().__eq__(other)

    def __gt__(self, other)-> bool:
        if isinstance(other, int):
            return self.value > other
        else:
            return super().__eq__(other)

    def __le__(self, other)-> bool:
        if isinstance(other, int):
            return self.value <= other
        else:
            return super().__eq__(other)

    def __ge__(self, other)-> bool:
        if isinstance(other, int):
            return self.value >= other
        else:
            return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value)
