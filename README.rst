Radar
-----

Plagiate detector for source code and other tokenizable data.

Accepts HTTP hook requests that record new data submissions. Alternatively
submissions can be loaded from command line. Cron task will sequentially
complete provider tasks, tokenize submissions and match them against all
previously matched submissions.

Similarity matches will form submission groups for easy evaluation of the
cases. Views are provided to follow submitters over series of exercises.

teemu.t.lehtinen@aalto.fi, 9.2.2015

Requirements
............
* Python 3
* Django 1.7
* Scala 2.11 (for Scala tokenizer)
* Write access to ``submission_files/``

Directory structure
...................
* ``radar/`` Django main
* ``data/`` Django app: models, commands and cron
* ``review/`` Django app: reviewer interface
* ``bootstrapform/`` Django app: formats Django forms for Bootstrap
* ``provider/`` Data integrations for different sources
* ``tokenizer/`` Tokenizers for supported data formats
* ``matcher/`` Algorithms for matching token strings
* ``templates/`` Django main level templates
* ``static/`` Django static files

Built on open source
....................
* https://www.djangoproject.com/
* http://jquery.com/
* http://getbootstrap.com/
* https://github.com/tzangms/django-bootstrap-form
* https://highlightjs.org/

Configuring with A+
...................
Radar can be added to `A+`_ as an external service that uses LTI login for authentication.
Enabling Radar on a course is then simply a matter of adding the Radar menu link from the `A+`_ user UI.

Below is a brief checklist of the steps required.

* Generate LTI-login tokens with `Django LTI login`_
  E.g. ``python manage.py add_lti_key --desc aplus``
* Add Radar into A+ as an LTI service: append ``auth/lti_login`` to the Radar URL, check ``Enable api access`` and use they recently generated key and secret.
  E.g. log into A+ admin and under EXTERNAL_SERVICES, choose Lti services.
* Verify in your Django settings file  that ``PROVIDERS["a+"]["host"]`` matches the URL of your A+ service and ``PROVIDERS["a+"]["token"]`` matches an existing auth token in A+.
  E.g. ``radar/local_settings.py`` or ``radar/settings.py``.

.. _A+: https://github.com/Aalto-LeTech/a-plus
.. _Django LTI login: https://github.com/Aalto-LeTech/django-lti-login
