import tornado.web
from tornado import gen

from heroku2elk.lib.Statsd import StatsClientSingleton


class HeartbeatHandler(tornado.web.RequestHandler):
    """ The Heroku HealthCheck handler class
    """

    @gen.coroutine
    def get(self):
        """ A simple healthCheck handler
            reply 200 to every GET called
        """
        StatsClientSingleton().incr('heartbeat', count=1)
        self.set_status(200)