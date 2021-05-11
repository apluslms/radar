#!/bin/sh -eu

# Ensure LTI key
if ! setuidgid $USER python3 manage.py list_lti_keys -k testradar 2>/dev/null | grep -qsF testradar; then
    setuidgid $USER python3 manage.py add_lti_key -k testradar -s testradar -d "test key" 2>/dev/null
else
    setuidgid $USER python3 manage.py list_lti_keys -k testradar 2>/dev/null
fi

# Export LTI key for A+
mkdir -p /data/aplus/lti-services-in/
setuidgid $USER python3 \
    manage.py export_for_aplus -k testradar -l Radar -i send -b http://$(hostname -i):8001 \
    > /data/aplus/lti-services-in/radar.json
