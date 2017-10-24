import tornado
from tornado.testing import AsyncHTTPTestCase
from heroku2elk.handlers.heartbeat import HeartbeatHandler


class TestHeartbeat(AsyncHTTPTestCase):
    def get_app(self):
        return tornado.web.Application([
            (r"/api/healthcheck", HeartbeatHandler, ),
            (r"/api/heartbeat", HeartbeatHandler, ),
        ])

    def setUp(self):
        super(TestHeartbeat, self).setUp()

    def test_health_check(self):
        response = self.fetch('/api/healthcheck')
        self.assertEqual(response.code, 200)

    def test_heartbeat(self):
        response = self.fetch('/api/heartbeat')
        self.assertEqual(response.code, 200)