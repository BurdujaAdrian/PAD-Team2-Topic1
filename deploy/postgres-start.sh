#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == run ]]; then
    # Run after Bitnami setup (user creation/cloning), before the server starts.
    # Standbys need the same setting so promotion cannot silently become async.
    cat >> /opt/bitnami/postgresql/conf/postgresql.conf <<'CONF'
synchronous_commit = 'on'
synchronous_standby_names = 'ANY 1 (*)'
CONF
    exec "$2"
fi
rm -f /opt/bitnami/postgresql/tmp/.initialized
# During an election one standby may still report the old leader. The upstream
# entrypoint treats conflicting metadata as "no primary"; wait rather than
# starting a previously promoted node as a second primary.
for attempt in {1..60}; do
    votes=()
    IFS=',' read -ra peers <<< "$REPMGR_PARTNER_NODES"
    for peer in "${peers[@]}"; do
        vote=$(PGCONNECT_TIMEOUT=2 PGPASSWORD="$REPMGR_PASSWORD" psql \
            -h "$peer" -U repmgr -d repmgr -Atc \
            "SELECT node_id FROM repmgr.nodes WHERE active AND type='primary'" 2>/dev/null || true)
        if [[ "$vote" =~ ^[0-9]+$ ]]; then votes+=("$vote"); fi
    done
    count=$(printf '%s\n' "${votes[@]}" | sed '/^$/d' | sort -u | wc -l)
    if (( count <= 1 )); then
        exec /opt/bitnami/scripts/postgresql-repmgr/entrypoint.sh \
            /bin/bash "$0" run /opt/bitnami/scripts/postgresql-repmgr/run.sh
    fi
    echo 'Waiting for peers to agree on the elected primary.' >&2
    sleep 2
done
echo 'Conflicting primary metadata; refusing to start.' >&2
exit 1
