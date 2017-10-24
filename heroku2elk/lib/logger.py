import logging
from logging.handlers import SysLogHandler, RotatingFileHandler


def configure_logger():
    """
    configure logger object with handlers
    """
    app_log = logging.getLogger("tornado.application")
    app_log.setLevel(logging.INFO)
    default_formatter = logging.Formatter('%(asctime)-15s %(message)s')

    #  syslog
    handler = SysLogHandler(address='/dev/log')
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter(
        'heroku2Logstash: { "loggerName":"%(name)s", '
        '"asciTime":"%(asctime)s", "pathName":"%(pathname)s", '
        '"logRecordCreationTime":"%(created)f", '
        '"functionName":"%(funcName)s", '
        '"levelNo":"%(levelno)s", "lineNo":"%(lineno)d", "time":"%(msecs)d", '
        '"levelName":"%(levelname)s",'
        '"message":"%(message)s"}')
    handler.formatter = formatter
    app_log.addHandler(handler)

    # console log
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.formatter = default_formatter
    app_log.addHandler(ch)

    # File log (max 10GB: 10*2**30B)
    file_handler = RotatingFileHandler('Heroku2Logstash.log',
                                       maxBytes=10*2**30, backupCount=10)
    file_handler.setLevel(logging.INFO)
    file_handler.formatter = default_formatter
    app_log.addHandler(file_handler)
    return app_log