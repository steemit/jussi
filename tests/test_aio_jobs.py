# -*- coding: utf-8 -*-
import asyncio

import pytest


@pytest.mark.test_app
def test_aio_job_scheduled(app_with_wait):
    app = app_with_wait

    async def wait_middleware(request):
        request.app.config.logger.debug('wait middlware start')
        await asyncio.sleep(2)
        request.app.config.logger.debug('wait middlware finish')

    app.request_middleware.insert(0, wait_middleware)

    assert 'last_irreversible_block_num' not in app.config
    _, _ = app.test_client.get('/health')
    assert app.config.last_irreversible_block_num > 10000000


def test_aio_job_caching(app_with_wait):
    app = app_with_wait

    async def wait_middleware(request):
        request.app.config.logger.debug('wait middlware start')
        await asyncio.sleep(1)
        request.app.config.logger.debug('wait middlware finish')

    app.request_middleware.insert(0, wait_middleware)
    assert 'last_irreversible_block_num' not in app.config
    while True:
        print(f'app.config.last_irreversible_block_num not initialized')
        try:
            if app.config.last_irreversible_block_num > 0:
                break
        # pylint: disable=bare-except
        except:
            _, _ = app.test_client.get('/health')

    _, response = app.test_client.post(
        '/',
        json={
            "id": 4,
            "jsonrpc": "2.0",
            "method": "get_dynamic_global_properties"
        })
    assert response.headers[
        'x-jussi-cache-hit'] == 'steemd.database_api.get_dynamic_global_properties'

    assert response.json['id'] == 4
