import tornado.ioloop
import tornado.web
from tornado import httpclient, gen
from tornado.httpserver import HTTPServer
from src.lib import syslogSplitter
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler


stats = {
    'input': 0,
    'output': 0,
    'timeout': 0,
    'error': 0
}


class HealthCheckHandler(tornado.web.RequestHandler):
    """ A simple healthCheck handler
        reply 200 to every GET called
    """
    def get(self):
        self.set_status(200)


class MainHandler(tornado.web.RequestHandler):
    """ The Heroku HTTP drain handler class
    """

    def initialize(self, destination):
        """
        handler initialisation
        """
        self.logger = logging.getLogger("tornado.application")
        self.destination = destination
        self.http_client = httpclient.AsyncHTTPClient()


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
            stats['input'] += 1
            # 1. split
            logs = syslogSplitter.split(self.request.body)
            # 2. forward
            yield [self._forward_request(l) for l in logs]
        except Exception as e:
            self.logger.info("Error while splitting message {} input headers: {}, payload: {}"
                                .format(e, self.request.headers, self.request.body))
            stats['error'] += 1
        self.set_status(200)

    @gen.coroutine
    def _forward_request(self, payload):
        """
        Instanciate an AsyncHTTPClient and send a request with the payload in parameters to the destination
        """
        stats['output'] += 1
        destination = self.destination + self.request.uri
        try:
            print("call to ", destination)
            request = httpclient.HTTPRequest(destination, body=payload, method="POST")
            yield self.http_client.fetch(request)
        except Exception as e:
            self.logger.info("Error while splitting message {} input headers: {}, payload: {}"
                                .format(e, self.request.headers, payload))
            # no response, i.e. timeout, see http://www.tornadoweb.org/en/stable/httpclient.html
            if e.args[0] == 599:
                stats['timeout'] += 1
            else:
                stats['error'] += 1
            self.set_status(200)



def make_app():
    """
    Create the tornado application
    """
    return tornado.web.Application([
        (r"/heroku/.*", MainHandler, dict( destination='http://127.0.0.1:8888')),
        (r"/api/healthcheck", HealthCheckHandler),
        (r"/api/heartbeat", HealthCheckHandler),
    ])


def log_stats():
    """
    log a warning if errors or timeouts have been detected
    """
    if stats['error'] == 0:
        return
    if stats['timeout'] == 0:
        return
    logging.getLogger("tornado.application").warning('heroku2Logstash stats: {}'.format(stats))
    stats.update(
        input=0,
        output=0,
        error=0,
        timeout=0
    )


def configure_logger():
    """
    configure logger object with handlers
    """
    app_log = logging.getLogger("tornado.application")
    app_log.setLevel(logging.INFO)
    default_formatter = logging.Formatter('%(asctime)-15s %(message)s')

    #  syslog
    handler = SysLogHandler(address='/dev/log')
    app_log.setLevel(logging.WARNING)
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
    server = HTTPServer(app)
    server.bind(8080)
    server.start(0)  # autodetect number of cores and fork a process for each
    tornado.ioloop.PeriodicCallback(log_stats, 1000).start()  # each 10 minutes
    tornado.ioloop.IOLoop.instance().start()
