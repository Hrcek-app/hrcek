#!/usr/bin/env bash
# Deploy, roll back or restore Hrček on one host with docker compose.
#
#   deploy.sh vX.Y.Z             deploy that release; a rollback if it
#                                ran here before at fewer migrations
#   deploy.sh status             release history and snapshots
#   deploy.sh restore SNAPSHOT   put a snapshot back, start its release
#   deploy.sh --ssh              for a forced-command SSH key: the tag
#                                comes from SSH_ORIGINAL_COMMAND
#
# Environment: HRCEK_DIR (default: this script's folder), HRCEK_IMAGE
# (default ghcr.io/samastur/hrcek), HRCEK_HEALTH_TIMEOUT (default 90).
# See docs/dev/deployment.md.
set -euo pipefail

HRCEK_DIR=${HRCEK_DIR:-$(cd "$(dirname "$(readlink -f "$0")")" && pwd)}
HRCEK_IMAGE=${HRCEK_IMAGE:-ghcr.io/samastur/hrcek}
HRCEK_HEALTH_TIMEOUT=${HRCEK_HEALTH_TIMEOUT:-90}
export HRCEK_IMAGE
TAG_PATTERN='^v[0-9]+\.[0-9]+\.[0-9]+$'
SELF=$(basename "$0")

say() { printf '%s: %s\n' "$SELF" "$*" >&2; }
die() {
    say "$*"
    exit 1
}
usage() {
    sed -n '3,9s/^# \{0,1\}//p' "$0" >&2
    exit 2
}
valid_tag() { [[ $1 =~ $TAG_PATTERN ]]; }

prepare() {
    cd "$HRCEK_DIR"
    [[ -f compose.yaml && -f .env ]] ||
        die "$HRCEK_DIR needs compose.yaml and .env."
    # Rootless Docker listens in the user's runtime folder, which a
    # forced-command SSH session does not point the client at.
    local rootless
    rootless="/run/user/$(id -u)/docker.sock"
    if [[ -z ${DOCKER_HOST:-} && -S $rootless ]]; then
        export DOCKER_HOST="unix://$rootless"
    fi
}

lock() {
    exec 9>"$HRCEK_DIR/.deploy.lock"
    flock -n 9 || die "Another deploy is running."
}

compose() { docker compose "$@"; }
manage() { compose run --rm --no-deps -T app manage.py "$@"; }
start() {
    compose up -d --wait --wait-timeout "$HRCEK_HEALTH_TIMEOUT" app
}
current_tag() { sed -n 's/^HRCEK_TAG=//p' .env | tail -n 1; }
set_tag() {
    local next
    next=$(mktemp .env.XXXXXX)
    grep -v '^HRCEK_TAG=' .env >"$next" || true
    printf 'HRCEK_TAG=%s\n' "$1" >>"$next"
    mv "$next" .env
}
show_logs() { compose logs --no-color --tail 200 app >&2 || true; }

forward() {
    local tag=$1 previous started
    previous=$(current_tag)
    started=$(date -u +%Y%m%dT%H%M%SZ)
    set_tag "$tag"
    if start; then
        say "$tag is running."
        return
    fi
    say "$tag did not become healthy. Its logs:"
    show_logs
    compose stop app
    [[ -n $previous ]] || die "There is no earlier release to return to."
    set_tag "$previous"
    # The failed release never reported healthy, so it served nobody
    # and the snapshot it took before migrating loses nothing.
    manage restore --earliest-since "$started" ||
        die "Could not restore the snapshot $tag took. The app is stopped;" \
            "see: $SELF status"
    start || die "$previous did not come back either. See: $SELF status"
    die "Returned to $previous."
}

rollback() {
    local tag=$1
    compose stop app
    # The running release is the only one that knows how to reverse
    # its own migrations, so it migrates down before the switch.
    if ! manage rollback_to "$tag"; then
        say "Migrating down failed; restarting the current release."
        start || true
        die "Rollback to $tag failed. The database was put back from the" \
            "pre-rollback snapshot and nothing was switched."
    fi
    set_tag "$tag"
    if ! start; then
        show_logs
        die "$tag did not become healthy. It may have served writes, so" \
            "nothing was undone. To go back: $SELF restore <the newest" \
            "pre-rollback snapshot in: $SELF status>"
    fi
    say "Rolled back to $tag."
}

deploy() {
    local tag=$1 plan
    docker pull "$HRCEK_IMAGE:$tag"
    if [[ -z $(current_tag) ]]; then
        forward "$tag"
        return
    fi
    plan=$(manage release_plan "$tag")
    case $plan in
    current)
        say "$tag is already the current release."
        start
        ;;
    forward) forward "$tag" ;;
    rollback) rollback "$tag" ;;
    *) die "Unexpected plan '$plan'." ;;
    esac
}

restore_snapshot() {
    local tag
    compose stop app
    if ! manage restore "$1"; then
        start
        die "Nothing was restored; the current release is running again."
    fi
    tag=$(manage releases --current)
    valid_tag "$tag" ||
        die "The snapshot holds '$tag', which is not a release tag;" \
            "start one with $SELF vX.Y.Z."
    docker pull "$HRCEK_IMAGE:$tag"
    set_tag "$tag"
    start
    say "Restored; $tag is running."
}

main() {
    case ${1:-} in
    --ssh)
        [[ $# -eq 1 ]] || usage
        local request=${SSH_ORIGINAL_COMMAND:-}
        valid_tag "$request" ||
            die "Refused: only a release tag such as v1.2.3 may be requested."
        prepare
        lock
        deploy "$request"
        ;;
    status)
        prepare
        manage releases
        ;;
    restore)
        [[ $# -eq 2 ]] || usage
        prepare
        lock
        restore_snapshot "$2"
        ;;
    "" | -h | --help) usage ;;
    *)
        [[ $# -eq 1 ]] || usage
        valid_tag "$1" || die "Not a release tag: $1"
        prepare
        lock
        deploy "$1"
        ;;
    esac
}

main "$@"
