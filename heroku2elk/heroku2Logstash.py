import tornado.ioloop
import tornado.web
from tornado import httpclient, gen
from tornado.httpserver import HTTPServer
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
from statsd import StatsClient
import pika
import json
import socket
import os

from heroku2elk.config import MonitoringConfig, TruncateConfig, AmqpConfig, MainConfig
from heroku2elk.lib.syslogSplitter import SyslogSplitter
from heroku2elk.lib.AMQPConnection import AMQPConnection


class HealthCheckHandler(tornado.web.RequestHandler):
    """ The Heroku HealthCheck handler class
    """

    def initialize(self):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.statsdClient = StatsClient(
            MonitoringConfig.metrics_host,
            MonitoringConfig.metrics_port,
            prefix='heroku2logstash')
        self.http_client = httpclient.AsyncHTTPClient()
        self.hostname = socket.gethostname()

    @gen.coroutine
    def get(self):
        """ A simple healthCheck handler
            reply 200 to every GET called
        """
        self.statsdClient.incr('heartbeat.{}'.format(self.hostname), count=1)
        destination = 'http://127.0.0.1:15672/api/queues'
        try:
            request = httpclient.HTTPRequest(destination, method='GET', auth_mode='basic', auth_username=AmqpConfig.user, auth_password=AmqpConfig.password)
            response = yield self.http_client.fetch(request)
            stats = {}
            for q in json.loads(response.body.decode('utf-8')):
                stats[q['name']] = q['messages']
                self.statsdClient.gauge('{}.{}'.format(q['name'], self.hostname), q['messages'])
            self.write(json.dumps(stats))
            self.set_status(response.code)
        except Exception as error:
            self.logger.info('Error while fetching AMQP({}) queue state: {}'
                             .format(destination, error))
            self.statsdClient.incr('heartbeat_failure.{}'.format(self.hostname), count=1)
            self.set_status(500)

        self.set_status(200)


class HerokuHandler(tornado.web.RequestHandler):
    """ The Heroku HTTP drain handler class
    """

    def initialize(self):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.statsdClient = StatsClient(
            MonitoringConfig.metrics_host,
            MonitoringConfig.metrics_port,
            prefix='heroku2logstash')
        self.syslogSplitter = SyslogSplitter(TruncateConfig(), self.statsdClient)

    def set_default_headers(self):
        """
        specify the output headers to have an empty payload, as described here:
        https://devcenter.heroku.com/articles/log-drains#https-drain-caveats
        :return:
        """
        self.set_header('Content-Length', '0')

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
            self.statsdClient.incr('input.heroku', count=1)
            # 1. split
            logs = self.syslogSplitter.split(self.request.body)
            # 2. forward
            channel = yield AMQPConnection().get_channel()
            [self._push_to_AMQP(channel, l) for l in logs]
            self.set_status(200)
        except Exception as e:
            self.logger.info("Error while forwarding message, errors: {} input headers: {}, payload: {}"
                                .format(e, self.request.headers, self.request.body))
            self.statsdClient.incr('split.error', count=1)
            self.set_status(500)

    def _push_to_AMQP(self, channel, msg):
        try:
            self.statsdClient.incr('amqp.output', count=1)
            payload = dict()
            path = self.request.uri.split('/')[1:]
            payload['type'] = path[0]
            payload['parser_ver'] = path[1]
            payload['env'] = path[2]
            payload['app'] = path[3]
            payload['message'] = msg
            payload['http_content_length'] = len(msg)
            routing_key = "{}.{}.{}.{}".format(payload['type'], payload['parser_ver'], payload['env'], payload['app'])

            channel.basic_publish(exchange='logs',
                                  routing_key=routing_key,
                                  body=json.dumps(payload),
                                  properties=pika.BasicProperties(
                                      delivery_mode=1,  # make message persistent
                                  ),
                                  mandatory=True
                                  )

        except Exception as e:
            self.statsdClient.incr('amqp.output_exception', count=1)
            self.logger.info("Error while pushing message to AMQP, exception: {} msg: {}, uri: {}"
                             .format(e, msg, self.request.uri))


class MobileHandler(tornado.web.RequestHandler):
    """ The Mobile HTTP handler class
    """

    def initialize(self):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.statsdClient = StatsClient(
            MonitoringConfig.metrics_host,
            MonitoringConfig.metrics_port,
            prefix='heroku2logstash')


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
            channel = AMQPConnection().get_channel()
            self.statsdClient.incr('input.mobile', count=1)
            self.statsdClient.incr('amqp.output', count=1)
            routing_key = self.request.uri.replace('/', '.')[1:]

            channel.basic_publish(exchange='logs',
                                       routing_key=routing_key,
                                       body=self.request.body,
                                       properties=pika.BasicProperties(
                                          delivery_mode=1,  # make message persistent
                                       ),
                                       mandatory=True
                                       )
        except Exception as e:
            self.statsdClient.incr('amqp.output_exception', count=1)
            self.logger.info("Error while pushing mobile message to AMQP, exception: {} msg: {}, uri: {}"
                             .format(e, self.request.body, self.request.uri))


def make_app():
    """
    Create the tornado application
    """

    return tornado.web.Application([
        (r"/heroku/.*", HerokuHandler, ),
        (r"/mobile/.*", MobileHandler, ),
        (r"/api/healthcheck", HealthCheckHandler, ),
        (r"/api/heartbeat", HealthCheckHandler, ),
    ])


def configure_logger():
    """
    configure logger object with handlers
    """
    app_log = logging.getLogger("tornado.application")
    app_log.setLevel(logging.INFO)
    default_formatter = logging.Formatter('%(asctime)-15s %(message)s')

    #  syslog
    handler = SysLogHandler(address='/dev/log')
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter(
        'heroku2Logstash: { "loggerName":"%(name)s", "asciTime":"%(asctime)s", '
        '"pathName":"%(pathname)s", "logRecordCreationTime":"%(created)f", "functionName":"%(funcName)s", '
        '"levelNo":"%(levelno)s", "lineNo":"%(lineno)d", "time":"%(msecs)d", "levelName":"%(levelname)s", '
        '"message":"%(message)s"}')
    handler.formatter = formatter
    app_log.addHandler(handler)

    # console log
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.formatter = default_formatter
    app_log.addHandler(ch)

    # File log (max 10g: 10*1g)
    file_handler = RotatingFileHandler('Heroku2Logstash.log', maxBytes=1000000000, backupCount=10)
    file_handler.setLevel(logging.INFO)
    file_handler.formatter = default_formatter
    app_log.addHandler(file_handler)
    return app_log


if __name__ == "__main__":
    logger = configure_logger()

    app = make_app()
    if MainConfig.tornado_multiprocessing_activated:
        logger.info("Start H2L in multi-processing mode")
        server = HTTPServer(app)
        server.bind(8080)
        server.start(0)  # autodetect number of cores and fork a process for each
    else:
        logger.info("Start H2L in single-processing mode")
        app.listen(8080)

    # instantiate an AMQP connection at start to create the queues (needed when logstash starts)
    tornado.ioloop.IOLoop.instance().add_future(AMQPConnection().get_channel(), lambda x: logger.info("pid:{} AMQP is connected".format(os.getpid())))
    tornado.ioloop.IOLoop.instance().start()
