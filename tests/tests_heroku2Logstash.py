from tornado.testing import AsyncHTTPTestCase
import src.heroku2Logstash as h2l


class TestH2LApp(AsyncHTTPTestCase):
    def get_app(self):
        return h2l.make_app()

    def test_health_check(self):
        response = self.fetch('/api/healthcheck')
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'')

    def test_heartbeat(self):
        response = self.fetch('/api/heartbeat')
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'')

    def test_H2L1_noConnectionToLogstash(self):
        payload = b"83 <40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed from starting to up\n119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"
        response = self.fetch('/heroku/v1/toto', method='POST', body=payload)
        self.assertEqual(response.code, 200)
        self.assertEqual(len(response.body), 0)

    def test_H2L1_LogstashReply500(self):
        payload = b"83 <40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed from starting to up\n119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"
        response = self.fetch('/heroku/v1/toto', method='POST', body=payload)
        self.assertEqual(response.code, 200)
        self.assertEqual(len(response.body), 0)