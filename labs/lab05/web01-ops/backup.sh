#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=/dev/null
source /etc/backup.env

: "${DATA_DIR:?thiếu DATA_DIR}"
: "${DEST:?thiếu DEST}"
: "${RETAIN_DAYS:?thiếu RETAIN_DAYS}"
: "${ALERT_TO:?thiếu ALERT_TO}"

WORKDIR=""
ERROR_REPORTED=0

send_message() {
    local subject="$1"
    local body="$2"

    case "${MAIL_MODE:-file}" in
        smtp)
            printf '%s\n' "$body" | mail -s "$subject" "$ALERT_TO"
            ;;
        file)
            {
                printf 'To: %s\n' "$ALERT_TO"
                printf 'Subject: %s\n' "$subject"
                printf 'Date: %s\n\n' "$(date '+%Y-%m-%d %H:%M:%S')"
                printf '%s\n' "$body"
                printf '\n---\n\n'
            } >> /var/log/web01-mail.log
            ;;
        *)
            printf 'MAIL_MODE không hợp lệ: %s\n' "${MAIL_MODE:-}" >&2
            return 1
            ;;
    esac
}

on_error() {
    local exit_code=$?          # must be first line
    ERROR_REPORTED=1

    local line_no="$1"
    local failed_command="$2"
    local host_name
    host_name="$(hostname)"

    local body
    body="$(printf 'Host: %s\nTime: %s\nLine: %s\nCommand: %s\nExit code: %s\n' \
        "$host_name" "$(date '+%Y-%m-%d %H:%M:%S')" "$line_no" "$failed_command" "$exit_code")"

    send_message "BACKUP FAILED: ${host_name}" "$body"
}

cleanup() {
    local status=$?          # must be first line

    if (( status != 0 )) && (( ERROR_REPORTED == 0 )); then
        local host_name
        host_name="$(hostname)"
        send_message "BACKUP FAILED: ${host_name}" "Host: ${host_name}
Time: $(date '+%Y-%m-%d %H:%M:%S')
Exit code: ${status}"
    fi

    if [[ -n "$WORKDIR" ]]; then
        rm -rf "$WORKDIR"
    fi
}

trap 'on_error $LINENO "$BASH_COMMAND"' ERR
trap cleanup EXIT

if [[ ! -d "$DATA_DIR" ]]; then
    printf 'DATA_DIR không tồn tại: %s\n' "$DATA_DIR" >&2
    exit 1
fi

WORKDIR="$(mktemp -d)"

# relative manifest, same exclusions as archive
(
    cd "$DATA_DIR"
    find . -type f ! -name '*.log' ! -name '*.tmp' -exec md5sum {} + > "$WORKDIR/manifest.txt"
)

archive_name="web01-backup-$(date +%Y%m%d-%H%M%S).tar.gz"

# data + manifest, exclusions applied
tar -czf "$WORKDIR/$archive_name" \
    -C "$DATA_DIR" --exclude='*.log' --exclude='*.tmp' . \
    -C "$WORKDIR" manifest.txt

cp "$WORKDIR/$archive_name" "$DEST/$archive_name"

find "$DEST" -maxdepth 1 -type f -name 'web01-backup-*.tar.gz' -mtime +"$RETAIN_DAYS" -delete

archive_size="$(du -h "$DEST/$archive_name" | cut -f1)"
body="$(printf 'Archive: %s\nSize: %s\nDestination: %s\n' "$archive_name" "$archive_size" "$DEST")"
send_message "Backup OK" "$body"
