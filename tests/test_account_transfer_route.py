# -*- coding: utf-8 -*-
import os
from jussi.upstream import Upstream
from jussi.urn import URN

import pytest
from jussi.upstream import _Upstreams
from jussi.upstream import DEFAULT_UPSTREAM_CONFIG


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


dummy_request = AttrDict()
dummy_request.headers = dict()
dummy_request['jussi_request_id'] = '123456789012345'
dummy_request.app = AttrDict()
dummy_request.app.config = AttrDict()
dummy_request.app.config.upstreams = _Upstreams(DEFAULT_UPSTREAM_CONFIG, validate=False)


@pytest.mark.parametrize("jrpc_request,expected", [
    ({"id": 1,
        "jsonrpc": "2.0",
        "method": "call",
      "params": ["database_api", "get_state", ["/@justinw/transfers"]]},
     "test"),
    ({"id": 1,
        "jsonrpc": "2.0",
        "method": "get_state",
      "params": ["/@justinw/transfers"]},
     "test"),
    ({"id": 1,
        "jsonrpc": "2.0",
        "method": "call",
      "params": ["database_api", "get_state", ["\/@justinw\/transfers"]]},
     "test"),
    ({"id": 1,
        "jsonrpc": "2.0",
        "method": "get_state",
      "params": ["\/@justinw\/transfers"]},
     "test"),
    # normal cases
    ({'id': 1, 'jsonrpc': '2.0', 'method': 'get_account_count', 'params': []},
     'wss://steemd.steemit.com'
     ),
    ({'id': 1, 'jsonrpc': '2.0', 'method': 'get_account_count'},
        'wss://steemd.steemit.com'
     ),
    ({'id': 1, 'jsonrpc': '2.0', 'method': 'call', 'params': ['database_api', 'get_account_count', []]},
     'wss://steemd.steemit.com'
     ),
    ({'id': 1, 'jsonrpc': '2.0', 'method': 'yo.test', 'params': ['database_api', 'get_account_count', []]},
     'https://yo.steemit.com'
     ),
    ({'id': 1, 'jsonrpc': '2.0', 'method': 'yo.test', 'params': {'z': 'val1', 'a': [], 'f':1}},
     'https://yo.steemit.com'
     ),
    ({"id": "1", "jsonrpc": "2.0", "method": "get_block", "params": [1000]},
     'wss://steemd.steemit.com'
     ),
    ({"id": "1", "jsonrpc": "2.0", "method": "condenser_api.get_block", "params": [1000]},
     'wss://steemd.steemit.com'
     ),
    ({"id": "1", "jsonrpc": "2.0", "method": "call", "params": ["condenser_api", "get_block", [1000]]},
     'wss://steemd.steemit.com'
     ),
    ({"id": "1", "jsonrpc": "2.0", "method": "block_api.get_block", "params": {"block_num": 1000}},
     'wss://steemd.steemit.com'
     ),
    ({'id': 1,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['database_api', 'get_dynamic_global_properties']},
     'wss://steemd.steemit.com'),
    ({'id': 3,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['database_api', 'get_dynamic_global_properties', {}]},
     'wss://steemd.steemit.com'),
    ({'id': 4,
      'jsonrpc': '2.0',
      'method': 'database_api.get_dynamic_global_properties'},
     'wss://steemd.steemit.com'),
    ({'id': 5,
      'jsonrpc': '2.0',
      'method': 'database_api.get_dynamic_global_properties',
      'params': {}},
     'wss://steemd.steemit.com'),
    ({'id': 8,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['condenser_api', 'get_dynamic_global_properties', []]},
     'wss://steemd.steemit.com'),
    ({'id': 12,
      'jsonrpc': '2.0',
      'method': 'condenser_api.get_dynamic_global_properties',
      'params': []},
     'wss://steemd.steemit.com'),
    ({'id': 13,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['database_api', 'find_accounts', {'accounts': ['init_miner']}]},
     'wss://steemd.steemit.com'),
    ({'id': 14,
      'jsonrpc': '2.0',
      'method': 'database_api.find_accounts',
      'params': {'accounts': ['init_miner']}},
     'wss://steemd.steemit.com'),
    ({'id': 15,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['database_api', 'find_accounts', {}]},
     'wss://steemd.steemit.com'),
    ({'id': 15,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['database_api', 'find_accounts']},
     'wss://steemd.steemit.com'),
    ({'id': 17,
      'jsonrpc': '2.0',
      'method': 'database_api.find_accounts',
      'params': {'accounts': ['init_miner']}},
     'wss://steemd.steemit.com'),
    ({'id': 16,
      'jsonrpc': '2.0',
      'method': 'database_api.find_accounts',
      'params': {}},
     'wss://steemd.steemit.com'),
    ({'id': 18, 'jsonrpc': '2.0', 'method': 'database_api.find_accounts'},
     'wss://steemd.steemit.com'),
    ({'id': 6,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['condenser_api', 'get_accounts', [['init_miner']]]},
     'wss://steemd.steemit.com'),
    ({'id': 7,
      'jsonrpc': '2.0',
      'method': 'condenser_api.get_accounts',
      'params': [['init_miner']]},
     'wss://steemd.steemit.com'),
    ({'id': 8,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['condenser_api', 'get_accounts', [[]]]},
     'wss://steemd.steemit.com'),
    ({'id': 9,
      'jsonrpc': '2.0',
      'method': 'condenser_api.get_accounts',
      'params': [[]]},
     'wss://steemd.steemit.com'),
    ({'id': 10,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['block_api', 'get_block', {'block_num': 23}]},
     'wss://steemd.steemit.com'),
    ({'id': 11,
      'jsonrpc': '2.0',
      'method': 'block_api.get_block',
      'params': {'block_num': 0}},
     'wss://steemd.steemit.com')
])
def test_url_env_var_defined(jrpc_request, expected):
    os.environ['JUSSI_ACCOUNT_TRANSFER_STEEMD_URL'] = 'test'
    urn = URN.from_request(jrpc_request, dummy_request.app.config.upstreams.namespaces)
    upstream = Upstream.from_urn(urn, upstreams=dummy_request.app.config.upstreams)
    assert upstream.url == expected
    del os.environ['JUSSI_ACCOUNT_TRANSFER_STEEMD_URL']
