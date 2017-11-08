import unittest
from src.lib.Statsd import StatsClientSingleton


class StatsdSingletonTest(unittest.TestCase):
    def test_single_instance(self):
        instance1 = StatsClientSingleton()
        instance2 = StatsClientSingleton()
        self.assertEqual(instance1, instance2)
