# -*- coding: utf-8 -*-
import itertools as it
from typing import NoReturn

import structlog

from jussi.request.jsonrpc import JSONRPCRequest

#from .errors import InvalidRequest
from .errors import JussiCustomJsonOpLengthError
from .errors import JussiLimitsError
from .typedefs import JrpcRequest
from .typedefs import JrpcResponse
from .typedefs import RawRequest
from .typedefs import SingleJrpcResponse

logger = structlog.get_logger(__name__)

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

JSONRPC_REQUEST_KEYS = {'id', 'jsonrpc', 'method', 'params'}
JSONRPC_RESPONSE_KEYS = {'id', 'jsonrpc', 'result', 'error'}

NONE_TYPE = type(None)
ID_TYPES = (int, str, float, NONE_TYPE)
PARAMS_TYPES = (list, dict, NONE_TYPE)

CUSTOM_JSON_SIZE_LIMIT = 8192
CUSTOM_JSON_FOLLOW_RATE = 2

BROADCAST_TRANSACTION_METHODS = {
    'broadcast_transaction',
    'broadcast_transaction_synchronous'
}


#
# validate_* methods raise on invalid input
#


def validate_jsonrpc_request(request: RawRequest) -> NoReturn:
    from .errors import InvalidRequest
    if isinstance(request, dict):
        assert JSONRPC_REQUEST_KEYS.issuperset(request.keys()) and \
            request['jsonrpc'] == '2.0' and \
            isinstance(request['method'], str) and \
            isinstance(request.get('id', None), ID_TYPES) and \
            isinstance(request.get('params', None), (list, dict, type(None)))
    elif isinstance(request, list) and request:
        for r in request:
            assert JSONRPC_REQUEST_KEYS.issuperset(r.keys()) and \
                r['jsonrpc'] == '2.0' and \
                isinstance(r['method'], str) and \
                isinstance(r.get('id'), ID_TYPES) and \
                isinstance(r.get('params'), PARAMS_TYPES)
    elif isinstance(request, JSONRPCRequest):
        pass  # already be validated
    else:
        raise InvalidRequest(request=request)


#
# is_valid_* methods return True or False, but they don't raise
#


def is_valid_single_jsonrpc_response(response: SingleJrpcResponse) -> bool:
    # response.get('jsonrpc')  == '2.0' and \
    return isinstance(response, dict) and \
        (bool('result' in response) ^ bool('error' in response)) and \
        {'id', 'jsonrpc', 'result', 'error'}.issuperset(response.keys())


def is_valid_non_error_single_jsonrpc_response(response: SingleJrpcResponse) -> bool:
    # response.get('jsonrpc') == '2.0' and
    return isinstance(response, dict) and \
        'result' in response and \
        {'id', 'jsonrpc', 'result'}.issuperset(response.keys())


def is_valid_non_error_jussi_response(
        request: JrpcRequest,
        response: JrpcResponse) -> bool:
    try:
        if isinstance(request, JSONRPCRequest):
            if not is_valid_non_error_single_jsonrpc_response(response):
                return False
            if is_get_block_request(request):
                return is_valid_get_block_response(request, response)
            return True
        if isinstance(request, list):
            return len(response) > 0 and \
                isinstance(response, list) and \
                len(request) == len(response) and \
                all(is_valid_non_error_jussi_response(req, resp)
                    for req, resp in zip(request, response))
        return False
    except Exception as e:
        logger.error('is_valid_non_error_jussi_response error', e=e,
                     jid=request.jussi_request_id)
    return False


def is_get_block_request(request: JSONRPCRequest) -> bool:
    return request.urn.namespace in ('steemd', 'appbase') and request.urn.method == 'get_block'


def is_get_block_header_request(request: JSONRPCRequest) -> bool:
    return request.urn.namespace in (
        'steemd', 'appbase') and request.urn.method == 'get_block_header'


def is_get_dynamic_global_properties_request(request: JSONRPCRequest) -> bool:
    return request.urn.namespace in (
        'steemd', 'appbase') and request.urn.method == 'get_dynamic_global_properties'


def is_valid_get_block_response(
        request: JSONRPCRequest,
        response: SingleJrpcResponse) -> bool:
    if not is_get_block_request(request) and \
            is_valid_non_error_single_jsonrpc_response(response):
        return False
    request_block_num, response_block_num = 'nope', 'nope'
    try:
        params = request.urn.params
        if isinstance(params, list):
            request_block_num = params[0]
        elif isinstance(params, dict):
            request_block_num = params['block_num']
        else:
            raise ValueError(f'bad urn params from {request}: {params} ')

        if 'result' not in response:
            raise Exception('jsonrpc response did not contain result')
        elif response['result'] is None:
            return False  # block does not exist yet

        if 'block_id' in response['result']:
            block_id = response['result']['block_id']
        elif 'block' in response['result']:
            block_id = response['result']['block']['block_id']
        else:
            return False
        response_block_num = block_num_from_id(block_id)
        assert int(request_block_num) == response_block_num
        return True
    except KeyError as e:
        logger.error('is_valid_get_block_response key error',
                     e=e,
                     jid=request.jussi_request_id,
                     response=response)
    except AssertionError:
        logger.error('request_block != response block_num',
                     jid=request.jussi_request_id,
                     request_block_num=request_block_num,
                     response_block_num=response_block_num)
    except Exception as e:
        logger.error('is_valid_get_block_response error', e=e,
                     jid=request.jussi_request_id, )
    return False


def is_broadcast_transaction_request(request: JSONRPCRequest) -> bool:
    return request.urn.method in BROADCAST_TRANSACTION_METHODS


def limit_broadcast_transaction_request(request: JSONRPCRequest, limits=None) -> NoReturn:
    if is_broadcast_transaction_request(request):
        if isinstance(request.urn.params, list):
            request_params = request.urn.params[0]
        elif isinstance(request.urn.params, dict):
            request_params = request.urn.params['trx']
        else:
            raise ValueError(
                f'Unknown request params type: {type(request.urn.params)} urn:{request.urn}')
        ops = [op for op in request_params['operations'] if op[0] == 'custom_json']
        if not ops:
            return
        blacklist_accounts = set()
        try:
            blacklist_accounts = limits['accounts_blacklist']
        except Exception as e:
            logger.warning('using empty accounts_blacklist', e=e,
                           jid=request.jussi_request_id, )

        limit_custom_json_op_length(ops, size_limit=CUSTOM_JSON_SIZE_LIMIT)
        limit_custom_json_account(ops, blacklist_accounts=blacklist_accounts)


def limit_custom_json_op_length(ops: list, size_limit=None):
    if any(len(op[1]['json'].encode('utf-8')) > size_limit for op in ops):
        raise JussiCustomJsonOpLengthError(size_limit=size_limit)


def limit_custom_json_account(ops: list, blacklist_accounts=None):
    accts = set(
        it.chain.from_iterable(op[1]["required_posting_auths"] for op in ops))
    if not accts.isdisjoint(blacklist_accounts):
        raise JussiLimitsError()


def block_num_from_id(block_hash: str) -> int:
    """return the first 4 bytes (8 hex digits) of the block ID (the block_num)
    """
    return int(str(block_hash)[:8], base=16)


def jsonrpc_cache_key(request: JSONRPCRequest) -> str:
    return str(request.urn)
