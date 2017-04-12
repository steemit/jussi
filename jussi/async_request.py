# -*- coding: utf-8 -*-

import asyncio

from jsonrpcserver import config
from jsonrpcserver.dispatcher import Requests
from jsonrpcserver.request import Request
from jsonrpcserver.response import BatchResponse, NotificationResponse
from jsonrpcserver.response import ExceptionResponse, RequestResponse


class AsyncRequest(Request):
    """Asynchronous request"""

    async def call(self, methods):
        """Find the method from the passed list, and call it, returning a
        Response"""
        # Validation or parsing may have failed in __init__, in which case
        # there's no point calling. It would've already set the response.
        if not self.response:
            # call_context handles setting the result/exception of the call
            with self.handle_exceptions():
                # Get the method object from a list (raises MethodNotFound)

                callable_ = self._get_method(methods, self.method_name)
                # Ensure the arguments match the method's signature
                # self._validate_arguments_against_signature(callable_)
                # Call the method
                result = await callable_(self.method_name, *(self.args or []),
                                         **(self.kwargs or {}))
                # Set the response
                if self.is_notification:
                    self.response = NotificationResponse()
                else:
                    self.response = RequestResponse(self.request_id, result)  # pylint:disable=redefined-variable-type
        # Ensure the response has been set
        assert self.response, 'Call must set response'
        assert isinstance(self.response, (ExceptionResponse,
                                          NotificationResponse, RequestResponse)), 'Invalid response type'
        return self.response


class AsyncRequests(Requests):  # pylint:disable=too-few-public-methods
    """Asynchronous requests"""

    def __init__(self, requests):
        super(AsyncRequests, self).__init__(
            requests, request_type=AsyncRequest)

    async def dispatch(self, methods):
        """Process a JSON-RPC request, calling the requested method(s)"""
        # Init may have failed to parse the request, in which case the response
        # would already be set
        if not self.response:
            # Batch request
            if isinstance(self.requests, list):
                # Batch requests - call each request, and exclude Notifications
                # from the list of responses
                self.response = BatchResponse(
                    await asyncio.gather(*[
                        r.call(methods)
                        for r in map(self.request_type, self.requests)
                        if not r.is_notification
                    ]))
                # If the response list is empty, it should return nothing
                if not self.response:
                    self.response = NotificationResponse()  # pylint:disable=redefined-variable-type
            # Single request
            else:
                self.response = await self.request_type(self.requests) \
                    .call(methods)
        assert self.response, 'Response must be set'
        assert self.response.http_status, 'Must have http_status set'
        if config.log_responses:
            self._log_response(self.response)
        return self.response


async def dispatch(methods, requests):
    """Main public dispatch method"""
    return await AsyncRequests(requests).dispatch(methods)
