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
import socket
import os


class SingleAMQPPerProcess:
    __instance = dict()

    def getInstance(self, pid):
        if not pid in SingleAMQPPerProcess.__instance or SingleAMQPPerProcess.__instance[pid] is None:
            SingleAMQPPerProcess.__instance[pid] = self.create_amqp_client(pid)
        return SingleAMQPPerProcess.__instance[pid]

    def create_amqp_client(self, pid):
        logger = logging.getLogger("tornado.application")
        logger.info("pid:{} AMQP connecting to: exchange:{} host:{} port: {}"
                    .format(pid, AmqpConfig.exchange, AmqpConfig.host, AmqpConfig.port))
        credentials = pika.PlainCredentials(AmqpConfig.user, AmqpConfig.password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=AmqpConfig.host, port=AmqpConfig.port, credentials=credentials))
        channel = connection.channel()
        channel.exchange_declare(exchange=AmqpConfig.exchange, type='topic')
        # Enabled delivery confirmations
        channel.confirm_delivery()
        logger.info("pid:{} AMQP is connected exchange:{} host:{} port:{}"
                    .format(pid, AmqpConfig.exchange, AmqpConfig.host, AmqpConfig.port))

        # Declare the queues
        channel.queue_declare(queue="mobile_integration_queue", durable=True, exclusive=False, auto_delete=False)
        channel.queue_declare(queue="mobile_production_queue", durable=True, exclusive=False, auto_delete=False)
        channel.queue_declare(queue="heroku_integration_queue", durable=True, exclusive=False, auto_delete=False)
        channel.queue_declare(queue="heroku_production_queue", durable=True, exclusive=False, auto_delete=False)
        return channel;




class HealthCheckHandler(tornado.web.RequestHandler):
    """ The Heroku HealthCheck handler class
    """

    def initialize(self, statsdClient):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.statsdClient = statsdClient
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

    def initialize(self, statsdClient):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.statsdClient = statsdClient
        self.syslogSplitter = SyslogSplitter(TruncateConfig(), self.statsdClient)
        self.channel = SingleAMQPPerProcess().getInstance("heroku.{}".format(os.getpid()))


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
            [self._push_to_AMQP(l) for l in logs]
            self.set_status(200)
        except Exception as e:
            self.logger.info("Error while splitting message {} input headers: {}, payload: {}"
                                .format(e, self.request.headers, self.request.body))
            self.statsdClient.incr('split.error', count=1)
            self.set_status(500)


    def _push_to_AMQP(self, msg):
        try:
            self.statsdClient.incr('amqp.output', count=1)
            payload = dict()
            path = self.request.uri.split('/')[1:]
            payload['type'] = path[0]
            payload['parser_ver'] = path[1]
            payload['env'] = path[2]
            payload['app'] = path[3]
            payload['message'] = msg.decode('utf-8', 'replace')
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
                self.logger.info('channel.basic_publish on routing_key({}) return False for payload: {}'
                                 .format(routing_key, json.dumps(payload)))
        except Exception as e:
            self.statsdClient.incr('amqp.output_exception', count=1)
            self.logger.info("Error while pushing message to AMQP, exception: {} msg: {}, uri: {}"
                             .format(e, msg, self.request.uri))



class MobileHandler(tornado.web.RequestHandler):
    """ The Mobile HTTP handler class
    """

    def initialize(self, statsdClient):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.statsdClient = statsdClient
        self.channel = SingleAMQPPerProcess().getInstance("mobile.{}".format(os.getpid()))

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
            self.statsdClient.incr('input.mobile', count=1)
            self.statsdClient.incr('amqp.output', count=1)
            routing_key = self.request.uri.replace('/', '.')[1:]
            print(routing_key, self.request.body)

            if self.channel.basic_publish(exchange='logs',
                                  routing_key=routing_key,
                                  body=self.request.body,
                                  properties=pika.BasicProperties(
                                      delivery_mode=1,  # make message persistent
                                  ),
                                  mandatory=True
                                  ):
                self.statsdClient.incr('amqp.output_delivered', count=1)
            else:
                self.statsdClient.incr('amqp.output_failure', count=1)
        except Exception as e:
            self.statsdClient.incr('amqp.output_exception', count=1)
            self.logger.info("Error while pushing mobile message to AMQP, exception: {} msg: {}, uri: {}"
                             .format(e, self.request.body, self.request.uri))




def make_app():
    """
    Create the tornado application
    """
    statsdClient = StatsClient(
        MonitoringConfig.metrics_host,
        MonitoringConfig.metrics_port,
        prefix='heroku2logstash')

    return tornado.web.Application([
        (r"/heroku/.*", HerokuHandler, dict(statsdClient=statsdClient)),
        (r"/mobile/.*", MobileHandler, dict(statsdClient=statsdClient)),
        (r"/api/healthcheck", HealthCheckHandler, dict(statsdClient=statsdClient)),
        (r"/api/heartbeat", HealthCheckHandler, dict(statsdClient=statsdClient)),
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
    tornado.ioloop.IOLoop.instance().start()
