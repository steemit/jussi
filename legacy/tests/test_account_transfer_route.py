# -*- coding: utf-8 -*-
import pytest

from jussi.upstream import ACCOUNT_TRANSFER_PATTERN


NON_MATCH_PATTERNS = [
    (''),
    ('/'),
    ('/@'),
    ('@'),

    ('/@/'),
    ('@/'),

    ('/@ /transfer'),
    ('@ /transfer'),

    ('/@account/transfer'),
    ('@account/transfer'),

    ('/@account/path/transfers'),
    ('@account/path/transfers'),

    ('/@account//transfers'),
    ('@account//transfers'),

    ('/@account/transfers/'),
    ('@account/transfers/'),

    ('/@account /transfers'),
    ('@account /transfers'),

    ('/@account/ transfers'),
    ('@account/ transfers'),

]


@pytest.mark.parametrize('string', [
    ('/@account/transfers'),
    ('@account/transfers'),

])
def test_account_transfer_regex_matches(string):
    assert ACCOUNT_TRANSFER_PATTERN.match(string) is not None


@pytest.mark.parametrize('string', NON_MATCH_PATTERNS)
def test_account_transfer_regex_non_matches(string):
    assert ACCOUNT_TRANSFER_PATTERN.match(string) is None
