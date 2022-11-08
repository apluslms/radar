# Radar

This document describes installation for production use.

## System

As root

 1. Install required packages

    ```shell
    apt install \
        python3-venv \
        python3-dev \
        memcached \
        rabbitmq-server \
        nginx \
        postgresql \
        libpq-dev \
        build-essential
    ```

 2. Create a new user for radar

    ```shell
    adduser --system --group \
        --shell /bin/bash --home /srv/radar \
        --gecos "A-plus radar service" \
        radar
    ```

 3. Create a database and add permissions

    ```shell
    sudo -Hu postgres createuser radar
    sudo -Hu postgres createdb -O radar radar
    ```

 4. Create a run directory

    ```shell
    echo "d /run/radar 0750 radar www-data - -" \
        | tee /etc/tmpfiles.d/radar.conf > /dev/null
    systemd-tmpfiles --create
    ```

## Django

 1. Change to the service user

    ```shell
    su - radar
    ```

 2. Clone the application

    ```shell
    # Run as user radar in /srv/radar
    python3 -m venv venv
    source ~/venv/bin/activate
    git clone https://github.com/Aalto-LeTech/radar.git
    cd radar
    # Check out to whichever version is desired
    git checkout v0.0
    pip install -r requirements-prod.txt
    pip install -r requirements.txt

    cp radar/local_settings.example.py radar/local_settings.py
    # Add correct hostname and admin email address to settings
    editor radar/local_settings.py

    # The secret key will be automatically generated if
    # radar/secret_key.py is missing

    python manage.py migrate
    python manage.py collectstatic
    ```

    See README.rst for more detailed instructions about setting up A+

    ```shell
    python manage.py add_lti_key --desc aplus
    ```

    Select course -> Edit course -> Menu -> Add -> Select radar

    Click radar link in menu => Creates course in radar

## uWSGI, NGINX and Celery workers

As root

```shell
cd ~radar/radar
```

 1. Install uWSGI configuration

    ```shell
    cp ~radar/radar/doc/uwsgi-radar.ini ~radar/uwsgi-radar.ini
    chown radar:radar ~radar/uwsgi-radar.ini
    cp ~radar/radar/doc/radar-web-uwsgi.service /etc/systemd/system
    systemctl daemon-reload
    systemctl enable radar-web-uwsgi
    systemctl start radar-web-uwsgi
    ```

 2. NGINX configuration

    ```shell
    apt-get install nginx
    # Set custom name here if $(hostname) is not correct
    name=$(hostname)
    sed -e "s/__HOSTNAME__/$name/g" ~radar/radar/doc/radar-nginx.conf > \
        /etc/nginx/sites-available/$name.conf
    ln -s ../sites-available/$name.conf /etc/nginx/sites-enabled/$name.conf
    # Edit /etc/nginx/sites-available/$name.conf if necessary (set TLS
    # certificate path)
    editor /etc/nginx/sites-available/$name.conf
    systemctl reload nginx
    ```

 3. Install celery workers

    Worker `radar-celery_matcher` can also be run inside Kubernetes. This
    requires some extra configuration, including editing the queue name in
    `radar/local_settings.py`.

    ```shell
    cp ~radar/radar/doc/celery-systemd/radar-celery{,_db,_io,_matcher}.service \
        /etc/systemd/system
    systemctl daemon-reload
    systemctl enable radar-celery{,_db,_io,_matcher}
    systemctl start radar-celery{,_db,_io,_matcher}
    ```

## RabbitMQ configuration

The RabbitMQ messages between Radar and the matchlib can become large when there
are several submissions to be analaysed. If the message size exceeds the default
maximum message size (128 MB), it will be dropped and the Radar task never completes.
Therefore, it is recommended to increase the RabbitMQ maximum message size,
by adding the following line to `/etc/rabbitmq/rabbitmq.conf` (for doubling the max.
message size to 256 MB):

    max_message_size = 268435456
