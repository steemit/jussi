# -*- coding: utf-8 -*-

batch = [
    [],
    [{'Id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]}],
    [{'id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': 1000}, {}],
    [{'id': 1, 'json_rpc': '2.0', 'method': ['get_block'], 'params': '1000'},
        {'id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'jsonrpc': None, 'method': 'get_block', 'params': [1000]}],
    [{'METHOD': 'get_block', 'id': 1, 'json_rpc': '2.0', 'params': '1000'},
        {'id': 1, 'json_rpc': ['2.0'], 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]}],
    [None,
        {'METHOD': 'get_block', 'id': 1, 'json_rpc': '2.0', 'params': '1000'},
        b'',
        {},
        {'id': 1, 'method': 'get_block', 'params': [1000]}],
    ['',
        {'ID': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'json_rpc': '2.0', 'method': ['get_block'], 'params': '1000'},
        {'id': 1, 'jsonrpc': 2.0, 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        ''],
    [{'METHOD': 'get_block', 'id': 1, 'json_rpc': '2.0', 'params': '1000'},
        {'id': 1, 'jsonrpc': 2.0, 'method': 'get_block', 'params': [1000]},
        [],
        {'id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': 1000},
        {'id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': None},
        {'id': [1], 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        False],
    [{'id': 1, 'jsonrpc': None, 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'jsonrpc': 2.0, 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'jsonrpc': None, 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'jsonrpc': 2.0, 'method': 'get_block', 'params': [1000]},
        {'Id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        {'id': [1], 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'json-rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        {'id': None, 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]}],
    [{'id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': 1000},
        {'Id': 1, 'json_rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'json_rpc': '2.0', 'method': ['get_block'], 'params': '1000'},
        {'id': 1, 'json_rpc': '2.0', 'method': ['get_block'], 'params': '1000'},
        {'id': 1, 'json-rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        b'',
        {'id': 1, 'json_rpc': ['2.0'], 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'json-rpc': '2.0', 'method': 'get_block', 'params': [1000]},
        {'id': 1, 'json_rpc': ['2.0'], 'method': 'get_block', 'params': [1000]}]
]

requests = [
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

    # invalid
    False,
    'False',
    b'False',
    'false',
    b'false',

    True,
    'True',
    b'True',
    'true',
    b'true',

    None,
    'None',
    b'None',
    'null',
    b'null',

    1,
    '1',
    b'1',

    1.0,
    '1.0',
    b'1.0',

    {},
    '{}',
    b'{}',

    [],
    '[]',
    b'[]',

    '',
    b'',

]


responses = [
    False,
    'False',
    b'False',
    'false',
    b'false',

    True,
    'True',
    b'True',
    'true',
    b'true',

    # None,
    #'None',
    # b'None',
    #'null',
    # b'null',

    1,
    '1',
    b'1',

    1.0,
    '1.0',
    b'1.0',

    {},
    '{}',
    b'{}',

    [],
    '[]',
    b'[]',

    '',
    b'',

    # bad id
    {"id": False, "jsonrpc": "2.0", "result": 1},
    {"id": [1], "jsonrpc":"2.0", "result":1},
    {"id": {}, "jsonrpc": "2.0", "result": 1},

    # bad jsonrpc
    {"id": 1, "jsonrpc": 2.0, "result": 1},
    {"id": 1, "jsonrpc": 2, "result": 1},
    {"id": 1, "result": 1},

    # missing result and errpr
    {"id": 1, "jsonrpc": 2},

    # both result and error
    {"id": 1, "jsonrpc": "2.0", "result": 1, "error": {"code": -32600, "message": "Invalid Request"}}


]
