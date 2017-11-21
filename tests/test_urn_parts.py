# -*- coding: utf-8 -*-
from collections import OrderedDict

import pytest
from jussi.upstream.urn import x_jussi_urn_parts
from jussi.upstream.urn import limit_len

str_len_120 = ''.join('a' for i in range(120))
str_len_99 = ''.join('a' for i in range(99))
str_len_100 = ''.join('a' for i in range(100))
str_len_101 = ''.join('a' for i in range(101))
abbrev_str = ''.join([str_len_100, '...'])

ITEMS = [
    (
        ['test_api', 'test_method', [str_len_99]],
        ['test_api', 'test_method', [str_len_99]]
    ),
    (
        [str_len_99],
        [str_len_99]
    ),
    (
        ['test_api', 'test_method', [str_len_100]],
        ['test_api', 'test_method', [str_len_100]]
    ),
    (
        [str_len_100],
        [str_len_100]),
    (
        ['test_api', 'test_method', [str_len_101]],
        ['test_api', 'test_method', [abbrev_str]]
    ),
    (
        [str_len_101],
        [abbrev_str]
    ),
    (
        ['test_api', 'test_method', [str_len_120]],
        ['test_api', 'test_method', [abbrev_str]]
    ),
    (
        [str_len_120],
        [abbrev_str]),
    (
        {
            'str': '1',
            'none': None,
            'dict': {},
            'int': 1,
            'list': [],
            'str_len_99': str_len_99,
            'str_len_100': str_len_100,
            'str_len_101': str_len_101,
            'str_len_120': str_len_120,
        },
        {
            'str': '1',
            'none': None,
            'dict': {},
            'int': 1,
            'list': [],
            'str_len_99': str_len_99,
            'str_len_100': str_len_100,
            'str_len_101': abbrev_str,
            'str_len_120': abbrev_str,
        }
    ),
    (
        [
            '1',
            None,
            {},
            1,
            [],
            str_len_99,
            str_len_100,
            str_len_101,
            str_len_120
        ],
        [
            '1',
            None,
            {},
            1,
            [],
            str_len_99,
            str_len_100,
            abbrev_str,
            abbrev_str
        ]
    )
]

REQUESTS = [
    # item 0
    (
        {
            'id': 1,
            'jsonrpc': '2.0',
                       'method': 'call',
                       'params': ['test_api', 'test_method', [str_len_99]]
        },
        [str_len_99]
    ),

    # item 1
    (
        {
            'id': 1,
            'jsonrpc': '2.0',
                       'method': 'test_method',
                       'params': [str_len_99]
        },
        [str_len_99]
    ),

    # item 2
    (
        {
            'id': 1,
            'jsonrpc': '2.0',
                       'method': 'call',
                       'params': ['test_api', 'test_method', [str_len_100]]
        },
        [str_len_100]
    ),

    # item 3
    (
        {
            'id': 1,
            'jsonrpc': '2.0',
                       'method': 'test_method',
                       'params': [str_len_100]
        },
        [str_len_100]
    ),

    # item 4
    (
        {
            'id': 1,
            'jsonrpc': '2.0',
                       'method': 'call',
                       'params': ['test_api', 'test_method', [str_len_101]]
        },
        [abbrev_str]
    ),

    # item 5
    (
        {
            'id': 1,
            'jsonrpc': '2.0',
                       'method': 'test_method',
                       'params': [str_len_101]
        },
        [abbrev_str]
    ),

    # item 6
    (
        {
            'id': 1,
            'jsonrpc': '2.0',
                       'method': 'call',
                       'params': ['test_api', 'test_method', [str_len_120]]
        },
        [abbrev_str]
    ),

    # item 7
    (
        {
            'id': 1,
            'jsonrpc': '2.0',
                       'method': 'test_method',
                       'params': [str_len_120]
        },
        [abbrev_str]
    ),

    # item 8
    ({
        'id': 1,
        'jsonrpc': '2.0',
        'method': 'test_method',
        'params': {
            'str': '1',
            'none': None,
            'dict': {},
            'int': 1,
            'list': [],
            'str_len_99': str_len_99,
            'str_len_100': str_len_100,
            'str_len_101': str_len_101,
            'str_len_120': str_len_120,
        }
    },
        {
        'str': '1',
        'none': None,
        'dict': {},
        'int': 1,
        'list': [],
        'str_len_99': str_len_99,
        'str_len_100': str_len_100,
        'str_len_101': abbrev_str,
        'str_len_120': abbrev_str,
    }
    ),

    # item 9
    ({
        'id': 1,
        'jsonrpc': '2.0',
                   'method': 'test_method',
        'params': [
            '1',
            None,
            {},
            1,
            [],
            str_len_99,
            str_len_100,
            str_len_101,
            str_len_120
        ]
    },
        [
        '1',
        None,
        {},
        1,
        [],
        str_len_99,
        str_len_100,
        abbrev_str,
        abbrev_str
    ]
    ),

    # item 10
    ({
        'id': 1,
        'jsonrpc': '2.0',
                   'method': 'test_method',
                   'params': [
                       '1',
                       None,
                       {},
                       1,
                       [],
                       str_len_99,
                       str_len_100,
                       str_len_101,
                       str_len_120
                   ]
    },
        [
        '1',
        None,
        {},
        1,
        [],
        str_len_99,
        str_len_100,
        abbrev_str,
        abbrev_str
    ]
    )
]


@pytest.mark.parametrize("item,expected", ITEMS)
def test_limit_len(item, expected):
    result_params = limit_len(item)
    assert result_params == expected


@pytest.mark.parametrize("jsonrpc_request,expected", REQUESTS)
def test_x_jussi_urn_parts(jsonrpc_request, expected):
    parts = x_jussi_urn_parts(jsonrpc_request)
    assert parts.params == expected


def test_x_jussi_urn_parts_batch():
    jsonrpc_request = [
        {'id': 1, 'jsonrpc': '2.0', 'method': 'test_method', 'params': [str_len_120]},
        {'id': 1, 'jsonrpc': '2.0', 'method': 'test_method',
            'params': [str_len_120]
         }
    ]
    assert x_jussi_urn_parts(jsonrpc_request) == 'batch'
