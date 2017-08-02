# -*- coding: utf-8 -*-
import logging
import os
import sys

from sanic.defaultFilter import DefaultFilter

from jussi.typedefs import WebApp


def setup_logging(app: WebApp) -> WebApp:
    # init logging
    root_logger = logging.getLogger()
    root_logger.handlers = []
    LOG_LEVEL = getattr(logging, os.environ.get('LOG_LEVEL', 'INFO'))
    LOGGING['loggers']['sanic']['level'] = LOG_LEVEL
    LOGGING['loggers']['network']['level'] = LOG_LEVEL
    app.config.logger = logging.getLogger('jussi')
    return app


LOGGING = {
    'version': 1,
    'filters': {
        'accessFilter': {
            '()': DefaultFilter,
            'param': [0, 10, 20]
        },
        'errorFilter': {
            '()': DefaultFilter,
            'param': [30, 40, 50]
        }
    },
    'formatters': {
        'simple': {
            'format': '%(asctime)s - (%(name)s)[%(levelname)s]: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'access': {
            'format':
            '%(asctime)s - (%(name)s)[%(levelname)s][%(host)s]: ' +
            '%(request)s %(message)s %(status)d %(byte)d',
            'datefmt':
            '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'internal': {
            'class': 'logging.StreamHandler',
            'filters': ['accessFilter'],
            'formatter': 'simple',
            'stream': sys.stderr
        },
        'accessStream': {
            'class': 'logging.StreamHandler',
            'filters': ['accessFilter'],
            'formatter': 'access',
            'stream': sys.stderr
        },
        'errorStream': {
            'class': 'logging.StreamHandler',
            'filters': ['errorFilter'],
            'formatter': 'simple',
            'stream': sys.stderr
        }
    },
    'loggers': {
        'sanic': {
            'level': logging.DEBUG,
            'handlers': ['internal', 'errorStream']
        },
        'network': {
            'level': logging.DEBUG,
            'handlers': ['accessStream']
        }
    }
}
