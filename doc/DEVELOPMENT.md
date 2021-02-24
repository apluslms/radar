# Radar

This document guides into different development tasks without installing and running the complete production system on a personal workstation.

The core of the system is written in [Python 3](https://www.python.org/) and installing that is the minimum requirement. Then, clone the project and get started!

## Set up python virtual environment

Following terminal commands create an environment and install required packages.

Linux & OS X:<br>
`python3 -m virtualenv -p python3 py_venv`<br>
`source py_venv/bin/activate`<br>
`pip install -r requirements.txt`<br>
Windows:<br>
`C:\Python35\python -m venv py_venv`<br>
`py_venv\Scripts\activate.bat`<br>
`pip install -r requirements.txt`

When starting a new terminal for development, access the same virtual enviroment by enterint the activate-command alone (2nd line).

## Django

The repository contains a [Django web framework](https://www.djangoproject.com/) project where directory `radar` is the main module. Django offers a command line interface for controlling the system and this project further extends it with custom commands. Executing `python manage.py` lists all commands.

Useful maintenance actions:

1. `python manage.py migrate`<br>
   Creates/updates changed database models (default settings store data in filesystem `db.sqlite3`).
2. `python manage.py createsuperuser`<br>
   Creates a user that can login to the web UI.

Useful testing actions:

1. `python manage.py runserver`<br>
   Runs the web UI in http://localhost:8000/ as well as Django database admin in http://localhost:8000/admin/
2. `python manage.py loadsubmissions testcourse/exercise1 user1/sub1 user1/sub2 user2/sub1 ...`<br>
   Loads file submissions into analysis queue from the given directories (wildcards should work too, e.g. data/rainfall/2*/*). Each submission is a single directory - even if there is only one submitted file per submission.
3. `python manage.py matchsubmissions testcourse/exercise1`<br>
   Processes file submissions from the analysis queue. Beware, time requirement is exponential so
   better start with ten rather than hundred submissions.

Tip: create empty file `radar/local_settings.py` in order to get rid of extra warnings.
