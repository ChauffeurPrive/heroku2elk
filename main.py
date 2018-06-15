import tornado
from tornado import gen
from tornado.ioloop import IOLoop
import sys

from src.handlers.heartbeat import HeartbeatHandler
from src.handlers.heroku import HerokuHandler
from src.handlers.mobile import MobileHandler
from src.handlers.cloudtrail import CloudTrailHandler

from src.lib.AMQPConnection import AMQPConnection


@gen.coroutine
def connect_to_amqp():
    amqp_con = AMQPConnection()
    res = yield amqp_con.connect(IOLoop.current())
    if not res:
        sys.exit(1)
    yield amqp_con.declare_queue("mobile_integration_queue")
    yield amqp_con.declare_queue("mobile_production_queue")
    yield amqp_con.declare_queue("heroku_integration_queue")
    yield amqp_con.declare_queue("heroku_production_queue")
    yield amqp_con.declare_queue("cloudtrail_integration_queue")
    yield amqp_con.declare_queue("cloudtrail_production_queue")
    return amqp_con

amqp_con = IOLoop.current().run_sync(connect_to_amqp)


app = tornado.web.Application([
    (r"/heroku/.*", HerokuHandler, dict(amqp_con=amqp_con)),
    (r"/mobile/.*", MobileHandler, dict(amqp_con=amqp_con)),
    (r"/cloudtrail/.*", CloudTrailHandler, dict(amqp_con=amqp_con)),
    (r"/api/healthcheck", HeartbeatHandler),
    (r"/api/heartbeat", HeartbeatHandler),
   ])

