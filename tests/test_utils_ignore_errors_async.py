# -*- coding: utf-8 -*-

import pytest
from jussi.utils import ignore_errors_async


# pylint: disable=unused-argument
async def test_correct_result_async():

    @ignore_errors_async
    async def func1(a, b=2, c=None):
        return (a, b, c)

    a, b, c = await func1(1, c=3)
    assert a == 1
    assert b == 2
    assert c == 3


async def test_errors_ignored_async():
    with pytest.raises(Exception):

        async def func2(a, b=2, c=None):
            raise Exception('i should be ignored')

        await func2(1, c=3)

    @ignore_errors_async
    async def func3(a, b=2, c=None):
        raise Exception('i should be ignored')

    await func3(1, c=3)
