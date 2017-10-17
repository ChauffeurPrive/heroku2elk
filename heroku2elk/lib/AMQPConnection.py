import tornado.ioloop
from tornado import gen
from tornado.concurrent import Future
import logging
from statsd import StatsClient
from heroku2elk.config import MonitoringConfig, AmqpConfig
import pika
import os


class AMQPConnectionSingleton:
    __instance = None

    @gen.coroutine
    def get_channel(self, ioloop):
        if AMQPConnectionSingleton.__instance is None:
            AMQPConnectionSingleton.__instance = yield AMQPConnectionSingleton.AMQPConnection().create_amqp_client(ioloop)
        return AMQPConnectionSingleton.__instance

    def close_channel(self):
        if AMQPConnectionSingleton.__instance:
            AMQPConnectionSingleton.__instance.close()
        AMQPConnectionSingleton.__instance = None

    class AMQPConnection:
        def __init__(self):
            self._connection = None
            self._channel = None
            self.futureChannel = Future()
            self.logger = logging.getLogger("tornado.application")
            self.statsdClient = StatsClient(
                MonitoringConfig.metrics_host,
                MonitoringConfig.metrics_port,
                prefix=MonitoringConfig.metrics_prefix)

        @gen.coroutine
        def on_exchange_declareok(self, unused_frame):
            # Declare the queues
            yield self.declare_queue("mobile_integration_queue")
            yield self.declare_queue("mobile_production_queue")
            yield self.declare_queue("heroku_integration_queue")
            yield self.declare_queue("heroku_production_queue")
            self.logger.info("pid:{} Exchange is declared:{} host:{} port:{}"
                             .format(os.getpid(), AmqpConfig.exchange, AmqpConfig.host, AmqpConfig.port))
            self.futureChannel.set_result(self._channel)

        def declare_queue(self, name):
            future_result = Future()

            def on_queue_ready(method_frame):
                future_result.set_result(True)

            self.logger.info("pid:{} Queue declare:{}".format(os.getpid(), name))
            self._channel.queue_declare(on_queue_ready, queue=name, durable=True,
                                        exclusive=False, auto_delete=False)
            return future_result

        def on_connection_close(self, connection):
            self.logger.error("pid:{} AMQP is disconnected from exchange:{} host:{} port:{} connexion:{}"
                             .format(os.getpid(), AmqpConfig.exchange, AmqpConfig.host, AmqpConfig.port, connection))
            self._connection = None;
            self._channel = None;

        def on_connection_open(self, connection):
            self._connection = connection
            connection.channel(on_open_callback=self.on_channel_open)

            self.logger.info("pid:{} AMQP is connected exchange:{} host:{} port:{} connexion:{}"
                        .format(os.getpid(), AmqpConfig.exchange, AmqpConfig.host, AmqpConfig.port, connection))

        def on_channel_open(self, channel):
            self._channel = channel
            channel.add_on_close_callback(self.on_channel_closed)
            channel.exchange_declare(self.on_exchange_declareok,
                                     exchange=AmqpConfig.exchange, exchange_type='topic')
            self.logger.info("channel open {}".format(channel))
            # Enabled delivery confirmations
            self._channel.confirm_delivery(self.on_delivery_confirmation)

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
            self.logger.warning('Channel was closed: (%s) %s', reply_code, reply_text)
            self._channel = None
            self._connection.close()

        def on_delivery_confirmation(self, method_frame):
            confirmation_type = method_frame.method.NAME.split('.')[1].lower()
            if confirmation_type == 'ack':
                self.statsdClient.incr('amqp.output_delivered', count=1)
            elif confirmation_type == 'nack':
                self.logger.error("delivery_confirmation failed {}".format(method_frame))
                self.statsdClient.incr('amqp.output_failure', count=1)
            else:
                self.statsdClient.incr('amqp.output_other', count=1)

        def create_amqp_client(self, ioloop):
            self.logger.info("pid:{} AMQP connecting to: exchange:{} host:{} port: {}"
                        .format(os.getpid(), AmqpConfig.exchange, AmqpConfig.host, AmqpConfig.port))
            credentials = pika.PlainCredentials(AmqpConfig.user, AmqpConfig.password)

            pika.TornadoConnection(
                pika.ConnectionParameters(host=AmqpConfig.host, port=AmqpConfig.port, credentials=credentials),
                self.on_connection_open, on_close_callback=self.on_connection_close, custom_ioloop=ioloop)

            return self.futureChannel;