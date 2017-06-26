import requests
import datetime
from loremipsum import get_sentence
import random
import uuid
import threading
import time
import pytz


# Generates and send a fake request (aggregating n fake log lines)
class RequestGenerator:
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


# Generates a fake log line
class FakeLog:
    def __init__(self):
        self.date = datetime.datetime.now().replace(microsecond=0, tzinfo=pytz.utc)
        self.text = get_sentence(True)
        self.app = 'ponzi'
        self.dyno = 'web.1'
        self.msg = '<40>1 {} host {} {} - {}\n'.format(self.date.isoformat(), self.app, self.dyno, self.text)

    def encode(self):
        msg = self.msg.encode('utf-8')
        size = len(msg)
        msg_header = '{} '.format(size).encode('utf-8')
        return msg_header + msg


# Infinite message generation worker
class GenWorker:
    def __init__(self, url):
        self.shouldStop = False
        self.stats = {'sent': 0, 'timeout': 0}
        self.url = url

    def get_stats(self):
        return self.stats

    def run(self):
        gen = RequestGenerator(self.url)
        while self.shouldStop is False:
            r, msg = gen.send_random_request()
            if not r:
                self.stats['timeout'] += 1
                continue
            if r.status_code != 200:
                print('status_code != 200', r, msg)
            self.stats['sent'] += 1
            key = str(r.status_code)
            if key not in self.stats:
                self.stats[key] = 1
            else:
                self.stats[key] += 1


# helper func to start a thread
def start_thread(obj):
    print('start thread', obj)
    sender = threading.Thread(target=obj.run)
    sender.start()
    return obj, sender


# helper func to stop a dedicated thread
def stop_thread(o):
    obj, t = o
    print('stop thread', obj, t)
    obj.shouldStop = True
    t.join()


# generate stats
def get_stats(worker):
    stats = worker.get_stats()
    return stats['sent'], stats['timeout']


# run the fake log generator targeting the given 'url' with 'clientCount' clients
def run(url, client_count):
    workers = [GenWorker(url) for _ in range(client_count)]
    threads = list(map(start_thread, workers))

    try:
        last_sent = 0
        last_timeout = 0
        while True:
            time.sleep(1)
            zipped = list(zip(*map(get_stats, workers)))
            sent = sum(zipped[0]) - last_sent
            timeout = sum(zipped[1]) - last_timeout
            print('last second stats, sent:', sent, 'timeout:', timeout)
            last_sent = sum(zipped[0])
            last_timeout = sum(zipped[1])

    except KeyboardInterrupt:
        list(map(stop_thread, threads))

if __name__ == '__main__':
    run('http://127.0.0.1:8080/heroku/v1/toto', 1)
