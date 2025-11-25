# -*- coding: utf-8 -*-
import itertools

import pytest
import requests

http_methods = ['GET', 'HEAD', 'POST', 'PUT',
                'DELETE', 'CONNECT', 'OPTIONS', 'PATCH']


def make_params(path, allowed, not_allowed_status_code=403):
    for m in http_methods:
        if m in allowed:
            yield (path, m, 200)
        else:
            yield (path, m, not_allowed_status_code)


params1 = make_params('/', ['GET', 'HEAD', 'OPTIONS', 'POST'])
params2 = make_params('/health', ['GET', 'HEAD', 'OPTIONS'])
params3 = make_params('/.well-known/healthcheck.json', [])
params4 = make_params('/index.html', [])
params5 = make_params('/monitor', [])
params6 = make_params('/nginx_status', [])


@pytest.mark.live
@pytest.mark.parametrize('path,method,expected_status',
                         itertools.chain(params1, params2,
                                         params3, params4, params5),
                         ids=lambda a, b, c: '%s %s' % (a, b))
def test_restricted_routes(jussi_url, path, method, expected_status):
    session = requests.Session()
    url = ''.join([jussi_url, path])
    response = session.request(method, url)
    assert response.status_code == expected_status
