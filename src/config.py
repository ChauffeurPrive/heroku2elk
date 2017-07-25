from os import environ

class MainConfig:
    tornado_multiprocessing_activated = environ.get('TORNADO_MULTIPROCESSING_ACTIVATED', 'true') is 'true'

class MonitoringConfig:
    """
    This class contains monitoring configuration parameters.
    """
    metrics_host = environ.get('METRICS_HOST', 'localhost')
    metrics_port = int(environ.get('METRICS_PORT', '8125'))


class TruncateConfig:
    """
        This class is about the message truncation configuration.
        """
    truncate_activated = environ.get('TRUNCATE_ACTIVATION', 'true') is 'true'
    truncate_max_msg_length = int(environ.get('TRUNCATE_MAX_MSG_LENGTH', '1000'))


class AmqpConfig:
    """
    This class is about the AMQP broker configuration.
    """
    amqp_activated = environ.get('AMQP_ACTIVATION', 'true') is 'true'
    exchange = environ.get('AMQP_MAIN_EXCHANGE', 'logs')
    host = environ.get('AMQP_HOST', 'localhost')
    port = int(environ.get('AMQP_PORT', 5672))
    user = environ.get('AMQP_USER', 'guest')
    password = environ.get('AMQP_PASSWORD', 'guest')