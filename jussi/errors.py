# -*- coding: utf-8 -*-
import logging
import uuid
from typing import Dict
from typing import Optional
from typing import Union

from funcy.decorators import Call
from funcy.decorators import decorator
from sanic import response
from sanic.exceptions import RequestTimeout
from sanic.exceptions import SanicException
from sanic.request import Request as SanicRequest

import ujson

from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import JsonRpcErrorResponse
from .typedefs import WebApp

logger = logging.getLogger(__name__)


# pylint: disable=bare-except


def setup_error_handlers(app: WebApp) -> WebApp:
    # pylint: disable=unused-variable

    @app.exception(RequestTimeout)
    def handle_timeout_errors(request: HTTPRequest,
                              exception: SanicException) -> Optional[
            HTTPResponse]:
        """handles noisy request timeout errors"""
        # pylint: disable=unused-argument
        if not request:
            return None
        return RequestTimeourError(sanic_request=request).to_sanic_response()

    # pylint: disable=unused-argument
    @app.exception(JsonRpcError)
    def handle_jsonrpc_error(request: HTTPRequest,
                             exception: JsonRpcError) -> HTTPResponse:
        return exception.to_sanic_response()
    # pylint: enable=unused-argument

    @app.exception(Exception)
    def handle_errors(request: HTTPRequest,
                      exception: Exception) -> HTTPResponse:
        """handles all errors"""
        return JsonRpcError(sanic_request=request,
                            exception=exception).to_sanic_response()

    return app


def log_request_error(error_dict: dict, exception: Exception) -> None:
    try:
        logger.exception(str(error_dict), exc_info=exception)
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
        return await call()
    except Exception as e:
        logger.exception('Error ignored %s', e)
        return None


class JsonRpcError(Exception):
    """Base class for the other exceptions.

    :param data: Extra info (optional).
    """
    message = 'Internal Error'
    code = -32603
    # pylint: disable=too-many-arguments

    def __init__(self,
                 sanic_request: SanicRequest = None,
                 data: Dict[str, str] = None,
                 exception: Exception = None,
                 error_id: str = None,
                 log_error: bool = True,
                 error_logger: logging.Logger = None) -> None:
        super(JsonRpcError, self).__init__(self.message)

        self.logger = error_logger or logger
        self.sanic_request = sanic_request
        self.data = data
        self.exception = exception
        self.error_id = error_id or str(uuid.uuid4())

        self._id = self.jrpc_request_id()
        if log_error:
            self.log()

    def request_data(self):
        if not isinstance(self.sanic_request, SanicRequest):
            return None
        request = self.sanic_request

        request_data = {
            'method': getattr(request, 'method', None),
            'path': getattr(request, 'path', None),
        }

        request_data['body'] = self.request_body_data()

        if request.headers:
            request_data['amzn_trace_id'] = request.headers.get(
                'X-Amzn-Trace-Id')
            request_data['jussi_request_id'] = request.headers.get(
                'x-jussi-request-id')

        return request_data

    def request_body_data(self):
        from .utils import is_batch_jsonrpc
        if not isinstance(self.sanic_request, SanicRequest):
            return None
        request = self.sanic_request

        data = {'body': getattr(request, 'body', None)}

        try:
            body_json = request.json
            data.update({'body': body_json})
        except Exception:
            return data

        try:
            is_batch = is_batch_jsonrpc(request)
            data.update({'is_batch': is_batch})
        except Exception:
            return data

        try:
            batch_request_count = None
            if is_batch:
                batch_request_count = len(body_json)
            data.update({'batch_request_count': batch_request_count})
        except Exception:
            return data

        return data

    def add_data(self, new_data: dict) -> None:
        if self.data is None:
            self.data = {}
        if isinstance(new_data, dict):
            for k, v in new_data.items():
                if k not in self.data:
                    self.data[k] = v

    def compose_error_data(self, include_exception=False):
        error_data = {'error_id': self.error_id}
        request = self.request_data()

        if request:
            error_data['request'] = request

        if include_exception:
            error_data['exception'] = self.exception

        if self.data:
            error_data['data'] = self.data

        return error_data

    def jrpc_request_id(self) -> Optional[Union[str, int]]:
        try:
            return self.sanic_request.json['id']
        except Exception:
            return None

    def log(self) -> None:
        data = self.to_dict(include_exception=True)
        self.logger.error(str(data), exc_info=self.exception)

    def to_dict(self, include_exception=False) -> JsonRpcErrorResponse:
        try:
            error = {
                'jsonrpc': '2.0',
                'error': {
                    'code': self.code,
                    'message': self.message,
                    'data': self.compose_error_data(
                        include_exception=include_exception)
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
        }

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


class RequestTimeourError(JsonRpcError):
    code = 1000
    message = 'Request Timeout'


class UpstreamResponseError(JsonRpcError):
    code = 1100
    message = 'Bad or missing upstream response'
