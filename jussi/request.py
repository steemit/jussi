# coding=utf-8
import ujson

from .validators import is_valid_jsonrpc_request
from .upstream.urn import urn_parts
from .upstream.urn import urn
from .upstream.url import url_from_urn

class JRPCRequest(dict):
    """Properties of an HTTP JSONRPC request"""
    __slots__ = (
        'id', 'method', 'params', 'version',
        'namespace', 'urn', 'url', 'transport',
        'sanic_request', 'json',
    )


    @classmethod
    def from_sanic_request(cls, sanic_request, index=None):
        try:
            request_json = sanic_request.json
            assert is_valid_jsonrpc_request(request_json)
            instance = cls(sanic_request, index=index)
        except Exception as e:
            raise ValueError('Invalid JsonRpc request')
        return instance


    def __init__(self, sanic_request, index=None):
        super().__init__()
        self.sanic_request = sanic_request
        self.index = index
        if index:
            self.json = sanic_request.json[index]
            self.is_batch = True

        self.urn_parts = urn_parts(self.json)
        self.urn = urn(self.json)
        self.url = url_from_urn(self.json)

    @property
    def jrpc_id(self):
        return self.json.get('id')

    @property
    def jrpc_method(self):
        return self.json['method']

    @property
    def jrpc_params(self):
        return self.json['params']

    @property
    def namespace(self):
        return self.urn_parts.namespace

    @property
    def namespaced_method(self):
        return self.urn_parts.method

    @property
    def api(self):
        return self.urn_parts.api

    @property
    def params(self):
        return self.urn_parts.params


class BatchJrpcRequest:


class SingleJrpsRequest:
    pass
