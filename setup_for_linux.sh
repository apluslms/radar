#!/bin/bash

python3 -m virtualenv -p python3 py_venv
source py_venv/bin/activate

pip install -r requirements.txt

python manage.py migrate

cd matcher/greedy_string_tiling
pip install .

cd ../..

python -m playwright install --with-deps
