# Radar Testing Guide

This document provides a guide to create and run end-to-end tests for Radar using [Playwright](https://playwright.dev/python/).

## Set up environment

Make sure everything is set up following this [Radar development guide](https://github.com/apluslms/radar/blob/master/doc/DEVELOPMENT.md) before continuing.

1. Run Python environment: `source py_venv/bin/activate`

2. Before testing create super user using: `python manage.py createsuperuser`<br>
    Username: `Username`<br>
    Email: `Username@email.com`<br>
    Password: `Password`<br>

3. Run server: `python manage.py runserver`

4. Load submissions: `./run_loadsubmissions.sh ${directory_with_submissions} {course} {exercise} 1`

5. In a browser navigate to: `http://localhost:8000/{course}/{exercise}/settings/`
    * Press the "Recompare all" button

6. Match submissions: `python manage.py matchsubmissions {course}/{exercise}`

## Set up Dolos

Dolos is required for `test_dolos` in `e2e_tests/test_dolos.py`.

1. Clone the [Dolos](https://github.com/dodona-edu/dolos) repository

2. Launch Docker daemon: `dockerd`

3. In a new terminal at the root of the Dolos repository run: `docker compose up`

Now Dolos should be running in a separate window and work with Radar.

## Create tests

1. Open new terminal.

2. Run Python environment: `source py_venv/bin/activate`

3. Record tests: `playwright codegen --target python-pytest "localhost:8000"`

4. Copy generated code into a Python file.

[Generating tests](https://playwright.dev/python/docs/codegen-intro)

[Writing tests](https://playwright.dev/python/docs/writing-tests)

## Run and debug tests

Run all tests: `pytest`

Run and debug a specific test: `PWDEBUG=1 pytest -s -k <test_method_name>`

[Running and debugging tests](https://playwright.dev/python/docs/running-tests)
