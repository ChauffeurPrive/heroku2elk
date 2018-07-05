import tornado.web
import logging
import sys
import gzip
import json

from src.lib.Statsd import StatsClientSingleton


class CloudTrailHandler(tornado.web.RequestHandler):
    """ The AWS CloudTrail handler class
    """

    def initialize(self, amqp_con):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.amqp_con = amqp_con

    def post(self):
        """
        HTTP Post handler
        * Forward request: publish to AMQP
        :return: HTTPStatus 200
        """
        try:
            StatsClientSingleton().incr('cloudtrail.input', count=1)
            routing_key = self.request.uri.replace('/', '.')[1:]

            payload = self.request.body
            content_encoding = self.request.headers.get('Accept-Encoding')
            if content_encoding == 'gzip':
                payload = gzip.decompress(payload)

            try:
                entry_list = json.loads(payload.decode())["Records"]
                for entry in entry_list:
                    self.amqp_con.publish(routing_key, json.dumps(entry))

                StatsClientSingleton().incr('amqp.output', count=len(entry_list))
            except KeyError:
                self.logger.warning("Error with CloudTrail message, payload: {}".format(payload.decode()))

        except Exception as e:
            self.set_status(500)
            StatsClientSingleton().incr('amqp.output_exception', count=1)
            self.logger.info("Error while pushing CloudTrail message to AMQP, "
                             "exception: {} msg: {}, uri: {}"
                             .format(e, self.request.body, self.request.uri))
            sys.exit(1)
