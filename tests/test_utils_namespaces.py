# -*- coding: utf-8 -*-
import jussi.utils
import pytest


@pytest.mark.parametrize(
    "namspaced_method,expected",
    [("get_block", ('steemd', 'get_block')), ("call", ('steemd', 'call')),
     ("yo.get_block", ('yo', 'get_block')), ('sbds.get_block', ('sbds',
                                                                'get_block')),
     ('sbds.call', ('sbds', 'call')), ('sbds.get_block.get_block',
                                       ('sbds', 'get_block.get_block')),
     ('sbds.steemd.get_block', ('sbds', 'steemd.get_block'))])
def test_parse_namespaced_method(namspaced_method, expected):
    result = jussi.utils.parse_namespaced_method(namspaced_method)
    assert result == expected
