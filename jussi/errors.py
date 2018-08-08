# -*- coding: utf-8 -*-
import asyncio
import concurrent.futures
import logging
import uuid
from typing import Optional
from typing import Union

import sanic.exceptions
import structlog

from funcy.decorators import decorator
from sanic import response

from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import JrpcRequest
from .typedefs import JrpcResponse
from .typedefs import WebApp

logger = structlog.get_logger(__name__)


# pylint: disable=bare-except

class Default(dict):
    """helper for format strings in Exception messages"""

    def __missing__(self, key):
        return key


def setup_error_handlers(app: WebApp) -> WebApp:
    # pylint: disable=unused-variable


    @app.exception(sanic.exceptions.RequestTimeout)
    def handle_request_timeout_errors(request: HTTPRequest,
                                      exception: sanic.exceptions.RequestTimeout) -> Optional[HTTPResponse]:
        if not request:
            return None
        return RequestTimeoutError(http_request=request,
                                   jrpc_request=request.jsonrpc,
                                   exception=exception).to_sanic_response()


    @app.exception(sanic.exceptions.ServiceUnavailable)
    def handle_response_timeout_errors(request: HTTPRequest,
                                       exception: sanic.exceptions.ServiceUnavailable) -> Optional[HTTPResponse]:
        if not request:
            return None
        return ResponseTimeoutError(http_request=request,
                                    jrpc_request=request.jsonrpc,
                                    exception=exception).to_sanic_response()

    @app.exception(concurrent.futures.CancelledError,
                   concurrent.futures.TimeoutError,
                   asyncio.TimeoutError)
    def handle_async_timeout_errors(request: HTTPRequest,
                                    exception: Exception) -> Optional[HTTPResponse]:
        if not request:
            return None
        return RequestTimeoutError(http_request=request,
                                   jrpc_request=request.jsonrpc,
                                   exception=exception).to_sanic_response()

    @app.exception(JsonRpcError)
    def handle_jsonrpc_error(request: HTTPRequest,
                             exception: JsonRpcError) -> HTTPResponse:
        if not exception.http_request:
            exception.add_http_request(request)
        return exception.to_sanic_response()
    # pylint: enable=unused-argument

    @app.exception(Exception)
    def handle_errors(request: HTTPRequest,
                      exception: Exception) -> HTTPResponse:
        """handles all errors"""
        if isinstance(exception, InvalidRequest):
            return InvalidRequest(http_request=request,
                                  exception=exception,
                                  reason=exception.message).to_sanic_response()
        return JsonRpcError(http_request=request,
                            exception=exception).to_sanic_response()

    return app


@decorator
async def handle_middleware_exceptions(call):
    """Return response when exceptions happened in middleware
    """
    try:
        return await call()
    except Exception as e:
        # pylint: disable=no-member
        if isinstance(e, JsonRpcError):
            if not e.http_request:
                e.add_http_request(call.request)
            return e.to_sanic_response()
        return JsonRpcError(http_request=call.request,
                            exception=e).to_sanic_response()


# pylint: disable=too-many-instance-attributes,too-many-arguments


class JussiInteralError(Exception):
    """Base class for errors that Jussi logs, but don't
     result in JSONRPC error responses

    """
    message = 'Jussi internal error'

    def __init__(self,
                 http_request: HTTPRequest = None,
                 jrpc_request: JrpcRequest=None,
                 jrpc_response: JrpcResponse=None,
                 exception: Exception = None,
                 log_traceback: bool = False,
                 error_logger: logging.Logger = None,
                 **kwargs) -> None:

        self.kwargs = kwargs
        super().__init__(self.format_message())

        self.http_request = http_request
        self.jsonrpc_request = jrpc_request
        self.jsonrpc_response = jrpc_response
        self.exception = exception
        self.log_traceback = log_traceback
        self.logger = error_logger or logger
        self.kwargs = kwargs

        self.error_id = str(uuid.uuid4())

    def format_message(self, kwargs: dict=None) ->str:
        kwargs = kwargs or self.kwargs
        try:
            return self.message.format_map(Default(**kwargs))
        except Exception:
            return self.message

    @property
    def amzn_trace_id(self) -> Optional[str]:
        try:
            return self.jsonrpc_request.amzn_trace_id
        except BaseException:
            pass
        try:
            return self.http_request.headers['X-Amzn-Trace-Id']
        except BaseException:
            pass

    @property
    def jrpc_request_id(self) -> Optional[Union[str, int]]:
        try:
            return self.jsonrpc_request.id
        except BaseException:
            pass
        try:
            return self.http_request.jsonrpc['id']
        except BaseException:
            pass
        try:
            # pylint: disable=protected-access
            return self.http_request._parsed_json['id']
        except BaseException:
            pass

    @property
    def jussi_request_id(self) -> Optional[Union[str, int]]:
        try:
            return self.jsonrpc_request.jussi_request_id
        except BaseException:
            pass
        try:
            return self.http_request.jussi_request_id
        except BaseException:
            pass
        try:
            return self.http_request.headers['x-jussi-request-id']
        except BaseException:
            pass

    def add_http_request(self, http_request: HTTPRequest) -> None:
        self.http_request = http_request

    def add_jsonrpc_request(self, jsonrpc_request: JrpcRequest) -> None:
        self.jsonrpc_request = jsonrpc_request

    def add_jsonrpc_response(self, jsonrpc_response: JrpcResponse) -> None:
        self.jsonrpc_response = jsonrpc_response

    def to_dict(self) -> dict:
        base_error = {
            'message': self.format_message(),
            'error_id': self.error_id,
            'jrpc_request_id': self.jrpc_request_id,
            'jussi_request_id': self.jussi_request_id
        }

        try:
            base_error.update(**self.kwargs)
        except Exception as e:
            logger.warning('JussiInteralError kwargs serialization error', e=e)

        return base_error

    def log(self) -> None:
        if self.log_traceback and self.exception:
            self.logger.error(self.format_message(), **self.to_dict(),
                              exc_info=self.exception)
        else:
            self.logger.error(self.format_message(),
                              exception=self.exception,
                              **self.to_dict())
# pylint: enable=too-many-instance-attributes,too-many-arguments


class JsonRpcError(JussiInteralError):
    """Base class for the JsonRpc other exceptions.
    """
    message = 'Internal Error'
    code = -32603
    # pylint: disable=too-many-arguments

    def to_sanic_response(self) -> HTTPResponse:
        self.log()
        error = {
            'jsonrpc': '2.0',
            'id': self.jrpc_request_id,
            'error': {
                'code': self.code,
                'message': self.format_message(),
                'data': {
                    'error_id': self.error_id,
                    'jussi_request_id': self.jussi_request_id
                }
            }
        }
        return response.json(error, headers={'x-jussi-error-id': self.error_id})


class ParseError(JsonRpcError):
    """Raised when the request is not a valid JSON object.

    """
    code = -32700
    message = 'Parse error'


class InvalidRequest(JsonRpcError):
    """Raised when the request is not a valid JSON-RPC object.

    """
    code = -32600
    message = 'Invalid Request'


class ServerError(JsonRpcError):
    """Raised when there's an application-specific error on the server side.

    """
    code = -32000
    message = 'Server error'


class RequestTimeoutError(JsonRpcError):
    code = 1000
    message = 'Request Timeout'

    def to_dict(self):
        data = super().to_dict()
        try:
            timings = self.timings()
            if timings:
                data.update(**timings)
        except Exception as e:
            logger.info('error adding timing data to RequestTimeoutError', e=e)
        return data


class ResponseTimeoutError(JsonRpcError):
    code = 1050
    message = 'Response Timeout'

    def to_dict(self):
        data = super().to_dict()
        try:
            timings = self.timings()
            if timings:
                data.update(**timings)
        except Exception as e:
            logger.info('error adding timing data to RequestTimeoutError', e=e)
        return data

      
class UpstreamResponseError(JsonRpcError):
    code = 1100
    message = 'Upstream response error'


class InvalidNamespaceError(JsonRpcError):
    code = 1200
    message = 'Invalid JSONRPC method namespace {namespace}'


class InvalidNamespaceAPIError(JsonRpcError):
    code = 1300
    message = 'Invalid JSONRPC method namespace, unable to resolve {namespace}.{api}'


class InvalidUpstreamHost(JsonRpcError):
    code = 1400
    message = 'Invalid/unresolvable upstream hostname {url}'


class InvalidUpstreamURL(JsonRpcError):
    code = 1500
    message = 'Invalid/unhealthy upstream {url} {reason}'


class JsonRpcBatchSizeError(JsonRpcError):
    code = 1600
    message = 'JSONRPC batch size of {jrpc_batch_size} exceeds {jrpc_batch_size_limit}'


class JussiLimitsError(JsonRpcError):
    code = 1700
    message = 'Request exceeded limit'


class JussiCustomJsonOpLengthError(JsonRpcError):
    code = 1800
    message = 'Custom JSON operation size limit of {size_limit} exceeded'
