# -*- coding: utf-8 -*-
import logging

import ujson
from funcy.decorators import decorator
from sanic import response

logger = logging.getLogger('sanic')

# pylint: disable=bare-except


def log_request_error(request, exception):
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
    except:
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
        return JsonRpcError(sanic_request=call.request)


class JsonRpcError(Exception):
    """Base class for the other exceptions.

    :param data: Extra info (optional).
    """
    message = 'Internal Error'
    code = -32603

    def __init__(self, sanic_request=None, data=None, exception=None):
        super(JsonRpcError, self).__init__(self.message)
        self.sanic_request = sanic_request
        self.data = data
        self.exception = exception

        if exception:
            log_request_error(self.sanic_request, exception)

        self.id = self.jrpc_request_id()

    def jrpc_request_id(self):
        try:
            return self.sanic_request.json['id']
        except:
            return None

    def to_dict(self):
        base_error = {
            'jsonrpc': '2.0',
            'id': self.id,
            'error': {
                'code': self.code,
                'message': self.message
            }
        }
        if self.data:
            try:
                error = dict(base_error.items())
                error['error']['data'] = self.data
                ujson.dumps(error)
            except:
                return base_error
            else:
                return error
        return base_error

    def to_sanic_response(self):
        return response.json(self.to_dict())

    def __str__(self):
        return ujson.dumps(self.to_dict())

    def __repr__(self):
        return str(self.to_dict())


class ParseError(JsonRpcError):
    """Raised when the request is not a valid JSON object.

    :param data: Extra information about the error that occurred (optional).
    """
    code = -32700
    message = 'Parse error'

    def __init__(self, sanic_request=None, data=None, exception=None):
        super(ParseError, self).__init__(
            sanic_request=sanic_request, data=data, exception=exception)


class InvalidRequest(JsonRpcError):
    """Raised when the request is not a valid JSON-RPC object.

    :param data: Extra information about the error that occurred (optional).
    """
    code = -32600
    message = 'Invalid Request'

    def __init__(self, sanic_request=None, data=None, exception=None):
        super(InvalidRequest, self).__init__(
            sanic_request=sanic_request, data=data, exception=exception)


class ServerError(JsonRpcError):
    """Raised when there's an application-specific error on the server side.

    :param data: Extra information about the error that occurred (optional).
    """
    code = -32000
    message = 'Server error'

    def __init__(self, sanic_request=None, data=None, exception=None):
        super(ServerError, self).__init__(
            sanic_request=sanic_request, data=data, exception=exception)
