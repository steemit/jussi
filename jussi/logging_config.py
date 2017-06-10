# coding=utf-8
import sys
from sanic.defaultFilter import DefaultFilter

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
            'level': 'DEBUG',
            'handlers': ['internal', 'errorStream']
        },
        'network': {
            'level': 'DEBUG',
            'handlers': ['accessStream', 'errorStream']
        }
    }
}
