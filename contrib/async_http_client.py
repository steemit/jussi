# -*- coding: utf-8 -*-
# pylint: skip-file
import asyncio
import concurrent.futures
import logging
import time
import ujson
from itertools import islice

import aiohttp
import uvloop
import os
from collections import deque
from funcy.colls import get_in
from progress.bar import Bar

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.get_event_loop()
loop.set_debug(True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CORRECT_BATCH_TEST_RESPONSE = [
    {
        "id": 1, "result": {
            "previous": "000000b0c668dad57f55172da54899754aeba74b",
            "timestamp": "2016-03-24T16:14:21",
            "witness": "initminer",
            "transaction_merkle_root": "0000000000000000000000000000000000000000",
            "extensions": [],
            "witness_signature": "2036fd4ff7838ba32d6d27637576e1b1e82fd2858ac97e6e65b7451275218cbd2b64411b0a5d74edbde790c17ef704b8ce5d9de268cb43783b499284c77f7d9f5e",
            "transactions": [],
            "block_id": "000000b13707dfaad7c2452294d4cfa7c2098db4",
            "signing_key": "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
            "transaction_ids": []
        }
    },
    {
        "id": 2, "result": {
            "previous": "000000b0c668dad57f55172da54899754aeba74b",
            "timestamp": "2016-03-24T16:14:21",
            "witness": "initminer",
            "transaction_merkle_root": "0000000000000000000000000000000000000000",
            "extensions": [],
            "witness_signature": "2036fd4ff7838ba32d6d27637576e1b1e82fd2858ac97e6e65b7451275218cbd2b64411b0a5d74edbde790c17ef704b8ce5d9de268cb43783b499284c77f7d9f5e",
            "transactions": [],
            "block_id": "000000b13707dfaad7c2452294d4cfa7c2098db4",
            "signing_key": "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
            "transaction_ids": []
        }
    }
]

NO_BATCH_SUPPORT_RESPONSE = '7 bad_cast_exception: Bad Cast'

GET_BLOCK_RESULT_KEYS = {"previous",
                         "timestamp",
                         "witness",
                         "transaction_merkle_root",
                         "extensions",
                         "witness_signature",
                         "transactions",
                         "block_id",
                         "signing_key",
                         "transaction_ids"}


class RateBar(Bar):
    suffix = '%(index)d (%(rate)d/sec) time remaining: %(eta_td)s'
    sma_window = 10000

    @property
    def rate(self):
        if not self.elapsed:
            return 0
        return self.index / self.elapsed


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


class AsyncClient(object):
    def __init__(self, *, url=None, **kwargs):
        self.url = url or os.environ.get(
            'STEEMD_HTTP_URL', 'https://steemd.steemitdev.com')
        self.kwargs = kwargs
        self.session = kwargs.get('session', None)
        self.connector = get_in(kwargs, ['session', 'connector'])

        if not self.connector:
            self.connector = self._new_connector()
        if not self.session:
            self.session = self._new_session()

        self._batch_request_size = self.kwargs.get('batch_request_size', 150)
        self._concurrent_tasks_limit = self.kwargs.get(
            'concurrent_tasks_limit', 10)

        self.verify_responses = kwargs.get('verify_responses', False)

        self._perf_history = deque(maxlen=2000)
        self._batch_request_count = 0
        self._request_count = 0

    def _new_connector(self, connector_kwargs=None):
        connector_kwargs = connector_kwargs or self._connector_kwargs
        return aiohttp.TCPConnector(**connector_kwargs)

    def _new_session(self, session_kwargs=None):
        session_kwargs = session_kwargs or self._session_kwargs
        return aiohttp.ClientSession(**session_kwargs)

    async def fetch(self, request_data):
        if isinstance(request_data, list):
            self._batch_request_count += 1
            self._request_count += len(request_data)
        attempts = 0
        while attempts < 5:
            try:
                async with self.session.post(self.url, json=request_data, compress='gzip') as response:
                    attempts += 1
                    response_data = await response.json()
                    verify(response, response_data, _raise=True)
                    return response_data
            except aiohttp.client_exceptions.ServerDisconnectedError:
                self.session = self._new_session()
            except RuntimeError:
                self.close()
                raise KeyboardInterrupt
            except concurrent.futures._base.CancelledError:
                raise KeyboardInterrupt
            except Exception as e:
                logger.exception(e)
                raise e

    async def get_blocks(self, block_nums):
        requests = (
            {
                'jsonrpc': '2.0', 'id': block_num, 'method': 'get_block',
                'params': [block_num]
            } for block_num in block_nums)
        batched_requests = chunkify(requests, self.batch_request_size)
        coros = (self.fetch(batch) for batch in batched_requests)
        first_coros = islice(coros, 0, self.concurrent_tasks_limit)
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
                        except concurrent.futures._base.CancelledError:
                            return
                        start = time.perf_counter()
                        yield result
                except KeyboardInterrupt:
                    logger.debug('client.get blocks kbi')
                    for f in futures:
                        f.cancel()
                    self.close()
                    return
                except Exception as e:
                    logger.exception(f'client.get_blocks error:{e}')
                    continue

    async def test_batch_support(self, url):
        batch_request = [{
            "id": 1, "jsonrpc": "2.0",
            "method": "get_block", "params": [
                1]
        }, {
            "id": 2, "jsonrpc": "2.0",
            "method": "get_block", "params": [1]
        }]
        try:
            async with self.session.post(self.url,
                                         json=batch_request) as response:
                response_data = await response.text()
            if response_data.startswith(NO_BATCH_SUPPORT_RESPONSE):
                return False
            response_json = ujson.loads(response_data)
            print(ujson.dumps(response_json))
            assert len(response_json) == 2
            assert isinstance(response_json, list)
            for i, result in enumerate(response_json):
                print(result)
                print(CORRECT_BATCH_TEST_RESPONSE[i])
                assert result == CORRECT_BATCH_TEST_RESPONSE[i]
        except Exception as e:
            logger.exception(e)
        return False

    @property
    def _session_kwargs(self):
        session_kwargs = self.kwargs.get('session_kwargs', {})
        session_kwargs['skip_auto_headers'] = session_kwargs.get(
            'skip_auto_headers', ['User-Agent'])
        session_kwargs['json_serialize'] = session_kwargs.get(
            'json_serialize', ujson.dumps)
        session_kwargs['headers'] = session_kwargs.get(
            'headers', {'Content-Type': 'application/json'})
        session_kwargs['connector'] = session_kwargs.get('connector', None)
        return session_kwargs

    @property
    def _connector_kwargs(self):
        connector_kwargs = self.kwargs.get('connector_kwargs', {})
        connector_kwargs['keepalive_timeout'] = connector_kwargs.get(
            'keepalive_timeout', 60)
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
        logger.debug('client.close')
        self.session.close()
        for task in asyncio.Task.all_tasks():
            task.cancel()


def block_num_from_id(block_hash: str) -> int:
    """return the first 4 bytes (8 hex digits) of the block ID (the block_num)
    """
    return int(str(block_hash)[:8], base=16)


def verify_get_block_response(response, response_data, _raise=False):
    try:
        response_id = response_data['id']
        block_num = block_num_from_id(response_data['result']['block_id'])
        response_keys = set(response_data['result'].keys())
        assert response_id == block_num
        assert response_keys == GET_BLOCK_RESULT_KEYS
        return True
    except KeyError as e:
        # logger.error(response.headers)
        logger.error(f'response:{response_data["result"].keys()}')
        if _raise:
            raise e
    except AssertionError as e:
        logger.error(f'{response_id} {block_num}')
        # logger.error(response.headers)
        # logger.exception(f'response:{response_keys}')
        if _raise:
            raise e
    return False


def verify(response, response_data, _raise=True):
    if isinstance(response_data, list):

        for i, data in enumerate(response_data):
            verify_get_block_response(
                response, data, _raise=_raise)
    else:
        verify_get_block_response(response, response_data, _raise=_raise)


async def get_blocks(args):
    block_nums = range(args.start_block, args.end_block)
    url = args.url
    batch_request_size = args.batch_request_size
    concurrent_tasks_limit = args.concurrent_tasks_limit
    concurrent_connections = args.concurrent_connections

    client = AsyncClient(url=url,
                         batch_request_size=batch_request_size,
                         concurrent_tasks_limit=concurrent_tasks_limit,
                         connector_kwargs={'limit': concurrent_connections})

    bar = RateBar('Fetching blocks', max=len(block_nums))

    try:
        async for result in client.get_blocks(block_nums):
            if result:
                bar.next(n=len(result))
                print(result)
            else:
                logger.error('encountered missing result')
    except KeyboardInterrupt:
        logger.debug('get_blocks kbi')
        client.close()
        raise
    except Exception as e:
        client.close()
        logger.error(f'get_blocks error:{e}')
        raise e
    finally:
        bar.finish()


if __name__ == '__main__':
    import sys
    import argparse

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('async_http_client_main')

    parser = argparse.ArgumentParser('jussi client')

    subparsers = parser.add_subparsers()

    parser.add_argument('--url', type=str,
                        default='https://api.steemitdev.com')
    parser.add_argument('--start_block', type=int, default=1)
    parser.add_argument('--end_block', type=int, default=16_000_000)
    parser.add_argument('--batch_request_size', type=int, default=100)
    parser.add_argument('--concurrent_tasks_limit', type=int, default=5)
    parser.add_argument('--concurrent_connections', type=int, default=5)
    parser.add_argument('--print', type=bool, default=False)

    parser_get_blocks = subparsers.add_parser('get-blocks')
    parser_get_blocks.set_defaults(func=get_blocks)

    args = parser.parse_args()
    func = getattr(args, 'func', None)
    if not func:
        parser.print_help()
        sys.exit()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(args.func(args))
    except KeyboardInterrupt:
        logger.debug('main kbi')
    finally:
        for task in asyncio.Task.all_tasks():
            task.cancel()
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(loop.shutdown_asyncgens())
