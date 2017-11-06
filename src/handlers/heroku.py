import tornado.web
import logging
import json
import sys

from src.config import TruncateConfig
from src.lib.Statsd import StatsClientSingleton
from src.lib.syslogSplitter import split


class HerokuHandler(tornado.web.RequestHandler):
    """ The Heroku HTTP drain handler class
    """

    def initialize(self, amqp_con):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.amqp_con = amqp_con

    def set_default_headers(self):
        """
        specify the output headers to have an empty payload, as described here:
        https://devcenter.heroku.com/articles/log-drains#https-drain-caveats
        :return:
        """
        self.set_header('Content-Length', '0')

    def post(self):
        """
        HTTP Post handler
        1. Split the input payload into an array of bytes
        2. send HTTP requests to logstash for each element of the array
        3. aggregate answers
        :return: HTTPStatus 200
        """
        # 1. split
        try:
            StatsClientSingleton().incr('input.heroku', count=1)
            logs = split(self.request.body, TruncateConfig)
        except Exception as e:
            self.logger.info("Error while splitting message, errors: {} "
                             "input headers: {}, payload: {}".format(
                e, self.request.headers, self.request.body))
            StatsClientSingleton().incr('split.error', count=1)
            self.set_status(500)
            return

        # 2. forward
        try:
            [self._push_to_amqp(l) for l in logs]
            self.set_status(200)
        except Exception as e:
            self.set_status(500)
            StatsClientSingleton().incr('amqp.output_exception', count=1)
            self.logger.error("Error while pushing message to AMQP, exception:"
                              " {} uri: {}"
                              .format(e, self.request.uri))
            sys.exit(1)

    def _push_to_amqp(self, msg):
        StatsClientSingleton().incr('amqp.output', count=1)
        payload = dict()
        path = self.request.uri.split('/')[1:]
        payload['type'] = path[0]
        payload['parser_ver'] = path[1]
        payload['env'] = path[2]
        payload['app'] = path[3]
        payload['message'] = msg
        payload['http_content_length'] = len(msg)
        routing_key = "{}.{}.{}.{}".format(payload['type'],
                                           payload['parser_ver'],
                                           payload['env'], payload['app'])

        self.amqp_con.publish(routing_key, json.dumps(payload))