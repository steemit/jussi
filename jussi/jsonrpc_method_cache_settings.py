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
import pygtrie

DEFAULT_TTL = 3
NO_EXPIRE = 0
NO_CACHE = -1
NO_EXPIRE_IF_IRREVERSIBLE = -2

METHOD_SETTINGS = (
    # global default
    ('', DEFAULT_TTL),

    # steemd default
    ('steemd', DEFAULT_TTL),

    # steemd login_api
    ('steemd.login_api', NO_CACHE),

    # steemd network_broadcast_api
    ('steemd.network_broadcast_api', NO_CACHE),

    # steemd follow_api
    ('steemd.follow_api', 3),

    # steemd market_history_api
    ('steemd.market_history_api', 1),

    # steemd database_api
    ('steemd.database_api', 3),
    ('steemd.database_api.get_block', NO_EXPIRE_IF_IRREVERSIBLE),
    ('steemd.database_api.get_block_header', NO_EXPIRE_IF_IRREVERSIBLE),
    ('steemd.database_api.get_state', 1),
    ('steemd.database_api.get_dynamic_global_properties', 1),

    # sbds default
    ('sbds', 10),

    # yo default
    ('yo', NO_CACHE))

TTLS = pygtrie.StringTrie(METHOD_SETTINGS, separator='.')
