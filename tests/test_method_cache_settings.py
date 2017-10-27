# -*- coding: utf-8 -*-

import pytest
from jussi.cache.method_settings import TTL
from jussi.cache.method_settings import TTLS


def test_globals():
    assert TTL.DEFAULT_TTL.value == 3
    assert TTL.NO_CACHE.value == -1
    assert TTL.NO_EXPIRE.value is None
    assert TTL.NO_EXPIRE_IF_IRREVERSIBLE.value == -2


@pytest.mark.parametrize(
    "prefix,expected",
    [
        ('', TTL.DEFAULT_TTL),
        ('steemd', TTL.DEFAULT_TTL),
        ('steemd.network_broadcast_api',
         TTL.NO_CACHE),
        ('steemd.network_broadcast_api.',
         TTL.NO_CACHE),
        ('steemd.network_broadcast_api..',
         TTL.NO_CACHE),

        # steemd follow_api
        ('steemd.follow_api', 10),
        ('steemd.follow_api.', 10),

        # steemd market_history_api
        ('steemd.market_history_api', 1),
        ('steemd.market_history_ap',
         TTL.DEFAULT_TTL),

        # steemd database_api
        ('steemd.database_api', TTL.DEFAULT_TTL),
        ('steemd.database_api.get_block',
         TTL.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block.params',
         TTL.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block.params=',
         TTL.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block.params=[]',
         TTL.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block.params=[1000]',
         TTL.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block_header',
         TTL.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block_header.params',
         TTL.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_content', 1),
        ('steemd.database_api.get_state', 1),
        ('steemd.database_api.get_dynamic_global_properties', 1),

        # sbds default
        ('sbds', 10),

        # yo default
        ('yo', TTL.NO_CACHE)
    ],
    ids=lambda v: v[0])
def test_method_cache_settings_lookup(prefix, expected):
    _, ttl = TTLS.longest_prefix(prefix)
    assert ttl == expected
