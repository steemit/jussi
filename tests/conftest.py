# -*- coding: utf-8 -*-
import os

import sanic
import sanic.response
import ujson
from aiocache import caches as aiocaches
from funcy.funcs import rpartial

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


TEST_DIR = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(TEST_DIR, 'request-schema.json')) as f:
    REQUEST_SCHEMA = ujson.load(f)
with open(os.path.join(TEST_DIR, 'response-schema.json')) as f:
    RESPONSE_SCHEMA = ujson.load(f)
with open(os.path.join(TEST_DIR, 'steemd-response-schema.json')) as f:
    STEEMD_RESPONSE_SCHEMA = ujson.load(f)

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

STEEMD_JSON_RPC_CALLS = [{'id': 0,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_account_count', []]},
 {'id': 1,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_account_history', ['steemit', 20, 10]]},
 {'id': 2,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_account_votes', ['steemit', 'test']]},
 {'id': 3,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_accounts', [['steemit']]]},
 {'id': 4,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_active_votes', ['smooth', 'test']]},
 {'id': 5,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_active_witnesses', []]},
 {'id': 6,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_block_header', [1000]]},
 {'id': 7,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_chain_properties', []]},
 {'id': 8,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_config', []]},
 {'id': 9,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_content', ['steemit', 'test']]},
 {'id': 10,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_content_replies', ['steemit', 'test']]},
 {'id': 11,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_conversion_requests', ['steemit']]},
 {'id': 12,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_current_median_history_price', []]},
 {'id': 13,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_discussions_by_active',
   [{'limit': '1', 'tag': 'steem'}]]},
 {'id': 14,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_discussions_by_author_before_date',
   ['smooth', 'test', '2016-07-23T22:00:06', '1']]},
 {'id': 15,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_discussions_by_cashout',
   [{'limit': '1', 'tag': 'steem'}]]},
 {'id': 16,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_discussions_by_children',
   [{'limit': '1', 'tag': 'steem'}]]},
 {'id': 17,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_discussions_by_created',
   [{'limit': '1', 'tag': 'steem'}]]},
 {'id': 18,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_discussions_by_feed',
   [{'limit': '1', 'tag': 'steem'}]]},
 {'id': 19,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_discussions_by_hot',
   [{'limit': '1', 'tag': 'steem'}]]},
 {'id': 20,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_discussions_by_payout',
   [{'limit': '1', 'tag': 'steem'}]]},
 {'id': 21,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_discussions_by_trending',
   [{'limit': '1', 'tag': 'steem'}]]},
 {'id': 22,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_discussions_by_votes',
   [{'limit': '1', 'tag': 'steem'}]]},
 {'id': 23,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_dynamic_global_properties', []]},
 {'id': 24,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_feed_history', []]},
 {'id': 25,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_hardfork_version', []]},
 {'id': 26,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_liquidity_queue', ['steemit', 10]]},
 {'id': 27,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_miner_queue', []]},
 {'id': 28,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_next_scheduled_hardfork', ['steemit', 10]]},
 {'id': 29,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_open_orders', ['steemit']]},
 {'id': 30,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_order_book', [10]]},
 {'id': 31,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_owner_history', ['steemit']]},
 {'id': 32,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_recovery_request', ['steemit']]},
 {'id': 33,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api',
   'get_replies_by_last_update',
   ['smooth', 'test', 10]]},
 {'id': 34,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_state', ['/@layz3r']]},
 {'id': 35,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_trending_tags', ['steemit', 10]]},
 {'id': 36,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_witness_by_account', ['smooth.witness']]},
 {'id': 37,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_witness_count', []]},
 {'id': 38,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'get_witness_schedule', []]},
 {'id': 39,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'lookup_account_names', [['steemit']]]},
 {'id': 40,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'lookup_accounts', ['steemit', 10]]},
 {'id': 41,
  'jsonrpc': '2.0',
  'method': 'call',
  'params': ['database_api', 'lookup_witness_accounts', ['steemit', 10]]},
 {'id': 42, 'jsonrpc': '2.0', 'method': 'get_account_count', 'params': []},
 {'id': 43,
  'jsonrpc': '2.0',
  'method': 'get_account_history',
  'params': ['steemit', 20, 10]},
 {'id': 44,
  'jsonrpc': '2.0',
  'method': 'get_account_votes',
  'params': ['steemit', 'test']},
 {'id': 45,
  'jsonrpc': '2.0',
  'method': 'get_accounts',
  'params': [['steemit']]},
 {'id': 46,
  'jsonrpc': '2.0',
  'method': 'get_active_votes',
  'params': ['smooth', 'test']},
 {'id': 47, 'jsonrpc': '2.0', 'method': 'get_active_witnesses', 'params': []},
 {'id': 48, 'jsonrpc': '2.0', 'method': 'get_block_header', 'params': [1000]},
 {'id': 49, 'jsonrpc': '2.0', 'method': 'get_chain_properties', 'params': []},
 {'id': 50, 'jsonrpc': '2.0', 'method': 'get_config', 'params': []},
 {'id': 51,
  'jsonrpc': '2.0',
  'method': 'get_content',
  'params': ['steemit', 'test']},
 {'id': 52,
  'jsonrpc': '2.0',
  'method': 'get_content_replies',
  'params': ['steemit', 'test']},
 {'id': 53,
  'jsonrpc': '2.0',
  'method': 'get_conversion_requests',
  'params': ['steemit']},
 {'id': 54,
  'jsonrpc': '2.0',
  'method': 'get_current_median_history_price',
  'params': []},
 {'id': 55,
  'jsonrpc': '2.0',
  'method': 'get_discussions_by_active',
  'params': [{'limit': '1', 'tag': 'steem'}]},
 {'id': 56,
  'jsonrpc': '2.0',
  'method': 'get_discussions_by_author_before_date',
  'params': ['smooth', 'test', '2016-07-23T22:00:06', '1']},
 {'id': 57,
  'jsonrpc': '2.0',
  'method': 'get_discussions_by_cashout',
  'params': [{'limit': '1', 'tag': 'steem'}]},
 {'id': 58,
  'jsonrpc': '2.0',
  'method': 'get_discussions_by_children',
  'params': [{'limit': '1', 'tag': 'steem'}]},
 {'id': 59,
  'jsonrpc': '2.0',
  'method': 'get_discussions_by_created',
  'params': [{'limit': '1', 'tag': 'steem'}]},
 {'id': 60,
  'jsonrpc': '2.0',
  'method': 'get_discussions_by_feed',
  'params': [{'limit': '1', 'tag': 'steem'}]},
 {'id': 61,
  'jsonrpc': '2.0',
  'method': 'get_discussions_by_hot',
  'params': [{'limit': '1', 'tag': 'steem'}]},
 {'id': 62,
  'jsonrpc': '2.0',
  'method': 'get_discussions_by_payout',
  'params': [{'limit': '1', 'tag': 'steem'}]},
 {'id': 63,
  'jsonrpc': '2.0',
  'method': 'get_discussions_by_trending',
  'params': [{'limit': '1', 'tag': 'steem'}]},
 {'id': 64,
  'jsonrpc': '2.0',
  'method': 'get_discussions_by_votes',
  'params': [{'limit': '1', 'tag': 'steem'}]},
 {'id': 65,
  'jsonrpc': '2.0',
  'method': 'get_dynamic_global_properties',
  'params': []},
 {'id': 66, 'jsonrpc': '2.0', 'method': 'get_feed_history', 'params': []},
 {'id': 67, 'jsonrpc': '2.0', 'method': 'get_hardfork_version', 'params': []},
 {'id': 68,
  'jsonrpc': '2.0',
  'method': 'get_liquidity_queue',
  'params': ['steemit', 10]},
 {'id': 69, 'jsonrpc': '2.0', 'method': 'get_miner_queue', 'params': []},
 {'id': 70,
  'jsonrpc': '2.0',
  'method': 'get_next_scheduled_hardfork',
  'params': ['steemit', 10]},
 {'id': 71,
  'jsonrpc': '2.0',
  'method': 'get_open_orders',
  'params': ['steemit']},
 {'id': 72, 'jsonrpc': '2.0', 'method': 'get_order_book', 'params': [10]},
 {'id': 73,
  'jsonrpc': '2.0',
  'method': 'get_owner_history',
  'params': ['steemit']},
 {'id': 74,
  'jsonrpc': '2.0',
  'method': 'get_recovery_request',
  'params': ['steemit']},
 {'id': 75,
  'jsonrpc': '2.0',
  'method': 'get_replies_by_last_update',
  'params': ['smooth', 'test', 10]},
 {'id': 76, 'jsonrpc': '2.0', 'method': 'get_state', 'params': ['/@layz3r']},
 {'id': 77,
  'jsonrpc': '2.0',
  'method': 'get_trending_tags',
  'params': ['steemit', 10]},
 {'id': 78,
  'jsonrpc': '2.0',
  'method': 'get_witness_by_account',
  'params': ['smooth.witness']},
 {'id': 79, 'jsonrpc': '2.0', 'method': 'get_witness_count', 'params': []},
 {'id': 80, 'jsonrpc': '2.0', 'method': 'get_witness_schedule', 'params': []},
 {'id': 81,
  'jsonrpc': '2.0',
  'method': 'lookup_account_names',
  'params': [['steemit']]},
 {'id': 82,
  'jsonrpc': '2.0',
  'method': 'lookup_accounts',
  'params': ['steemit', 10]},
 {'id': 83,
  'jsonrpc': '2.0',
  'method': 'lookup_witness_accounts',
  'params': ['steemit', 10]}
]

STEEMD_JSONRPC_CALL_PAIRS = []
for c in STEEMD_JSON_RPC_CALLS:
    if c['method'] == 'call':
        method = c['params'][1]
        new_method = [m for m in STEEMD_JSON_RPC_CALLS if m['method'] == method]
        STEEMD_JSONRPC_CALL_PAIRS.append((c, new_method[0]))


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
def app(loop):
    args = jussi.serve.parse_args(args=[])
    # run app
    app = sanic.Sanic('testApp')
    app.config.args = args
    app.config.args.server_port = 42101
    app = jussi.logging_config.setup_logging(app)
    app = jussi.serve.setup_routes(app)
    app = jussi.middlewares.setup_middlewares(app)
    app = jussi.errors.setup_error_handlers(app)
    app = jussi.listeners.setup_listeners(app)
    try:
        loop.run_until_complete(aiocaches.get('default').clear())
        loop.run_until_complete(aiocaches.get('redis').clear())
    except KeyError:
        pass

    yield app
    try:
        loop.run_until_complete(aiocaches.get('default').close())
        loop.run_until_complete(aiocaches.get('redis').close())
    except KeyError:
        pass
    del app.config


@pytest.fixture(scope='function')
def caches(loop):
    aiocaches.set_config({
        'default': {
            'cache': "aiocache.SimpleMemoryCache",
            'serializer': {
                'class':'jussi.serializers.CompressionSerializer'
            }
        },
        'redis': {
            'cache': "aiocache.SimpleMemoryCache",
            'serializer': {
                'class':'jussi.serializers.CompressionSerializer'
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


@pytest.fixture(params=STEEMD_JSON_RPC_CALLS, ids=lambda c: c['method'])
def all_steemd_jrpc_calls(request):
    yield request.param


@pytest.fixture(params=STEEMD_JSONRPC_CALL_PAIRS)
def steemd_method_pairs(request):
    yield request.param

@pytest.fixture(params=JRPC_REQUESTS_AND_RESPONSES)
def steemd_requests_and_responses(request):
    yield request.param[0],request.param[1]

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
