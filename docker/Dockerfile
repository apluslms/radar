FROM apluslms/service-base:django-1.9

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
 && pip_install \
      debugpy \
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
 && pip_install -r requirements.txt \
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
# The most recent PyPi release of flower doesn't support celery>=5
# See https://github.com/mher/flower/issues/1109
RUN pip_install git+https://github.com/mher/flower#egg=flower
EXPOSE 5555
EXPOSE 8001
CMD [ "python3", "-m", "debugpy", "--listen", "0.0.0.0:5678", "manage.py", "runserver", "0.0.0.0:8001" ]
