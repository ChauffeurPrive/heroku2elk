from statsd import StatsClient
from heroku2elk.config import MonitoringConfig


class StatsClientSingleton:
    __instance = None

    def get_instance(self):
        if StatsClientSingleton.__instance is None:
            StatsClientSingleton.__instance = StatsClient(
                MonitoringConfig.metrics_host,
                MonitoringConfig.metrics_port,
                prefix=MonitoringConfig.metrics_prefix)
        return StatsClientSingleton.__instance