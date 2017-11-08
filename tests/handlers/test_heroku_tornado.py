import tornado
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.concurrent import Future
from tornado.testing import AsyncHTTPTestCase, gen_test
import json

from src.handlers.heroku import HerokuHandler
from src.lib.AMQPConnection import AMQPConnection


@gen.coroutine
def connect_to_amqp():
    amqp_con = AMQPConnection()
    yield amqp_con.connect(IOLoop.current())
    return amqp_con


class TestTornadoHeroku(AsyncHTTPTestCase):
    def get_app(self):
        con = self.io_loop.run_sync(connect_to_amqp)
        return tornado.web.Application([(r"/heroku/.*", HerokuHandler, dict(amqp_con=con))])

    def setUp(self):
        super(TestTornadoHeroku, self).setUp()

    def test_h2l_split_error(self):
        payload = b"50 <40>1 2017-06-14T13:52:29+00:00 host app web.3" \
                  b" - State changed from starting to up\n119 <40>1 " \
                  b"2017-06-14T13:53:26+00:00 host app web.3 - " \
                  b"Starting process with command `bundle exec rackup config.ru -p 24405`"
        response = self.fetch('/heroku/v1/toto', method='POST', body=payload)
        self.assertEqual(response.code, 500)
        self.assertEqual(len(response.body), 0)

    @gen_test
    def test_h2l_heroku_push_to_amqp_success(self):
        """
        Message is forwarded to amqp without errors
        :return:
        """
        consumer = AMQPConnection()
        yield consumer.connect(self.io_loop)

        self.futureMsg = Future()
        yield consumer.subscribe("heroku.v1.integration.toto", "heroku_queue", self.on_message)

        payload = b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - " \
                  b"Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.\n"
        response = self.http_client.fetch(self.get_url('/heroku/v1/integration/toto'), method='POST', body=payload)

        res = yield self.futureMsg
        json_res = json.loads(res.decode('utf-8'))
        self.assertEqual(json_res['app'], 'toto')
        self.assertEqual(json_res['env'], 'integration')
        self.assertEqual(json_res['type'], 'heroku')
        self.assertEqual(json_res['http_content_length'], 122)
        self.assertEqual(json_res['parser_ver'], 'v1')
        self.assertEqual(json_res['message'], '<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1'
                                              ' - Lorem ipsum dolor sit amet, consecteteur'
                                              ' adipiscing elit b\'quis\' b\'ad\'.')
        value = yield response
        self.assertEqual(value.code, 200)
        self.assertEqual(len(value.body), 0)

        yield consumer.disconnect()

    def on_message(self, channel, basic_deliver, properties, body):
        if not self.futureMsg.done():
            self.futureMsg.set_result(body)
        channel.basic_ack(basic_deliver.delivery_tag)

    @gen_test
    def test_h2l_heroku_push_to_amqp_success_no_routing(self):
        """
        Message is forwarded to amqp without errors
        :return:
        """
        payload = b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - " \
                  b"Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.\n"
        response = self.http_client.fetch(self.get_url('/heroku/v1/integration/toto2'), method='POST', body=payload)
        value = yield response
        self.assertEqual(value.code, 200)
        self.assertEqual(len(value.body), 0)
