# -*- coding: utf-8 -*-
from jussi.upstream.urn import parse_namespaced_method
from jussi.upstream.urn import urn
import pytest


@pytest.mark.parametrize(
    "namspaced_method,expected",
    [("get_block", ('steemd', 'get_block')), ("call", ('steemd', 'call')),
     ("yo.get_block", ('yo', 'get_block')
      ), ('sbds.get_block', ('sbds', 'get_block')),
     ('sbds.call', ('sbds', 'call')), ('sbds.get_block.get_block',
                                       ('sbds', 'get_block.get_block')),
     ('sbds.steemd.get_block', ('sbds', 'steemd.get_block'))])
def test_parse_namespaced_method(namspaced_method, expected):
    result = parse_namespaced_method(namspaced_method)
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
     )
])
def test_urns(jsonrpc_request, expected):
    result = urn(jsonrpc_request)
    assert result == expected


def test_urn_pairs(steemd_method_pairs):
    old, new = steemd_method_pairs
    old_urn = urn(old)
    new_urn = urn(new)
    assert old_urn == new_urn
    assert old_urn.startswith('steemd.database_api')
