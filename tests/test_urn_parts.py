# -*- coding: utf-8 -*-
from collections import OrderedDict

import pytest
from jussi.upstream.urn import x_jussi_urn_parts

str_len_120 = ''.join('a' for i in range(120))
str_len_99 = ''.join('a' for i in range(99))
str_len_100 = ''.join('a' for i in range(100))
str_len_101 = ''.join('a' for i in range(101))
abbrev_str = ''.join([str_len_100, '...'])


@pytest.mark.parametrize(
    "jsonrpc_request,expected",
    [
        (
            {'id': 1,
             'jsonrpc': '2.0',
             'method': 'call',
             'params': ['test_api', 'test_method', [str_len_99]]
             },
            [str_len_99]
        ),
        (
            {
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'test_method',
                'params': [str_len_99]
            },
            [str_len_99]
        ),
        (
            {'id': 1,
             'jsonrpc': '2.0',
             'method': 'call',
             'params': ['test_api', 'test_method', [str_len_100]]
             },
            [str_len_100]
        ),
        (
            {
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'test_method',
                'params': [str_len_100]
            },
            [str_len_100]
        ),
        (
            {
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'call',
                'params': ['test_api', 'test_method', [str_len_101]]
            },
            [abbrev_str]
        ),
        (
            {
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'test_method',
                'params': [str_len_101]
            },
            [abbrev_str]
        ),
        (
            {
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'call',
                'params': ['test_api', 'test_method', [str_len_120]]
            },
            [abbrev_str]
        ),
        (
            {
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'test_method',
                'params': [str_len_120]
            },
            [abbrev_str]
        ),



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
            'str_len_101': str_len_101,
            'str_len_120': str_len_120,
        }
        ),

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
    ],
    ids=lambda v: v['method'])
def test_urn_parts(jsonrpc_request, expected):
    parts = x_jussi_urn_parts(jsonrpc_request)
    assert parts.params == expected
