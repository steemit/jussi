# -*- coding: utf-8 -*-
import time

from toolz.functoolz import compose


def replace_jsonrpc_id(request):
    try:
        int(request['id'])
    except ValueError:
        request['id'] = 1
    return request


def generate_int_id():
    return int(time.time() * 1000000)


def replace_jsonrpc_version(request):
    request['jsonrpc'] = '2.0'
    return request


patch_requests = compose(replace_jsonrpc_id, replace_jsonrpc_version)

patch_responses = compose(replace_jsonrpc_version)


def strip_namespace(request, namespace):
    request['method'] = request['method'].strip('%s.' % namespace)
    return request


def split_namespaced_method(namespaced_method, default_namespace='steemd'):
    try:
        namespace, method = namespaced_method.split('.')
    except ValueError:
        namespace, method = default_namespace, namespaced_method
    return namespace, method
