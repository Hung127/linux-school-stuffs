#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=/dev/null
source /etc/monitoring.env

: "${ALERT_TO:?thiếu ALERT_TO}"
: "${DISK_THRESHOLD:?thiếu DISK_THRESHOLD}"
: "${RAM_MIN_FREE:?thiếu RAM_MIN_FREE}"
: "${SERVICES:?thiếu SERVICES}"
: "${HEALTH_URL:?thiếu HEALTH_URL}"

ALERTS=()
HOST_NAME="$(hostname)"
CHECKED_AT="$(date '+%Y-%m-%d %H:%M:%S')"

# --- checks ---
disk_pct="$(df --output=pcent / | awk 'NR==2 {gsub("%",""); print}')"
if (( disk_pct > DISK_THRESHOLD )); then
    ALERTS+=("Disk usage high: ${disk_pct}% (threshold ${DISK_THRESHOLD}%)")
fi

ram_pct="$(awk '/MemAvailable/{a=$2} /MemTotal/{t=$2} END {if (t>0) printf "%d", a*100/t; else print 0}' /proc/meminfo)"
if (( ram_pct < RAM_MIN_FREE )); then
    ALERTS+=("RAM available low: ${ram_pct}% (min ${RAM_MIN_FREE}%)")
fi

read -r -a services <<< "$SERVICES"
for svc in "${services[@]}"; do
    systemctl is-active --quiet "$svc" 2>/dev/null || ALERTS+=("Service not active: ${svc}")
done

if ! curl -sf --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
    ALERTS+=("Web endpoint failed: ${HEALTH_URL}")
fi

# --- alerting ---
send_alert() {
    local subject count
    count="${#ALERTS[@]}"
    subject="[ALERT] ${HOST_NAME}: ${count} vấn đề"

    case "${MAIL_MODE:-file}" in
        smtp)
            {
                printf 'Host: %s\nChecked: %s\n\n' "$HOST_NAME" "$CHECKED_AT"
                for alert in "${ALERTS[@]}"; do printf '%s\n' "$alert"; done
            } | mail -s "$subject" "$ALERT_TO"
            ;;
        file)
            {
                printf 'To: %s\n' "$ALERT_TO"
                printf 'Subject: %s\n' "$subject"
                printf 'Date: %s\n\n' "$CHECKED_AT"
                for alert in "${ALERTS[@]}"; do printf '%s\n' "$alert"; done
                printf '\n---\n\n'
            } >> /var/log/web01-mail.log
            ;;
    esac
}

if (( ${#ALERTS[@]} > 0 )); then
    send_alert
    exit 1
fi

exit 0
