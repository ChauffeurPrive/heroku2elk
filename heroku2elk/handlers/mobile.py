import tornado.web
import logging
from tornado import gen
import sys
import pika

from heroku2elk.lib.Statsd import StatsClientSingleton
from heroku2elk.lib.AMQPConnection import AMQPConnectionSingleton


class MobileHandler(tornado.web.RequestHandler):
    """ The Mobile HTTP handler class
    """

    def initialize(self, ioloop):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.ioloop = ioloop

    @gen.coroutine
    def post(self):
        """
        HTTP Post handler
        1. Split the input payload into an array of bytes
        2. send HTTP requests to logstash for each element of the array
        3. aggregate answers
        :return: HTTPStatus 200
        """
        try:
            channel = yield AMQPConnectionSingleton().get_channel(self.ioloop)
            StatsClientSingleton().incr('input.mobile', count=1)
            StatsClientSingleton().incr('amqp.output', count=1)
            routing_key = self.request.uri.replace('/', '.')[1:]

            channel.basic_publish(exchange='logs',
                                  routing_key=routing_key,
                                  body=self.request.body,
                                  properties=pika.BasicProperties(
                                          delivery_mode=1,
                                          # make message persistent
                                       ),
                                  mandatory=True
                                  )
        except Exception as e:
            self.set_status(500)
            StatsClientSingleton().incr('amqp.output_exception', count=1)
            self.logger.info("Error while pushing mobile message to AMQP, "
                             "exception: {} msg: {}, uri: {}"
                             .format(e, self.request.body, self.request.uri))
            sys.exit(1)