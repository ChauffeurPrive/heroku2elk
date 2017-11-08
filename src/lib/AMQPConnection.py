from tornado import gen
from tornado.concurrent import Future
import logging
from statsd import StatsClient
from src.config import MonitoringConfig, AmqpConfig
import pika
import os


class AMQPConnection:
    """
    This class is inspired from the following pika sample:
    http://pika.readthedocs.io/en/0.11.0/examples/tornado_consumer.html

    If the channel is closed, it will indicate a problem with one of the
    commands that were issued and that should surface in the output as well.

    """
    def __init__(self, config=AmqpConfig):
        """
        Create a new instance of the AMQPConnection class, passing in the AMQPConfig
        class to connect to RabbitMQ.
        :param config:
        """

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

    @gen.coroutine
    def connect(self, ioloop):
        """
        This method connects to RabbitMQ, returning the state.
        When the connection is established, the on_connection_open method
        will be invoked by pika.
        This method waits for the connection to be open

        :param ioloop: the ioloop to be used by the tornadoConnection
        :return: True if the connection is successful
        """
        self.logger.info("pid:{} AMQP connecting to: exchange:{} host:{} port: {}"
                         .format(os.getpid(), self._config.exchange, self._config.host, self._config.port))
        credentials = pika.PlainCredentials(self._config.user, self._config.password)

        pika.TornadoConnection(
            pika.ConnectionParameters(host=self._config.host, port=self._config.port, credentials=credentials),
            self._on_connection_open, on_open_error_callback=self._on_connection_open_error,
            on_close_callback=self._on_connection_closed, custom_ioloop=ioloop)

        res = yield self._isStarted
        return res

    @gen.coroutine
    def disconnect(self):
        """
        This method closes the channel and the connection to RabbitMQ.
        :return:
        """
        res = yield self._isStarted
        if not res:
            return

        self._channelClosed = Future()
        self._connectionClosed = Future()
        self._channel.close()
        yield self._channelClosed
        yield self._connectionClosed

    @gen.coroutine
    def declare_queue(self, name):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. This method wait for the queue to be declared successfully

        :param str|unicode name: The name of the queue to declare.

        """
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

    @gen.coroutine
    def subscribe(self, routing_key, queue_name, handler):
        """
        This method subscribe to a routing_key, binding the routing_key to the given
        queue name.
        The input handler will be called when a message will be received
        :param routing_key: a string describing the routing_key
        :param queue_name: a string describing the queue_name
        :param handler: the message handler
        :return:
        """
        self.logger.info('Subscribe to routing_key: %s %s', routing_key, handler)

        # declare queue
        yield self.declare_queue(queue_name)

        #  bind it
        bind_ok = Future()

        def on_bind_ok(unused_frame):
            bind_ok.set_result(True)

        self._channel.queue_bind(on_bind_ok, queue_name,
                                 self._config.exchange, routing_key)
        yield bind_ok

        # consume it
        self._channel.basic_consume(handler, queue_name)

    def publish(self, routing_key, msg):
        """publish a message to RabbitMQ, check for delivery confirmations in the
        _on_delivery_confirmations method.

        """
        self._channel.basic_publish(exchange=self._config.exchange,
                                    routing_key=routing_key,
                                    body=msg,
                                    properties=pika.BasicProperties(
                                        delivery_mode=2,
                                        # make message persistent
                                    ),
                                    mandatory=True
                                    )

    def _on_exchange_declare_ok(self, unused_frame):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.

        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame

        """
        self.logger.info("pid:{} Exchange is declared:{} host:{} port:{}"
                         .format(os.getpid(), self._config.exchange, self._config.host, self._config.port))
        self._isStarted.set_result(True)

    def _on_connection_closed(self, connection, reply_code, reply_text):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed.

        :param pika.connection.Connection connection: The closed connection obj
        :param int reply_code: The server provided reply_code if given
        :param str reply_text: The server provided reply_text if given

        """
        self.logger.info("pid:{} AMQP is disconnected from exchange:{} host:{} port:{} connexion:{}"
                         .format(os.getpid(), self._config.exchange, self._config.host, self._config.port, connection))
        self._connection = None;
        self._channel = None;
        self._connectionClosed.set_result(True)

    def _on_connection_open(self, connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.

        :type connection: pika.TornadoConnection

        """
        self._connection = connection
        connection.channel(on_open_callback=self._on_channel_open)

        self.logger.info("pid:{} AMQP is connected exchange:{} host:{} port:{} connexion:{}"
                    .format(os.getpid(), self._config.exchange, self._config.host, self._config.port, connection))

    def _on_connection_open_error(self, unused_connection, msg):
        """This method is called by pika in case of connection errors to
        RabbitMQ. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.

        :type unused_connection: pika.TornadoConnection

        """
        self.logger.error("on_open_error callback: {}".format(msg))
        self._isStarted.set_result(False)

    def _on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.

        Since the channel is now open, we'll declare the exchange to use.

        :param pika.channel.Channel channel: The channel object

        """
        self._channel = channel
        channel.add_on_close_callback(self._on_channel_closed)
        channel.exchange_declare(self._on_exchange_declare_ok,
                                 exchange=self._config.exchange, durable=True, exchange_type='topic')
        self.logger.info("channel open {}".format(channel))
        # Enabled delivery confirmations
        self._channel.confirm_delivery(self._on_delivery_confirmation)

        self._channel.add_on_return_callback(self._on_return_message_callback)

    def _on_channel_closed(self, channel, reply_code, reply_text):
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

    def _on_return_message_callback(self, channel, method, properties, body):
        """
        This method is called when the message sent to AMQP
        hasn't been published to any queues
        :param channel: channel used for sending the message
        :param method:
        :param properties:
        :param body: message body
        :return:
        """
        self.logger.error("message has been returned by the rabbitmq server: {}".format(body))
        self.statsdClient.incr('amqp.output_return', count=1)

    def _on_delivery_confirmation(self, method_frame):
        """Invoked by pika when RabbitMQ responds to a Basic.Publish RPC
        command, passing in either a Basic.Ack or Basic.Nack frame with
        the delivery tag of the message that was published. The delivery tag
        is an integer counter indicating the message number that was sent
        on the channel via Basic.Publish. Here we're just doing house keeping
        to keep track of stats and remove message numbers that we expect
        a delivery confirmation of from the list used to keep track of messages
        that are pending confirmation.

        :param pika.frame.Method method_frame: Basic.Ack or Basic.Nack frame

        """
        confirmation_type = method_frame.method.NAME.split('.')[1].lower()
        if confirmation_type == 'ack':
            self.statsdClient.incr('amqp.output_delivered', count=1)
        else:
            self.logger.error("delivery_confirmation failed {}".format(method_frame))
            self.statsdClient.incr('amqp.output_failure', count=1)
