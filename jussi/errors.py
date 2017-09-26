# -*- coding: utf-8 -*-
import asyncio
import logging
import uuid
from typing import Dict
from typing import Optional
from typing import Union


import ujson

from funcy.decorators import Call
from funcy.decorators import decorator
from sanic import response
from sanic.request import Request as SanicRequest
from sanic.exceptions import RequestTimeout
from sanic.exceptions import SanicException

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse
from jussi.typedefs import JsonRpcErrorResponse
from jussi.typedefs import WebApp

logger = logging.getLogger(__name__)

# pylint: disable=bare-except


def setup_error_handlers(app: WebApp) -> WebApp:
    # pylint: disable=unused-variable

    @app.exception(RequestTimeout)
    def handle_timeout_errors(request: HTTPRequest,
                              exception: SanicException) -> HTTPResponse:
        """handles noisy request timeout errors"""
        # pylint: disable=unused-argument
        return JsonRpcError(sanic_request=request,
                            exception=None, data={'message': 'Request timeout error'}).to_sanic_response()

    @app.exception(Exception)
    def handle_errors(request: HTTPRequest,
                      exception: Exception) -> HTTPResponse:
        """handles all errors"""
        return JsonRpcError(sanic_request=request,
                            exception=exception).to_sanic_response()

    return app


def log_request_error(error_dict: dict, exception: Exception) -> None:
    try:
        logger.exception(error_dict, exc_info=exception)
    except Exception as e:
        logger.exception(f'Error while logging exception: {e}')


@decorator
async def handle_middleware_exceptions(call):
    """Return response when exceptions happend in middleware
    """
    try:
        return await call()
    except Exception as e:
        logger.error(f'handling middlware error: {e}')
        # pylint: disable=no-member
        if isinstance(e, JsonRpcError):
            return e.to_sanic_response()
        return JsonRpcError(sanic_request=call.request,
                            exception=e).to_sanic_response()


@decorator
async def ignore_errors_async(call: Call) -> Optional[dict]:
    try:
        # pylint: disable=protected-access
        if not asyncio.iscoroutinefunction(call._func):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(call)
        return await call()
    except Exception as e:
        logger.exception('Error ignored %s', e)


class JsonRpcError(Exception):
    """Base class for the other exceptions.

    :param data: Extra info (optional).
    """
    message = 'Internal Error'
    code = -32603

    def __init__(self,
                 sanic_request: SanicRequest = None,
                 data: Dict[str, str] = None,
                 exception: Exception = None,
                 error_id: str = None) -> None:
        super(JsonRpcError, self).__init__(self.message)

        self.sanic_request = sanic_request
        self.data = data
        self.exception = exception
        self.error_id = error_id or str(uuid.uuid4())
        self.error_data = self.compose_error_data()
        self._id = self.jrpc_request_id()
        log_request_error(self.to_dict(include_exception=True), self.exception)

    def request_data(self):
        if not self.sanic_request:
            return
        request = self.sanic_request
        request_data = {
            'method': getattr(request, 'method', None),
            'path': getattr(request, 'path', None),
            'body': getattr(request, 'body', None),
        }
        if request.headers:
            request_data['amzn_trace_id'] = request.headers.get(
                'X-Amzn-Trace-Id')
            request_data['amzn_request_id'] = request.headers.get(
                'X-Amzn-RequestId')
            request_data['jussi_request_id'] = request.headers.get(
                'x-jussi-request-id')
        return request_data

    def exception_data(self):
        if not self.exception:
            return
        exception = self.exception
        exception_data = {
            'message': getattr(exception, 'message', 'Internal Error'),
            'data': getattr(exception, 'data', None)
        }
        return exception_data

    def compose_error_data(self, include_exception=False):
        error_data = {
            'error_id': self.error_id,
            'request': self.request_data(),
        }
        if include_exception:
            error_data['exception'] = self.exception_data()

        if self.data is not None:
            error_data['data'] = self.data

        return error_data

    def jrpc_request_id(self) -> Optional[Union[str, int]]:
        try:
            return self.sanic_request.json['id']
        except Exception:
            return None

    def to_dict(self, include_exception=False) -> JsonRpcErrorResponse:
        try:
            error = {
                'jsonrpc': '2.0',
                'error': {
                    'code': self.code,
                    'message': self.message,
                    'data': self.compose_error_data(include_exception=include_exception)
                }
            }  # type:  JsonRpcErrorResponse

            if self._id:
                error['id'] = self._id
            return error

        except Exception:
            logger.exception('Error generating jsonrpc error response data')

        return {
            'jsonrpc': '2.0',
            'error': {
                'code': self.code,
                'message': self.message

            }
        }  # type:  JsonRpcErrorResponse

    def to_sanic_response(self) -> HTTPResponse:
        return response.json(self.to_dict())

    def __str__(self) -> str:
        return ujson.dumps(self.to_dict())

    def __repr__(self) -> str:
        return str(self.to_dict())


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
