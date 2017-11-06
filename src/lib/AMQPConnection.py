from tornado import gen
from tornado.concurrent import Future
import logging
from statsd import StatsClient
from src.config import MonitoringConfig, AmqpConfig
import pika
import os


class AMQPConnection:
    def __init__(self, config=AmqpConfig):
        self._config = config
        self._connection = None
        self._channel = None
        self._isStarted = Future()
        self._channelClosed = Future()
        self._connectionClosed = Future()
        self.logger = logging.getLogger("tornado.application")
        self.statsdClient = StatsClient(
            MonitoringConfig.metrics_host,
            MonitoringConfig.metrics_port,
            prefix=MonitoringConfig.metrics_prefix)
        self.msg_count = 0

    def on_exchange_declareok(self, unused_frame):
        self.logger.info("pid:{} Exchange is declared:{} host:{} port:{}"
                         .format(os.getpid(), self._config.exchange, self._config.host, self._config.port))
        self._isStarted.set_result(True)

    @gen.coroutine
    def declare_queue(self, name):
        future_result = Future()

        def on_queue_ready(method_frame):
            self.logger.info("pid:{} Queue {} has been declared"
                             .format(os.getpid(), name))

            future_result.set_result(True)

        self.logger.info("pid:{} Queue declare:{}".format(os.getpid(), name))
        self._channel.queue_declare(on_queue_ready, queue=name, durable=True,
                                    exclusive=False, auto_delete=False)
        res = yield future_result
        return res

    def on_connection_closed(self, connection, reply_code, reply_text):
        self.logger.info("pid:{} AMQP is disconnected from exchange:{} host:{} port:{} connexion:{}"
                         .format(os.getpid(), self._config.exchange, self._config.host, self._config.port, connection))
        self._connection = None;
        self._channel = None;
        self._connectionClosed.set_result(True)

    def on_connection_open(self, connection):
        self._connection = connection
        connection.channel(on_open_callback=self.on_channel_open)

        self.logger.info("pid:{} AMQP is connected exchange:{} host:{} port:{} connexion:{}"
                    .format(os.getpid(), self._config.exchange, self._config.host, self._config.port, connection))

    def on_channel_open(self, channel):
        self._channel = channel
        channel.add_on_close_callback(self.on_channel_closed)
        channel.exchange_declare(self.on_exchange_declareok,
                                 exchange=self._config.exchange, durable=True, exchange_type='topic')
        self.logger.info("channel open {}".format(channel))
        # Enabled delivery confirmations
        self._channel.confirm_delivery(self.on_delivery_confirmation)

        self._channel.add_on_return_callback(self.on_return_cb)

    def on_return_cb(self, channel, method, properties, body):
        self.logger.error("message has been returned by the rabbitmq server: {}".format(body))
        self.statsdClient.incr('amqp.output_return', count=1)

    def on_channel_closed(self, channel, reply_code, reply_text):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.
        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.

        :param pika.channel.Channel channel: The closed channel
        :param int reply_code: The numeric reason the channel was closed
        :param str reply_text: The text reason the channel was closed

        """
        self.logger.info('Channel was closed: (%s) %s', reply_code, reply_text)
        self._channel = None
        self._channelClosed.set_result(True)
        self._connection.close()

    @gen.coroutine
    def subscribe(self, routing_key, queue_name, handler):
        self.logger.info('Subscribe to routing_key: %s %s', routing_key, handler)

        # declare queue
        yield self.declare_queue(queue_name)

        # bind it
        bind_ok = Future()
        def on_bind_ok(unused_frame):
            bind_ok.set_result(True)
        self._channel.queue_bind(on_bind_ok, queue_name,
                                 self._config.exchange, routing_key)
        yield bind_ok

        # consume it
        self._channel.basic_consume(handler, queue_name)

    def publish(self, routing_key, msg):
        self._channel.basic_publish(exchange=self._config.exchange,
                          routing_key=routing_key,
                          body=msg,
                          properties=pika.BasicProperties(
                              delivery_mode=2,
                              # make message persistent
                          ),
                          mandatory=True
                          )

    def on_delivery_confirmation(self, method_frame):
        confirmation_type = method_frame.method.NAME.split('.')[1].lower()
        print(confirmation_type)
        print("stats", self.statsdClient)
        if confirmation_type == 'ack':
            self.statsdClient.incr('amqp.output_delivered', count=1)
        else:
            self.logger.error("delivery_confirmation failed {}".format(method_frame))
            self.statsdClient.incr('amqp.output_failure', count=1)

    def on_open_error(self, connection, msg):
        self.logger.error("on_open_error callback: {}".format(msg))
        self._isStarted.set_result(False)

    @gen.coroutine
    def connect(self, ioloop):
        self.logger.info("pid:{} AMQP connecting to: exchange:{} host:{} port: {}"
                    .format(os.getpid(), self._config.exchange, self._config.host, self._config.port))
        credentials = pika.PlainCredentials(self._config.user, self._config.password)

        pika.TornadoConnection(
            pika.ConnectionParameters(host=self._config.host, port=self._config.port, credentials=credentials),
            self.on_connection_open, on_open_error_callback=self.on_open_error,
            on_close_callback=self.on_connection_closed, custom_ioloop=ioloop)

        res = yield self._isStarted
        return res

    @gen.coroutine
    def disconnect(self):
        res = yield self._isStarted
        if not res:
            return

        self._channelClosed = Future()
        self._connectionClosed = Future()
        self._channel.close()
        yield self._channelClosed
        yield self._connectionClosed
