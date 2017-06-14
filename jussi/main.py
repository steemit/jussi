# coding=utf-8
import logging
import argparse
from serve import app

logger = logging.getLogger(__name__)


def main(app=app):
    # parse CLI args and add them to app.config for use by registered listeners
    parser = argparse.ArgumentParser(description="jussi reverse proxy server")
    parser.add_argument('--server_host', type=str, default='0.0.0.0')
    parser.add_argument('--server_port', type=int, default=9000)
    parser.add_argument('--server_workers', type=int, default=os.cpu_count())
    parser.add_argument(
            '--steemd_websocket_url', type=str,
            default='wss://steemd.steemitdev.com')
    parser.add_argument('--sbds_url', type=str,
                        default='https://sbds.steemit.com')
    parser.add_argument('--redis_host', type=str, default=None)
    parser.add_argument('--redis_port', type=int, default=6379)
    parser.add_argument('--redis_namespace', type=str, default='jussi')
    parser.add_argument('--statsd_host', type=str)
    parser.add_argument('--statsd_port', type=int, default=8125)
    parser.add_argument('--statsd_prefix', type=str, default='jussi')
    args = parser.parse_args()
    app.config.args = args


    # run app
    logger.info('app.run')
    app.run(
            host=args.server_host,
            port=args.server_port,
            workers=args.server_workers,
            log_config=LOGGING)