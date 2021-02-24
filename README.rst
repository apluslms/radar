Radar
=====

Automatic similarity analysis for source code and other tokenizable data.

Accepts HTTP hook requests that record new data submissions, which are then fetched from some provider API.
Recorded submissions will be processed asynchronously using Celery.
Submission sources are matched using the `greedy string tiling`_ library, which also provides a simple Celery interface.

Similarity matches will form submission groups for easy evaluation of the cases.
Views are provided to follow submitters over series of exercises.

`Development instructions`_ as well as
`installation instructions`_ are located in the doc directory.

Requirements
------------
* Python 3.5
* RabbitMQ 3.5
* Django 2.2
* Celery 4.1
* Memcached 1.5
* and other Python packages, see ``requirements.txt``

Optional
........

* Scala 2.11 (for Scala tokenizer)
* Node.js 4.2 (for JavaScript tokenizer)
* Esprima 4.0 (for JavaScript tokenizer)
* Write access to ``submission_files/`` (By default, submission files are downloaded when needed and stay only in main memory)

Directory structure
-------------------

* ``accounts/`` Django app: user models that have A+ API access
* ``data/`` Django app: models, commands and cron
* ``ltilogin/`` Django app: handling user creation on first login using LTI access
* ``matcher/`` Task definitions for matching token string
* ``provider/`` Data integrations for different sources
* ``radar/`` Django main
* ``review/`` Django app: reviewer interface
* ``static/`` Django static files
* ``templates/`` Django main level templates
* ``tokenizer/`` Tokenizers for supported data formats

Built on open source
--------------------
* https://www.djangoproject.com/
* http://jquery.com/
* http://getbootstrap.com/
* https://github.com/tzangms/django-bootstrap-form
* https://highlightjs.org/

Configuring with A+
-------------------
Radar can be added to `A+`_ as an external service that uses LTI login for authentication and API access.

Below is a brief checklist of the steps required.

* Log into the A+ admin page in your A+ service and under EXTERNAL_SERVICES, add a new LTI service.
* Set URL to ``<Radar>/auth/lti_login``, where ``<Radar>`` is the URL where you host Radar.
* Check ``Enable api access``.
* Generate the consumer key and secret with `Django LTI login`_ (in the Radar repo): ``python manage.py add_lti_key --desc aplus``.
* Verify in your Django settings file that ``PROVIDERS["a+"]["host"]`` matches the URL of your A+ service.
* Radar can now be added into an A+ course instance menu as an external service.

If you want Radar to fetch new submissions automatically as they are submitted into A+, you can add a course hook into A+.

* After adding Radar into an A+ course instance as a menu item, navigate to the Radar service using the URL, which automatically configures a new Radar course instance to match the instance in A+.
* Choose the course you want to add a hook for.
* Using the current URL, ``<Radar>/<course-instance-key>``, append ``/hook-submission`` to produce something like ``<Radar>/<course-instance-key>/hook-submission``. This is the submission hook url that A+ sends a POST to each time a new submission is created.
* Log into the A+ admin page in your A+ service and under COURSE, add a new entry into Course hooks.

Original author
---------------

teemu.t.lehtinen@aalto.fi, 9.2.2015


.. _Development instructions: doc/DEVELOPMENT.md
.. _installation instructions: doc/INSTALL.md
.. _A+: https://github.com/apluslms/a-plus
.. _Django LTI login: https://github.com/Aalto-LeTech/django-lti-login
.. _greedy string tiling: https://github.com/Aalto-LeTech/greedy-string-tiling

