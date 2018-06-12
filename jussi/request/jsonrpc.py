# -*- coding: utf-8 -*-
from time import perf_counter
from ujson import dumps

from cytoolz import sliding_window
from typing import Any
from typing import Dict
from typing import Optional
from typing import TypeVar
from typing import Union


class Empty:
    def __bool__(self):
        return False

    def __repr__(self):
        return '<Empty>'

    def __str__(self):
        return '<Empty>'


_empty = Empty()

JsonRpcRequestIdField = TypeVar('JRPCIdField', str, int, float, Empty)
JsonRpcRequestParamsField = TypeVar('JRPCParamsField', Empty, list, dict)
JsonRpcRequestVersionField = str
JsonRpcRequestMethodField = str


class JSONRPCRequest:
    __slots__ = ('id',
                 'jsonrpc',
                 'method',
                 'params',
                 'urn',
                 'upstream',
                 'amzn_trace_id',
                 'jussi_request_id',
                 'batch_index',
                 'original_request',
                 'timings')

    def __init__(self,
                 _id: JsonRpcRequestIdField,
                 jsonrpc: JsonRpcRequestVersionField,
                 method: JsonRpcRequestMethodField,
                 params: JsonRpcRequestParamsField,
                 urn,
                 upstream,
                 amzn_trace_id: str,
                 jussi_request_id: str,
                 batch_index: int,
                 original_request,
                 timings: Dict[str, float]) -> None:
        self.id = _id
        self.jsonrpc = jsonrpc
        self.method = method
        self.params = params
        self.urn = urn
        self.upstream = upstream
        self.amzn_trace_id = amzn_trace_id
        self.jussi_request_id = jussi_request_id
        self.batch_index = batch_index
        self.original_request = original_request
        self.timings = timings

    def to_dict(self):
        return {k: getattr(self, k) for k in
                ('id', 'jsonrpc', 'method', 'params') if getattr(self, k) is not _empty}

    def json(self) -> str:
        return dumps(self.to_dict(), ensure_ascii=False)

    def to_upstream_request(self, as_json=True) -> Union[str, dict]:
        jrpc_dict = self.to_dict()
        jrpc_dict.update({'id': self.upstream_id})
        if as_json:
            return dumps(jrpc_dict, ensure_ascii=False)
        return jrpc_dict

    @property
    def upstream_headers(self) -> dict:
        headers = {'x-jussi-request-id': self.jussi_request_id}
        if self.amzn_trace_id:
            headers['x-amzn-trace-id'] = self.amzn_trace_id
        return headers

    @property
    def upstream_id(self) -> int:
        return int(self.jussi_request_id) + self.batch_index

    @property
    def translated(self) -> bool:
        return self.original_request is not None

    @property
    def timings_str(self):
        try:
            return {t2[0]: t2[1] - t1[1] for t1, t2 in
                    sliding_window(2, self.timings.items())}
        except Exception:
            return {}

    def log_extra(self, **kwargs) -> Optional[Dict[str, Any]]:
        try:
            base_extra = {
                'x-amzn-trace-id': self.amzn_trace_id,
                'jussi_request_id': self.jussi_request_id,
                'jsonrpc_id': self.id,
                'batch_index': self.batch_index,
                'upstream_request_id': self.upstream_id,
                'translated': self.translated,
                **self.urn.to_dict(),
                **self.upstream._asdict(),
            }
            base_extra.update(**kwargs)
            return base_extra

        except Exception:
            return None

    def __hash__(self) -> int:
        return hash(self.urn)

    @staticmethod
    def translate_to_appbase(request, urn) -> dict:
        params = urn.params
        if params is _empty:
            params = []
        return {
            'id': request.get('id', _empty),
            'jsonrpc': request['jsonrpc'],
            'method': 'call',
            'params': ['condenser_api', urn.method, params]
        }


# pylint: disable=no-member

def from_request(http_request, batch_index: int, request: Dict[str, any]):
    from ..urn import from_request as urn_from_request
    from ..upstream import Upstream
    from ..urn import URN

    upstreams = http_request.app.config.upstreams
    urn = urn_from_request(request)  # type:URN
    upstream = Upstream.from_urn(urn, upstreams=upstreams)  # type: Upstream
    original_request = None

    if upstreams.translate_to_appbase(urn):
        original_request = request
        request = JSONRPCRequest.translate_to_appbase(request, urn)
        urn = urn_from_request(request)
        upstream = Upstream.from_urn(urn, upstreams=upstreams)

    _id = request.get('id', _empty)
    jsonrpc = request['jsonrpc']
    method = request['method']
    params = request.get('params', _empty)
    timings = {'created': perf_counter()}
    return JSONRPCRequest(_id,
                          jsonrpc,
                          method,
                          params,
                          urn,
                          upstream,
                          http_request.amzn_trace_id,
                          http_request.jussi_request_id,
                          batch_index,
                          original_request,
                          timings)
