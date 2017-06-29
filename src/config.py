from os import environ


class MonitoringConfig:
    """
    This class contains monitoring configuration parameters.
    """
    metrics_host = environ.get('METRICS_HOST', 'localhost')
    metrics_port = int(environ.get('METRICS_PORT', '8125'))
