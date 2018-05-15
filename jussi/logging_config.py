# -*- coding: utf-8 -*-
import logging
import os
import sys
import time

import structlog
from pythonjsonlogger.jsonlogger import JsonFormatter
from sanic.log import DefaultFilter

import ujson
from jussi.typedefs import WebApp

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        # structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


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
    'severity',
    # 'pathname',
    # 'process',
    # 'processName',
    # 'relativeCreated',
    # 'thread',
    # 'threadName',
    'extra'
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
        'json': {
            '()': CustomJsonFormatter,
            'format': JSON_LOG_FORMAT,
            'datefmt': LOG_DATETIME_FORMAT,
            'json_indent': None
        },
        'struct': {
            'format': '%(message)s'
        }
    },
    'handlers': {
        'internal': {
            'class': 'logging.StreamHandler',
            'filters': ['accessFilter'],
            'formatter': 'simple',
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
        'struct': {
            'class': 'logging.StreamHandler',
            'formatter': 'struct',
            'stream': sys.stdout
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
            'level': logging.DEBUG,
            'handlers': ['struct'],
            'propagate': True
        },
        'root': {
            'level': logging.DEBUG,
            'handlers': ['struct'],
            'propagate': True
        }
    }
}


def setup_logging(app: WebApp, log_level: str = None) -> WebApp:
    LOG_LEVEL = log_level or getattr(logging, os.environ.get('LOG_LEVEL', 'INFO'))
    LOGGING['loggers']['sanic']['level'] = LOG_LEVEL
    LOGGING['loggers']['network']['level'] = LOG_LEVEL
    LOGGING['loggers']['jussi']['level'] = LOG_LEVEL

    logger = structlog.get_logger('jussi')
    logger.info('configuring jussi logger')
    app.config.logger = logger
    return app
