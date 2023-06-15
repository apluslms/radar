FROM --platform=$TARGETPLATFORM apluslms/service-base:django-1.18

# Set container related configuration via environment variables
ENV CONTAINER_TYPE="radar" \
    RADAR_LOCAL_SETTINGS="/srv/radar-cont-settings.py" \
    RADAR_SECRET_KEY_FILE="/local/radar/secret_key.py"

COPY docker/rootfs /
COPY . /srv/radar

RUN : \
 && apt_install \
      curl \
      htop \
      netcat \
      vim \
      curl \
      wget \
      less \
\
  # create user
 && adduser --system --no-create-home --disabled-password --gecos "A+ radar service,,," --home /srv/radar --ingroup nogroup radar \
 && chown radar.nogroup /srv/radar \
\
 && cd /srv/radar \
  # prebuild .pyc files
 && python3 -m compileall -q . \
\
  # install requirements, remove the file, remove unrequired locales and tests
 && pip_install \
      -r requirements.txt \
      "flower ~= 1.2.0" \
      "django-debug-toolbar >= 3.8.1" \
 && rm requirements.txt \
 && find /usr/local/lib/python* -type d -regex '.*/locale/[a-z_A-Z]+' -not -regex '.*/\(en\|fi\|sv\)' -print0 | xargs -0 rm -rf \
 && find /usr/local/lib/python* -type d -name 'tests' -print0 | xargs -0 rm -rf \
\
  # preprocess
 && export \
    RADAR_SECRET_KEY="-" \
    RADAR_BASE_URL="-" \
    RADAR_CACHES="{\"default\": {\"BACKEND\": \"django.core.cache.backends.dummy.DummyCache\"}}" \
 && create-db.sh radar radar django-migrate.sh \
\
  # create celery backend location
 && mkdir -p /var/celery/results \
 && chown radar:nogroup /var/celery/results \
 && :


WORKDIR /srv/radar
EXPOSE 5555
EXPOSE 8001
CMD [ "python3", "-m", "debugpy", "--listen", "0.0.0.0:5678", "manage.py", "runserver", "0.0.0.0:8001" ]
