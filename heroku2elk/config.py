from os import environ
get = environ.get

class MainConfig:
    tornado_multiprocessing_activated = get(
            'TORNADO_MULTIPROCESSING_ACTIVATED', 'true') == 'true'
    tornado_debug = get('TORNADO_DEBUG', 'false') == 'true'

class MonitoringConfig:
    """
    This class contains monitoring configuration parameters.
    """
    metrics_host = get('METRICS_HOST', 'localhost')
    metrics_port = int(get('METRICS_PORT', '8125'))
    metrics_prefix = get('METRICS_PREFIX', 'heroku2logstash')


class TruncateConfig:
    """
    This class is about the message truncation configuration.
    """
    truncate_activated = get('TRUNCATE_ACTIVATION', 'true') == 'true'
    truncate_max_msg_length = int(get('TRUNCATE_MAX_MSG_LENGTH', '1000'))
    stack_pattern = get('TRUNCATE_EXCEPT_STACK_PATTERN', 'stack')
    token_pattern = get('REPLACE_TOKEN_PATTERN', '(token":")(.*?)(")')


class AmqpConfig:
    """
    This class is about the AMQP broker configuration.
    """
    amqp_activated = get('AMQP_ACTIVATION', 'true') == 'true'
    exchange = get('AMQP_MAIN_EXCHANGE', 'logs')
    host = get('AMQP_HOST', 'localhost')
    port = int(get('AMQP_PORT', 5672))
    user = get('AMQP_USER', 'guest')
    password = get('AMQP_PASSWORD', 'guest')
