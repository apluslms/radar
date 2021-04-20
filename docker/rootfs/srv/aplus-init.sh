#!/bin/sh -eu

# Start background services/tasks
#start_services
# start course updater (will exit when successful)
run_services aplus-course-update aplus-lti-services
