# Heroku 2 ELK

This service is a thin layer between heroku http drains and logstash.
It is responsible for:
 * handle Heroku HTTP drain with syslog formatted payload
 * split them
 * forward them to logstash

Heroku is using a syslog formatted payload with multiple log lines per request, hard to split in a logstash input plugin.
https://devcenter.heroku.com/articles/log-drains#https-drains
https://tools.ietf.org/html/rfc6587#section-3.4.1

This service is written in python and based on the well-known Tornado web server (http://www.tornadoweb.org) for the scalability.

## How to run it ?

### Requirements

Install the following requirements:
```
pip install -r requirements.txt
```
### Run
You're ready to go!

```
python -m src.heroku2Logstash
```

### Development

#### Unit-testing

```
python -m unittests
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
