import unittest
from src.lib.syslogSplitter import split
from src.config import TruncateConfig


class SyslogSplitterTest(unittest.TestCase):
    def setUp(self):
        self.conf = TruncateConfig()

    def test_splitHerokuSample(self):
        stream = b"83 <40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed " \
                 b"from starting to up\n119 <40>1 2017-06-14T13:53:26+00:00 host app web.3" \
                 b" - Starting process with command `bundle exec rackup config.ru -p 24405`"
        logs = split(stream, self.conf)
        self.assertEqual(logs, [
            "<40>1 2017-06-14T13:52:29+00:00 host app web.3 - State changed from starting to up",
            "<40>1 2017-06-14T13:53:26+00:00 host app web.3 - Starting "
            "process with command `bundle exec rackup config.ru -p 24405`"
        ])

    def test_splitHerokuSampleWithoutCarriageReturn(self):
        stream = b"82 <40>1 2012-11-30T06:45:29+00:00 host app web.3 - State changed from " \
                 b"starting to up118 <40>1 2012-11-30T06:45:26+00:00 host app web.3 - Starting" \
                 b" process with command `bundle exec rackup config.ru -p 24405`"
        logs = split(stream, self.conf)
        self.assertEqual(logs, [
            "<40>1 2012-11-30T06:45:29+00:00 host app web.3 - State changed from starting to up",
            "<40>1 2012-11-30T06:45:26+00:00 host app web.3 - Starting process"
            " with command `bundle exec rackup config.ru -p 24405`"
        ])

    def test_splitFakeLog(self):
        stream = b"73 <40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum dolor " \
                 b"sit.103 <40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum " \
                 b"dolor sit amet, consecteteur adipiscing.127 <40>1 2017-06-21T16:37:25+00:00" \
                 b" host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit" \
                 b" b'odio' b'ut' b'a'.63 <40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 -" \
                 b" Lorem ipsum."
        logs = split(stream, self.conf)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum dolor sit.",
            "<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem"
            " ipsum dolor sit amet, consecteteur adipiscing.",
            "<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem"
            " ipsum dolor sit amet, consecteteur adipiscing elit b'odio' b'ut' b'a'.",
            "<40>1 2017-06-21T16:37:25+00:00 host ponzi web.1 - Lorem ipsum."
        ])

    def test_splitFakeLog2(self):
        stream = b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit " \
                 b"amet, consecteteur adipiscing elit b'quis' b'ad'.\n64 <40>1 2017-06-21T17:02:55+00:00" \
                 b" host ponzi web.1 - Lorem ipsum.\n179 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1" \
                 b" - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'arcu' b'mi' b'et' b'a'" \
                 b" b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.\n104 <40>1 2017-06-21T17:02:55+00:00 host" \
                 b" ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing."
        logs = split(stream, self.conf)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, "
            "consecteteur adipiscing elit b'quis' b'ad'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet,"
            " consecteteur adipiscing elit b'arcu' b'mi' b'et' b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet,"
            " consecteteur adipiscing."
        ])

    def test_splitAndTruncate(self):
        stream = b"123 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet," \
                 b" consecteteur adipiscing elit b'quis' b'ad'.\n64 <40>1 2017-06-21T17:02:55+00:00 host" \
                 b" ponzi web.1 - Lorem ipsum.\n179 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - " \
                 b"Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'arcu' b'mi' b'et' b'a' " \
                 b"b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.\n104 <40>1 2017-06-21T17:02:55+00:00 " \
                 b"host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing."
        self.conf.truncate_activated = True
        self.conf.truncate_max_msg_length = 100
        logs = split(stream, self.conf)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__  amet, "
            "consecteteur adipiscing elit b'quis' b'ad'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ b'a' "
            "b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ rem "
            "ipsum dolor sit amet, consecteteur adipiscing."
        ])

    def test_noTruncateStacktrance(self):
        stream = b"140 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - {'stack':'toto'} Lorem ipsum " \
                 b"dolor sit amet, consecteteur adipiscing elit b'quis' b'ad'.\n64 <40>1 " \
                 b"2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.\n179 <40>1 2017-06-21T17:02:55+00:00" \
                 b" host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing elit b'arcu' b'mi'" \
                 b" b'et' b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.\n104 <40>1 2017-06-21T17:02:55+00:00 " \
                 b"host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur adipiscing."
        self.conf.truncate_activated = True
        self.conf.truncate_max_msg_length = 100
        logs = split(stream, self.conf)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - {'stack':'toto'} Lorem ipsum dolor sit amet,"
            " consecteteur adipiscing elit b'quis' b'ad'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ b'a' b'vel' b'ad' "
            "b'taciti' b'a' b'facilisi' b'a'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ rem ipsum dolor sit "
            "amet, consecteteur adipiscing."
        ])

    def test_removeToken(self):
        stream = b"140 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet," \
                 b" consecteteur adipiscing elit b'quis' b'ad'.{\"token\":\"sdfs\"} \n64 <40>1" \
                 b" 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.\n179 <40>1 " \
                 b"2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur " \
                 b"adipiscing elit b'arcu' b'mi' b'et' b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'.\n" \
                 b"104 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, " \
                 b"consecteteur adipiscing."
        self.conf.truncate_activated = True
        self.conf.truncate_max_msg_length = 100
        logs = split(stream, self.conf)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ elit b'quis' b'ad'."
            "{\"token\":\"__TOKEN_REPLACED__\"} ",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ b'a' b'vel' b'ad' b'taciti'"
            " b'a' b'facilisi' b'a'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ rem ipsum dolor sit amet,"
            " consecteteur adipiscing."
        ])

    def test_removeToken2(self):
        stream = b"145 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet," \
                 b" consecteteur adipiscing elit b'quis' b'ad'.{\"toto_token\":\"sdfs\"} \n64 <40>1 " \
                 b"2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.\n179 <40>1 " \
                 b"2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet, consecteteur" \
                 b" adipiscing elit b'arcu' b'mi' b'et' b'a' b'vel' b'ad' b'taciti' b'a' b'facilisi' b'a'." \
                 b"\n104 <40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum dolor sit amet," \
                 b" consecteteur adipiscing."
        self.conf.truncate_activated = True
        self.conf.truncate_max_msg_length = 100
        logs = split(stream, self.conf)
        self.assertEqual(logs, [
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ b'quis' b'ad'."
            "{\"toto_token\":\"__TOKEN_REPLACED__\"} ",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - Lorem ipsum.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ b'a' b'vel' b'ad'"
            " b'taciti' b'a' b'facilisi' b'a'.",
            "<40>1 2017-06-21T17:02:55+00:00 host ponzi web.1 - __TRUNCATED__ rem ipsum dolor sit amet,"
            " consecteteur adipiscing."
        ])

if __name__ == '__main__':
    unittest.main()
