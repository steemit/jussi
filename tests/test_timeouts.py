# -*- coding: utf-8 -*-

import pytest
from jussi.upstream.timeouts import TIMEOUTS
from jussi.upstream.timeouts import DEFAULT_TIMEOUT
from jussi.upstream.timeouts import NO_TIMEOUT
from jussi.upstream.timeouts import timeout_from_urn


@pytest.mark.parametrize(
    "prefix,expected",
    [
        # global default
        ('', DEFAULT_TIMEOUT),

        # sbds default
        ('hivemind', DEFAULT_TIMEOUT),

        # sbds default
        ('overseer', DEFAULT_TIMEOUT),

        # sbds default
        ('sbds', DEFAULT_TIMEOUT),

        # steemd default
        ('steemd', DEFAULT_TIMEOUT),

        # steemd login_api
        ('steemd.login_api', DEFAULT_TIMEOUT),


        # steemd follow_api
        ('steemd.follow_api', DEFAULT_TIMEOUT),

        # steemd market_history_api
        ('steemd.market_history_api', DEFAULT_TIMEOUT),

        # steemd database_api
        ('steemd.database_api', DEFAULT_TIMEOUT),
        ('steemd.database_api.get_block', DEFAULT_TIMEOUT),
        ('steemd.database_api.get_block_header', DEFAULT_TIMEOUT),
        ('steemd.database_api.get_state', DEFAULT_TIMEOUT),
        ('steemd.database_api.get_dynamic_global_properties', DEFAULT_TIMEOUT),

        # yo default
        ('yo', DEFAULT_TIMEOUT),

        # steemd network_broadcast_api
        ('steemd.network_broadcast_api', NO_TIMEOUT),

    ],
    ids=lambda v: v[0])
def test_timeout(prefix, expected):
    _, timeout = TIMEOUTS.longest_prefix(prefix)
    assert timeout == expected


@pytest.mark.parametrize(
    "urn,expected",
    [  # global default
        ('', DEFAULT_TIMEOUT),

        # sbds default
        ('hivemind', DEFAULT_TIMEOUT),

        # sbds default
        ('overseer', DEFAULT_TIMEOUT),

        # sbds default
        ('sbds', DEFAULT_TIMEOUT),

        # steemd default
        ('steemd', DEFAULT_TIMEOUT),

        # steemd login_api
        ('steemd.login_api', DEFAULT_TIMEOUT),


        # steemd follow_api
        ('steemd.follow_api', DEFAULT_TIMEOUT),

        # steemd market_history_api
        ('steemd.market_history_api', DEFAULT_TIMEOUT),

        # steemd database_api
        ('steemd.database_api', DEFAULT_TIMEOUT),
        ('steemd.database_api.get_block', DEFAULT_TIMEOUT),
        ('steemd.database_api.get_block_header', DEFAULT_TIMEOUT),
        ('steemd.database_api.get_state', DEFAULT_TIMEOUT),
        ('steemd.database_api.get_dynamic_global_properties', DEFAULT_TIMEOUT),

        # yo default
        ('yo', DEFAULT_TIMEOUT),

        # steemd network_broadcast_api
        ('steemd.network_broadcast_api', NO_TIMEOUT),

    ],
    ids=lambda v: v[0])
def test_timeout_from_urn(urn, expected):
    timeout = timeout_from_urn(urn)
    assert timeout == expected
