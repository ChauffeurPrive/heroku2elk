import tornado.ioloop
import tornado.web
from tornado import httpclient, gen
from tornado.httpserver import HTTPServer
from src.lib import syslogSplitter
import logging
import os
from logging.handlers import SysLogHandler, RotatingFileHandler

stats = {
    'input': 0,
    'output': 0,
    'timeout': 0,
    'error': 0
}


class HealthCheckHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_status(200)


class MainHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header('Content-Length', '0')

    @gen.coroutine
    def post(self):
        payload = self.request.body

        stats['input'] += 1
        logs = []
        try:
            logs = syslogSplitter.split(payload)
        except Exception as e:
            logging.getLogger("tornado.application").warning("Error while splitting message ".format(e))
            logging.getLogger("tornado.application").warning("input headers:{}".format(self.request.headers))
            logging.getLogger("tornado.application").warning("input payload:{}".format(payload))

        @gen.coroutine
        def forward(log):
            stats['output'] += 1
            destination = 'http://127.0.0.1:8888{}'.format(self.request.uri)
            try:
                http_client = httpclient.AsyncHTTPClient()
                request = httpclient.HTTPRequest(destination, body=log, method="POST")
                yield http_client.fetch(request)
            except Exception as error:
                logging.getLogger("tornado.application")\
                    .warning("Error while forwarding msg to logstash: {}".format(error))
                logging.getLogger("tornado.application").warning("input header:{}".format(self.request.headers))
                logging.getLogger("tornado.application").warning("input payload:{}".format(log))
                if error.args[0] == 599:
                    stats['timeout'] += 1
                else:
                    stats['error'] += 1
                self.set_status(200)

        yield [forward(l) for l in logs]
        self.set_status(200)


def display_stats():
    if stats['input'] == 0:
        return
    logging.getLogger("tornado.application").info('heroku2logstash statistics (pid:{}): {}'.format(os.getpid(), stats))
    stats['input'] = 0
    stats['output'] = 0
    stats['error'] = 0
    stats['timeout'] = 0


def make_app():
    return tornado.web.Application([
        (r"/heroku/.*", MainHandler),
        (r"/api/healthcheck", HealthCheckHandler),
        (r"/api/heartbeat", HealthCheckHandler),
    ])

if __name__ == "__main__":
    app_log = logging.getLogger("tornado.application")
    app_log.setLevel(logging.INFO)

    defaultFormatter = logging.Formatter('%(asctime)-15s %(message)s')

    # syslog handler
    handler = SysLogHandler(address='/dev/log')
    app_log.setLevel(logging.WARNING)
    formatter = logging.Formatter(
        'herokuDrainSplitter: { "loggerName":"%(name)s", "asciTime":"%(asctime)s", '
        '"pathName":"%(pathname)s", "logRecordCreationTime":"%(created)f", "functionName":"%(funcName)s", '
        '"levelNo":"%(levelno)s", "lineNo":"%(lineno)d", "time":"%(msecs)d", "levelName":"%(levelname)s", '
        '"message":"%(message)s"}')
    handler.formatter = formatter
    app_log.addHandler(handler)

    # console log
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.formatter = defaultFormatter
    app_log.addHandler(ch)

    # File log (max 10g: 10*1g)
    fileHandler = RotatingFileHandler('Heroku2Logstash.log', maxBytes=1000000000, backupCount=10)
    fileHandler.setLevel(logging.INFO)
    fileHandler.formatter = defaultFormatter
    app_log.addHandler(fileHandler)

    app = make_app()
    server = HTTPServer(app)
    server.bind(8080)
    # autodetect number of cores and fork a process for each
    server.start(0)
    # each 10 minutes
    tornado.ioloop.PeriodicCallback(display_stats, 1000).start()
    tornado.ioloop.IOLoop.instance().start()
