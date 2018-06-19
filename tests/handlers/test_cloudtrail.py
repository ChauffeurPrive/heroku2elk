import unittest
from unittest.mock import Mock, patch

from src.handlers.cloudtrail import CloudTrailHandler


class TestCloudTrail(unittest.TestCase):

    @patch('src.handlers.heroku.sys.exit')
    def test_h2l_cloudtrail_post_failure(self, sysExit):
        """
        Exception occurs while pushing message to rabbitmq
        return 500
        :return:
        """

        sysExit = Mock(return_value=True)
        amqp_con = Mock()
        amqp_con.publish = Mock(side_effect=Exception)
        application = Mock()
        application.ui_methods = Mock()
        application.ui_methods.items = Mock(return_value=[])
        request = Mock()
        request.uri = "./cloudtrail/v1/integration/toto"
        handler = CloudTrailHandler(application, request, amqp_con=amqp_con)

        handler.request.body = '{"test": "plop"}'

        handler.post()

        handler.get_status()
        self.assertEqual(handler.get_status(), 500)
