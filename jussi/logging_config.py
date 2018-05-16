# -*- coding: utf-8 -*-
import logging
import os
import sys
import time

import structlog
from pythonjsonlogger.jsonlogger import JsonFormatter

import rapidjson
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
        structlog.processors.JSONRenderer(serializer=rapidjson.dumps)
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
    # pylint: disable=no-self-use
    def _jsonify_log_record(self, log_record):
        """Returns a json string of the log record."""
        return ujson.dumps(log_record)


LOG_LEVEL = getattr(logging, os.environ.get('LOG_LEVEL', 'INFO'))
LOGGING = {
    'version': 1,
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
            'formatter': 'simple',
            'stream': sys.stderr
        },
        'errorStream': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'stream': sys.stderr
        },
        'struct': {
            'class': 'logging.StreamHandler',
            'formatter': 'struct',
            'stream': sys.stdout
        }
    },
    'loggers': {
        'sanic': {
            'level': LOG_LEVEL,
            'handlers': ['errorStream']
        },
        'network': {
            'level': LOG_LEVEL,
            'handlers': []
        },
        'jussi': {
            'level': LOG_LEVEL,
            'handlers': ['struct'],
            'propagate': True
        },
        'root': {
            'level': LOG_LEVEL,
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
    LOGGING['loggers']['root']['level'] = LOG_LEVEL

    logger = structlog.get_logger('jussi')
    logger.info('configuring jussi logger')
    app.config.logger = logger
    return app
