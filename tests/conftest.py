# -*- coding: utf-8 -*-
import ujson

import asynctest
import copy
import jsonschema
import os
import pytest
import requests
import requests.exceptions
import sanic
import sanic.response
from aiocache import caches as aiocaches
from funcy.funcs import rpartial

import jussi.errors
import jussi.handlers
import jussi.listeners
import jussi.logging_config
import jussi.middlewares
import jussi.serve
from jussi.urn import URN
from jussi.upstream import _Upstreams
from jussi.request import JussiJSONRPCRequest


def pytest_addoption(parser):
    parser.addoption("--rundocker", action="store_true",
                     default=False, help="run docker tests")

    parser.addoption("--jussiurl", action="store",
                     help="url to use for integration level jussi tests")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if 'route' in item.nodeid:
            item.add_marker(pytest.mark.test_app)
    if not config.getoption("--rundocker") and not config.getoption("--jussiurl"):
        skip_live = pytest.mark.skip(reason="need --rundocker or --jussiurl option to run")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)


@pytest.fixture(scope='function')
def jussi_url(request):
    if request.config.getoption("--rundocker"):
        # request.config.getoption("--jussiurl")
        return request.getfixturevalue('jussi_docker_service')
    else:
        return request.config.getoption("--jussiurl")


TEST_DIR = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(TEST_DIR, 'request-schema.json')) as f:
    REQUEST_SCHEMA = ujson.load(f)

with open(os.path.join(TEST_DIR, 'response-schema.json')) as f:
    RESPONSE_SCHEMA = ujson.load(f)

with open(os.path.join(TEST_DIR, 'steemd-response-schema.json')) as f:
    STEEMD_RESPONSE_SCHEMA = ujson.load(f)

with open(os.path.join(TEST_DIR, 'jrpc_requests_and_responses.json')) as f:
    JRPC_REQUESTS_AND_RESPONSES = ujson.load(f)

with open(os.path.join(TEST_DIR, 'appbase_jrpc_requests_and_responses.json')) as f:
    APPBASE_REQUESTS_AND_RESPONSES = ujson.load(f)

with open(os.path.join(TEST_DIR, 'TEST_UPSTREAM_CONFIG.json')) as f:
    TEST_UPSTREAM_CONFIG = ujson.load(f)


APPBASE_REQUESTS = [p[0] for p in APPBASE_REQUESTS_AND_RESPONSES]

INVALID_JRPC_REQUESTS = [
    # bad/missing jsonrpc
    {
        'id': 1,
        'method': 'get_block',
        'params': [1000]
    },
    {
        'id': 1,
        'jsonrpc': 2.0,
        'method': 'get_block',
        'params': [1000]
    },
    {
        'id': 1,
        'json-rpc': '2.0',
        'method': 'get_block',
        'params': [1000]
    },
    {
        'id': 1,
        'json_rpc': '2.0',
        'method': 'get_block',
        'params': [1000]
    },
    {
        'id': 1,
        'json_rpc': ['2.0'],
        'method': 'get_block',
        'params': [1000]
    },
    {
        'id': 1,
        'jsonrpc': None,
        'method': 'get_block',
        'params': [1000]
    },

    # bad/missing id
    {
        'id': None,
        'json_rpc': '2.0',
        'method': 'get_block',
        'params': [1000]
    },
    {
        'ID': 1,
        'json_rpc': '2.0',
        'method': 'get_block',
        'params': [1000]
    },
    {
        'Id': 1,
        'json_rpc': '2.0',
        'method': 'get_block',
        'params': [1000]
    },
    {
        'id': [1],
        'json_rpc': '2.0',
        'method': 'get_block',
        'params': [1000]
    },
    {
        'id': None,
        'json_rpc': '2.0',
        'method': 'get_block',
        'params': [1000]
    },

    # bad params
    {
        'id': 1,
        'json_rpc': '2.0',
        'method': 'get_block',
        'params': 1000
    },
    {
        'id': 1,
        'json_rpc': '2.0',
        'method': 'get_block',
        'params': '1000'
    },
    {
        'id': 1,
        'json_rpc': '2.0',
        'method': 'get_block',
        'params': None
    },

    # bad/missing method
    {
        'id': 1,
        'json_rpc': '2.0',
        'params': [1000]
    },
    {
        'id': 1,
        'json_rpc': '2.0',
        'METHOD': 'get_block',
        'params': '1000'
    },
    {
        'id': 1,
        'json_rpc': '2.0',
        'method': ['get_block'],
        'params': '1000'
    },
    {
        'id': 1,
        'json_rpc': '2.0',
        'method': None,
        'params': '1000'
    },

    # malformed
    [],
    dict(),
    '',
    b'',
    None,
    False
]

INVALID_JRPC_RESPONSES = [
    None,
    {},
    [],
    '',
    b'',
    "{'id':1}"
]

STEEMD_JSON_RPC_CALLS = [{
    'id': 0,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_account_count',
               []]
},
    {
        'id': 1,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_account_history',
                   ['steemit', 20, 10]]
},
    {
        'id': 2,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_account_votes',
                   ['steemit', 'test']]
},
    {
        'id': 3,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_accounts',
                   [['steemit']]]
},
    {
        'id': 4,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_active_votes',
                   ['smooth', 'test']]
},
    {
        'id': 5,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_active_witnesses',
                   []]
},
    {
        'id': 6,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_block_header',
                   [1000]]
},
    {
        'id': 7,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_chain_properties',
                   []]
},
    {
        'id': 8,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_config', []]
},
    {
        'id': 9,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_content',
                   ['steemit', 'test']]
},
    {
        'id': 10,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_content_replies',
                   ['steemit', 'test']]
},
    {
        'id': 11,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_conversion_requests', ['steemit']]
},
    {
        'id': 12,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_current_median_history_price', []]
},
    {
        'id': 13,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_discussions_by_active',
                   [{'limit': '1', 'tag': 'steem'}]]
},
    {
        'id': 14,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_discussions_by_author_before_date',
                   ['smooth', 'test',
                    '2016-07-23T22:00:06', '1']]
},
    {
        'id': 15,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_discussions_by_cashout',
                   [{'limit': '1', 'tag': 'steem'}]]
},
    {
        'id': 16,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_discussions_by_children',
                   [{'limit': '1', 'tag': 'steem'}]]
},
    {
        'id': 17,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_discussions_by_created',
                   [{'limit': '1', 'tag': 'steem'}]]
},
    {
        'id': 18,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_discussions_by_feed',
                   [{'limit': '1', 'tag': 'steem'}]]
},
    {
        'id': 19,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_discussions_by_hot',
                   [{'limit': '1', 'tag': 'steem'}]]
},
    {
        'id': 20,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_discussions_by_payout',
                   [{'limit': '1', 'tag': 'steem'}]]
},
    {
        'id': 21,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_discussions_by_trending',
                   [{'limit': '1', 'tag': 'steem'}]]
},
    {
        'id': 22,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_discussions_by_votes',
                   [{'limit': '1', 'tag': 'steem'}]]
},
    {
        'id': 23,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_dynamic_global_properties', []]
},
    {
        'id': 24,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_feed_history', []]
},
    {
        'id': 25,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_hardfork_version',
                   []]
},
    {
        'id': 26,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_liquidity_queue',
                   ['steemit', 10]]
},
    {
        'id': 27,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_miner_queue', []]
},
    {
        'id': 28,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_next_scheduled_hardfork',
                   ['steemit', 10]]
},
    {
        'id': 29,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_open_orders',
                   ['steemit']]
},
    {
        'id': 30,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_order_book', [10]]
},
    {
        'id': 31,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_owner_history',
                   ['steemit']]
},
    {
        'id': 32,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_recovery_request',
                   ['steemit']]
},
    {
        'id': 33,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_replies_by_last_update',
                   ['smooth', 'test', 10]]
},
    {
        'id': 34,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_state',
                   ['/@layz3r']]
},
    {
        'id': 35,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_trending_tags',
                   ['steemit', 10]]
},
    {
        'id': 36,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'get_witness_by_account',
                   ['smooth.witness']]
},
    {
        'id': 37,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_witness_count',
                   []]
},
    {
        'id': 38,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'get_witness_schedule',
                   []]
},
    {
        'id': 39,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'lookup_account_names',
                   [['steemit']]]
},
    {
        'id': 40,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api', 'lookup_accounts',
                   ['steemit', 10]]
},
    {
        'id': 41,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': ['database_api',
                   'lookup_witness_accounts',
                   ['steemit', 10]]
},
    {
        'id': 42, 'jsonrpc': '2.0',
        'method': 'get_account_count', 'params': []
},
    {
        'id': 43,
        'jsonrpc': '2.0',
        'method': 'get_account_history',
        'params': ['steemit', 20, 10]
},
    {
        'id': 44,
        'jsonrpc': '2.0',
        'method': 'get_account_votes',
        'params': ['steemit', 'test']
},
    {
        'id': 45,
        'jsonrpc': '2.0',
        'method': 'get_accounts',
        'params': [['steemit']]
},
    {
        'id': 46,
        'jsonrpc': '2.0',
        'method': 'get_active_votes',
        'params': ['smooth', 'test']
},
    {
        'id': 47, 'jsonrpc': '2.0',
        'method': 'get_active_witnesses', 'params': []
},
    {
        'id': 48, 'jsonrpc': '2.0',
        'method': 'get_block_header', 'params': [1000]
},
    {
        'id': 49, 'jsonrpc': '2.0',
        'method': 'get_chain_properties', 'params': []
},
    {
        'id': 50, 'jsonrpc': '2.0',
        'method': 'get_config', 'params': []
},
    {
        'id': 51,
        'jsonrpc': '2.0',
        'method': 'get_content',
        'params': ['steemit', 'test']
},
    {
        'id': 52,
        'jsonrpc': '2.0',
        'method': 'get_content_replies',
        'params': ['steemit', 'test']
},
    {
        'id': 53,
        'jsonrpc': '2.0',
        'method': 'get_conversion_requests',
        'params': ['steemit']
},
    {
        'id': 54,
        'jsonrpc': '2.0',
        'method': 'get_current_median_history_price',
        'params': []
},
    {
        'id': 55,
        'jsonrpc': '2.0',
        'method': 'get_discussions_by_active',
        'params': [{'limit': '1', 'tag': 'steem'}]
},
    {
        'id': 56,
        'jsonrpc': '2.0',
        'method': 'get_discussions_by_author_before_date',
        'params': ['smooth', 'test',
                   '2016-07-23T22:00:06', '1']
},
    {
        'id': 57,
        'jsonrpc': '2.0',
        'method': 'get_discussions_by_cashout',
        'params': [{'limit': '1', 'tag': 'steem'}]
},
    {
        'id': 58,
        'jsonrpc': '2.0',
        'method': 'get_discussions_by_children',
        'params': [{'limit': '1', 'tag': 'steem'}]
},
    {
        'id': 59,
        'jsonrpc': '2.0',
        'method': 'get_discussions_by_created',
        'params': [{'limit': '1', 'tag': 'steem'}]
},
    {
        'id': 60,
        'jsonrpc': '2.0',
        'method': 'get_discussions_by_feed',
        'params': [{'limit': '1', 'tag': 'steem'}]
},
    {
        'id': 61,
        'jsonrpc': '2.0',
        'method': 'get_discussions_by_hot',
        'params': [{'limit': '1', 'tag': 'steem'}]
},
    {
        'id': 62,
        'jsonrpc': '2.0',
        'method': 'get_discussions_by_payout',
        'params': [{'limit': '1', 'tag': 'steem'}]
},
    {
        'id': 63,
        'jsonrpc': '2.0',
        'method': 'get_discussions_by_trending',
        'params': [{'limit': '1', 'tag': 'steem'}]
},
    {
        'id': 64,
        'jsonrpc': '2.0',
        'method': 'get_discussions_by_votes',
        'params': [{'limit': '1', 'tag': 'steem'}]
},
    {
        'id': 65,
        'jsonrpc': '2.0',
        'method': 'get_dynamic_global_properties',
        'params': []
},
    {
        'id': 66, 'jsonrpc': '2.0',
        'method': 'get_feed_history', 'params': []
},
    {
        'id': 67, 'jsonrpc': '2.0',
        'method': 'get_hardfork_version', 'params': []
},
    {
        'id': 68,
        'jsonrpc': '2.0',
        'method': 'get_liquidity_queue',
        'params': ['steemit', 10]
},
    {
        'id': 69, 'jsonrpc': '2.0',
        'method': 'get_miner_queue', 'params': []
},
    {
        'id': 70,
        'jsonrpc': '2.0',
        'method': 'get_next_scheduled_hardfork',
        'params': ['steemit', 10]
},
    {
        'id': 71,
        'jsonrpc': '2.0',
        'method': 'get_open_orders',
        'params': ['steemit']
},
    {
        'id': 72, 'jsonrpc': '2.0',
        'method': 'get_order_book', 'params': [10]
},
    {
        'id': 73,
        'jsonrpc': '2.0',
        'method': 'get_owner_history',
        'params': ['steemit']
},
    {
        'id': 74,
        'jsonrpc': '2.0',
        'method': 'get_recovery_request',
        'params': ['steemit']
},
    {
        'id': 75,
        'jsonrpc': '2.0',
        'method': 'get_replies_by_last_update',
        'params': ['smooth', 'test', 10]
},
    {
        'id': 76, 'jsonrpc': '2.0',
        'method': 'get_state', 'params': ['/@layz3r']
},
    {
        'id': 77,
        'jsonrpc': '2.0',
        'method': 'get_trending_tags',
        'params': ['steemit', 10]
},
    {
        'id': 78,
        'jsonrpc': '2.0',
        'method': 'get_witness_by_account',
        'params': ['smooth.witness']
},
    {
        'id': 79, 'jsonrpc': '2.0',
        'method': 'get_witness_count', 'params': []
},
    {
        'id': 80, 'jsonrpc': '2.0',
        'method': 'get_witness_schedule', 'params': []
},
    {
        'id': 81,
        'jsonrpc': '2.0',
        'method': 'lookup_account_names',
        'params': [['steemit']]
},
    {
        'id': 82,
        'jsonrpc': '2.0',
        'method': 'lookup_accounts',
        'params': ['steemit', 10]
},
    {
        'id': 83,
        'jsonrpc': '2.0',
        'method': 'lookup_witness_accounts',
        'params': ['steemit', 10]
}


]

COMBINED_STEEMD_APPBASE_JSONRPC_CALLS = STEEMD_JSON_RPC_CALLS + APPBASE_REQUESTS

STEEMD_JSONRPC_CALL_PAIRS = []
for c in STEEMD_JSON_RPC_CALLS:
    if c['method'] == 'call':
        method = c['params'][1]
        new_method = [
            m for m in STEEMD_JSON_RPC_CALLS if m['method'] == method]
        STEEMD_JSONRPC_CALL_PAIRS.append((c, new_method[0]))

LONG_REQUESTS = [
    {
        'id': 1,
        'jsonrpc': '2.0',
        'method': 'get_accounts',
        'params': [["a-0", "a-00", "a-1", "a-100-great", "a-2", "a-3", "a-5", "a-7", "a-a", "a-a-7", "a-a-a", "a-a-a-a", "a-a-lifemix", "a-a-ron", "a-aka-assassin", "a-alice", "a-angel", "a-aron", "a-ayman", "a-b", "a-b-c-0", "a-big-sceret", "a-blockchain", "a-bold-user", "a-buz", "a-c", "a-c-s", "a-cakasaurus", "a-cat-named-joe", "a-chixywilson", "a-churchill", "a-condor", "a-diddy", "a-enoch", "a-eye", "a-f", "a-future", "a-guy-named-brad", "a-h", "a-harkness12", "a-hitler", "a-human", "a-jay", "a-jeffrey", "a-jimynguyen", "a-jns", "a-k11u", "a-kiran", "a-kopf", "a-kristin", "a-l-e-x", "a-league", "a-louis", "a-luigh", "a-ly-ba-ba-lou", "a-m-s", "a-m3001", "a-man", "a-neuron", "a-normal-life", "a-ok", "a-osorio", "a-payment-btc-a", "a-pile-of-steem", "a-priori", "a-random-person", "a-rod", "a-run", "a-s-h", "a-sakura83", "a-share", "a-sheeple-nomore", "a-sojourner", "a-spears", "a-tall-lion", "a-team", "a-train", "a-u", "a-val", "a-vm", "a-vytimy", "a-wadyanto", "a-xyli", "a-yo", "a-z", "a-zajonc", "a00", "a000346", "a001", "a0047a", "a007", "a007-steem", "a01", "a01.cshrem", "a0101201012", "a02.cshrem", "a0487987", "a0903l22", "a0de6qzchbut", "a0dh", "a10", "a10-c", "a100", "a1000eyes", "a10cwarhog", "a10inchcock", "a11", "a110", "a1148639279", "a114haeun", "a119315", "a11at", "a11stabilizer", "a11y", "a12345678", "a1270", "a12a", "a12inchcock", "a12kcm5518", "a12najafi", "a12oma1784", "a13inchcock", "a13x", "a13xz", "a13yus", "a1412", "a14inchcock", "a153048", "a154103040", "a1848art", "a186r", "a1933production", "a1962w", "a1a", "a1a1a11a", "a1an120", "a1b2c3d4", "a1beatznj", "a1choi", "a1dunn13", "a1exe1", "a1i-00ba0eb5", "a1i-01e13986", "a1i-03a7078f", "a1i-04a70788", "a1i-04ba0eb1", "a1i-05a70789", "a1i-06a7078a", "a1i-06ba0eb3", "a1i-06e13981", "a1i-07a7078b", "a1i-07ba0eb2", "a1i-07e13980", "a1i-0b6eb596", "a1i-0f6eb592", "a1i-106eb58d", "a1i-107e64e9", "a1i-10ba0ea5", "a1i-10e23a97", "a1i-111d3fc9", "a1i-11ba0ea4", "a1i-121d3fca", "a1i-137e64ea", "a1i-13e23a94", "a1i-16ba0ea3", "a1i-16e23a91", "a1i-172e8d9b", "a1i-176eb58a", "a1i-17ba0ea2", "a1i-17e23a90", "a1i-182f8c94", "a1i-188530ad", "a1i-19571a91", "a1i-19a70795", "a1i-19bb0eac", "a1i-1a8530af", "a1i-1ae18298", "a1i-1b2f8c97", "a1i-1b7e64e2", "a1i-1b8530ae", "a1i-1d7f65e4", "a1i-211c3ef9", "a1i-216ccfad", "a1i-221c3efa", "a1i-231c3efb", "a1i-286db6b5", "a1i-296db6b4", "a1i-29e182ab", "a1i-2a4fe79f", "a1i-2a6db6b7", "a1i-2b6db6b6", "a1i-2c511ca4", "a1i-2fe182ad", "a1i-34e182b6", "a1i-34e487b6", "a1i-35b112b9", "a1i-374fe782", "a1i-39982f8c", "a1i-412f8ccd", "a1i-42e281c0", "a1i-439522f6", "a1i-43c3a0c1", "a1i-458530f0", "a1i-45a33fcf", "a1i-483192d5", "a1i-4b1c3e93", "a1i-4b9a2ffe", "a1i-4c1c3e94", "a1i-4ccfacce", "a1i-4d1c3e95", "a1i-4dcfaccf", "a1i-4e3192d3", "a1i-53b112df", "a1i-596eb5c4", "a1i-5c6eb5c1", "a1i-5f6eb5c2", "a1i-608b22d5", "a1i-628b22d7", "a1i-668a23d3", "a1i-67e139e0", "a1i-699126dc", "a1i-69e487eb", "a1i-6a40e8df", "a1i-6d40e8d8", "a1i-6d920ee7", "a1i-6f01a2e3", "a1i-71b918ec", "a1i-7941e9cc", "a1i-7a8530cf", "a1i-7dbb0fc8", "a1i-7fbb0fca", "a1i-8042f635", "a1i-80ef8c02", "a1i-80f59602", "a1i-816db61c", "a1i-90a8081c", "a1i-91a8081d", "a1i-92a8081e", "a1i-93a8081f", "a1i-93e2c04b", "a1i-94a80818", "a1i-94e2c04c", "a1i-95a80819", "a1i-95e2c04d", "a1i-96e2c04e", "a1i-a7ec8f25", "a1i-a8bb0f1d", "a1i-a9bb0f1c", "a1i-ab1c3e73", "a1i-ac2e8d20", "a1i-ad2e8d21", "a1i-adbb0f18", "a1i-ae2e8d22", "a1i-aebb0f1b", "a1i-af2e8d23", "a1i-afbb0f1a", "a1i-b08c103a", "a1i-b18c103b", "a1i-b28c1038", "a1i-b78c103d", "a1i-bca70730", "a1i-bda70731", "a1i-bea70732", "a1i-bfa70733", "a1i-c2e23a45", "a1i-c3e23a44", "a1i-c631925b", "a1i-c7e23a40", "a1i-c973d045", "a1i-cc1c3e14", "a1i-cd1c3e15", "a1i-ce1c3e16", "a1i-d0930f5a", "a1i-d0b1125c", "a1i-d241e967", "a1i-d2843167", "a1i-d3843166", "a1i-d641e963", "a1i-dd843168", "a1i-de84316b", "a1i-df84316a", "a1i-e16cb77c", "a1i-e1a8086d", "a1i-e26cb77f", "a1i-e2b0136e", "a1i-e36cb77e", "a1i-e6b8197b", "a1i-ea96215f", "a1i-eb1d3f33", "a1i-ec1d3f34", "a1i-ed1d3f35", "a1i-ee1d3f36", "a1i-eea80862", "a1i-f4873241", "a1i-f57dc940", "a1i-f5852779", "a1i-f5873240", "a1i-f6873243", "a1i-f7873242", "a1i-fafa5876"]]
    }
]

# pylint:  disable=unused-variable,unused-argument,attribute-defined-outside-init


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


@pytest.fixture
def dummy_app_config():
    app = AttrDict()
    app.config = AttrDict()
    return app


@pytest.fixture
def dummy_request():
    dummy_request = AttrDict()
    dummy_request.headers = dict()
    dummy_request['jussi_request_id'] = '123456789012345'
    dummy_request.app = AttrDict()
    dummy_request.app.config = AttrDict()
    dummy_request.app.config.upstreams = _Upstreams(TEST_UPSTREAM_CONFIG,
                                                    validate=False)
    return dummy_request


@pytest.fixture(scope='session')
def upstreams():
    yield _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)


@pytest.fixture(scope='function')
def app(loop):
    args = jussi.serve.parse_args(args=[])
    upstream_config_path = os.path.abspath(
        os.path.join(TEST_DIR, 'TEST_UPSTREAM_CONFIG.json'))
    args.upstream_config_file = upstream_config_path
    args.test_upstream_urls = False
    # run app
    app = sanic.Sanic('testApp')
    app.config.args = args
    app.config.args.server_port = 42101
    app.config.args.websocket_pool_minsize = 0
    app.config.args.websocket_pool_maxsize = 1
    app = jussi.logging_config.setup_logging(app)
    app = jussi.serve.setup_routes(app)
    app = jussi.middlewares.setup_middlewares(app)
    app = jussi.errors.setup_error_handlers(app)
    app = jussi.listeners.setup_listeners(app)

    try:
        loop.run_until_complete(app.config.cache_group.clear())
    except BaseException:
        pass

    yield app

    try:
        loop.run_until_complete(app.config.cache_group.clear())
    except BaseException:
        pass

    del app.config


@pytest.fixture(scope='function')
def app_without_ws(app):
    for i, l in enumerate(app.listeners['before_server_start']):
        if 'websocket' in str(l.__name__):
            del app.listeners['before_server_start'][i]
    for i, l in enumerate(app.listeners['after_server_stop']):
        if 'websocket' in str(l.__name__):
            del app.listeners['after_server_stop'][i]
    yield app


@pytest.fixture
def test_cli(app, loop, test_client):
    return loop.run_until_complete(test_client(app))


@pytest.fixture
def mocked_app_test_cli(app, loop, test_client):
    with asynctest.patch('jussi.ws.pool.connect') as mocked_connect:
        mocked_ws_conn = asynctest.CoroutineMock()
        mocked_ws_conn.send = asynctest.CoroutineMock()
        mocked_ws_conn.send.return_value = None
        mocked_ws_conn.recv = asynctest.CoroutineMock()
        mocked_ws_conn.close = asynctest.CoroutineMock()
        mocked_ws_conn.close_connection = asynctest.CoroutineMock()
        mocked_ws_conn.worker_task = asynctest.MagicMock()
        mocked_ws_conn.messages = asynctest.MagicMock()
        mocked_ws_conn.messages.qsize.return_value = 0
        mocked_ws_conn.messages.maxsize.return_value = 1
        mocked_ws_conn.messages._unfinished_tasks.return_value = 0
        mocked_ws_conn.messages.empty.return_value = True
        mocked_ws_conn._stream_reader = asynctest.MagicMock()
        mocked_connect.return_value = mocked_ws_conn

        yield mocked_ws_conn, loop.run_until_complete(test_client(app))


@pytest.fixture(scope='function')
def caches(loop):
    aiocaches.set_config({
        'default': {
            'cache': "aiocache.SimpleMemoryCache",
            'serializer': {
                'class': 'aiocache.serializers.NullSerializer'
            }
        },
        'redis': {
            'cache': "aiocache.SimpleMemoryCache",
            'serializer': {
                'class': 'aiocache.serializers.NullSerializer'
            }
        }
    })
    active_caches = [
        aiocaches.create(**aiocaches.get_alias_config('default')),
        aiocaches.create(**aiocaches.get_alias_config('redis'))
    ]
    yield active_caches
    loop.run_until_complete(aiocaches.get('default').clear())
    loop.run_until_complete(aiocaches.get('redis').clear())


@pytest.fixture(
    scope='function',
    params=['/', '/health', '/.well-known/healthcheck.json'])
def healthcheck_path(request):
    return request.param


@pytest.fixture
def healthcheck_url(jussi_url, healthcheck_path):
    return f'{jussi_url}{healthcheck_path}'


@pytest.fixture
def jrpc_response_validator():
    return rpartial(jsonschema.validate, RESPONSE_SCHEMA)


@pytest.fixture
def jrpc_request_validator():
    return rpartial(jsonschema.validate, REQUEST_SCHEMA)


@pytest.fixture
def steemd_jrpc_response_validator():
    return rpartial(jsonschema.validate, STEEMD_RESPONSE_SCHEMA)


@pytest.fixture
def valid_single_jrpc_request():
    return {'id': 1, 'jsonrpc': '2.0', 'method': 'get_block', 'params': [1000]}


@pytest.fixture
def valid_batch_jrpc_request(valid_single_jrpc_request):
    return [valid_single_jrpc_request, valid_single_jrpc_request]


@pytest.fixture(params=INVALID_JRPC_REQUESTS)
def invalid_jrpc_requests(request):
    yield request.param


@pytest.fixture(scope='session', params=INVALID_JRPC_REQUESTS)
def invalid_jussi_jsonrpc_requests(request, dummy_request):
    invalid_request = request.param
    invalid_jussijsonrpc_request = JussiJSONRPCRequest(dummy_request, 0, invalid_request)
    yield invalid_jussijsonrpc_request


@pytest.fixture(params=INVALID_JRPC_RESPONSES)
def invalid_jrpc_responses(request):
    yield request.param


@pytest.fixture(params=COMBINED_STEEMD_APPBASE_JSONRPC_CALLS, ids=lambda c: c['method'])
def all_steemd_jrpc_calls(request):
    yield request.param


@pytest.fixture(params=STEEMD_JSONRPC_CALL_PAIRS)
def steemd_method_pairs(request):
    yield request.param


@pytest.fixture(
    scope='function', params=APPBASE_REQUESTS_AND_RESPONSES + JRPC_REQUESTS_AND_RESPONSES,
    ids=lambda reqresp: URN(reqresp[0]))
def steemd_requests_and_responses(request):
    yield copy.deepcopy(request.param[0]), copy.deepcopy(request.param[1])


@pytest.fixture(
    scope='function', params=JRPC_REQUESTS_AND_RESPONSES,
    ids=lambda reqresp: URN(reqresp[0]))
def steemd_requests_and_responses_without_resp_id(request):
    req, resp = copy.deepcopy(
        request.param[0]), copy.deepcopy(request.param[1])
    if 'id' in resp:
        del resp['id']
    yield req, resp


@pytest.fixture(params=JRPC_REQUESTS_AND_RESPONSES)
def jrpc_response(request):
    yield request.param[1]


def is_responsive(url):
    """Check if something responds to ``url``."""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return True
    except requests.exceptions.ConnectionError:
        return False


@pytest.fixture(scope='session')
def jussi_docker_service(docker_ip, docker_services):
    """Ensure that "some service" is up and responsive."""
    url = 'http://%s:%s' % (docker_ip, docker_services.port_for('jussi', 8080))
    print(url)
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1,
        check=lambda: is_responsive(url)
    )
    return url


@pytest.fixture(scope='session')
def requests_session():
    session = requests.Session()
    return session


@pytest.fixture(scope='session')
def prod_url():
    return 'https://api.steemitdev.com'


@pytest.fixture
def sanic_server(loop, app, test_server):
    return loop.run_until_complete(test_server(app))


@pytest.fixture(params=LONG_REQUESTS)
def long_request(request):
    yield request.param
