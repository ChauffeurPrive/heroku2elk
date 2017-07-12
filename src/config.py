from os import environ


class MonitoringConfig:
    """
    This class contains monitoring configuration parameters.
    """
    metrics_host = environ.get('METRICS_HOST', 'localhost')
    metrics_port = int(environ.get('METRICS_PORT', '8125'))


class TruncateConfig:
    truncate_activated = environ.get('TRUNCATE_ACTIVATION', 'true') is 'true'
    truncate_max_msg_length = int(environ.get('TRUNCATE_MAX_MSG_LENGTH', '1000'))