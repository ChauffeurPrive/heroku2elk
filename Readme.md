# Heroku 2 ELK

This service is a thin layer between http logs and rabbitmq.
It is responsible for:
 * handle Heroku HTTP drain with syslog formatted payload and split them
 * handle Mobile HTTP json logs
 * forward them to logstash

Heroku is using a syslog formatted payload with multiple log lines per request, hard to split in a logstash input plugin.
https://devcenter.heroku.com/articles/log-drains#https-drains
https://tools.ietf.org/html/rfc6587#section-3.4.1

This service is written in python and based on Tornado web server (http://www.tornadoweb.org) for the scalability.

## How to run it ?

### Requirements

Install the following requirements:
```
pip install -r requirements.txt
```
### Run
You're ready to go!

```
 venv/bin/gunicorn -b :8080 -w 4 -k tornado --max-requests 100000000 main:app 
```

### Development

#### Unit-testing

```
py.test tests/
```

#### Fake Log Generator
##### Requirements

Install the following requirements
```
pip install -r dev.txt
```
##### What is it for?
To send fake heroku logs, to debug

```
python -m src.fakelogGenerator
```
