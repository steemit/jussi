# -*- coding: utf-8 -*-
import logging
from copy import deepcopy
from typing import Optional
from typing import Union

import ujson
from funcy.decorators import decorator
from sanic import response

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse
from jussi.typedefs import WebApp

logger = logging.getLogger('sanic')

# pylint: disable=bare-except


def setup_error_handlers(app: WebApp) -> WebApp:
    # pylint: disable=unused-variable

    @app.exception(Exception)
    def handle_errors(request: HTTPRequest, exception: Exception) -> None:
        """handles all errors"""
        log_request_error(request, exception)

    return app


def log_request_error(request: HTTPRequest, exception: Exception) -> None:
    try:
        method = getattr(request, 'method', 'HTTP Method:None')
        path = getattr(request, 'path', 'Path:None')
        body = getattr(request, 'body', 'Body:None')
        try:
            amzn_trace_id = request.headers.get('X-Amzn-Trace-Id')
        except Exception as e:
            logger.warning('No X-Amzn-Trace-Id in request: %s', e)
            amzn_trace_id = ''
        try:
            amzn_request_id = request.headers.get('X-Amzn-RequestId')
        except Exception as e:
            logger.warning('No X-Amzn-RequestId in request: %s', e)
            amzn_request_id = ''

        message = getattr(exception, 'message', 'Internal Error')
        data = getattr(exception, 'data', 'None')
        logger.exception(
            '%s %s %s --> %s data:%s TraceId:%s, RequestId:%s',
            method,
            path,
            body,
            message,
            data,
            amzn_trace_id,
            amzn_request_id,
            exc_info=exception)
    except BaseException:
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
        except BaseException:
            return None

    def to_dict(self) -> dict:
        base_error = {
            'jsonrpc': '2.0',
            'error': {
                'code': self.code,
                'message': self.message
            }
        }
        if self._id:
            base_error['id'] = self._id
        if self.data:
            try:
                error = deepcopy(base_error)
                error['error']['data'] = self.data
                return error
            except Exception:
                logger.exception('Error generating jsonrpc error response')
                return base_error

        return base_error

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
