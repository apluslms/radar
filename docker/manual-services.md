# Launching misc services manually, for debug purposes

The commands in this file are not meant to be used as part of a normal
development process, they're only for debugging the behaviour of the container
itself. The services mentioned in this document should launch automatically
when the container is created if the image is working properly.

## Usage

1. Build the image with `build.sh`
2. Launch with either `docker-compose up -d` within this repository, or
   `docker-up.sh` in [aplus-manual](https://github.com/apluslms/aplus-manual) or
   similar
3. Connect to the container with `docker-compose exec radar bash`

## epmd

```shell
su - rabbitmq
/usr/bin/epmd -d -address ""
```

## rabbit

```shell
su - rabbitmq
/usr/lib/rabbitmq/bin/rabbitmq-server
```

## rabbit logs

```shell
cd /var/log/rabbitmq
tail -f rabbit\@localhost.log
```

## celery

```shell
su - radar
export RADAR_SECRET_KEY_FILE=/local/radar/secret_key.py RADAR_LOCAL_SETTINGS=/srv/radar-cont-settings.py
celery --app radar worker --loglevel=debug --concurrency 1 --hostname worker_main@radar

python3 -m debugpy --listen 0.0.0.0:5679 -m celery --app radar worker \
    --loglevel=debug --concurrency 1 --hostname worker_main@radar

celery -A radar flower --address=0.0.0.0

s6-svc -d /run/s6/services/celery
```
