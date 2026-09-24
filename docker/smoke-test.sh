#!/usr/bin/env bash
# Start an image on an empty data folder and wait for it to be healthy.
# Usage: docker/smoke-test.sh IMAGE
set -euo pipefail

image=${1:?usage: smoke-test.sh IMAGE}
name="hrcek-smoke-$$"
data=$(mktemp -d)
# The image runs as uid 10001, which owns nothing on the runner.
chmod 0777 "$data"

cleanup() {
    docker rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
    echo "smoke test: $*" >&2
    docker logs "$name" >&2 || true
    exit 1
}

docker run -d --name "$name" -v "$data:/data" \
    -e HRCEK_SECRET_KEY=smoke-test-not-a-secret \
    -e HRCEK_ALLOWED_HOSTS=localhost \
    -e HRCEK_SMTP_HOST=localhost \
    "$image" >/dev/null

status=starting
for _ in $(seq 60); do
    [[ $(docker inspect -f '{{.State.Running}}' "$name") == true ]] \
        || fail "the container exited"
    status=$(docker inspect -f '{{.State.Health.Status}}' "$name")
    [[ $status == healthy || $status == unhealthy ]] && break
    sleep 2
done
[[ $status == healthy ]] || fail "health is '$status'"

docker exec "$name" python manage.py releases
docker exec "$name" test -f /app/staticfiles/staticfiles.json \
    || fail "collectstatic did not run"
[[ -f $data/db.sqlite3 && -f $data/releases.json ]] \
    || fail "state was not written to /data"
echo "smoke test: $image is healthy"
