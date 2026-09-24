#!/bin/sh
# Start Hrček, or run a one-off command in its environment.
#
#   (no arguments), serve   check, snapshot, migrate, record, then serve
#   manage.py ARGS...       a management command, with no startup steps
#   anything else           executed as given
set -eu

if [ "$#" -eq 0 ] || [ "$1" = "serve" ]; then
    python manage.py check_schema
    python manage.py backup --reason pre-release --if-new-release --prune
    python manage.py migrate --no-input
    python manage.py record_release
    exec gunicorn --config /app/docker/gunicorn.conf.py hrcek.wsgi:application
fi

if [ "$1" = "manage.py" ]; then
    shift
    exec python manage.py "$@"
fi

exec "$@"
