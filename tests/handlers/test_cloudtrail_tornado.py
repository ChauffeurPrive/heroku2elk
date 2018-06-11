import json
import gzip
import tornado
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.concurrent import Future
from tornado.testing import AsyncHTTPTestCase, gen_test

from src.handlers.cloudtrail import CloudTrailHandler
from src.lib.AMQPConnection import AMQPConnection


@gen.coroutine
def connect_to_amqp():
    amqp_con = AMQPConnection()
    yield amqp_con.connect(IOLoop.current())
    return amqp_con


class TestTornadoCloudTrail(AsyncHTTPTestCase):
    def get_app(self):
        con = self.io_loop.run_sync(connect_to_amqp)
        return tornado.web.Application([(r"/cloudtrail/.*", CloudTrailHandler, dict(amqp_con=con))])

    def setUp(self):
        super(TestTornadoCloudTrail, self).setUp()

    @gen_test
    def test_cloudtrail_push_to_amqp_success(self):
        consumer = AMQPConnection()
        yield consumer.connect(self.io_loop)

        self.futureMsg = Future()
        yield consumer.subscribe("cloudtrail.v1.integration.toto", "cloudtrail_queue", self.on_message)

        payload = b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - " \
                  b"Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.\n"
        response = self.http_client.fetch(
            self.get_url('/cloudtrail/v1/integration/toto'),
            method='POST',
            body=payload,
            use_gzip=False
        )

        res = yield self.futureMsg
        self.assertEqual(res, b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - "
                              b"Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.\n")
        value = yield response
        self.assertEqual(value.code, 200)
        self.assertEqual(len(value.body), 0)

        yield consumer.disconnect()

    @gen_test
    def test_cloudtrail_push_to_amqp_success_gzip(self):
        consumer = AMQPConnection()
        yield consumer.connect(self.io_loop)

        self.futureMsg = Future()
        yield consumer.subscribe("cloudtrail.v1.integration.toto", "cloudtrail_queue", self.on_message)

        payload = gzip.compress(json.dumps({'message': 'this is a log message'}).encode())

        request = tornado.httpclient.HTTPRequest(
            self.get_url('/cloudtrail/v1/integration/toto'),
            method='POST',
            body=payload,
            use_gzip=True)

        response = self.http_client.fetch(request)

        res = yield self.futureMsg
        self.assertEqual(res, b'{"message": "this is a log message"}')
        value = yield response
        self.assertEqual(value.code, 200)
        self.assertEqual(len(value.body), 0)

        yield consumer.disconnect()

    def on_message(self, channel, basic_deliver, properties, body):
        if not self.futureMsg.done():
            self.futureMsg.set_result(body)
        channel.basic_ack(basic_deliver.delivery_tag)
