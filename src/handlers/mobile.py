import tornado.web
import logging
import sys

from src.lib.Statsd import StatsClientSingleton


class MobileHandler(tornado.web.RequestHandler):
    """ The Mobile HTTP handler class
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
            StatsClientSingleton().incr('input.mobile', count=1)
            StatsClientSingleton().incr('amqp.output', count=1)
            routing_key = self.request.uri.replace('/', '.')[1:]

            self.amqp_con.publish(routing_key, self.request.body)

        except Exception as e:
            self.set_status(500)
            StatsClientSingleton().incr('amqp.output_exception', count=1)
            self.logger.info("Error while pushing mobile message to AMQP, "
                             "exception: {} msg: {}, uri: {}"
                             .format(e, self.request.body, self.request.uri))
            sys.exit(1)