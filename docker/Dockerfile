FROM apluslms/service-base:django-1.9

# Set container related configuration via environment variables
ENV CONTAINER_TYPE="aplus" \
    APLUS_LOCAL_SETTINGS="/srv/aplus-cont-settings.py" \
    APLUS_SECRET_KEY_FILE="/local/aplus/secret_key.py"

COPY rootfs /

ARG BRANCH=v1.8.1
RUN : \
 && apt_install \
      python3-lxml \
      python3-lz4 \
      python3-pillow \
\
  # create user
 && adduser --system --no-create-home --disabled-password --gecos "A+ webapp server,,," --home /srv/aplus --ingroup nogroup aplus \
 && mkdir /srv/aplus && chown aplus.nogroup /srv/aplus \
\
 && cd /srv/aplus \
  # clone and prebuild .pyc files
 && git clone --quiet --single-branch --branch $BRANCH https://github.com/apluslms/a-plus.git . \
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
    APLUS_SECRET_KEY="-" \
    APLUS_BASE_URL="-" \
    APLUS_CACHES="{\"default\": {\"BACKEND\": \"django.core.cache.backends.dummy.DummyCache\"}}" \
 && python3 manage.py compilemessages 2>&1 \
 && create-db.sh aplus aplus django-migrate.sh \
 && :


WORKDIR /srv/aplus
EXPOSE 8000
CMD [ "manage", "runserver", "0.0.0.0:8000" ]
