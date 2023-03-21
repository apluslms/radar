# Radar development container

## Known issues

When inspecting a match (<http://192.168.48.4:8001/1921684838000defcurrent/29/compare/123456-admin/13>),
the link to a submission in A+ (<http://plus:8000/def/current/programming_exercises/radar/programming_exercises_radar_python_radar/submissions/3/>)
uses `plus:8000` instead of localhost and exposed port.

## Getting started

This image is meant to be used with the [aplus-manual](https://github.com/apluslms/aplus-manual)
repository. The image can also be run stand-alone by using the included `docker-compose.yaml`,
but that's not a recommended workflow.

### Using with aplus-manual

1. Compile the image with `./build.sh`
2. Follow the [instructions](https://github.com/apluslms/aplus-manual/blob/master/README.md)
   for aplus-manual

The Radar source code can be mounted in the radar container at `/srv/radar` for
automatic code reloading. See [run-aplus-front](https://github.com/apluslms/run-aplus-front#usage)
for more information about mounting development code.

By default the following ports are used:

- 8001: radar http
- 5555: flower http (celery dashboard)
- 5678: radar debug (vscode debugpy)
- 5679: celery debug (vscode debugpy)

### Using stand-alone

You can either clone the `aplus-manual` repository or mount your preferred
course in the grader container.

```shell
# Fetch and compile the course
git clone https://github.com/apluslms/aplus-manual
pushd aplus-manual
git submodule update --init --recursive
./docker-compile.sh
popd
# Build the image and launch
./build.sh
docker-compose up
```

By default the following services are exposed:

- <http://localhost:8000/>: aplus
- <http://localhost:8001/>: radar
- <http://localhost:8080/>: grader
- <http://localhost:5555/>: flower (celery dashboard)

The default course instance and Radar LTI instance are configured automatically
in A+ as well as the course menu link to Radar in the default course.

## Debugging

Because this image is intended for development purposes, it includes built-in
debugging features. Both the Django process that handles the main Radar code as
well as the Celery worker are launched using Microsoft's
[debugpy](https://code.visualstudio.com/docs/python/debugging). Debug interfaces
for the two services are available at the following ports:

- 5678: radar/django
- 5679: celery

There is an example configuration for debugging Django below.
Note that the host ports need to match the published ports set in docker-compose.yaml.

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Remote Attach to Radar",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 5670
            },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}",
                    "remoteRoot": "/srv/radar"
                },
                // Uncomment this if you have copied the venv locally and want
                // to debug the libraries in the virtualenv
                // {
                //     "localRoot": "${workspaceFolder}/radar-venv/dist-packages",
                //     "remoteRoot": "/usr/local/lib/python3.7/dist-packages"
                // }
            ],
            // Uncomment this if you want to debug the libraries in the virtualenv
            // "justMyCode": false,
        },
        {
            "name": "Remote Attach to Radar Celery worker",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 5671
            },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}",
                    "remoteRoot": "/srv/radar"
                }
            ],
            "justMyCode": false
        }
    ]
}
```

Adjust `localRoot` to point to the local copy of the Radar source code. If you
want to step into the libraries installed with pip, copy the virtual environment
from the image with `docker cp` and uncomment the appropriate lines.
