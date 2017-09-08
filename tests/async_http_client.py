# -*- coding: utf-8 -*-
# pylint: skip-file
import asyncio
import logging
import os
import time
import zlib
from collections import deque
from itertools import islice

import aiohttp
import ujson
from funcy.colls import get_in

import uvloop
from progress.bar import Bar

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CORRECT_BATCH_TEST_RESPONSE='''
[{"id":1,"result":{"previous":"000000b0c668dad57f55172da54899754aeba74b","timestamp":"2016-03-24T16:14:21","witness":"initminer","transaction_merkle_root":"0000000000000000000000000000000000000000","extensions":[],"witness_signature":"2036fd4ff7838ba32d6d27637576e1b1e82fd2858ac97e6e65b7451275218cbd2b64411b0a5d74edbde790c17ef704b8ce5d9de268cb43783b499284c77f7d9f5e","transactions":[],"block_id":"000000b13707dfaad7c2452294d4cfa7c2098db4","signing_key":"STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX","transaction_ids":[]}},{"id":2,"result":{"previous":"000000b0c668dad57f55172da54899754aeba74b","timestamp":"2016-03-24T16:14:21","witness":"initminer","transaction_merkle_root":"0000000000000000000000000000000000000000","extensions":[],"witness_signature":"2036fd4ff7838ba32d6d27637576e1b1e82fd2858ac97e6e65b7451275218cbd2b64411b0a5d74edbde790c17ef704b8ce5d9de268cb43783b499284c77f7d9f5e","transactions":[],"block_id":"000000b13707dfaad7c2452294d4cfa7c2098db4","signing_key":"STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX","transaction_ids":[]}}]
'''
NO_BATCH_SUPPORT_RESPONSE = '7 bad_cast_exception: Bad Cast'

class RateBar(Bar):
    suffix = '%(index)d (%(rate)d/sec) time remaining: %(eta_td)s'

    @property
    def rate(self):
        if not self.elapsed:
            return 0
        return self.index/elapsed

def chunkify(iterable, chunksize=3000):
    i = 0
    chunk = []
    for item in iterable:
        chunk.append(item)
        i += 1
        if i == chunksize:
            yield chunk
            i = 0
            chunk = []
    if chunk:
        yield chunk


class SimpleSteemAPIClient(object):
    def __init__(self, *, url=None, **kwargs):
        self.url = url or os.environ.get('STEEMD_HTTP_URL', 'https://steemd.steemitdev.com')
        self.kwargs = kwargs
        self.session = kwargs.get('session', None)
        self.connector = get_in(kwargs, ['session','connector'])

        if not self.connector:
            self.connector = self._new_connector()
        if not self.session:
            self.session = self._new_session()

        self._batch_request_size = self.kwargs.get('batch_request_size', 150)
        self._concurrent_tasks_limit = self.kwargs.get('concurrent_tasks_limit', 10)

        self._perf_history = deque(maxlen=2000)
        self._batch_request_count = 0
        self._request_count = 0


    def _new_connector(self, connector_kwargs=None):
        connector_kwargs = connector_kwargs or self._connector_kwargs
        return aiohttp.TCPConnector(**connector_kwargs)

    def _new_session(self, session_kwargs=None):
        session_kwargs = session_kwargs or self._session_kwargs
        return aiohttp.ClientSession(**session_kwargs)

    async def fetch(self,request_data):
        if isinstance(request_data, list):
            self._batch_request_count += 1
            self._request_count += len(request_data)
        async with self.session.post(self.url, json=request_data, compress='gzip') as response:
            try:
                response_data = await response.json()
            except Exception as e:
                logger.error(e)
                logger.error(await response.text())
                return
        return response_data

    async def get_blocks(self, block_nums):
        requests = ({'jsonrpc':'2.0','id':block_num,'method':'get_block','params':[block_num]} for _id,block_num in enumerate(block_nums))
        batched_requests = chunkify(requests, self.batch_request_size)
        coros = (self.fetch(batch) for batch in batched_requests)
        first_coros = islice(coros,0,self.concurrent_tasks_limit)
        futures = [asyncio.ensure_future(c) for c in first_coros]

        logger.debug(f'inital futures:{len(futures)}')
        start = time.perf_counter()

        while futures:
            await asyncio.sleep(0)
            for f in futures:
                try:
                    if f.done():
                        self._perf_history.append(time.perf_counter() - start)
                        result = f.result()
                        futures.remove(f)
                        logger.debug(f'futures:{len(futures)}')
                        try:
                            futures.append(asyncio.ensure_future(next(coros)))
                        except StopIteration as e:
                            logger.debug('StopIteration')
                        start = time.perf_counter()
                        yield result
                except Exception as e:
                    logger.error(e)


    async def test_batch_support(self, url):
        batch_request = [{"id":1,"jsonrpc":"2.0","method":"get_block","params":[1]},{"id":2,"jsonrpc":"2.0","method":"get_block","params":[1]}]
        try:
            async with self.session.post(self.url, json=batch_request) as response:
                response_data = await response.text()
            if response_data.startswith(NO_BATCH_SUPPORT_RESPONSE):
                return False
            return ujson.loads(response_data) == CORRECT_BATCH_TEST_RESPONSE
        except Exception as e:
            logger.error(e)
        return False

    @property
    def _session_kwargs(self):
        session_kwargs = self.kwargs.get('session_kwargs', {})
        session_kwargs['skip_auto_headers'] = session_kwargs.get('skip_auto_headers', ['User-Agent'])
        session_kwargs['json_serialize'] = session_kwargs.get('json_serialize', ujson.dumps)
        session_kwargs['headers'] = session_kwargs.get('headers', {'Content-Type': 'application/json'})
        session_kwargs['connector'] = session_kwargs.get('connector', None)
        return session_kwargs

    @property
    def _connector_kwargs(self):
        connector_kwargs = self.kwargs.get('connector_kwargs', {})
        connector_kwargs['keepalive_timeout'] = connector_kwargs.get('keepalive_timeout', 60)
        connector_kwargs['limit'] = connector_kwargs.get('limit', 100)
        return connector_kwargs

    @property
    def concurrent_connections(self):
        """number of tcp connections to steemd"""
        return self.connector.limit

    @property
    def batch_request_size(self):
        """number of individual jsonrpc requests to combine into a jsonrpc batch request"""
        return self._batch_request_size

    @property
    def concurrent_tasks_limit(self):
        """number of jsonrpc batch requests tasks to submit to event loop at any one time"""
        return self._concurrent_tasks_limit


    def close(self):
        self.session.close()
        for task in asyncio.Task.all_tasks():
            task.cancel()

if __name__ == '__main__':
    import argparse
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('async_http_client_main')
    parser = argparse.ArgumentParser('jussi perf test script')
    parser.add_argument('--blocks', type=int, default=20000)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--url', type=str, default='https://api.steemitdev.com')
    parser.add_argument('--batch_request_size', type=int, default=1000)
    parser.add_argument('--concurrent_tasks_limit', type=int, default=5)
    parser.add_argument('--concurrent_connections', type=int, default=0)
    parser.add_argument('--print', type=bool, default=False)
    args = parser.parse_args()
    block_nums = list(range(args.offset, args.blocks))
    loop = asyncio.get_event_loop()
    loop.set_debug(True)


    def verify_response(response):
        try:
            assert 'result' in response
            assert 'error' not in response
            return True
        except Exception as e:
            print(f'error:{e} response:{response}')
        return False

    def verify(response):
        if isinstance(response, list):
            return all(verify_response(r) for r in response)
        else:
            return verify_response(response)

    async def run(block_nums, url=None, batch_request_size=None, concurrent_tasks_limit=None, concurrent_connections=None):
        client = SimpleSteemAPIClient(url=url,
                                      batch_request_size=batch_request_size,
                                      concurrent_tasks_limit=concurrent_tasks_limit,
                                      connector_kwargs={'limit':concurrent_connections})
        logger.debug(f'blocks:{len(block_nums)} {client.batch_request_size} concurrent_tasks_limit:{client.concurrent_tasks_limit} concurrent_connections:{client.concurrent_connections}')
        responses = []
        start = time.perf_counter()

        bar = RateBar('Fetching blocks', max=len(block_nums))
        try:
            start = time.perf_counter()
            async for result in client.get_blocks(block_nums):
                if result:
                    bar.next(n=len(result))
                    verify(result)


        except Exception as e:
            logger.error(e)
        finally:
            bar.finish()
            elapsed = time.perf_counter() - start
            client.close()

        return client, responses, elapsed

    try:
        client, responses, elapsed = loop.run_until_complete(run(block_nums,
                                                url=args.url,
                                                batch_request_size=args.batch_request_size,
                                                concurrent_tasks_limit=args.concurrent_tasks_limit,
                                                concurrent_connections=args.concurrent_connections))
    finally:
        pass
        #loop.run_until_complete(loop.shutdown_asyncgens())
        #loop.close()

    history = client._perf_history
    request_count = client._request_count
    total_time = elapsed
    total_time_sequential = sum(client._perf_history)
    total_get_block_requests = client._request_count
    total_batch_requests = client._batch_request_count

    get_block_time = total_time/total_get_block_requests
    batch_request_time = total_time/total_batch_requests

    hours_to_sync = (14000000 * get_block_time)/360
    hours_to_sync2 = ((14000000/args.batch_request_size) * batch_request_time)/360

    concurrency = 1/(total_time / total_time_sequential)

    def verify_response(response):
        try:
            assert 'result' in response
            assert 'error' not in response
            return True
        except Exception as e:
            print(f'error:{e} response:{response}')
        return False

    print()
    #print(responses[0])
    #_ids = set([r['id'] for r in responses])
    #block_nums = set(block_nums)
    #print(block_nums - _ids)


    print()
    print(f'batch request_size:\t\t{client.batch_request_size}')
    print(f'concurrent_tasks_limit:\t\t{client.concurrent_tasks_limit}')
    print(f'concurrent_connections:\t\t{client.concurrent_connections}')
    print()
    print(f'total time:\t\t\t{total_time}')
    print(f'total time sequential:\t\t{total_time_sequential}')
    print(f'concurrency:\t\t\t{concurrency}')
    print(f'total get_block requests:\t{total_get_block_requests}')
    print(f'total get_block responses:\t{len(responses)}')
    print(f'total batch_requests:\t\t{total_batch_requests}')
    print(f'get_block requests/s:\t\t{total_get_block_requests/total_time}')
    print(f'batch requests/s:\t\t{total_batch_requests/total_time}')
    print(f'avg get_block request time:\t{total_time/total_get_block_requests}')
    print(f'avg batch request time:\t\t{total_time/total_batch_requests}')
    print(f'est. hours to sync: \t\t{hours_to_sync}')
    print(f'est. hours to sync2: \t\t{hours_to_sync2}')
