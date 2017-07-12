import unittest
from src.lib.syslogSplitter import SyslogSplitter
from mock import patch, Mock
from src.config import TruncateConfig

class SyslogSplitterTest(unittest.TestCase):
    def setUp(self):
        self.conf = TruncateConfig()
        self.statsdClient = Mock()
        self.statsdClient.incr = Mock()

    def test_splitHerokuSample(self):
        stream = b"83 <40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed from starting to up\n119 <40>1 2017-06-14T13:53:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"
        logs = SyslogSplitter(self.conf, self.statsdClient).split(stream)
        self.assertEqual(logs, [
            b"<40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed from starting to up",
            b"<40>1 2017-06-14T13:53:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"
        ])

    def test_splitHerokuSampleWithoutCarriageReturn(self):
        stream = b"82 <40>1 2012-11-30T06:45:29+00:00 host app web.3 - State changed from starting to up118 <40>1 2012-11-30T06:45:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"
        logs = SyslogSplitter(self.conf, self.statsdClient).split(stream)
        self.assertEqual(logs, [
            b"<40>1 2012-11-30T06:45:29+00:00 host app web.3 - State changed from starting to up",
            b"<40>1 2012-11-30T06:45:26+00:00 host app web.3 - Starting process with command `bundle exec rackup config.ru -p 24405`"
        ])

    def test_splitFakeLog(self):
        stream = b"73 <40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum dolor sit.103 <40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing.127 <40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'odio' b'ut' b'a'.63 <40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum."
        logs = SyslogSplitter(self.conf, self.statsdClient).split(stream)
        self.assertEqual(logs, [
            b"<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum dolor sit.",
            b"<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing.",
            b"<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'odio' b'ut' b'a'.",
            b"<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum."
        ])

    def test_splitFakeLog2(self):
        stream = b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.\n64 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.\n179 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'arcu' b'mi' b'et' b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.\n104 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing."
        logs = SyslogSplitter(self.conf, self.statsdClient).split(stream)
        self.assertEqual(logs, [
            b"<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.",
            b"<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            b"<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'arcu' b'mi' b'et' b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.",
            b"<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing."
        ])

    def test_splitAndTruncate(self):
        stream = b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.\n64 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.\n179 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'arcu' b'mi' b'et' b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.\n104 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing."
        self.conf.truncate_activated = True
        self.conf.truncate_max_msg_length = 100
        logs = SyslogSplitter(self.conf, self.statsdClient).split(stream)
        self.assertEqual(logs, [
            b"<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipisci __TRUNCATED__",
            b"<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            b"<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipisci __TRUNCATED__",
            b"<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipisci __TRUNCATED__"
        ])



if __name__ == '__main__':
    unittest.main()