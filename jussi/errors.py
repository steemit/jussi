# -*- coding: utf-8 -*-
import logging
from typing import Optional
from typing import Union

import ujson
from funcy.decorators import decorator
from sanic import response
from sanic.exceptions import RequestTimeout
from sanic.exceptions import SanicException

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse
from jussi.typedefs import JsonRpcErrorResponse
from jussi.typedefs import WebApp

logger = logging.getLogger('sanic')

# pylint: disable=bare-except


def setup_error_handlers(app: WebApp) -> WebApp:
    # pylint: disable=unused-variable

    @app.exception(RequestTimeout)
    def handle_timeout_errors(request: HTTPRequest,
                              exception: SanicException) -> None:
        """handles noisy request timeout errors"""
        # pylint: disable=unused-argument
        return JsonRpcError(sanic_request=request,
                            exception=None).to_sanic_response()

    @app.exception(SanicException)
    def handle_errors(request: HTTPRequest, exception: SanicException) -> None:
        """handles all errors"""
        return JsonRpcError(sanic_request=request,
                            exception=exception).to_sanic_response()

    return app


def log_request_error(request: HTTPRequest, exception: Exception) -> None:
    try:
        # only log exception i no request data is present
        if not request:
            logger.error(f'Request error without request: {exception}')
            return
        # assemble request data
        method = getattr(request, 'method', 'HTTP Method:None')
        path = getattr(request, 'path', 'Path:None')
        body = getattr(request, 'body', 'Body:None')
        if request.headers:
            amzn_trace_id = request.headers.get('X-Amzn-Trace-Id', None)
            amzn_request_id = request.headers.get('X-Amzn-RequestId', None)

        # assemble exception data
        message = getattr(exception, 'message', 'Internal Error')
        data = getattr(exception, 'data', 'None')

        logger.exception(
            f'Method:{method} Path:{path} Body:{body} --> Error:{message} data:{data} TraceId:{amzn_trace_id}, RequestId:{amzn_request_id}',
            exc_info=exception)
    except Exception:
        logger.error('%s --> %s', request, exception)
        logger.exception('Error while logging exception')


@decorator
async def handle_middleware_exceptions(call):
    """Return response when exceptions happend in middleware
    """
    try:
        return await call()
    except Exception as e:
        # pylint: disable=no-member
        if isinstance(e, JsonRpcError):
            return e.to_sanic_response()
        log_request_error(call.request, e)
        return JsonRpcError(sanic_request=call.request).to_sanic_response()


class JsonRpcError(Exception):
    """Base class for the other exceptions.

    :param data: Extra info (optional).
    """
    message = 'Internal Error'
    code = -32603

    def __init__(self,
                 sanic_request: HTTPRequest=None,
                 data: dict=None,
                 exception: Exception=None) -> None:
        super(JsonRpcError, self).__init__(self.message)
        self.sanic_request = sanic_request
        self.data = data
        self.exception = exception

        if exception:
            log_request_error(self.sanic_request, exception)

        self._id = self.jrpc_request_id()

    def jrpc_request_id(self) -> Optional[Union[str, int]]:
        try:
            return self.sanic_request.json['id']
        except Exception:
            return None

    def to_dict(self) -> JsonRpcErrorResponse:
        error = {
            'jsonrpc': '2.0',
            'error': {
                'code': self.code,
                'message': self.message
            }
        }  # type:  JsonRpcErrorResponse

        if self._id:
            error['id'] = self._id
        if self.data:
            try:
                error['error']['data'] = self.data
                return error
            except Exception:
                logger.exception(
                    'Error generating jsonrpc error response data from %s', self.data)
        return error

    def to_sanic_response(self) -> HTTPResponse:
        return response.json(self.to_dict())

    def __str__(self) -> str:
        return ujson.dumps(self.to_dict())

    def __repr__(self) -> str:
        return str(self.to_dict())


class ParseError(JsonRpcError):
    """Raised when the request is not a valid JSON object.

    :param data: Extra information about the error that occurred (optional).
    """
    code = -32700
    message = 'Parse error'

    def __init__(self,
                 sanic_request: HTTPRequest=None,
                 data: dict=None,
                 exception: Exception=None) -> None:
        super(ParseError, self).__init__(
            sanic_request=sanic_request, data=data, exception=exception)


class InvalidRequest(JsonRpcError):
    """Raised when the request is not a valid JSON-RPC object.

    :param data: Extra information about the error that occurred (optional).
    """
    code = -32600
    message = 'Invalid Request'

    def __init__(self,
                 sanic_request: HTTPRequest=None,
                 data: dict=None,
                 exception: Exception=None) -> None:
        super(InvalidRequest, self).__init__(
            sanic_request=sanic_request, data=data, exception=exception)


class ServerError(JsonRpcError):
    """Raised when there's an application-specific error on the server side.

    :param data: Extra information about the error that occurred (optional).
    """
    code = -32000
    message = 'Server error'

    def __init__(self,
                 sanic_request: HTTPRequest=None,
                 data: dict=None,
                 exception: Exception=None) -> None:
        super(ServerError, self).__init__(
            sanic_request=sanic_request, data=data, exception=exception)
