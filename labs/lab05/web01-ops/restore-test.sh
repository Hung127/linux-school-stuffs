#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=/dev/null
source /etc/backup.env

: "${DATA_DIR:?thiếu DATA_DIR}"
: "${DEST:?thiếu DEST}"

if [[ ! -d "$DEST" ]]; then
    printf 'DEST không tồn tại: %s\n' "$DEST" >&2
    exit 1
fi

latest_archive="$(
    find "$DEST" -maxdepth 1 -type f -name 'web01-backup-*.tar.gz' -printf '%T@ %p\n' \
    | sort -nr | head -n 1 | cut -d' ' -f2-
)"

if [[ -z "$latest_archive" ]]; then
    printf 'Không tìm thấy archive nào trong %s\n' "$DEST" >&2
    exit 1
fi

workdir=""
cleanup() {
    # shellcheck disable=SC2317
    if [[ -n "${workdir:-}" ]]; then
        # shellcheck disable=SC2317
        rm -rf -- "$workdir"
    fi
}
trap cleanup EXIT

workdir="$(mktemp -d)"
tar -xzf "$latest_archive" -C "$workdir"

if [[ ! -f "$workdir/manifest.txt" ]]; then
    printf 'Thiếu manifest.txt trong %s\n' "$latest_archive" >&2
    exit 1
fi

total="$(wc -l < "$workdir/manifest.txt")"
md5_output="$(cd "$workdir" && md5sum -c manifest.txt)" || true

ok_count="$(printf '%s\n' "$md5_output" | grep -c ': OK$' || true)"
fail_count="$(printf '%s\n' "$md5_output" | grep -Ec ': FAILED' || true)"

if (( fail_count == 0 )); then
    printf 'Restore test: %s/%s file OK\n' "$ok_count" "$total"
    exit 0
fi

printf '%s\n' "$md5_output" >&2
printf 'Restore test: %s/%s file OK; %s failed\n' "$ok_count" "$total" "$fail_count" >&2
exit 1
