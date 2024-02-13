#!/bin/bash

docker build -f .github/workflows/lint.Dockerfile . -t radar_prospector
docker run --rm -v ${PWD}:/app -w /app radar_prospector sh -c 'prospector'
