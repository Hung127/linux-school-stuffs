# Linux Operating System & Applications — Course Materials

Personal study notes, slide decks and lab reports for the **Linux Operating System &
Applications** course at HCMUS. Shared openly so my classmates can use, reuse and
build on any of it — take whatever is useful, ignore the rest.

Everything here is written from my own work. Lab reports follow a
*command → explanation → screenshot* pattern, so you can see not just *what* to run
but *why* each flag is there.

---

## Contents

- [What's in here](#whats-in-here)
- [Repository layout](#repository-layout)
- [Command cheat-sheet](#command-cheat-sheet)
  - [Log analysis](#log-analysis)
  - [Finding and inspecting files](#finding-and-inspecting-files)
  - [Text processing](#text-processing)
  - [Links and inodes](#links-and-inodes)
  - [Shell productivity](#shell-productivity)
- [Slides](#slides)
- [Labs](#labs)
- [The web version](#the-web-version)
  - [Run the site](#run-the-site)
  - [What gets published](#what-gets-published)
  - [Three ignore systems](#three-ignore-systems)
  - [Layer order](#layer-order)
- [Seminar topics](#seminar-topics)
- [Books](#books)
- [Contributing](#contributing)

---

## What's in here

- **4 interactive slide decks** covering Sessions 01–04 — self-contained HTML, just
  open them in a browser.
- **1 complete lab report** (Lab 01) with a written explanation for every single
  command, plus the dataset it was written against.
- **A command cheat-sheet** — the reusable pipelines from those labs, distilled and
  copy-pasteable.
- **A list of 13 seminar topics** with the infrastructure each one needs, so you can
  pick a topic and know the scope before committing to it.
- **A browsable web version** of all of it, in one container — see
  [The web version](#the-web-version).

---

## Repository layout

| Path | What it is |
|---|---|
| `syllabus.html` | Full course syllabus — 5 modules, 11 sessions, assessment breakdown, capstone tracks |
| `slides/` | Interactive HTML slide decks, one file per session |
| `labs/lab01/` | Lab 01 — assignment sheet, dataset, report and screenshots |
| `seminar/` | Seminar topic list with per-topic infrastructure requirements |
| `books/` | Reference books — **not in the repo**, see [Books](#books) |
| `docker/` | Build tooling — the site generator and its tests, see [The web version](#the-web-version) |
| `Dockerfile` | Builds and serves the site in one container |
| `.dockerignore` | Keeps `books/` and `.venv/` out of the build context |

---

## Command cheat-sheet

The commands that actually earned their place in the lab reports. Every example below
is written to be run **from the repository root** and has been verified against the
real data.

> **Note:** the original `labs/lab01/report.md` refers to the log as `lab01/access.log`.
> That path is stale — the file is at `labs/lab01/access.log`. The commands below use
> the correct path.

### Log analysis

Dataset: `labs/lab01/access.log` — 100,000 lines of nginx combined-format log.

```bash
# Top 10 client IPs by request count
awk '{print $1}' labs/lab01/access.log | sort | uniq -c | sort -k1 -nr | head -10

# Top 5 URLs returning 404 — check for vulnerability scanners
awk '$9 == 404 {print $7}' labs/lab01/access.log | sort | uniq -c | sort -rn | head -5

# Count requests per hour of day
awk '{split($4,a,":"); h=a[2]; arr[h]++}
     END {for (k in arr) print k, arr[k]}' labs/lab01/access.log | sort -n -k1

# Status code breakdown with percentage share
awk 'BEGIN{sum=0} {c[$9]++; sum++}
     END {for (k in c) printf "%s %d %.1f%%\n", k, c[k], c[k]*100/sum}' \
    labs/lab01/access.log

# Total requests that returned 5xx
awk '$9>=500 && $9<=599' labs/lab01/access.log | wc -l
```

Two things worth internalising:

- **Match fields, not substrings.** `awk '$9 == 404'` is correct where `grep 404` is
  not — `grep` would also match a byte count of `40428`.
- **Aggregate on the field you care about, not the whole line.** Extracting `$1` before
  `sort | uniq -c` is what turns 100,000 lines into a ranked list.

### Finding and inspecting files

```bash
# 10 largest files under a directory, human-readable
find . -type f -printf '%s %p\n' | sort -nr -k1 | numfmt --to=iec | head -10

# Files modified in the last 24 hours
find . -type f -mtime -1

# World-writable files (audit only — do not change)
sudo find /tmp -type f -perm -o+w

# Empty files and empty directories, listed separately
find . -type f -empty
find . -type d -empty
```

Use `-empty`, **not** `-size 0`, to find empty directories — a directory always
occupies space for its own metadata, so `-size 0` silently misses every one of them.

### Text processing

```bash
# Recursive search, skipping noise, counting matching files
grep -lir --exclude-dir=.git --exclude-dir=node_modules -e "TODO" . | wc -l

# Bulk replace across many files, with automatic backups
find ./configs -type f -print0 | xargs -0 sed -i.bak 's/old-server\.local/10.5.0.2/'

# Verify: no output means every file was changed
grep -r -e "old-server.local" ./configs
```

- Always pair `find -print0` with `xargs -0`. Plain `xargs` splits on whitespace, so a
  filename containing a space will be treated as two files and the command will fail.
- `-i.bak` leaves a `.bak` next to every file it edits. The backup *keeps the old
  value*, so verify with `grep -r` before you start wondering why old values still
  appear.
- Escape the dot (`old-server\.local`) or it matches any character.

### Links and inodes

```bash
touch original.txt
ln    original.txt hard.txt     # hard link — another name for the same inode
ln -s original.txt soft.txt     # symlink — a small file holding a path

ls -li original.txt hard.txt soft.txt
```

`hard.txt` and `original.txt` share one inode; `soft.txt` has its own and points at a
path. Delete `original.txt` and the hard link still reads fine, while the symlink is
left broken — because the data lives in the inode, which the hard link still
references, and in the path string, which no longer resolves.

### Shell productivity

```bash
# create a directory and cd into it
mkcd() { mkdir "$1" && cd "$1"; }

# unpack by extension
extract() {
    case "$1" in
        *.zip)     unzip "$1";  return 0 ;;
        *.tar.gz)  tar -xzf "$1"; return 0 ;;
        *.tar.bz2) tar -xjf "$1"; return 0 ;;
        *) echo "extract: Unsupported file type: $1" >&2; return 1 ;;
    esac
}

alias l='ls -al'
alias li='ls -li'
alias ..='cd ..'
alias nvimrc='cd ~/.config/nvim'
alias runcpp='g++ -std=c++23 -Wall -Werror *.cpp -o main && ./main'

HISTTIMEFORMAT="%Y-%m-%d %H:%M:%S || "
```

`mkcd` and `extract` are functions rather than aliases because they run several
commands and use their arguments. Add them to `~/.bashrc` and they apply to every new
shell — or run `source ~/.bashrc` in the current one.

---

## Slides

Four self-contained interactive decks. **No setup or build step** — open the `.html`
file directly in a browser.

| Session | Deck | Covers |
|---|---|---|
| 01 | [Linux Architecture](slides/1_linux_architecture.html) | Unix history, kernel/user/shell layers, distro choice, FHS, boot sequence, systemd |
| 02 | [CLI & Text Processing](slides/2_cli-text-processing.html) | Navigation, redirection, pipes, `xargs`, and the text tools — `grep`, `sed`, `awk`, `sort`, `uniq` |
| 03 | [Users, Permissions & Processes](slides/3_users-permissions.html) | `useradd`/`usermod`, `/etc/passwd`/`shadow`/`group`, `chmod`, SUID/SGID/sticky, ACLs, process management |
| 04 | [Software, Storage & Tasks](slides/4-software-storage-tasks.html) | `apt`/`dpkg`, PPAs, building from source, partitioning and `fstab`, LVM, cron, systemd timers |

The decks are clickable rather than slide-by-slide — use the navigation on each page
to move between sections.

---

## Labs

### Lab 01 — CLI & text processing

Everything for this lab lives in [`labs/lab01/`](labs/lab01/).

| File | What it is |
|---|---|
| `linux_lab_1.html` | The assignment sheet — 10 labs plus stretch goals and questions |
| `access.log` | The dataset: 100,000 lines, ~17 MB, nginx combined format |
| `report.md` | My write-up — source format |
| `report.pdf` | Same report, PDF |
| `screenshots/` | 20 terminal captures, referenced from the report |

Topics covered: directory navigation and brace expansion, stdout/stderr redirection
and `tee`, `grep` pattern hunting, `awk` log analytics, `sed` bulk replacement,
disk-hog hunting and permission auditing, hard links vs symlinks, shell customisation,
and a capstone that chases down a failing deploy using nothing but
`grep · awk · sed · sort · uniq`.

Each task in the report follows the same shape:

1. the command
2. an **Explain:** paragraph covering each flag and why it is there
3. a screenshot of the actual output
4. a written answer where the sheet asks a question

`access.log` is committed so that every command in the report runs exactly as written,
with identical results. Fields are positional — `$1` is the client IP, `$7` the request
URL, `$9` the status code, `$10` the response size.

---

## The web version

The notes are a static site, so serving them needs no application server — `slides/`,
`syllabus.html` and the screenshots are already HTML. The only thing that is not
already a web page is this repository's three Markdown files. `docker/build_site.py`
renders those to HTML **at the same relative paths**, which is the whole trick: because
`README.md` becomes `index.html` and `report.md` becomes `labs/lab01/index.html`, every
relative link in this file keeps working once it is served.

| Source | Becomes | Served at |
|---|---|---|
| `README.md` | the landing page | `/` |
| `labs/lab01/report.md` | the lab report, screenshots intact | `/labs/lab01/` |
| `seminar/de_tai_seminar.md` | the seminar topic list | `/seminar/` |

### Run the site

**With Docker** — nothing to install but Docker:

```bash
docker build -t linux-notes .
docker run --rm -p 8080:8000 linux-notes
```

**Without Docker** — the same generator, run directly:

```bash
python -m venv .venv && source .venv/bin/activate
pip install markdown-it-py==4.2.0 mdit-py-plugins==0.6.1

python docker/build_site.py . /tmp/course-site
cd /tmp/course-site && python -m http.server 8000 --bind 127.0.0.1
```

Two details in that second version are deliberate. The generator takes **the repository
first and the output directory second**, and its defaults are `/build/src` and
`/build/out` — the container paths — so running it with no arguments fails outside
Docker. And `--bind 127.0.0.1` is not optional advice: `http.server` listens on every
interface by default, which on shared Wi-Fi hands the whole repository to the network.

### What gets published

| Published | Not published | Why |
|---|---|---|
| `index.html`, `syllabus.html`, `slides/` | `books/` | 22 MB of copyrighted textbooks |
| `labs/lab01/` — report, screenshots, `report.pdf` | `docker/`, `Dockerfile` | build inputs, not course notes |
| `labs/lab01/access.log` — 18 MB | `.git/`, `.venv`, `.gitignore` | tooling and metadata |
| `seminar/index.html` | the raw `.md` sources | rendered instead, so a page is one file, not two |

`access.log` is 18 MB and ships on purpose. Every command in the report is written
against it, so serving it is what lets a classmate reproduce a result without a second
18 MB download.

### Three ignore systems

This repository has three independent mechanisms for deciding what to leave out, and
**none of them knows about the other two**:

| System | Controls | Knows about the others? |
|---|---|---|
| `.venv/.gitignore` | what git tracks | no |
| `.dockerignore` | what enters the build context | no |
| `EXCLUDED_NAMES` in `build_site.py` | what gets published | no |

`python -m venv` writes a `.gitignore` containing `*` into every virtualenv it creates,
so `git status` stays clean and the venv looks handled. But Docker never reads that
file, and neither does the generator — a 13 MB virtualenv reached the published site
this way. **`.dockerignore` and `.gitignore` are different tools protecting different
things**, and a path can be gitignored and still end up baked into an image layer.

The fix is a **rule, not a list**: anything whose name starts with `.` is excluded, at
any depth. `.vscode`, `.idea`, `.DS_Store` and a stray `.env` full of secrets are
covered without anyone remembering to add them. A denylist only ever contains what
someone thought of in advance — the whole point is to stop needing to.

`.dockerignore` is still needed, and is not a substitute. The generator's rules keep
junk out of the site; only `.dockerignore` keeps 14 MB of virtualenv out of the build
context in the first place.

### Layer order

```dockerfile
FROM python:3.14.7-alpine3.24

EXPOSE 8000

RUN pip install --no-cache-dir \
    markdown-it-py==4.2.0 \
    mdit-py-plugins==0.6.1 \
    pygments==2.21.0
WORKDIR /app
COPY . build/
RUN python build/docker/build_site.py ./build ./build-out
WORKDIR /app/build-out

CMD [ "python", "-m", "http.server", "8000" ]
```

Docker caches **each instruction as a layer**, and one invalidated layer invalidates
everything after it. That is why `pip install` sits *above* `COPY`: editing a note
reuses the cached package layer. Move it below and every keystroke in this file
re-runs pip.

The experiment that proves it: build once, add a space to `README.md`, build again,
and watch where the `CACHED` markers stop.

> **Note:** `CMD` in the exec form is an argument array, not a command line, so
> nothing is split for you. `["python", "-m", "http.server 8000"]` reads sensibly and
> fails with `No module named http.server 8000` — the module and its port have to be
> separate elements.

### Tests

```bash
python -m unittest discover -s docker -t docker -v
```

161 tests, run against both a synthetic fixture and this repository — so a broken link
or a leaked file fails the build rather than shipping.

---

## Seminar topics

Thirteen topics, each with the infrastructure it assumes. Pick based on what you want
to learn and what you can spin up.

> The course `syllabus.html` contains a shorter, different table of 10 topics. This
> list is the expanded one, with the infrastructure requirements attached.

| # | Topic | Infrastructure |
|---|---|---|
| 1 | **Nginx Web Server & Reverse Proxy** — event-driven vs Apache's process/thread model, server blocks, `access.log`/`error.log`, 502/503/504, rate limiting with `burst`/`nodelay` | 1 VM (512 MB) |
| 2 | **MongoDB Document Database Server** — document model vs RDBMS, `bindIp`, authentication and RBAC, single/compound indexes, `.explain()`, `mongodump`/`mongorestore` | 1 VM (1 GB) |
| 3 | **MySQL Database Server** — server layer vs storage engine, InnoDB vs MyISAM, `GRANT`/`REVOKE`, binary log, slow query log, ACID transactions | 1 VM (1 GB) |
| 4 | **Docker CE (Single Node)** — containers vs VMs, namespaces and cgroups, image layers and build cache, multi-stage builds, bind mounts vs named volumes | 1 VM (1 GB) |
| 5 | **Docker Swarm Orchestration** — manager/worker roles, desired state and reconciliation, routing mesh and overlay networks, rolling updates | 2 VMs (1 GB each) |
| 6 | **HAProxy Load Balancer** — `roundrobin` vs `leastconn` vs `source`, sticky sessions, health checks (`inter`/`rise`/`fall`), custom error pages | 3 VMs (512 MB each) |
| 7 | **Redis In-Memory Data Store** — cache-aside, why single-threaded is fast, RDB vs AOF persistence, eviction policies (`noeviction`, `allkeys-lru`, `volatile-ttl`) | 1 VM (512 MB) |
| 8 | **NFS Network File System** — NFS vs SMB/CIFS, UID/GID-based permissions, `root_squash` vs `no_root_squash`, hard vs soft mounts | 2 VMs (512 MB each) |
| 9 | **Ansible Configuration Management** — idempotency, agentless over SSH, inventories, playbooks, roles, handlers, Jinja2 templates, `ansible-vault` | 2 VMs (512 MB each) |
| 10 | **Prometheus & Grafana Monitoring** — pull vs push, Counter/Gauge/Histogram, PromQL with `rate()`, alert lifecycle, Alertmanager | 2 VMs (1.5 GB + 512 MB) |
| 11 | **ELK Stack (Centralized Logging)** — Filebeat → Elasticsearch → Kibana, the inverted index, parsing unstructured logs into structured fields | 1 VM (3 GB) |
| 12 | **BorgBackup (Deduplicated Backup)** — full/incremental/differential, deduplication, the 3-2-1 rule, RPO/RTO, `--append-only` against ransomware | 2 VMs (512 MB each) |
| 13 | **BIND9 Domain Name System** — recursive vs authoritative DNS, record types, forward and reverse zones, zone transfer (AXFR/IXFR) | 2 VMs (512 MB each) |

The original topic descriptions — including the theory outline and the required demos
for each — are in [`seminar/de_tai_seminar.md`](seminar/de_tai_seminar.md) (Vietnamese).

---

## Books

Two reference books are useful for this course but are **not committed to this
repository** — they are large and under copyright:

- *How Linux Works* — what every superuser should know (Brian Ward)
- *Linux Command Line and Shell Scripting Bible* (3rd edition)

Look for your own copies. The syllabus references them as background reading.

---

## Contributing

This is not a curated collection — take whatever you want, and add whatever you want.
If you solved a lab differently, found a cleaner pipeline, or built a deck for a
session that isn't here yet, please put it up.

If you'd like things to stay consistent, the pattern that already works is:

- **One folder per lab** — `labs/labNN/`
- **Keep the assignment sheet, the dataset, and your write-up together** in that folder
- **Write the report in Markdown** (`report.md`) so diffs stay readable
- **Reference screenshots relatively** (`screenshots/lab1_1.png`) so the report renders
  on GitHub
- **Explain every command** — a command someone cannot understand is worth much less
  than the one that opened their eyes

There are no rules beyond that, and no pull request is too small.
