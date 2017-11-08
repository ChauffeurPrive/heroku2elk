import unittest
from unittest.mock import Mock, patch

from src.handlers.mobile import MobileHandler


class TestHeroku(unittest.TestCase):

    @patch('src.handlers.heroku.sys.exit')
    def test_h2l_heroku_post_failure(self, sysExit):
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
        request.uri = "./heroku/v1/integration/toto"
        handler = MobileHandler(application, request, amqp_con=amqp_con)

        handler.request.body = b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - " \
            b"Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.\n"

        handler.post()

        handler.get_status()
        self.assertEqual(handler.get_status(), 500)
