import sys

import pika
import tornado.ioloop
import tornado.web
from tornado.httpserver import HTTPServer

from heroku2elk.config import MainConfig
from heroku2elk.handlers.heartbeat import HeartbeatHandler
from heroku2elk.handlers.heroku import HerokuHandler
from heroku2elk.handlers.mobile import MobileHandler
from heroku2elk.lib.AMQPConnection import AMQPConnectionSingleton
from heroku2elk.lib.logger import configure_logger


def make_app(ioloop):
    """
    Create the tornado application
    """
    return tornado.web.Application([
            (r"/heroku/.*", HerokuHandler, dict(ioloop=ioloop)),
            (r"/mobile/.*", MobileHandler, dict(ioloop=ioloop)),
            (r"/api/healthcheck", HeartbeatHandler, ),
            (r"/api/heartbeat", HeartbeatHandler, ),
           ])


def run(logger):
    """
    Run the app
    :param logger:
    :return:
    """
    app = make_app()
    if MainConfig.tornado_multiprocessing_activated:
        logger.info("Start H2L in multi-processing mode")
        server = HTTPServer(app)
        server.bind(8080)
        # autodetect number of cores and fork a process for each
        server.start(0)
    else:
        logger.info("Start H2L in single-processing mode")
        app.listen(8080)

    # instantiate an AMQP connection at start to create the queues
    # (needed when logstash starts)
    ins = tornado.ioloop.IOLoop.instance()

    def _instanciate_channel(ins):
        try:
            AMQPConnectionSingleton().get_channel(ins)
        except pika.exceptions.AMQPConnectionError as e:
            logger.error("Error while connecting to rabbitmq %s".format(e))
            sys.exit(1)

    ins.add_future(_instanciate_channel(ins),
                   lambda x: logger.info("AMQP is connected"))

    if MainConfig.tornado_debug:
        logger.info("Start H2L in memory debug mode")
        from heroku2elk.tools.dump_mem import record_top, start
        start()
        tornado.ioloop.PeriodicCallback(record_top, 3600000).start()

    ins.start()


if __name__ == "__main__":
    logger = configure_logger()
    run(logger)

