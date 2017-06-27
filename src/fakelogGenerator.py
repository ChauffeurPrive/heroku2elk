import requests
import datetime
from loremipsum import get_sentence
import random
import uuid
import threading
import time
import pytz


class RequestGenerator:
    """
    Generates and send a fake request (aggregating n fake log lines)
    """
    def __init__(self, url):
        self.url = url
        self.frameCount = 0
        self.drainId = uuid.uuid4()
        self.headers = {
            'Content-type': 'application/logplex-1',
            'Logplex-Drain-Token': str(self.drainId),
            'User-Agent': 'Logplex/v72'
        }

    def send_random_request(self):
        """
        send a fake request using a random number of logs in the payload
        """
        msg_count = random.randrange(1, 10)
        payload = bytes()
        for n in range(msg_count):
            payload += FakeLog().encode()

        self.headers['Logplex-Msg-Count'] = str(msg_count)
        self.headers['Logplex-Frame-Id'] = str(self.frameCount)
        self.frameCount += 1
        try:
            return requests.post(self.url, data=payload, headers=self.headers), payload
        except requests.exceptions.Timeout:
            return None, payload


class FakeLog:
    """
    Generates a fake log line
    """
    def __init__(self):
        self.date = datetime.datetime.now().replace(microsecond=0, tzinfo=pytz.utc)
        self.text = get_sentence(True)
        self.app = 'DummyAppName'
        self.dyno = 'web.1'
        self.msg = '<40>1 {} host {} {} - {}\n'.format(self.date.isoformat(), self.app, self.dyno, self.text)

    def encode(self):
        msg = self.msg.encode('utf-8')
        size = len(msg)
        msg_header = '{} '.format(size).encode('utf-8')
        return msg_header + msg


class GenWorker:
    """
    Infinite message generation worker
    """
    def __init__(self, url):
        self.shouldStop = False
        self.stats = {'sent': 0, 'timeout': 0}
        self.url = url

    def get_stats(self):
        return self.stats

    def run(self):
        gen = RequestGenerator(self.url)
        while self.shouldStop is False:
            self.stats['sent'] += 1
            r, msg = gen.send_random_request()
            if not r:
                self.stats['timeout'] += 1
                continue
            if r.status_code != 200:
                print('status_code != 200', r, msg)


def start_thread(obj):
    """
    helper func to create and start a thread
    :param obj: the target object
    :return: a tuple with the worker, and the created started thread
    """
    sender = threading.Thread(target=obj.run)
    sender.start()
    return obj, sender


def stop_thread(o):
    """
    helper func to stop a dedicated thread
    :param o: a tuple containing the worker and the thread
    :return:
    """
    obj, t = o
    obj.shouldStop = True
    t.join()


def get_stats(worker):
    """
    generate statistics on a given worker and return them
    :param worker: a worker object
    :return:
    """
    stats = worker.get_stats()
    return stats['sent'], stats['timeout']


def run(url, client_count):
    """
    run the fake log generator targeting the given 'url' with 'clientCount' clients
    :param url: the target url
    :param client_count: number of client to create (nb of threads)
    :return:
    """
    workers = [GenWorker(url) for _ in range(client_count)]
    threads = list(map(start_thread, workers))

    try:
        last_sent = 0
        last_timeout = 0
        while True:
            time.sleep(1)
            [total_sent, total_timeout] = [sum(el) for el in zip(*map(get_stats, workers))]
            print('last second stats, sent:', total_sent - last_sent, 'timeout:', total_timeout - last_timeout)
            last_sent, last_timeout = total_sent, total_timeout

    except KeyboardInterrupt:
        list(map(stop_thread, threads))

if __name__ == '__main__':
    run('http://127.0.0.1:8080/heroku/v1/DummyAppName', 1)
