# -*- coding: utf-8 -*-
from collections import OrderedDict

import jussi.cache
import pytest


@pytest.mark.parametrize(
    "jsonrpc_request,expected",
    [(OrderedDict([('id', 1), ('jsonrpc', '2.0'), ('method', 'call'),
                   ('params', ['database_api', 'get_account_count', []])]),
      '183c48ac56b588bf796692c7cbb3dab1a1d070c7'), (OrderedDict(
          [('id',
            1), ('jsonrpc', '2.0'), ('method', 'call'), ('params', [
                'database_api', 'get_account_history', ['steemit', 10, 20]
            ])]), '2e889404a6f46c668819edb22bf550ee63952019'),
     (OrderedDict([('id', 1), ('jsonrpc', '2.0'), ('method', 'call'),
                   ('params',
                    ['database_api', 'get_account_references', ['steemit']])]),
      'aad4b92f54687da366172673d233479d498b8755'), (OrderedDict(
          [('id', 1), ('jsonrpc', '2.0'), ('method', 'call'),
           ('params', ['database_api', 'get_account_votes',
                       []])]), '1a9d131e432c0dc9d265744a206cf57ed8a88655'),
     (OrderedDict([('id', 1), ('jsonrpc', '2.0'), ('method', 'test_dict'),
                   ('params', {
                       'dict': {},
                       'int': 1,
                       'list': [],
                       'none': None,
                       'str': '1'
                   })]), 'd9407a341d3c2c90335dd85f5b2c205bfe69e64a'),
     (OrderedDict([('id', 1), ('jsonrpc', '2.0'), ('method', 'test_list'),
                   ('params', [{}, 1, [], '1', None])]),
      '4c60f37ea2c117621103de7692f5147e2613093c'), (OrderedDict([
          ('id', 1), ('jsonrpc', '2.0'), ('method', 'test_no_params')
      ]), '002587998be9dd24a0d215e12e51cd8fc342cd49')],
    ids=lambda v: v['method'])
def test_cache_key(jsonrpc_request, expected):
    result = jussi.cache.jsonrpc_cache_key(jsonrpc_request)
    assert result == expected
