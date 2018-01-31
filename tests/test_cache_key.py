# -*- coding: utf-8 -*-
from collections import OrderedDict

import pytest

from jussi.cache.utils import jsonrpc_cache_key
from jussi.request import JussiJSONRPCRequest
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


@pytest.mark.parametrize(
    "jsonrpc_request,expected",
    [
        (JussiJSONRPCRequest.from_request(dummy_request, 0, OrderedDict([('id', 1), ('jsonrpc', '2.0'), ('method', 'call'),
                                                                         ('params', ['database_api', 'get_account_count', []])])),
         'steemd.database_api.get_account_count'),
        (JussiJSONRPCRequest.from_request(dummy_request, 0, OrderedDict(
            [('id', 1), ('jsonrpc', '2.0'), ('method', 'call'),
             ('params',
              ['database_api', 'get_account_history', ['steemit', 10, 20]])])),
         "steemd.database_api.get_account_history.params=['steemit',10,20]"),
        (JussiJSONRPCRequest.from_request(dummy_request, 0, OrderedDict([('id', 1), ('jsonrpc', '2.0'), ('method', 'call'),
                                                                         ('params',
                                                                          ['database_api', 'get_account_references',
                                                                           ['steemit']])])),
         "steemd.database_api.get_account_references.params=['steemit']"),

        # test ordering or dict params
        (JussiJSONRPCRequest.from_request(dummy_request, 0, OrderedDict([('id', 1), ('jsonrpc', '2.0'),
                                                                         ('method', 'yo.test_dict'), ('params', {
                                                                             'str': '1',
                                                                             'none': None,
                                                                             'dict': {},
                                                                             'int': 1,
                                                                             'list': [],
                                                                         })])),
         "yo.test_dict.params={'dict':{},'int':1,'list':[],'none':None,'str':'1'}"
         ),

        # test list params
        (JussiJSONRPCRequest.from_request(dummy_request, 0, OrderedDict([('id', 1), ('jsonrpc', '2.0'),
                                                                         ('method', 'sbds.test_list'), ('params', [{}, 1, [], '1',
                                                                                                                   None])])),
         "sbds.test_list.params=[{},1,[],'1',None]"),

        # test no params
        (JussiJSONRPCRequest.from_request(dummy_request, 0, OrderedDict([('id', 1), ('jsonrpc', '2.0'),
                                                                         ('method', 'yo.test_no_params')])),
         'yo.test_no_params'),
        (JussiJSONRPCRequest.from_request(dummy_request, 0, OrderedDict([('id', 1), ('jsonrpc', '2.0'),
                                                                         ('method', 'condenser_api.get_dynamic_global_properties')])),
         'steemd.condenser_api.get_dynamic_global_properties'),
    ],
    ids=lambda v: v['method'])
def test_cache_key(jsonrpc_request, expected):
    result = jsonrpc_cache_key(jsonrpc_request)
    assert result == expected
