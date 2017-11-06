from unittest.mock import Mock
import tornado.web
from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.concurrent import Future
import json

from src.lib.AMQPConnection import AMQPConnection
from src.config import AmqpConfig


class TestAMQPConnection(AsyncHTTPTestCase):
    def get_app(self):
        return tornado.web.Application()

    @gen_test
    def test_connect(self):
        sub = AMQPConnection()
        res = yield sub.connect(self.io_loop)
        self.assertTrue(res)
        yield sub.disconnect()

    @gen_test
    def test_connect_failure(self):
        AmqpConfig.port = 1432
        sub = AMQPConnection(AmqpConfig)
        res = yield sub.connect(self.io_loop)
        self.assertFalse(res)
        yield sub.disconnect()

    @gen_test
    def test_pubsub(self):
        routing_key = 'toto'
        AmqpConfig.port = 5672
        sub = AMQPConnection(AmqpConfig)
        yield sub.connect(self.io_loop)
        self.futureMsg = Future()
        yield sub.subscribe(routing_key, "pubsub", self.handle_msg)

        pub = AMQPConnection()
        yield pub.connect(self.io_loop)
        msg_sent = {'toto': 'tutu'}
        yield pub.publish(routing_key, json.dumps(msg_sent))

        msg_rcv = yield self.futureMsg
        self.assertEqual(msg_rcv, msg_sent)

        yield sub.disconnect()
        yield pub.disconnect()

    def handle_msg(self, channel, basic_deliver, properties, body):
        if not self.futureMsg.done():
            self.futureMsg.set_result(json.loads(body.decode('utf-8')))
        channel.basic_ack(basic_deliver.delivery_tag)

    def test_delivery_confirmation_nack(self):
        con = AMQPConnection()
        frame = Mock()
        frame.method = Mock()
        frame.method.NAME = 'toto.nack'
        con.statsdClient = Mock()
        con.statsdClient.incr = Mock()
        con._on_delivery_confirmation(frame)
        con.statsdClient.incr.assert_called_with('amqp.output_failure', count=1)

    def test_delivery_confirmation_ack(self):
        con = AMQPConnection()
        frame = Mock()
        frame.method = Mock()
        frame.method.NAME = 'toto.ack'
        con.statsdClient = Mock()
        con.statsdClient.incr = Mock()
        con._on_delivery_confirmation(frame)
        con.statsdClient.incr.assert_called_with('amqp.output_delivered', count=1)
