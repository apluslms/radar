# Radar

## System

As root

 1. Install required packages

    ```shell
    apt install \
        uwsgi-core \
        uwsgi-plugin-python3 \
        python3-virtualenv \
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
    python3 -m virtualenv --python python3 venv
    source ~/venv/bin/activate
    git clone https://github.com/Aalto-LeTech/radar.git
    cd radar
    # Check out to whichever version is desired
    git checkout v0.0
    pip install -r requirements.txt
    # This extra library is required if postgres is used as the database
    pip install psycopg2

    cp radar/local_settings.example.py radar/local_settings.py
    # Add correct hostname and admin email address to settings
    editor radar/local_settings.py

    # Generate the secret key
    python - << EOF > ~/radar/radar/secret_key
    from django.core.management.utils import get_random_secret_key
    print(get_random_secret_key())
    EOF
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
    cp doc/uwsgi-radar.ini /srv/radar/uwsgi-radar.ini
    cp doc/radar-web-uwsgi.service /etc/systemd/system
    systemctl daemon-reload
    systemctl enable radar-web-uwsgi
    systemctl start radar-web-uwsgi
    ```

 2. NGINX configuration

    ```shell
    cp doc/radar-nginx.conf /etc/nginx/sites-available/radar.conf
    ln -s /etc/nginx/sites-available/radar.conf \
        /etc/nginx/sites-enabled/radar.conf
    # Add correct hostname and SSL certificate path to the config
    editor /etc/nginx/sites-available/radar.conf
    systemctl reload nginx
    ```

 3. Install celery workers

    Worker `radar-celery_matcher` can also be run inside Kubernetes. This
    requires some extra configuration, including editing the queue name in
    `radar/local_settings.py`.

    ```shell
    cp doc/celery-systemd/radar-celery{_db,_io,_matcher,}.service \
    /etc/systemd/system
    systemctl daemon-reload
    systemctl enable radar-celery{_db,_io,_matcher,}
    systemctl start radar-celery{_db,_io,_matcher,}
    ```
