Radar
=====

Plagiate detector for source code and other tokenizable data.

Accepts HTTP hook requests that record new data submissions. Alternatively
submissions can be loaded from command line. Cron task will sequentially
complete provider tasks, tokenize submissions and match them against all
previously matched submissions.

Similarity matches will form submission groups for easy evaluation of the
cases. Views are provided to follow submitters over series of exercises.

teemu.t.lehtinen@aalto.fi, 9.2.2015

Requirements
------------
* Python 3.5
* Django 2.0

Optional
........

* Scala 2.11 (for Scala tokenizer)
* Node.js 4.2 (for JavaScript tokenizer)
* Esprima 4.0 (for JavaScript tokenizer)
* Write access to ``submission_files/`` (By default, submission files are downloaded when needed and stay only in main memory)

Directory structure
-------------------
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

.. _A+: https://github.com/Aalto-LeTech/a-plus
.. _Django LTI login: https://github.com/Aalto-LeTech/django-lti-login
