# -*- coding: utf-8 -*-
import logging
import os
import sys
import time

from pythonjsonlogger.jsonlogger import JsonFormatter
from sanic.log import DefaultFilter

import ujson
from jussi.typedefs import WebApp

LOG_DATETIME_FORMAT = r'%Y-%m-%dT%H:%M:%S.%s%Z'
os.environ['TZ'] = 'UTC'
time.tzset()
# JsonFormatter.converter = time.gmtime

SUPPORTED_LOG_MESSAGE_KEYS = (
    'levelname',
    'asctime',
    # 'created',
    # 'filename',
    # 'levelno',
    # 'module',
    'funcName',
    'lineno',
    'msecs',
    'message',
    'name',
    'timestamp',
    'severity'
    # 'pathname',
    # 'process',
    # 'processName',
    # 'relativeCreated',
    # 'thread',
    # 'threadName'
)

JSON_LOG_FORMAT = ' '.join(
    ['%({0:s})'.format(i) for i in SUPPORTED_LOG_MESSAGE_KEYS])


class CustomJsonFormatter(JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(
            CustomJsonFormatter,
            self).add_fields(
            log_record,
            record,
            message_dict)
        if getattr(record, 'asctime', None):
            log_record['timestamp'] = record.asctime
            if 'asctime' in log_record:
                del log_record['asctime']
        if getattr(record, 'levelname', None):
            log_record['severity'] = record.levelname
            if 'levelname' in log_record:
                del log_record['levelname']

    # pylint: disable=no-self-use
    def _jsonify_log_record(self, log_record):
        """Returns a json string of the log record."""
        return ujson.dumps(log_record)


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
            '()': CustomJsonFormatter,
            'format': '%(asctime)s %(name) %(levelname) %(message)',
            'datefmt': LOG_DATETIME_FORMAT,
            'json_indent': None
        },
        'json_access': {
            '()': CustomJsonFormatter,
            'format':
            '%(asctime)  %(name) %(levelname) %(host) ' +
            '%(request) %(message) %(status) %(byte)',
            'datefmt': LOG_DATETIME_FORMAT,
            'json_indent': None
        },
        'json_request': {
            '()': CustomJsonFormatter,
            'format': '%(asctime)s',
        },
        'json': {
            '()': CustomJsonFormatter,
            'format': JSON_LOG_FORMAT,
            'datefmt': LOG_DATETIME_FORMAT,
            'json_indent': None
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
            'formatter': 'json_access',
            'stream': sys.stderr
        },
        'errorStream': {
            'class': 'logging.StreamHandler',
            'filters': ['errorFilter'],
            'formatter': 'simple',
            'stream': sys.stderr
        },
        'jussiStdOut': {
            'class': 'logging.StreamHandler',
            'formatter': 'json'
        },
        'jussiRequest': {
            'class': 'logging.StreamHandler',
            'formatter': 'json_request'
        }
    },
    'loggers': {
        'sanic': {
            'level': logging.INFO,
            'handlers': ['errorStream']
        },
        'network': {
            'level': logging.INFO,
            'handlers': []
        },
        'jussi': {
            'level': logging.INFO,
            'handlers': ['jussiStdOut']
        },
        'jussi_debug': {
            'level': logging.INFO,
            'handlers': ['jussiStdOut']
        },
        'jussi_request': {
            'level': logging.INFO,
            'handlers': ['jussiRequest']
        },
    }
}


def setup_logging(app: WebApp, log_level: str = None) -> WebApp:
    LOG_LEVEL = log_level or getattr(logging, os.environ.get('LOG_LEVEL', 'INFO'))
    LOGGING['loggers']['sanic']['level'] = LOG_LEVEL
    LOGGING['loggers']['network']['level'] = LOG_LEVEL
    LOGGING['loggers']['jussi']['level'] = LOG_LEVEL
    LOGGING['loggers']['jussi_debug']['level'] = os.environ.get(
        'REQUEST_LOG_LEVEL', logging.INFO)
    LOGGING['loggers']['jussi_request']['level'] = LOG_LEVEL

    logger = logging.getLogger('jussi')
    logger.info('configuring jussi logger')
    app.config.logger = logger
    return app
