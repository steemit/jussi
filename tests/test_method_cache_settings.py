# -*- coding: utf-8 -*-
import jussi.jsonrpc_method_cache_settings
import pytest


def test_globals():
    assert jussi.jsonrpc_method_cache_settings.DEFAULT_TTL == 3
    assert jussi.jsonrpc_method_cache_settings.NO_CACHE == -1
    assert jussi.jsonrpc_method_cache_settings.NO_EXPIRE == 0
    assert jussi.jsonrpc_method_cache_settings.NO_EXPIRE_IF_IRREVERSIBLE == -2


@pytest.mark.parametrize(
    "prefix,expected",
    [
        ('', jussi.jsonrpc_method_cache_settings.DEFAULT_TTL),
        ('steemd', jussi.jsonrpc_method_cache_settings.DEFAULT_TTL),
        ('steemd.network_broadcast_api',
         jussi.jsonrpc_method_cache_settings.NO_CACHE),
        ('steemd.network_broadcast_api.',
         jussi.jsonrpc_method_cache_settings.NO_CACHE),
        ('steemd.network_broadcast_api..',
         jussi.jsonrpc_method_cache_settings.NO_CACHE),

        # steemd follow_api
        ('steemd.follow_api', 3),
        ('steemd.follow_api.', 3),

        # steemd market_history_api
        ('steemd.market_history_api', 1),
        ('steemd.market_history_ap',
         jussi.jsonrpc_method_cache_settings.DEFAULT_TTL),

        # steemd database_api
        ('steemd.database_api', 3),
        ('steemd.database_api.get_block',
         jussi.jsonrpc_method_cache_settings.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block.params',
         jussi.jsonrpc_method_cache_settings.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block.params=',
         jussi.jsonrpc_method_cache_settings.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block.params=[]',
         jussi.jsonrpc_method_cache_settings.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block.params=[1000]',
         jussi.jsonrpc_method_cache_settings.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block_header',
         jussi.jsonrpc_method_cache_settings.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_block_header.params',
         jussi.jsonrpc_method_cache_settings.NO_EXPIRE_IF_IRREVERSIBLE),
        ('steemd.database_api.get_state', 1),
        ('steemd.database_api.get_dynamic_global_properties', 1),

        # sbds default
        ('sbds', 10),

        # yo default
        ('yo', jussi.jsonrpc_method_cache_settings.NO_CACHE)
    ],
    ids=lambda v: v[0])
def test_method_cache_settings_lookup(prefix, expected):
    TTLS = jussi.jsonrpc_method_cache_settings.TTLS
    _, ttl = TTLS.longest_prefix(prefix)
    assert ttl == expected
