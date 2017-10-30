# -*- coding: utf-8 -*-
import logging

from funcy.decorators import Call
from funcy.decorators import decorator

from .errors import ServerError
from .typedefs import JsonRpcRequest
from .typedefs import JsonRpcResponse
from .typedefs import SingleJsonRpcRequest
from .typedefs import SingleJsonRpcResponse
from .upstream.urn import urn
from .upstream.urn import urn_parts

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

JSONRPC_REQUEST_KEYS = {'id', 'jsonrpc', 'method', 'params'}


@decorator
async def validate_response_decorator(call: Call) -> SingleJsonRpcResponse:
    """Return response if valid
    """
    json_response = await call()
    try:
        if is_get_block_request(call.jsonrpc_request):
            assert is_valid_get_block_response(
                call.jsonrpc_request, json_response)
        return json_response
    except AssertionError as e:
        raise ServerError(sanic_request=call.sanic_http_request,
                          data={
                              'message': 'Bad or missing upstream response',
                              'upstream_response': json_response
                          },
                          exception=e)


#
# validate_* methods raise on invalid input
#


def validate_jsonrpc_request(jsonrpc_request: JsonRpcRequest) -> None:
    if isinstance(jsonrpc_request, list):
        # pylint: disable=expression-not-assigned
        [validate_jsonrpc_request(r) for r in jsonrpc_request]
        # pylint: enable=expression-not-assigned
    elif isinstance(jsonrpc_request, dict):
        assert JSONRPC_REQUEST_KEYS.issuperset(jsonrpc_request.keys())
        assert len(jsonrpc_request.keys()) >= 2
        assert jsonrpc_request.get('jsonrpc') == '2.0', 'bad jsonrpc version'
        assert isinstance(jsonrpc_request.get('method'), str), ''
        assert isinstance(jsonrpc_request.get('id'),
                          (int, str, float, type(None))), 'bad jsonrpc id'
        assert isinstance(jsonrpc_request.get('params'),
                          (list, dict, type(None))), 'bad jsonrpc params'
    else:
        raise TypeError('Bad JSONRPC Request Type')


def validate_jussi_response(jsonrpc_request: JsonRpcRequest,
                            jsonrpc_response: JsonRpcResponse) -> None:
    if isinstance(jsonrpc_request, list):
        assert isinstance(jsonrpc_response, list)
        assert len(jsonrpc_request) > 0 and (jsonrpc_request) == len(
            jsonrpc_response)
        assert all(validate_jussi_response(req, resp) for req, resp in
                   zip(jsonrpc_request, jsonrpc_response))
    elif isinstance(jsonrpc_request, dict):
        assert is_valid_non_error_single_jsonrpc_response(jsonrpc_response)
        if is_get_block_request(jsonrpc_request):
            assert is_valid_get_block_response(
                jsonrpc_request, jsonrpc_response)
    else:
        raise TypeError('Invalid response type')


#
# is_valid_* methods return True or False, but they don't raise
#


def is_valid_jsonrpc_request(
        jsonrpc_request: JsonRpcRequest = None) -> bool:
    try:
        validate_jsonrpc_request(jsonrpc_request)
        return True
    except Exception as e:
        logger.error(f'{e}')
    return False


def is_valid_single_jsonrpc_response(
        jsonrpc_response: SingleJsonRpcResponse) -> bool:
    return isinstance(
        jsonrpc_response, dict) and len(
        jsonrpc_response.keys()) >= 2 and {
        'id', 'jsonrpc', 'result', 'error'}.issuperset(
        jsonrpc_response.keys())


def is_valid_non_error_single_jsonrpc_response(
        jsonrpc_response: SingleJsonRpcResponse) -> bool:
    return isinstance(
        jsonrpc_response, dict) and len(
        jsonrpc_response.keys()) >= 2 and {
        'id', 'jsonrpc', 'result'}.issuperset(
        jsonrpc_response.keys())


def is_valid_jsonrpc_response(jsonrpc_request: JsonRpcRequest,
                              jsonrpc_response: JsonRpcResponse) -> bool:
    if not is_valid_jsonrpc_request(jsonrpc_request):
        return False
    if isinstance(jsonrpc_request, dict):
        return isinstance(
            jsonrpc_response, dict) and is_valid_single_jsonrpc_response(
            jsonrpc_response)
    if isinstance(jsonrpc_response, list):
        return len(jsonrpc_request) > 0 and len(jsonrpc_request) == len(
            jsonrpc_response) and all(is_valid_single_jsonrpc_response(r)
                                      for r in jsonrpc_response)
    else:
        return False


def is_valid_non_error_jsonrpc_response(jsonrpc_request: JsonRpcRequest,
                                        jsonrpc_response: JsonRpcResponse) -> bool:
    if not is_valid_jsonrpc_request(jsonrpc_request):
        return False
    if isinstance(jsonrpc_request, dict):
        return isinstance(jsonrpc_response,
                          dict) and is_valid_non_error_single_jsonrpc_response(
            jsonrpc_response)
    if isinstance(jsonrpc_response, list):
        return len(jsonrpc_request) > 0 and len(jsonrpc_request) == len(
            jsonrpc_response) and all(
            is_valid_non_error_single_jsonrpc_response(r)
            for r in jsonrpc_response)
    else:
        return False


def is_valid_jussi_response(
        jsonrpc_request: SingleJsonRpcRequest,
        response: SingleJsonRpcResponse) -> bool:
    try:
        if not is_valid_jsonrpc_request(jsonrpc_request):
            return False
        if isinstance(jsonrpc_request, dict):
            if not is_valid_jsonrpc_response(
                    jsonrpc_request, response):
                return False
            if is_get_block_request(jsonrpc_request):
                return is_valid_get_block_response(jsonrpc_request, response)
            return True
        if isinstance(jsonrpc_request, list):
            return len(jsonrpc_request) > 0 and len(jsonrpc_request) == len(
                response) and all(
                is_valid_jussi_response(req, resp) for req,
                resp in
                zip(jsonrpc_request, response))
        return False
    except Exception as e:
        logger.error(f'{e}')
    return False


def is_valid_non_error_jussi_response(
        jsonrpc_request: SingleJsonRpcRequest,
        response: SingleJsonRpcResponse) -> bool:
    try:
        if not is_valid_jsonrpc_request(jsonrpc_request):
            return False
        if isinstance(jsonrpc_request, dict):
            if not is_valid_non_error_jsonrpc_response(
                    jsonrpc_request, response):
                return False
            if is_get_block_request(jsonrpc_request):
                return is_valid_get_block_response(jsonrpc_request, response)
            return True
        if isinstance(jsonrpc_request, list):
            return len(jsonrpc_request) > 0 and len(jsonrpc_request) == len(
                response) and all(
                is_valid_jussi_response(req, resp) for req,
                resp in
                zip(jsonrpc_request, response))
        return False
    except Exception as e:
        logger.error(f'{e}')
    return False


def is_get_block_request(jsonrpc_request: SingleJsonRpcRequest = None) -> bool:
    try:
        jussi_jrpc_call = urn_parts(jsonrpc_request)
        return jussi_jrpc_call.method == 'get_block'
    except Exception as e:
        logger.debug(f'is_get_block_request errored: {e}')
        return False


def is_get_block_header_request(
        jsonrpc_request: SingleJsonRpcRequest = None) -> bool:
    try:
        jussi_jrpc_call = urn_parts(jsonrpc_request)
        return jussi_jrpc_call.method == 'get_block_header'
    except Exception as e:
        logger.debug(f'is_get_block_request errored: {e}')
        return False


def is_get_dynamic_global_properties_request(
        jsonrpc_request: SingleJsonRpcRequest = None) -> bool:
    try:
        jussi_jrpc_call = urn_parts(jsonrpc_request)
        return jussi_jrpc_call.namespace == 'steemd' and jussi_jrpc_call.method == 'get_dynamic_global_properties'
    except Exception:
        return False


def is_valid_get_block_response(
        jsonrpc_request: SingleJsonRpcRequest,
        response: SingleJsonRpcResponse) -> bool:
    if not is_get_block_request(
            jsonrpc_request) and is_valid_non_error_single_jsonrpc_response(
            response):
        return False
    try:
        request_block_num = urn_parts(jsonrpc_request).params[0]
        response_block_num = block_num_from_id(response['result']['block_id'])
        assert int(request_block_num) == response_block_num
        return True
    except KeyError as e:
        logger.error(f'is_valid_get_block_response key error:{e}')
    except AssertionError:
        logger.error(f'{request_block_num} != {response_block_num}')
    except Exception as e:
        logger.error(f'is_valid_get_block_response error :{e}')
    return False


def is_valid_get_block_header_response(
        jsonrpc_request: SingleJsonRpcRequest,
        response: SingleJsonRpcResponse) -> bool:
    if not is_get_block_request(
            jsonrpc_request) and is_valid_non_error_single_jsonrpc_response(
            response):
        return False
    try:
        request_block_num = urn_parts(jsonrpc_request).params[0]
        response_block_num = block_num_from_id(
            response['result']['previous']) + 1
        assert int(request_block_num) == response_block_num
        return True
    except KeyError as e:
        logger.error(f'is_valid_get_block_header_response key error:{e}')
    except AssertionError:
        logger.error(f'{request_block_num} != {response_block_num}')
    except Exception as e:
        logger.error(f'is_valid_get_block_header_response error :{e}')
    return False


def block_num_from_id(block_hash: str) -> int:
    """return the first 4 bytes (8 hex digits) of the block ID (the block_num)
    """
    return int(str(block_hash)[:8], base=16)


def jsonrpc_cache_key(single_jsonrpc_request: SingleJsonRpcRequest) -> str:
    return urn(single_jsonrpc_request)
