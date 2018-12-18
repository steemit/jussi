# -*- coding: utf-8 -*-
import logging
import os
import sys
import time

import structlog
import ujson
from pythonjsonlogger.jsonlogger import JsonFormatter

# pylint: disable=c-extension-no-member
import rapidjson
from jussi.typedefs import WebApp

# pylint: disable=no-member
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        # structlog.processors.TimeStamper(fmt="iso",utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        # structlog.dev.ConsoleRenderer(colors=True)
        structlog.processors.JSONRenderer(serializer=rapidjson.dumps)
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
# pylint: enable=no-member

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
        'root': {
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
        'sanic.error': {
            'level': LOG_LEVEL,
            'handlers': ['errorStream']
        },
        'sanic.access': {
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
            'handlers': ['root'],
            'propagate': True
        }
    }
}


def setup_logging(app: WebApp, log_level: str = None) -> WebApp:
    LOG_LEVEL = log_level or getattr(logging, os.environ.get('LOG_LEVEL', 'INFO'))
    LOGGING['loggers']['sanic.access']['level'] = LOG_LEVEL
    LOGGING['loggers']['sanic.error']['level'] = LOG_LEVEL
    LOGGING['loggers']['jussi']['level'] = LOG_LEVEL
    LOGGING['loggers']['root']['level'] = LOG_LEVEL

    logger = structlog.get_logger('jussi')
    logger.info('configuring jussi logger')
    app.config.logger = logger
    return app
