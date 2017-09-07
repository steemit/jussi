# -*- coding: utf-8 -*-
import logging
import os
import sys

from sanic.log import DefaultFilter

from jussi.typedefs import WebApp

LOG_DATETIME_FORMAT = r'%Y-%m-%dT%H:%M:%S.%s%Z'
SUPPORTED_LOG_MESSAGE_KEYS = (
    'levelname',
    'asctime',
    #'created',
    'filename',
    # 'levelno',
    'module',
    'funcName',
    'lineno',
    'msecs',
    'message',
    'name',
    'pathname',
    'process',
    'processName',
    # 'relativeCreated',
    #'thread',
    'threadName')

JSON_LOG_FORMAT = ' '.join(
    ['%({0:s})'.format(i) for i in SUPPORTED_LOG_MESSAGE_KEYS])

#JSON_FORMATTER.converter = time.gmtime


def setup_logging(app: WebApp) -> WebApp:
    # init logging
    #root_logger = logging.getLogger()
    #root_logger.handlers = []
    LOG_LEVEL = getattr(logging, os.environ.get('LOG_LEVEL', 'INFO'))
    LOGGING['loggers']['sanic']['level'] = LOG_LEVEL
    LOGGING['loggers']['network']['level'] = LOG_LEVEL
    LOGGING['loggers']['jussi']['level'] = LOG_LEVEL
    logger = logging.getLogger('jussi')
    logger.info('configuring jussi logger')
    app.config.logger = logger
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
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name) %(levelname) %(message)',
            'datefmt': LOG_DATETIME_FORMAT
        },
        'json_access': {
            '()':
            'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format':
            '%(asctime)  %(name) %(levelname) %(host) ' +
            '%(request) %(message) %(status) %(byte)',
            'datefmt':
            LOG_DATETIME_FORMAT
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': JSON_LOG_FORMAT,
            'datefmt': LOG_DATETIME_FORMAT
        }
    },
    'handlers': {
        'internal': {
            'class': 'logging.StreamHandler',
            'filters': ['accessFilter'],
            'formatter': 'json',
            'stream': sys.stderr
        },
        'accessStream': {
            'class': 'logging.StreamHandler',
            'filters': ['accessFilter'],
            'formatter': 'json',
            'stream': sys.stderr
        },
        'errorStream': {
            'class': 'logging.StreamHandler',
            'filters': ['errorFilter'],
            'formatter': 'json',
            'stream': sys.stderr
        },
        'jussi_hdlr': {
            'class': 'logging.StreamHandler',
            'stream': sys.stderr,
            'formatter': 'json'
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
        },
        'jussi': {
            'level': logging.DEBUG,
            'handlers': ['jussi_hdlr']
        }
    }
}
