FROM apluslms/service-base:django-1.9

# Set container related configuration via environment variables
ENV CONTAINER_TYPE="radar" \
    RADAR_LOCAL_SETTINGS="/srv/radar-cont-settings.py" \
    RADAR_SECRET_KEY_FILE="/local/radar/secret_key.py"

COPY docker/rootfs /

ARG BRANCH=container
RUN : \
 && apt_install \
      curl \
\
  # create user
 && adduser --system --no-create-home --disabled-password --gecos "A+ radar service,,," --home /srv/radar --ingroup nogroup radar \
 && mkdir /srv/radar && chown radar.nogroup /srv/radar \
\
 && cd /srv/radar \
  # clone and prebuild .pyc files
 && git clone --quiet --single-branch --branch $BRANCH https://github.com/gehock/radar.git . \
 && (echo "On branch $(git rev-parse --abbrev-ref HEAD) | $(git describe)"; echo; git log -n5) > GIT \
 && rm -rf .git \
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
 && :


WORKDIR /srv/radar
EXPOSE 8001
CMD [ "manage", "runserver", "0.0.0.0:8001" ]
