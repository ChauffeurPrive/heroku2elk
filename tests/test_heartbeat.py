from tornado.testing import AsyncHTTPTestCase
import heroku2elk.heroku2Logstash as h2l
from heroku2elk.heroku2Logstash import configure_logger


class TestH2LApp(AsyncHTTPTestCase):
    def get_app(self):
        configure_logger()
        return h2l.make_app(self.io_loop)

    def setUp(self):
        super(TestH2LApp, self).setUp()

    def test_health_check(self):
        response = self.fetch('/api/healthcheck')
        self.assertEqual(response.code, 200)

    def test_heartbeat(self):
        response = self.fetch('/api/heartbeat')
        self.assertEqual(response.code, 200)


