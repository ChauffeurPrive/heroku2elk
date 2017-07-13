import tornado.ioloop
import tornado.web
from tornado import httpclient, gen
from tornado.httpserver import HTTPServer
from src.lib.syslogSplitter import SyslogSplitter
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
from statsd import StatsClient
from src.config import MonitoringConfig, TruncateConfig, AmqpConfig, MainConfig
import pika
import json


class HealthCheckHandler(tornado.web.RequestHandler):
    """ A simple healthCheck handler
        reply 200 to every GET called
    """
    def get(self):
        self.set_status(200)


class MainHandler(tornado.web.RequestHandler):
    """ The Heroku HTTP drain handler class
    """

    def initialize(self, destination, channel, statsdClient):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.destination = destination
        self.http_client = httpclient.AsyncHTTPClient()
        self.statsdClient = statsdClient
        self.syslogSplitter = SyslogSplitter(TruncateConfig(), self.statsdClient)
        self.channel = channel


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
            self.statsdClient.incr('input', count=1)
            # 1. split
            logs = self.syslogSplitter.split(self.request.body)
            # 2. forward
            if AmqpConfig.amqp_activated:
                [self._push_to_AMQP(l) for l in logs]
            else:
                yield [self._forward_request(l) for l in logs]
            self.set_status(200)
        except Exception as e:
            self.logger.info("Error while splitting message {} input headers: {}, payload: {}"
                                .format(e, self.request.headers, self.request.body))
            self.statsdClient.incr('split.error', count=1)
            self.set_status(500)

    @gen.coroutine
    def _push_to_AMQP(self, msg):
        self.statsdClient.incr('amqp.output', count=1)
        payload = {}
        path = self.request.uri.split('/')[1:]
        payload['type'] = path[0]
        payload['parser_ver'] = path[1]
        payload['env'] = path[2]
        payload['app'] = path[3]
        payload['message'] = msg.decode('utf-8')
        payload['http_content_length'] = len(msg)
        routing_key = "{}.{}.{}.{}".format(payload['type'], payload['parser_ver'], payload['env'], payload['app'])

        if self.channel.basic_publish(exchange='logs',
                              routing_key=routing_key,
                              body=json.dumps(payload),
                              properties=pika.BasicProperties(
                                  delivery_mode=1,  # make message persistent
                              ),
                              mandatory=True
                              ):
            self.statsdClient.incr('amqp.output_delivered', count=1)
        else:
            self.statsdClient.incr('amqp.output_failure', count=1)


    @gen.coroutine
    def _forward_request(self, payload):
        """
        Instanciate an AsyncHTTPClient and send a request with the payload in parameters to the destination
        """
        self.statsdClient.incr('output', count=1)
        destination = self.destination + self.request.uri
        try:
            request = httpclient.HTTPRequest(destination, body=payload, method="POST")
            res = yield self.http_client.fetch(request)
            if res.code != 200:
                self.statsdClient.incr('forward.error', count=1)
        except Exception as e:
            self.logger.info("Error while splitting message {} input headers: {}, payload: {}"
                                .format(e, self.request.headers, payload))
            # no response, i.e. timeout, see http://www.tornadoweb.org/en/stable/httpclient.html
            if e.args[0] == 599:
                self.statsdClient.incr('forward.timeout', count=1)
            else:
                self.statsdClient.incr('forward.exception', count=1)


def make_app():
    """
    Create the tornado application
    """
    statsdClient = StatsClient(
        MonitoringConfig.metrics_host,
        MonitoringConfig.metrics_port,
        prefix='heroku2logstash')

    logger = logging.getLogger("tornado.application")
    logger.info("AMQP connecting to: exchange:{} host:{} port: {}"
                     .format(AmqpConfig.exchange, AmqpConfig.host, AmqpConfig.port))
    credentials = pika.PlainCredentials(AmqpConfig.user, AmqpConfig.password)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=AmqpConfig.host, port=AmqpConfig.port, credentials=credentials))
    channel = connection.channel()
    channel.exchange_declare(exchange=AmqpConfig.exchange, type='topic')
    # Enabled delivery confirmations
    channel.confirm_delivery()
    logger.info("AMQP is connected"
                     .format(AmqpConfig.exchange, AmqpConfig.host, AmqpConfig.port))

    return tornado.web.Application([
        (r"/heroku/.*", MainHandler, dict(destination='http://127.0.0.1:8888', channel=channel, statsdClient=statsdClient)),
        (r"/api/healthcheck", HealthCheckHandler),
        (r"/api/heartbeat", HealthCheckHandler),
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
    #app_log.addHandler(ch)

    # File log (max 10g: 10*1g)
    file_handler = RotatingFileHandler('Heroku2Logstash.log', maxBytes=1000000000, backupCount=10)
    file_handler.setLevel(logging.INFO)
    file_handler.formatter = default_formatter
    app_log.addHandler(file_handler)


if __name__ == "__main__":
    configure_logger()

    app = make_app()
    if MainConfig.tornado_multiprocessing_activated:
        server = HTTPServer(app)
        server.bind(8080)
        server.start(0)  # autodetect number of cores and fork a process for each
    else:
        app.listen(8080)
    tornado.ioloop.IOLoop.instance().start()
