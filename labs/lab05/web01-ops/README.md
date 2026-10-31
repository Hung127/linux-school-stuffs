# Guide — Lab 10: Bash Automation (web01)

One guided path from blank VM to graded submission. VM: `web01` (AlmaLinux 9), `lab@192.168.122.90`, `~/.ssh/id_ed25519`.

## 0. Connect

```bash
ssh -i ~/.ssh/id_ed25519 lab@192.168.122.90
```

## 1. Install dependencies

```bash
sudo dnf install -y epel-release ShellCheck
sudo systemctl enable --now crond
```

## 2. Prepare data + endpoint

```bash
mkdir -p ~/web01-data/docs ~/web01-ops ~/logs
printf 'hello from web01\n' > ~/web01-data/index.html
printf 'tài liệu nội bộ\n' > ~/web01-data/docs/readme.txt
printf 'log không cần backup\n' > ~/web01-data/access.log
printf 'file tạm không cần backup\n' > ~/web01-data/cache.tmp
cp /path/to/server.py ~/web01-ops/server.py
chmod +x ~/web01-ops/server.py
nohup python3 ~/web01-ops/server.py ~/web01-data 8080 > ~/logs/web01.log 2>&1 &
curl -sf http://127.0.0.1:8080/health   # OK
```

Stop endpoint for failure tests: `pkill -f server.py`

## 3. Config files (root, 600)

`/etc/monitoring.env`

```bash
ALERT_TO="admin@example.com"
MAIL_MODE="file"
DISK_THRESHOLD=80
RAM_MIN_FREE=10
SERVICES="sshd crond"
HEALTH_URL="http://127.0.0.1:8080/health"
```

`/etc/backup.env`

```bash
DATA_DIR="/home/lab/web01-data"
DEST="/srv/backup-target"
RETAIN_DAYS=7
ALERT_TO="admin@example.com"
MAIL_MODE="file"
```

```bash
sudo chown root:root /etc/monitoring.env /etc/backup.env
sudo chmod 600 /etc/monitoring.env /etc/backup.env
sudo mkdir -p /srv/backup-target
```

Mail goes to `/var/log/web01-mail.log` in file mode.

## 4. Write scripts

Create `~/web01-ops/health-check.sh`, `backup.sh`, `restore-test.sh` with:
- `#!/usr/bin/env bash` + `set -euo pipefail`
- source `/etc/*.env`, validate vars with `: "${VAR:?...}"`
- absolute paths only, no `~`
- `send_alert()` shared via `lib/common.sh` or duplicated
- `trap` for backup failures and ERR where required

Test manually:
```bash
sudo ./health-check.sh; echo $?   # 0 when healthy
sudo ./backup.sh
sudo ./restore-test.sh
```

For shellcheck:

```bash
shellcheck health-check.sh backup.sh restore-test.sh
```

Fix every warning; use `# shellcheck source=/dev/null` before sourcing env if needed.

## 5. Capture evidence

Save under `screenshots/`:
- Task 1: healthy silent + multi-failure email
- Task 2: backup OK, rotation before/after, tar list, restore-test, trap failure with `/tmp` before/after
- Task 3: stopped line not printed, ERR email, shellcheck before/after
- Task 4: crontab, scheduled log, incident email

## 6. Cron

Create `/etc/cron.d/web01-ops`:

```cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
*/5 * * * * root /home/lab/web01-ops/health-check.sh >> /var/log/web01-health.log 2>&1
0 2 * * * root /home/lab/web01-ops/backup.sh >> /var/log/web01-backup.log 2>&1
```

For grading, temporarily use `*/1`, trigger an incident, then restore `*/5`.

## 7. Package

```bash
cp -r ~/web01-ops /tmp/web01-ops-submission
cd /tmp/web01-ops-submission
# remove real .env, keep examples/
zip -r web01-ops.zip .
```

Include: `server.py`, scripts, `examples/`, `cron/`, `README.md`, `REPORT.md`.
Do not include real `/etc/*.env` or mail logs.