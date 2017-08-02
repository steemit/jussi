# -*- coding: utf-8 -*-
import asyncio


'''
@pytest.mark.test_app
def test_aio_job_scheduled(app_with_wait):
    app = app_with_wait
    #app.config.args.server_port = 42101

    _, _ = app.test_client.get('/wait/1')
    _, _ = app.test_client.get('/wait/1')
    _, _ = app.test_client.get('/wait/1')
    assert app.config.last_irreversible_block_num > 10000000
'''

def test_aio_job_caching(loop, app_with_wait):

    app = app_with_wait

    async def wait_middleware(request):
        request.app.config.logger.debug('wait middlware start')
        await asyncio.sleep(.3)
        request.app.config.logger.debug('wait middlware finish')

    app.request_middleware.insert(0, wait_middleware)

    _, response = app.test_client.post(
        '/',
        json={
            "id": 4,
            "jsonrpc": "2.0",
            "method": "get_dynamic_global_properties"
        })
    assert response.headers[
        'x-jussi-cache-hit'] == 'steemd.database_api.get_dynamic_global_properties'
    response_json = loop.run_until_complete(response.json())
    assert response_json['id'] == 4
