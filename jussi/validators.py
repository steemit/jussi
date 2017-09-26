# -*- coding: utf-8 -*-
import logging

import cytoolz
from funcy.decorators import decorator
from funcy.decorators import Call

from .errors import ServerError
from .typedefs import JsonRpcRequest
from .typedefs import JsonRpcResponse
from .typedefs import SingleJsonRpcRequest
from .typedefs import SingleJsonRpcResponse
from .upstream import method_urn
from .upstream import method_urn_parts

logger = logging.getLogger(__name__)

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


JSONRPC_REQUEST_KEYS = {'id','jsonrpc','method','params'}

@decorator
async def validate_response(call:Call) -> SingleJsonRpcResponse:
    """Return response if valid
    """
    json_response = await call()
    try:
        assert is_valid_non_error_single_jsonrpc_response(json_response)
        if is_get_block_request(call.jsonrpc_request):
            assert is_valid_get_block_response(
                call.jsonrpc_request, json_response)
        return json_response
    except Exception as e:
        raise ServerError(sanic_request=call.sanic_http_request,
                          data={'message': 'Bad or missing server response'},
                          exception=e)


def is_valid_jsonrpc_request(
        jsonrpc_request: JsonRpcRequest=None) -> bool:
    if isinstance(jsonrpc_request, list):
        return all(is_valid_jsonrpc_request(r) for r in jsonrpc_request)
    elif isinstance(jsonrpc_request, dict):
        try:
            assert JSONRPC_REQUEST_KEYS.issuperset(jsonrpc_request.keys())
            assert jsonrpc_request.get('jsonrpc') == '2.0'
            assert isinstance(jsonrpc_request.get('method'), str)
            assert isinstance(jsonrpc_request.get('id', None), (int, str, type(None)))
            return True
        except Exception as e:
            return False
    else:
        return False

def is_valid_single_jsonrpc_response(
        jsonrpc_response: SingleJsonRpcResponse) -> bool:
    return isinstance(jsonrpc_response, dict) and len(jsonrpc_response.keys()) >= 2 and {
        'id', 'jsonrpc', 'result', 'error'}.issuperset(jsonrpc_response.keys())


def is_valid_non_error_single_jsonrpc_response(
        jsonrpc_response: SingleJsonRpcResponse) -> bool:
    return isinstance(jsonrpc_response, dict) and len(jsonrpc_response.keys()) >= 2 and {
        'id', 'jsonrpc', 'result'}.issuperset(jsonrpc_response.keys())


def is_jsonrpc_error_response(jsonrpc_response: SingleJsonRpcResponse) -> bool:
    return isinstance(jsonrpc_response, dict) and len(jsonrpc_response.keys()) >= 2 and {
        'id', 'jsonrpc', 'error'}.issuperset(jsonrpc_response.keys())


def is_valid_jsonrpc_response(jsonrpc_response: JsonRpcResponse) -> bool:
    if isinstance(jsonrpc_response, dict):
        return len(jsonrpc_response.keys()) >= 2 and {
            'id', 'jsonrpc', 'result', 'error'}.issuperset(jsonrpc_response.keys())
    if isinstance(jsonrpc_response, list):
        return all(is_valid_single_jsonrpc_response(r)
                   for r in jsonrpc_response)


def is_valid_non_error_jsonrpc_response(
        jsonrpc_response: JsonRpcResponse) -> bool:
    if isinstance(jsonrpc_response, dict):
        return len(jsonrpc_response.keys()) >= 2 and {
            'id', 'jsonrpc', 'result'}.issuperset(jsonrpc_response.keys())
    if isinstance(jsonrpc_response, list):
        return all(is_valid_non_error_single_jsonrpc_response(r)
                   for r in jsonrpc_response)


def is_get_block_request(jsonrpc_request: SingleJsonRpcRequest=None) -> bool:
    try:
        jussi_jrpc_call = method_urn_parts(jsonrpc_request)
        return jussi_jrpc_call.method == 'get_block'
    except Exception as e:
        logger.debug(f'is_get_block_request errored: {e}')
        return False


def is_get_block_header_request(
        jsonrpc_request: SingleJsonRpcRequest=None) -> bool:
    try:
        jussi_jrpc_call = method_urn_parts(jsonrpc_request)
        return jussi_jrpc_call.method == 'get_block_header'
    except Exception as e:
        logger.debug(f'is_get_block_request errored: {e}')
        return False


def is_valid_get_block_response(
        jsonrpc_request: SingleJsonRpcRequest,
        response: SingleJsonRpcResponse) -> bool:
    if not isinstance(response, dict):
        return False
    if not {'id', 'jsonrpc', 'result'}.issuperset(response.keys()):
        return False
    try:
        request_block_num = block_num_from_jsonrpc_request(jsonrpc_request)
        response_block_num = block_num_from_id(response['result']['block_id'])
        assert int(request_block_num) == response_block_num
        return True
    except KeyError as e:
        logger.error(f'is_valid_get_block_response key error:{e}')
        return False
    except AssertionError:
        logger.error(f'{request_block_num} != {response_block_num}')
        return False
    except Exception as e:
        logger.error(f'is_valid_get_block_response error :{e}')
        return False


def block_num_from_jsonrpc_response(
        jsonrpc_response: SingleJsonRpcResponse=None) -> int:
    # pylint: disable=no-member
    # for get_block
    block_id = cytoolz.get_in(['result', 'block_id'], jsonrpc_response)
    if block_id:
        return block_num_from_id(block_id)

    # for get_block_header
    previous = cytoolz.get_in(['result', 'previous'], jsonrpc_response)
    return block_num_from_id(previous) + 1


def block_num_from_jsonrpc_request(
        jsonrpc_request: SingleJsonRpcRequest=None) -> int:
    # pylint: disable=no-member
    request_block_num = cytoolz.get_in(['params', -1, 0], jsonrpc_request)
    if not request_block_num:
        request_block_num = cytoolz.get_in(['params', -1], jsonrpc_request)
    return request_block_num


def block_num_from_id(block_hash: str) -> int:
    """return the first 4 bytes (8 hex digits) of the block ID (the block_num)
    """
    return int(str(block_hash)[:8], base=16)


def jsonrpc_cache_key(single_jsonrpc_request: SingleJsonRpcRequest) -> str:
    return method_urn(single_jsonrpc_request)
