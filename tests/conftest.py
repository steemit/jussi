# -*- coding: utf-8 -*-
import os
import random
import time

import sanic
import sanic.response
import ujson
from aiocache import caches as aiocaches

import jsonschema
import jussi.errors
import jussi.handlers
import jussi.listeners
import jussi.logging_config
import jussi.middlewares
import jussi.serve
import pytest
import requests
import requests.exceptions


def pytest_collection_modifyitems(items):
    for item in items:
        if "docker" in item.nodeid:
            item.add_marker(pytest.mark.docker)
        if 'route' in item.nodeid:
            item.add_marker(pytest.mark.test_app)


def randomize_jrpc_ids(jrpc_calls):
    calls = list(jrpc_calls)
    rand_calls = []
    for call in calls:
        rand_calls.append(randomize_jrpc_id(call))
    return rand_calls


def randomize_jrpc_id(jrpc_call):
    # randomize ids, some strings, some ints, some nulls
    if 'id' in jrpc_call:
        _id = random.randint(1, 1000)
        # if _id % 6 == 0:
        #    _id = None
        #    jrpc_call['id'] = _id
        #    return jrpc_call
        # if _id % 2 == 0:
        #    _id = str(_id)
        jrpc_call['id'] = _id
    return jrpc_call


def _random_batches(jrpc_calls):
    choices = random.sample(randomize_jrpc_ids(jrpc_calls),
                            k=len(jrpc_calls))
    batches = []
    # pylint: disable=len-as-condition
    while len(choices) > 0:
        batch_size = random.randint(1, 10)
        if batch_size > len(choices):
            batch_size = len(choices)
        batch = [choices.pop() for i in range(batch_size)]
        batches.append(batch)
    return batches


TEST_DIR = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(TEST_DIR, 'request-schema.json')) as f:
    REQUEST_SCHEMA = ujson.load(f)
with open(os.path.join(TEST_DIR, 'response-schema.json')) as f:
    RESPONSE_SCHEMA = ujson.load(f)

with open(os.path.join(TEST_DIR, 'jrpc_requests_and_responses.json')) as f:
    JRPC_REQUESTS_AND_RESPONSES = ujson.load(f)

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
]

_STEEMD_JSON_RPC_CALLS = [{
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_account_count', []]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_account_history', ['steemit', 20, 10]]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_account_votes', ['steemit', 'test']]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_accounts', [['steemit']]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_active_votes', ['smooth', 'test']]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_active_witnesses', []]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_block_header', [1000]]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_chain_properties', []]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_config', []]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_content', ['steemit', 'test']]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_content_replies', ['steemit', 'test']]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_conversion_requests', ['steemit']]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_current_median_history_price', []]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_discussions_by_active', [{"tag": "steem", "limit": "1"}]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_discussions_by_author_before_date', [
        "smooth",
        "test",
        "2016-07-23T22:00:06",
        "1"]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_discussions_by_cashout', [{"tag": "steem", "limit": "1"}]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_discussions_by_children', [{"tag": "steem", "limit": "1"}]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_discussions_by_created', [{"tag": "steem", "limit": "1"}]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_discussions_by_feed', [{"tag": "steem", "limit": "1"}]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_discussions_by_hot', [{"tag": "steem", "limit": "1"}]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_discussions_by_payout', [{"tag": "steem", "limit": "1"}]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_discussions_by_trending', [{"tag": "steem", "limit": "1"}]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_discussions_by_votes', [{"tag": "steem", "limit": "1"}]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_dynamic_global_properties', []]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_feed_history', []]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_hardfork_version', []]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_liquidity_queue', ['steemit', 10]]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_miner_queue', []]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_next_scheduled_hardfork', ['steemit', 10]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_open_orders', ['steemit']]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_order_book', [10]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_owner_history', ['steemit']]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_recovery_request', ['steemit']]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_replies_by_last_update', ['smooth', 'test', 10]]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_state', ["/@layz3r"]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_trending_tags', ['steemit', 10]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'get_witness_by_account', ['smooth.witness']]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_witness_count', []]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'call',
    'params': ['database_api', 'get_witness_schedule', []]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'lookup_account_names', [['steemit']]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'lookup_accounts', ['steemit', 10]]
}, {
    'id':
        1,
    'jsonrpc':
        '2.0',
    'method':
        'call',
    'params': ['database_api', 'lookup_witness_accounts', ['steemit', 10]]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_account_count',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_account_history',
    'params': ['steemit', 20, 10]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_account_votes',
    'params': ['steemit', 'test']
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_accounts',
    'params': [['steemit']]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_active_votes',
    'params': ['smooth', 'test']
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_active_witnesses',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_block_header',
    'params': [1000]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_chain_properties',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_config',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_content',
    'params': ['steemit', 'test']
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_content_replies',
    'params': ['steemit', 'test']
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_conversion_requests',
    'params': ['steemit']
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_current_median_history_price',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_discussions_by_active',
    'params': [{"tag": "steem", "limit": "1"}]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_discussions_by_author_before_date',
    'params': ["smooth", "test", "2016-07-23T22:00:06", "1"]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_discussions_by_cashout',
    'params': [{"tag": "steem", "limit": "1"}]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_discussions_by_children',
    'params': [{"tag": "steem", "limit": "1"}]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_discussions_by_created',
    'params': [{"tag": "steem", "limit": "1"}]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_discussions_by_feed',
    'params': [{"tag": "steem", "limit": "1"}]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_discussions_by_hot',
    'params': [{"tag": "steem", "limit": "1"}]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_discussions_by_payout',
    'params': [{"tag": "steem", "limit": "1"}]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_discussions_by_trending',
    'params': [{"tag": "steem", "limit": "1"}]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_discussions_by_votes',
    'params': [{"tag": "steem", "limit": "1"}]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_dynamic_global_properties',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_feed_history',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_hardfork_version',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_liquidity_queue',
    'params': ['steemit', 10]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_miner_queue',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_next_scheduled_hardfork',
    'params': ['steemit', 10]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_open_orders',
    'params': ['steemit']
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_order_book',
    'params': [10]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_owner_history',
    'params': ['steemit']
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_recovery_request',
    'params': ['steemit']
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_replies_by_last_update',
    'params': ['smooth', 'test', 10]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_state',
    'params': ["/@layz3r"]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_trending_tags',
    'params': ['steemit', 10]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_witness_by_account',
    'params': ['smooth.witness']
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_witness_count',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'get_witness_schedule',
    'params': []
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'lookup_account_names',
    'params': [['steemit']]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'lookup_accounts',
    'params': ['steemit', 10]
}, {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'lookup_witness_accounts',
    'params': ['steemit', 10]
}]

STEEMD_JSON_RPC_CALLS = randomize_jrpc_ids(_STEEMD_JSON_RPC_CALLS)

STEEMD_JSONRPC_CALL_PAIRS = []
for c in STEEMD_JSON_RPC_CALLS:
    if c['method'] == 'call':
        method = c['params'][1]
        new_method = [m for m in STEEMD_JSON_RPC_CALLS if m['method'] == method]
        STEEMD_JSONRPC_CALL_PAIRS.append((c, new_method[0]))

STEEMD_JRPC_BATCHES = [[{'id': 129,
                         'jsonrpc': '2.0',
                         'method': 'get_discussions_by_feed',
                         'params': [{'limit': '1', 'tag': 'steem'}]},
                        {'id': 92,
                         'jsonrpc': '2.0',
                         'method': 'get_dynamic_global_properties',
                         'params': []},
                        {'id': 377, 'jsonrpc': '2.0', 'method': 'get_account_count', 'params': []},
                        {'id': 149,
                         'jsonrpc': '2.0',
                         'method': 'get_discussions_by_payout',
                         'params': [{'limit': '1', 'tag': 'steem'}]},
                        {'id': 635,
                         'jsonrpc': '2.0',
                         'method': 'get_content',
                         'params': ['steemit', 'test']},
                        {'id': 49,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_hardfork_version', []]},
                        {'id': 589,
                         'jsonrpc': '2.0',
                         'method': 'get_open_orders',
                         'params': ['steemit']},
                        {'id': 102,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_conversion_requests', ['steemit']]},
                        {'id': 721,
                         'jsonrpc': '2.0',
                         'method': 'get_discussions_by_cashout',
                         'params': [{'limit': '1', 'tag': 'steem'}]}],
                       [{'id': 377,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_account_votes', ['steemit', 'test']]},
                        {'id': 834,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_discussions_by_cashout',
                                    [{'limit': '1', 'tag': 'steem'}]]},
                        {'id': 562, 'jsonrpc': '2.0', 'method': 'get_feed_history', 'params': []},
                        {'id': 227,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'lookup_witness_accounts', ['steemit', 10]]},
                        {'id': 309, 'jsonrpc': '2.0', 'method': 'get_miner_queue', 'params': []},
                        {'id': 572,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_witness_schedule', []]},
                        {'id': 666,
                         'jsonrpc': '2.0',
                         'method': 'get_witness_schedule',
                         'params': []},
                        {'id': 673,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_discussions_by_trending',
                                    [{'limit': '1', 'tag': 'steem'}]]},
                        {'id': 501,
                         'jsonrpc': '2.0',
                         'method': 'get_replies_by_last_update',
                         'params': ['smooth', 'test', 10]}],
                       [{'id': 564, 'jsonrpc': '2.0', 'method': 'get_config', 'params': []},
                        {'id': 208,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_active_votes', ['smooth', 'test']]},
                        {'id': 978,
                         'jsonrpc': '2.0',
                         'method': 'get_discussions_by_author_before_date',
                         'params': ['smooth', 'test', '2016-07-23T22:00:06', '1']},
                        {'id': 919,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_open_orders', ['steemit']]},
                        {'id': 884,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_content_replies', ['steemit', 'test']]},
                        {'id': 858,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_accounts', [['steemit']]]},
                        {'id': 111,
                         'jsonrpc': '2.0',
                         'method': 'lookup_accounts',
                         'params': ['steemit', 10]},
                        {'id': 339,
                         'jsonrpc': '2.0',
                         'method': 'get_block_header',
                         'params': [1000]},
                        {'id': 340,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_current_median_history_price', []]}],
                       [{'id': 947,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_dynamic_global_properties', []]},
                        {'id': 950,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_content', ['steemit', 'test']]}],
                       [{'id': 96, 'jsonrpc': '2.0', 'method': 'get_state', 'params': ['/@layz3r']},
                        {'id': 340,
                         'jsonrpc': '2.0',
                         'method': 'get_account_votes',
                         'params': ['steemit', 'test']},
                        {'id': 209,
                         'jsonrpc': '2.0',
                         'method': 'get_liquidity_queue',
                         'params': ['steemit', 10]},
                        {'id': 661,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_discussions_by_active',
                                    [{'limit': '1', 'tag': 'steem'}]]},
                        {'id': 140,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_discussions_by_children',
                                    [{'limit': '1', 'tag': 'steem'}]]}],
                       [{'id': 255,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_discussions_by_votes',
                                    [{'limit': '1', 'tag': 'steem'}]]},
                        {'id': 60,
                         'jsonrpc': '2.0',
                         'method': 'get_current_median_history_price',
                         'params': []},
                        {'id': 874,
                         'jsonrpc': '2.0',
                         'method': 'get_chain_properties',
                         'params': []},
                        {'id': 423,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'lookup_account_names', [['steemit']]]},
                        {'id': 915,
                         'jsonrpc': '2.0',
                         'method': 'get_hardfork_version',
                         'params': []}],
                       [{'id': 541,
                         'jsonrpc': '2.0',
                         'method': 'get_active_votes',
                         'params': ['smooth', 'test']},
                        {'id': 274,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_discussions_by_feed',
                                    [{'limit': '1', 'tag': 'steem'}]]}],
                       [{'id': 804,
                         'jsonrpc': '2.0',
                         'method': 'get_accounts',
                         'params': [['steemit']]},
                        {'id': 916,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_witness_by_account', ['smooth.witness']]},
                        {'id': 186,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_state', ['/@layz3r']]},
                        {'id': 72,
                         'jsonrpc': '2.0',
                         'method': 'get_account_history',
                         'params': ['steemit', 20, 10]},
                        {'id': 573,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_next_scheduled_hardfork', ['steemit', 10]]},
                        {'id': 678,
                         'jsonrpc': '2.0',
                         'method': 'get_active_witnesses',
                         'params': []},
                        {'id': 348, 'jsonrpc': '2.0', 'method': 'get_witness_count', 'params': []},
                        {'id': 334,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_discussions_by_created',
                                    [{'limit': '1', 'tag': 'steem'}]]},
                        {'id': 333,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_account_count', []]}],
                       [{'id': 623,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_witness_count', []]},
                        {'id': 986,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_liquidity_queue', ['steemit', 10]]},
                        {'id': 113,
                         'jsonrpc': '2.0',
                         'method': 'get_content_replies',
                         'params': ['steemit', 'test']},
                        {'id': 653,
                         'jsonrpc': '2.0',
                         'method': 'lookup_witness_accounts',
                         'params': ['steemit', 10]},
                        {'id': 101,
                         'jsonrpc': '2.0',
                         'method': 'get_recovery_request',
                         'params': ['steemit']},
                        {'id': 175,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_replies_by_last_update',
                                    ['smooth', 'test', 10]]},
                        {'id': 481, 'jsonrpc': '2.0', 'method': 'get_order_book', 'params': [10]}],
                       [{'id': 850,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_discussions_by_payout',
                                    [{'limit': '1', 'tag': 'steem'}]]}],
                       [{'id': 995,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_discussions_by_hot',
                                    [{'limit': '1', 'tag': 'steem'}]]},
                        {'id': 148,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_active_witnesses', []]},
                        {'id': 916,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'lookup_accounts', ['steemit', 10]]},
                        {'id': 738,
                         'jsonrpc': '2.0',
                         'method': 'get_conversion_requests',
                         'params': ['steemit']}],
                       [{'id': 30,
                         'jsonrpc': '2.0',
                         'method': 'get_discussions_by_active',
                         'params': [{'limit': '1', 'tag': 'steem'}]},
                        {'id': 89,
                         'jsonrpc': '2.0',
                         'method': 'get_discussions_by_children',
                         'params': [{'limit': '1', 'tag': 'steem'}]},
                        {'id': 75,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_account_history', ['steemit', 20, 10]]}],
                       [{'id': 326,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_miner_queue', []]},
                        {'id': 407,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_config', []]},
                        {'id': 769,
                         'jsonrpc': '2.0',
                         'method': 'get_discussions_by_created',
                         'params': [{'limit': '1', 'tag': 'steem'}]},
                        {'id': 539,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_order_book', [10]]},
                        {'id': 658,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_owner_history', ['steemit']]},
                        {'id': 247,
                         'jsonrpc': '2.0',
                         'method': 'get_discussions_by_hot',
                         'params': [{'limit': '1', 'tag': 'steem'}]},
                        {'id': 42,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_chain_properties', []]},
                        {'id': 717,
                         'jsonrpc': '2.0',
                         'method': 'get_discussions_by_trending',
                         'params': [{'limit': '1', 'tag': 'steem'}]}],
                       [{'id': 17,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_recovery_request', ['steemit']]},
                        {'id': 680,
                         'jsonrpc': '2.0',
                         'method': 'get_next_scheduled_hardfork',
                         'params': ['steemit', 10]},
                        {'id': 711,
                         'jsonrpc': '2.0',
                         'method': 'lookup_account_names',
                         'params': [['steemit']]}],
                       [{'id': 915,
                         'jsonrpc': '2.0',
                         'method': 'get_witness_by_account',
                         'params': ['smooth.witness']}],
                       [{'id': 201,
                         'jsonrpc': '2.0',
                         'method': 'get_owner_history',
                         'params': ['steemit']},
                        {'id': 862,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_trending_tags', ['steemit', 10]]},
                        {'id': 834,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_block_header', [1000]]},
                        {'id': 267,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api',
                                    'get_discussions_by_author_before_date',
                                    ['smooth', 'test', '2016-07-23T22:00:06', '1']]},
                        {'id': 691,
                         'jsonrpc': '2.0',
                         'method': 'get_discussions_by_votes',
                         'params': [{'limit': '1', 'tag': 'steem'}]}],
                       [{'id': 155,
                         'jsonrpc': '2.0',
                         'method': 'call',
                         'params': ['database_api', 'get_feed_history', []]},
                        {'id': 347,
                         'jsonrpc': '2.0',
                         'method': 'get_trending_tags',
                         'params': ['steemit', 10]}]]


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
def dummy_request(dummy_app_config):
    request = AttrDict()
    request.app = dummy_app_config
    return request


@pytest.fixture(scope='function')
def app():
    args = jussi.serve.parse_args(args=[])
    # run app
    app = sanic.Sanic('testApp')
    app.config.args = args
    app = jussi.logging_config.setup_logging(app)
    app = jussi.serve.setup_routes(app)
    app = jussi.middlewares.setup_middlewares(app)
    app = jussi.errors.setup_error_handlers(app)
    app = jussi.listeners.setup_listeners(app)
    yield app

@pytest.fixture(scope='function')
def caches():

    aiocaches.set_config({
        'default': {
            'cache': "aiocache.SimpleMemoryCache",
            'serializer':{
            'class':'aiocache.serializers.JsonSerializer'}},
        'redis': {'cache': "aiocache.SimpleMemoryCache",
        'serializer': {
            'class':'aiocache.serializers.JsonSerializer'}
    }})
    active_caches = [
        aiocaches.create(**aiocaches.get_alias_config('default')),
        aiocaches.create(**aiocaches.get_alias_config('redis'))
    ]
    return active_caches

# pylint:;  disable=unused-argument
@pytest.fixture(scope='function')
def app_with_wait(loop, app):
    @app.route('/wait/<seconds:number>')
    async def wait_route(request, seconds):
        time.sleep(seconds)
        return sanic.response.text('OK')

    yield app


@pytest.fixture
def test_cli(loop, app, test_client, unused_port):
    return test_client(app, port=unused_port)


@pytest.fixture(
    scope='function',
    params=['/', '/health', '/.well-known/healthcheck.json'])
def healthcheck_path(request):
    return request.param


@pytest.fixture
def jrpc_response_validator():
    return jsonschema.Draft4Validator(RESPONSE_SCHEMA)


@pytest.fixture
def jrpc_request_validator():
    return jsonschema.Draft4Validator(REQUEST_SCHEMA)


@pytest.fixture
def valid_single_jrpc_request():
    return {'id': 1, 'jsonrpc': '2.0', 'method': 'get_block', 'params': [1000]}


@pytest.fixture
def valid_batch_jrpc_request(valid_single_jrpc_request):
    return [valid_single_jrpc_request, valid_single_jrpc_request]


@pytest.fixture(params=INVALID_JRPC_REQUESTS)
def invalid_jrpc_requests(request):
    yield request.param


@pytest.fixture(params=STEEMD_JSON_RPC_CALLS, ids=lambda c: '%s%s' % (c['method'], c['params']))
def all_steemd_jrpc_calls(request):
    yield request.param


@pytest.fixture(params=STEEMD_JSONRPC_CALL_PAIRS)
def steemd_method_pairs(request):
    yield request.param


@pytest.fixture(params=STEEMD_JRPC_BATCHES)
def random_jrpc_batch(request):
    yield request.param

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
