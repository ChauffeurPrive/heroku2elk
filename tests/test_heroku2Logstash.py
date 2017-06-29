import tornado
from tornado.testing import AsyncHTTPTestCase
import src.heroku2Logstash as h2l
from mock import patch, Mock
from tornado import httpclient, gen


class TestH2LApp(AsyncHTTPTestCase):
    def get_app(self):
        return h2l.make_app()

    def setUp(self):
        super(TestH2LApp, self).setUp()
        h2l.stats = {
            'input': 0,
            'output': 0,
            'timeout': 0,
            'error': 0
        }
        self.async_patcher = patch('tornado.httpclient.AsyncHTTPClient')
        self.mocked_async_client = self.async_patcher.start()

    def tearDown(self):
        self.async_patcher.stop()

    def test_health_check(self):
        response = self.fetch('/api/healthcheck')
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'')

    def test_heartbeat(self):
        response = self.fetch('/api/heartbeat')
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'')

    def test_H2L_no_connection_to_logstash(self):
        payload = b"83 <40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed from starting to up\n119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"
        response = self.fetch('/heroku/v1/toto', method='POST', body=payload)
        self.assertEqual(response.code, 200)
        self.assertEqual(len(response.body), 0)
        self.assertEqual(h2l.stats["input"], 1)
        self.assertEqual(h2l.stats["output"], 2)
        self.assertEqual(h2l.stats["error"], 2)
        self.assertEqual(h2l.stats["timeout"], 0)

    def test_H2L_split_error(self):
        payload = b"50 <40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed from starting to up\n119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"
        response = self.fetch('/heroku/v1/toto', method='POST', body=payload)
        self.assertEqual(response.code, 500)
        self.assertEqual(len(response.body), 0)
        self.assertEqual(h2l.stats["input"], 1)
        self.assertEqual(h2l.stats["output"], 0)
        self.assertEqual(h2l.stats["error"], 1)
        self.assertEqual(h2l.stats["timeout"], 0)

    def test_H2L_logstash_reply_500(self):
        request = tornado.httpclient.HTTPRequest('http://127.0.0.1:8888/heroku/v1/toto', method="POST")
        http_response = tornado.httpclient.HTTPResponse(request, 500, buffer='')
        @gen.coroutine
        def handler(res):
            return http_response
        self.mocked_async_client().fetch.side_effect = handler
        payload = b"83 <40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed from starting to up\n119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"
        response = self.fetch('/heroku/v1/toto', method='POST', body=payload)
        self.assertEqual(response.code, 200)
        self.assertEqual(len(response.body), 0)
        self.assertEqual(h2l.stats["input"], 1)
        self.assertEqual(h2l.stats["output"], 2)
        self.assertEqual(h2l.stats["error"], 2)
        self.assertEqual(h2l.stats["timeout"], 0)

    def test_H2L_logstash_reply_200(self):
        request = tornado.httpclient.HTTPRequest('http://127.0.0.1:8888/heroku/v1/toto', method="POST")
        http_response = tornado.httpclient.HTTPResponse(request, 200, buffer='')
        @gen.coroutine
        def handler(res):
            return http_response
        self.mocked_async_client().fetch.side_effect = handler
        payload = b"83 <40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed from starting to up\n119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"
        response = self.fetch('/heroku/v1/toto', method='POST', body=payload)
        self.assertEqual(response.code, 200)
        self.assertEqual(len(response.body), 0)
        self.assertEqual(h2l.stats["input"], 1)
        self.assertEqual(h2l.stats["output"], 2)
        self.assertEqual(h2l.stats["error"], 0)
        self.assertEqual(h2l.stats["timeout"], 0)