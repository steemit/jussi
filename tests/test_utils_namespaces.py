# -*- coding: utf-8 -*-
from jussi.urn import parse_namespaced_method, URN
import pytest
from jussi.upstream import _Upstreams
from jussi.upstream import DEFAULT_UPSTREAM_CONFIG
upstreams = _Upstreams(DEFAULT_UPSTREAM_CONFIG, validate=False)
namespaces = upstreams.namespaces


@pytest.mark.parametrize("namspaced_method,expected", [
    ("get_block", ('steemd', 'get_block')),
    ("call", ('steemd', 'call')),
    ("yo.get_block", ('yo', 'get_block')),
    ('sbds.get_block', ('sbds', 'get_block')),
    ('sbds.call', ('sbds', 'call')),
    ('sbds.get_block.get_block', ('sbds', 'get_block.get_block')),
    ('sbds.steemd.get_block', ('sbds', 'steemd.get_block')),
    ('call', ('steemd', 'call')),
    ('call', ('steemd', 'call')),
    ('database_api.get_dynamic_global_properties',
     ('steemd', 'database_api.get_dynamic_global_properties')),
    ('database_api.get_dynamic_global_properties',
     ('steemd', 'database_api.get_dynamic_global_properties')),
    ('call', ('steemd', 'call')),
    ('condenser_api.get_dynamic_global_properties',
     ('steemd', 'condenser_api.get_dynamic_global_properties')),
    ('call', ('steemd', 'call')),
    ('database_api.find_accounts', ('steemd', 'database_api.find_accounts')),
    ('call', ('steemd', 'call')),
    ('call', ('steemd', 'call')),
    ('database_api.find_accounts', ('steemd', 'database_api.find_accounts')),
    ('database_api.find_accounts', ('steemd', 'database_api.find_accounts')),
    ('database_api.find_accounts', ('steemd', 'database_api.find_accounts')),
    ('call', ('steemd', 'call')),
    ('condenser_api.get_accounts', ('steemd', 'condenser_api.get_accounts')),
    ('call', ('steemd', 'call')),
    ('condenser_api.get_accounts', ('steemd', 'condenser_api.get_accounts')),
    ('call', ('steemd', 'call')),
    ('block_api.get_block', ('steemd', 'block_api.get_block'))
])
def test_parse_namespaced_method(namspaced_method, expected):
    result = parse_namespaced_method(namspaced_method, namespaces=namespaces)
    assert result == expected


@pytest.mark.parametrize("jsonrpc_request,expected", [
    ({'id': 1, 'jsonrpc': '2.0', 'method': 'get_account_count', 'params': []},
        'steemd.database_api.get_account_count'
     ),
    ({'id': 1, 'jsonrpc': '2.0', 'method': 'get_account_count'},
        'steemd.database_api.get_account_count'
     ),
    ({'id': 1, 'jsonrpc': '2.0', 'method': 'call', 'params': ['database_api', 'get_account_count', []]},
     'steemd.database_api.get_account_count'
     ),
    ({'id': 1, 'jsonrpc': '2.0', 'method': 'yo.test', 'params': ['database_api', 'get_account_count', []]},
     "yo.test.params=['database_api','get_account_count',[]]"
     ),
    ({'id': 1, 'jsonrpc': '2.0', 'method': 'yo.test', 'params': {'z': 'val1', 'a': [], 'f':1}},
     "yo.test.params={'a':[],'f':1,'z':'val1'}"
     ),
    ({"id": "1", "jsonrpc": "2.0", "method": "get_block", "params": [1000]},
     'steemd.database_api.get_block.params=[1000]'
     ),
    ({"id": "1", "jsonrpc": "2.0", "method": "condenser_api.get_block", "params": [1000]},
     'steemd.condenser_api.get_block.params=[1000]'
     ),
    ({"id": "1", "jsonrpc": "2.0", "method": "call", "params": ["condenser_api", "get_block", [1000]]},
     'steemd.condenser_api.get_block.params=[1000]'
     ),
    ({"id": "1", "jsonrpc": "2.0", "method": "block_api.get_block", "params": {"block_num": 1000}},
     "steemd.block_api.get_block.params={'block_num':1000}"
     ),
    ({'id': 1,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['database_api', 'get_dynamic_global_properties']},
     'steemd.database_api.get_dynamic_global_properties'),
    ({'id': 3,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['database_api', 'get_dynamic_global_properties', {}]},
     'steemd.database_api.get_dynamic_global_properties'),
    ({'id': 4,
      'jsonrpc': '2.0',
      'method': 'database_api.get_dynamic_global_properties'},
     'steemd.database_api.get_dynamic_global_properties'),
    ({'id': 5,
      'jsonrpc': '2.0',
      'method': 'database_api.get_dynamic_global_properties',
      'params': {}},
     'steemd.database_api.get_dynamic_global_properties'),
    ({'id': 8,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['condenser_api', 'get_dynamic_global_properties', []]},
     'steemd.condenser_api.get_dynamic_global_properties'),
    ({'id': 12,
      'jsonrpc': '2.0',
      'method': 'condenser_api.get_dynamic_global_properties',
      'params': []},
     'steemd.condenser_api.get_dynamic_global_properties'),
    ({'id': 13,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['database_api', 'find_accounts', {'accounts': ['init_miner']}]},
     "steemd.database_api.find_accounts.params={'accounts':['init_miner']}"),
    ({'id': 14,
      'jsonrpc': '2.0',
      'method': 'database_api.find_accounts',
      'params': {'accounts': ['init_miner']}},
     "steemd.database_api.find_accounts.params={'accounts':['init_miner']}"),
    ({'id': 15,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['database_api', 'find_accounts', {}]},
     'steemd.database_api.find_accounts'),
    ({'id': 15,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['database_api', 'find_accounts']},
     'steemd.database_api.find_accounts'),
    ({'id': 17,
      'jsonrpc': '2.0',
      'method': 'database_api.find_accounts',
      'params': {'accounts': ['init_miner']}},
     "steemd.database_api.find_accounts.params={'accounts':['init_miner']}"),
    ({'id': 16,
      'jsonrpc': '2.0',
      'method': 'database_api.find_accounts',
      'params': {}},
     'steemd.database_api.find_accounts'),
    ({'id': 18, 'jsonrpc': '2.0', 'method': 'database_api.find_accounts'},
     'steemd.database_api.find_accounts'),
    ({'id': 6,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['condenser_api', 'get_accounts', [['init_miner']]]},
     "steemd.condenser_api.get_accounts.params=[['init_miner']]"),
    ({'id': 7,
      'jsonrpc': '2.0',
      'method': 'condenser_api.get_accounts',
      'params': [['init_miner']]},
     "steemd.condenser_api.get_accounts.params=[['init_miner']]"),
    ({'id': 8,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['condenser_api', 'get_accounts', [[]]]},
     'steemd.condenser_api.get_accounts.params=[[]]'),
    ({'id': 9,
      'jsonrpc': '2.0',
      'method': 'condenser_api.get_accounts',
      'params': [[]]},
     'steemd.condenser_api.get_accounts.params=[[]]'),
    ({'id': 10,
      'jsonrpc': '2.0',
      'method': 'call',
      'params': ['block_api', 'get_block', {'block_num': 23}]},
     "steemd.block_api.get_block.params={'block_num':23}"),
    ({'id': 11,
      'jsonrpc': '2.0',
      'method': 'block_api.get_block',
      'params': {'block_num': 0}},
     "steemd.block_api.get_block.params={'block_num':0}")

])
def test_urns(jsonrpc_request, expected):
    result = str(URN.from_request(jsonrpc_request, namespaces=namespaces))
    assert result == expected


def test_urn_pairs(steemd_method_pairs):
    old, new = steemd_method_pairs
    old_urn = str(URN.from_request(old, namespaces=namespaces))
    new_urn = str(URN.from_request(new, namespaces=namespaces))
    assert old_urn == new_urn
    assert old_urn.startswith('steemd.database_api')
