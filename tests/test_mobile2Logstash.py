from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.concurrent import Future
import heroku2elk.heroku2Logstash as h2l
from heroku2elk.heroku2Logstash import configure_logger
from heroku2elk.config import AmqpConfig
from heroku2elk.lib.AMQPConnection import AMQPConnectionSingleton


class TestH2LApp(AsyncHTTPTestCase):
    def get_app(self):
        configure_logger()
        return h2l.make_app(self.io_loop)

    def setUp(self):
        super(TestH2LApp, self).setUp()

    def tearDown(self):
        h2l.close_app()

    @gen_test
    def test_H2L_mobile_push_to_amqp_success(self):
        self._channel = yield AMQPConnectionSingleton.AMQPConnection().create_amqp_client(self.io_loop)
        consumer_tag = self._channel.queue_bind(self.on_bindok, "mobile_production_queue",
                                                AmqpConfig.exchange, "mobile.v1.integration.toto")
        self._channel.basic_consume(self.on_message, "mobile_production_queue")
        self.futureMsg = Future()

        payload = b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.\n"
        response = self.http_client.fetch(self.get_url('/mobile/v1/integration/toto'), method='POST', body=payload)

        res = yield self.futureMsg
        self.assertEqual(res, b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.\n")
        value = yield response
        self.assertEqual(value.code, 200)
        self.assertEqual(len(value.body), 0)
        self._channel.close()

    def on_message(self, unused_channel, basic_deliver, properties, body):
        if not self.futureMsg.done():
            self.futureMsg.set_result(body)
        self._channel.basic_ack(basic_deliver.delivery_tag)

    def on_bindok(self, unused_frame):
        pass
