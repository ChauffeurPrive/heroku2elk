from logging import getLogger
from linecache import getline
from os import sep
from tracemalloc import start, Filter, take_snapshot


def record_top(key_type='lineno', limit=10):
    kb = 2**10
    logger = getLogger("tornado.application")
    record = logger.info
    snapshot = take_snapshot()
    snapshot = snapshot.filter_traces((
        Filter(False, "<frozen importlib._bootstrap>"),
        Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    record("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        # replace "/path/to/module/file.py" with "module/file.py"
        filename = sep.join(frame.filename.split(sep)[-2:])
        record("#%s: %s:%s: %.1f KiB" % (index, filename, frame.lineno,
                                         stat.size / kb))
        line = getline(frame.filename, frame.lineno).strip()
        if line:
            record('    %s' % line)

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        record("%s other: %.1f KiB" % (len(other), size / kb))
    total = sum(stat.size for stat in top_stats)
    record("Total allocated size: %.1f KiB" % (total / kb))
