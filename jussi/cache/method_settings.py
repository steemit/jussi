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
  - A TTL of `-2` will be cached without expiration only if it is 'irreversible' in terms of blockchain consesus
- For readabilty/writabilty, there are shorthand variables for these 'special' TTL values:
   - `NO_EXPIRE` == 0
   - `NO_CACHE` == -1
   - `NO_EXPIRE_IF_IRREVERSIBLE` == -2

"""

import logging
from enum import Enum

import pygtrie

logger = logging.getLogger(__name__)


class TTL(Enum):
    DEFAULT_TTL = 3
    NO_EXPIRE = None
    NO_CACHE = -1
    NO_EXPIRE_IF_IRREVERSIBLE = -2

    # pylint: disable=no-else-return
    def __eq__(self, other):
        if isinstance(other, (int, type(None))):
            return self.value == other
        else:
            return super().__eq__(other)

    def __lt__(self, other):
        if isinstance(other, int):
            return self.value < other
        else:
            return super().__eq__(other)

    def __gt__(self, other):
        if isinstance(other, int):
            return self.value > other
        else:
            return super().__eq__(other)

    def __le__(self, other):
        if isinstance(other, int):
            return self.value <= other
        else:
            return super().__eq__(other)

    def __ge__(self, other):
        if isinstance(other, int):
            return self.value >= other
        else:
            return super().__eq__(other)


METHOD_SETTINGS = (
    # global default
    ('', TTL.DEFAULT_TTL),

    # sbds default
    ('hivemind', TTL.DEFAULT_TTL),

    # sbds default
    ('overseer', TTL.NO_CACHE),

    # sbds default
    ('sbds', 10),

    # steemd default
    ('steemd', TTL.DEFAULT_TTL),

    # steemd login_api
    ('steemd.login_api', TTL.NO_CACHE),

    # steemd network_broadcast_api
    ('steemd.network_broadcast_api', TTL.NO_CACHE),

    # steemd follow_api
    ('steemd.follow_api', 10),

    # steemd market_history_api
    ('steemd.market_history_api', 1),

    # steemd database_api
    ('steemd.database_api', TTL.DEFAULT_TTL),
    ('steemd.database_api.get_block', TTL.NO_EXPIRE_IF_IRREVERSIBLE),
    ('steemd.database_api.get_block_header', TTL.NO_EXPIRE_IF_IRREVERSIBLE),
    ('steemd.database_api.get_content', 1),
    ('steemd.database_api.get_state', 1),
    ("steemd.database_api.get_state.params=['/trending']", 30),
    ("steemd.database_api.get_state.params=['trending']", 30),
    ("steemd.database_api.get_state.params=['/hot']", 30),
    ("steemd.database_api.get_state.params=['/welcome']", 30),
    ("steemd.database_api.get_state.params=['/promoted']", 30),
    ("steemd.database_api.get_state.params=['/created']", 10),
    ('steemd.database_api.get_dynamic_global_properties', 1),

    # yo default
    ('yo', TTL.NO_CACHE))

TTLS = pygtrie.StringTrie(METHOD_SETTINGS, separator='.')


def ttl_from_urn(urn: str) -> TTL:
    _, ttl = TTLS.longest_prefix(urn)
    logger.debug(f'ttl from urn:{urn} ttl:{ttl}')
    return ttl
