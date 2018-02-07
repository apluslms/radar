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
