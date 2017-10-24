import tornado.web
from tornado.testing import AsyncHTTPTestCase, gen_test

from heroku2elk.lib.AMQPConnection import AMQPConnectionSingleton
from heroku2elk.lib.logger import configure_logger

class TestAMQPConnection(AsyncHTTPTestCase):
    def get_app(self):
        configure_logger()
        return tornado.web.Application()

    def setUp(self):
        super(TestAMQPConnection, self).setUp()

    @gen_test
    def test_single_instance(self):
        instance1 = yield AMQPConnectionSingleton().get_channel(self.io_loop)
        instance2 = yield AMQPConnectionSingleton().get_channel(self.io_loop)
        self.assertEqual(instance1, instance2)

    @gen_test
    def test_close_channel(self):
        channel = yield AMQPConnectionSingleton().get_channel(self.io_loop)
        print("channel", channel)
        result = yield AMQPConnectionSingleton().close_channel()
        self.assertEqual(result, True)