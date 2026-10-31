# Bài tập về nhà — Buổi 10: Bash Scripting & Tự động hóa vận hành

> **Không cần cài web server hay database.** Toàn bộ bài chạy trên một VM Linux thông thường, chỉ dùng công cụ có sẵn (`bash`, `tar`, `rsync`/`cp`, `find`, `cron`, `curl`) và `python3` với thư viện chuẩn. Máy lab cấu hình thấp vẫn làm được.
>
> **Tổng điểm: 10** · Hình thức: cá nhân · Nộp: 1 file `.zip`

---

## Bối cảnh

Bạn quản trị một máy chủ Linux nhỏ tên **`web01`**. Trên máy có một web endpoint đơn giản (viết bằng Python) phục vụ một thư mục file. **Thư mục đó là "dữ liệu quan trọng"** cần được bảo vệ.

Vấn đề: không ai trực màn hình lúc 3 giờ sáng, không ai nhớ chạy backup, và ổ đĩa thì tự đầy dần. Nhiệm vụ của bạn là giúp `web01` **tự giám sát, tự sao lưu và tự báo lỗi**, tức là biến các thao tác kiểm tra thủ công trên lớp thành script chạy tự động, **chỉ lên tiếng khi có sự cố**.

Bạn sẽ viết 4 script tạo thành một bộ công cụ vận hành nhỏ, kèm báo cáo chứng minh từng script hoạt động.

## Mục tiêu học tập

Sau bài này, sinh viên có thể viết script Bash an toàn với strict mode và `trap`; thu thập trạng thái hệ thống và gửi cảnh báo qua email; thực hiện backup xoay vòng có **kiểm chứng khôi phục (verified restore)**; bắt và báo lỗi chính xác đến từng dòng lệnh; viết code sạch qua `shellcheck`; và lập lịch chạy tự động bằng `cron`.

---

## Phần 0 — Chuẩn bị môi trường (làm trước tiên)

### 0.1. Máy ảo

Một VM **CentOS Stream 9** *hoặc* **Ubuntu Server 22.04**. Ghi rõ bản phân phối trong báo cáo, vì tên dịch vụ khác nhau:

| Dịch vụ | CentOS Stream 9 | Ubuntu 22.04 |
|---|---|---|
| SSH | `sshd` | `ssh` |
| Cron | `crond` | `cron` |
| Cài shellcheck | `dnf install epel-release && dnf install ShellCheck` | `apt install shellcheck` |

### 0.2. Tạo dữ liệu mẫu

Tạo thư mục dữ liệu, cố ý thêm file `.log` và `.tmp` để kiểm tra việc loại trừ khi backup:

```bash
mkdir -p ~/web01-data/docs
echo "hello from web01"          > ~/web01-data/index.html
echo "tài liệu nội bộ"            > ~/web01-data/docs/readme.txt
echo "log không cần backup"       > ~/web01-data/access.log
echo "file tạm không cần backup"  > ~/web01-data/cache.tmp
```

### 0.3. Web endpoint mẫu (`server.py`)

Lưu file sau ở **ngoài** thư mục dữ liệu, ví dụ `~/web01-ops/server.py` hoặc `/opt/web01/server.py`:

```python
#!/usr/bin/env python3
"""web01 — web endpoint tối giản cho bài tập (chỉ dùng thư viện chuẩn).

Cách chạy:  python3 server.py <thư_mục_dữ_liệu> [cổng]
  GET /         -> phục vụ file trong thư mục dữ liệu
  GET /health   -> trả về "OK" (dùng cho health-check)
"""
import sys
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
BIND = "127.0.0.1"   # chỉ nghe nội bộ, không mở ra mạng ngoài


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b"OK\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()


if __name__ == "__main__":
    handler = partial(Handler, directory=DATA_DIR)
    with ThreadingHTTPServer((BIND, PORT), handler) as httpd:
        print(f"web01: phục vụ {DATA_DIR} tại http://{BIND}:{PORT} (health: /health)")
        httpd.serve_forever()
```

Chạy, kiểm tra và dừng:

```bash
# Chạy nền, ghi log ra ngoài thư mục dữ liệu
mkdir -p ~/logs
nohup python3 ~/web01-ops/server.py ~/web01-data 8080 > ~/logs/web01.log 2>&1 &

# Kiểm tra
curl -sf http://127.0.0.1:8080/health          # -> OK
curl -s  http://127.0.0.1:8080/index.html      # -> hello from web01

# Dừng (dùng khi giả lập sự cố ở Task 1)
pkill -f server.py
```

### 0.4. Gửi email

Cấu hình `msmtp` (hoặc `mail`) gửi đến một hộp thư test. **Nếu không có SMTP relay**, cho hàm `send_alert()` ghi thư ra file (ví dụ `/var/log/web01-mail.log`) để vẫn quan sát được cảnh báo. Gợi ý: dùng biến `MAIL_MODE="smtp"` hoặc `MAIL_MODE="file"` trong file cấu hình. **Ghi rõ lựa chọn trong báo cáo.**

### 0.5. Đích backup

Chọn một trong hai, ghi rõ trong báo cáo:

- **Phương án A:** VM thứ hai, truy cập SSH bằng key (không mật khẩu). `DEST="backup@10.0.0.20:/srv/backups/web01"`.
- **Phương án B (dự phòng):** một thư mục local đóng vai máy remote. `DEST="/srv/backup-target"`.

### 0.6. File cấu hình

Tạo `/etc/monitoring.env` và `/etc/backup.env` với **owner root, quyền `600`**:

```bash
sudo touch /etc/monitoring.env /etc/backup.env
sudo chown root:root /etc/monitoring.env /etc/backup.env
sudo chmod 600 /etc/monitoring.env /etc/backup.env
```

Vì file chỉ root đọc được, **các script phải chạy bằng root** (`sudo ./health-check.sh`, và đặt cron trong crontab của root hoặc `/etc/cron.d`).

Trong bài nộp chỉ đưa **file mẫu** với giá trị giả (thư mục `examples/`). **Không đưa file `.env` thật** (có thể chứa mật khẩu SMTP) vào file `.zip`.

```bash
# examples/monitoring.env.example
ALERT_TO="admin@example.com"
MAIL_MODE="smtp"                 # smtp | file
DISK_THRESHOLD=80                # cảnh báo khi / dùng trên 80%
RAM_MIN_FREE=10                  # cảnh báo khi RAM khả dụng dưới 10%
SERVICES="sshd crond"            # Ubuntu: "ssh cron"
HEALTH_URL="http://127.0.0.1:8080/health"
```

```bash
# examples/backup.env.example
DATA_DIR="/home/student/web01-data"   # dùng đường dẫn tuyệt đối, KHÔNG dùng ~
DEST="/srv/backup-target"             # hoặc user@host:/path
RETAIN_DAYS=7
ALERT_TO="admin@example.com"
MAIL_MODE="smtp"
```

> Lưu ý: không dùng `~` trong file cấu hình. Khi chạy bằng root hoặc cron, `~` thành `/root`, không còn là thư mục của bạn.

### Quy ước chung cho mọi script

1. Dòng đầu là `#!/usr/bin/env bash`, ngay sau đó là `set -euo pipefail`.
2. **Source file cấu hình**, không hard-code giá trị.
3. Kiểm tra biến bắt buộc ngay sau khi source, ví dụ `: "${ALERT_TO:?thiếu ALERT_TO}"`.
4. Dùng đường dẫn tuyệt đối cho file và thư mục.

---

## Task 1 — Health-check có cảnh báo email (2.5 điểm)

*Dựa trên Lab 1.* Viết `health-check.sh` kiểm tra `web01` và gửi **đúng một** email khi, và chỉ khi, có vấn đề.

### Yêu cầu

1. Source `/etc/monitoring.env` để lấy `ALERT_TO`, `DISK_THRESHOLD`, `RAM_MIN_FREE`, `SERVICES`, `HEALTH_URL`.
2. Gom các phát hiện vào mảng `ALERTS=()`. **Chỉ quyết định gửi mail một lần ở cuối script**, không gửi rải rác.
3. Kiểm tra tối thiểu 4 nhóm:

| Kiểm tra | Cách làm gợi ý | Điều kiện cảnh báo |
|---|---|---|
| Dung lượng phân vùng `/` | `df --output=pcent /` | % sử dụng > `DISK_THRESHOLD` |
| RAM khả dụng | `MemAvailable` / `MemTotal` trong `/proc/meminfo` | % khả dụng < `RAM_MIN_FREE` |
| Từng dịch vụ trong `$SERVICES` | `systemctl is-active --quiet <unit>` | Dịch vụ không ở trạng thái active |
| Web endpoint | `curl -sf --max-time 5 "$HEALTH_URL"` | curl thất bại hoặc timeout |

4. Chỉ thêm vào `ALERTS` khi **vượt ngưỡng**. Máy khỏe thì **không in gì, không gửi gì, thoát mã `0`**. Khi có cảnh báo, nên thoát với mã khác 0 (ví dụ `1`) sau khi gửi mail.
5. Viết hàm `send_alert()` gửi một email dễ đọc: **tiêu đề có hostname** (ví dụ `[ALERT] web01: 2 vấn đề`), nội dung liệt kê **tất cả** phát hiện, kèm thời điểm kiểm tra.
6. Một phép kiểm tra thất bại **không được làm dừng toàn bộ script** (vì đang bật `set -e`). Mọi chỉ số vẫn phải được kiểm tra. Gợi ý: `lệnh_kiểm_tra || ALERTS+=("mô tả lỗi")`.

### Tiêu chí nghiệm thu (phải chứng minh trong báo cáo)

- Máy khỏe: script chạy im lặng, không có email, `echo $?` ra `0`.
- Hạ một ngưỡng (ví dụ `DISK_THRESHOLD=1`) **hoặc** tắt endpoint (`pkill -f server.py`): lần chạy kế tiếp gửi **đúng một** email, có tên máy và chỉ số vi phạm.
- **Đồng thời** hạ ngưỡng disk **và** tắt endpoint: email liệt kê **cả hai** vấn đề, chứng tỏ các kiểm tra khác vẫn chạy sau khi curl thất bại.

**Nộp:** `health-check.sh`, `examples/monitoring.env.example`, ảnh chụp (a) lần chạy im lặng khi máy khỏe, (b) email cảnh báo nhiều vấn đề.

---

## Task 2 — Backup tự động, dọn dẹp an toàn (2.5 điểm)

*Dựa trên Lab 2.* Viết `backup.sh` nén thư mục dữ liệu, chuyển ra khỏi máy, xoay vòng bản cũ, và **không bao giờ để lại một bản backup dở dang trông như hợp lệ**.

### Yêu cầu

1. Source `/etc/backup.env` để lấy `DATA_DIR`, `DEST`, `RETAIN_DAYS`, `ALERT_TO`. Kiểm tra biến bắt buộc, ví dụ `: "${DATA_DIR:?thiếu DATA_DIR}"`.
2. Tạo thư mục làm việc tạm bằng `mktemp -d`. Đăng ký `trap cleanup EXIT`. Hàm `cleanup()`:
   - đọc `$?` **ngay dòng đầu tiên** của hàm;
   - nếu khác 0: gửi email tiêu đề **"BACKUP FAILED"** kèm hostname;
   - **trong mọi trường hợp**: xóa thư mục tạm.
3. **Tạo manifest trước khi nén**: checksum của từng file, dùng **đường dẫn tương đối** và **loại trừ đúng các file sẽ bị loại khỏi archive**:
   ```bash
   cd "$DATA_DIR"
   find . -type f ! -name '*.log' ! -name '*.tmp' -exec md5sum {} + > "$WORKDIR/manifest.txt"
   ```
   *Vì sao tương đối:* nếu manifest chứa đường dẫn tuyệt đối, khi giải nén sang thư mục khác `md5sum -c` sẽ kiểm tra nhầm file gốc. *Vì sao phải loại trừ giống nhau:* nếu manifest có `access.log` mà archive không có, bước kiểm chứng sẽ báo thiếu file.
4. Nén thành file có timestamp, tên theo mẫu `web01-backup-YYYYmmdd-HHMMSS.tar.gz`, **gồm dữ liệu và `manifest.txt`**, loại trừ `*.log` và `*.tmp`. Sau đó chuyển sang `$DEST` bằng `cp` (phương án B) hoặc `rsync -az` (phương án A).
5. **Xoay vòng:** xóa archive cũ hơn `$RETAIN_DAYS` ngày tại đích. Luôn giới hạn theo mẫu tên để không xóa nhầm file khác:
   ```bash
   find "$DEST" -name 'web01-backup-*.tar.gz' -mtime +"$RETAIN_DAYS" -delete
   ```
   (Phương án A: chạy lệnh này qua `ssh`.)
6. Thành công: gửi email ngắn **"Backup OK"** gồm tên archive, dung lượng và đích.
7. Viết thêm `restore-test.sh`:
   - tìm archive **mới nhất** tại `$DEST`;
   - giải nén vào thư mục tạm (`mktemp -d`), dọn thư mục này khi kết thúc;
   - chạy `md5sum -c manifest.txt` **bên trong** thư mục đã giải nén;
   - in kết quả dạng `Restore test: 3/3 file OK` và thoát mã khác 0 nếu có file sai.

### Tiêu chí nghiệm thu

- Chạy `backup.sh` tạo ra file `.tar.gz` có ngày giờ tại `$DEST`.
- **Kiểm chứng xoay vòng:** tạo vài archive giả "cũ", chạy lại `backup.sh`, chứng minh bản cũ bị xóa còn bản mới được giữ:
  ```bash
  touch -d "10 days ago" /srv/backup-target/web01-backup-20260101-020000.tar.gz
  ```
- `tar -tzf <archive>` cho thấy có `manifest.txt` và **không có** `access.log`, `cache.tmp`.
- `restore-test.sh` báo **tất cả file OK**. *Backup không có restore được kiểm chứng thì yêu cầu 7 được **0 điểm**.*
- **Giả lập lỗi** (ví dụ trỏ `DATA_DIR` tới thư mục không tồn tại): chứng minh `trap` đã chạy, tức là có email "BACKUP FAILED" **và** thư mục tạm đã bị xóa (chụp `ls /tmp` trước và sau).

**Nộp:** `backup.sh`, `restore-test.sh`, `examples/backup.env.example`, ảnh chụp: lần chạy thành công, danh sách archive tại đích (trước/sau xoay vòng), kết quả restore-test, email báo lỗi.

---

## Task 3 — Bắt lỗi và kiểm tra code (2.0 điểm)

*Dựa trên Lab 3.* Làm cho mọi lỗi không thể bị bỏ sót, rồi chứng minh code sạch.

### Yêu cầu

1. Thêm handler `on_error()` vào **một** script (khuyến nghị `backup.sh`), gắn bằng:
   ```bash
   set -Eeuo pipefail      # -E để trap ERR có hiệu lực cả trong hàm
   trap 'on_error $LINENO "$BASH_COMMAND"' ERR
   ```
2. Handler gửi email gồm: **số dòng** lỗi, **lệnh** gây lỗi, **mã thoát** (exit code), **hostname**. Lưu `$?` vào biến ngay dòng đầu của handler, trước khi chạy bất kỳ lệnh nào khác.
3. Nếu script đã có `trap cleanup EXIT` (như `backup.sh`), tránh gửi **hai** email cho cùng một lỗi. Gợi ý: `on_error()` đặt một cờ, ví dụ `ERROR_REPORTED=1`, và `cleanup()` kiểm tra cờ này trước khi gửi "BACKUP FAILED".
4. Cố ý đưa vào **một lỗi thật**, ví dụ:
   ```bash
   tar -czf /tmp/out.tgz /no/such/dir
   echo "DÒNG NÀY KHÔNG ĐƯỢC IN RA"
   ```
   Chứng minh script dừng **đúng tại dòng đó**, lệnh phía sau không chạy.
5. Chạy `shellcheck` trên **tất cả** script và sửa **mọi** cảnh báo. Với dòng `source /etc/...env`, có thể thêm chỉ thị `# shellcheck source=/dev/null` ngay phía trên. Nếu không cài được shellcheck, dùng shellcheck.net và ghi chú trong báo cáo.

### Tiêu chí nghiệm thu

- Lỗi cố ý làm script dừng đúng dòng; email cảnh báo có đủ dòng + lệnh + mã thoát + hostname.
- `shellcheck *.sh lib/*.sh` **không còn cảnh báo nào** (dán output sạch).

**Nộp:** script đã gắn handler, ảnh chụp email báo lỗi, output `shellcheck` **trước và sau** khi sửa.

---

## Task 4 — Lập lịch với cron (1.5 điểm)

*Dựa trên Lab 4.* Để mọi thứ tự chạy.

### Yêu cầu

1. Lập lịch `health-check.sh` **mỗi 5 phút**, `backup.sh` **hằng ngày lúc 02:00**. Dùng crontab của root (`sudo crontab -e`) **hoặc** file `/etc/cron.d/web01-ops` (lưu ý: định dạng `cron.d` có **thêm cột user**).
2. Đảm bảo môi trường tối giản của cron không làm hỏng script: khai báo `PATH` ở đầu crontab, dùng đường dẫn tuyệt đối cho script, không phụ thuộc thư mục hiện hành hay biến môi trường của shell đăng nhập.
3. Chuyển output của mỗi job vào log riêng, ví dụ `/var/log/web01-health.log` và `/var/log/web01-backup.log`, ghi cả stdout và stderr (`>> file 2>&1`).
4. **Để chấm bài:** tạm đặt health-check thành `*/1` (mỗi phút), cho chạy vài phút, gây một sự cố trong khoảng đó, rồi **trả lại `*/5`**.

Mẫu `/etc/cron.d/web01-ops`:

```cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# phút giờ ngày tháng thứ  user  lệnh
*/5 * * * *   root  /opt/web01-ops/health-check.sh >> /var/log/web01-health.log 2>&1
0   2 * * *   root  /opt/web01-ops/backup.sh       >> /var/log/web01-backup.log 2>&1
```

### Tiêu chí nghiệm thu

- `sudo crontab -l` (hoặc `cat /etc/cron.d/web01-ops`) hiển thị cả hai job.
- Log cho thấy health-check chạy đúng lịch (gợi ý: dùng `journalctl -u cron` / `journalctl -u crond`, hoặc ghi một dòng timestamp vào log mỗi lần cron gọi job). Một sự cố trong khoảng thời gian đó đã sinh ra email.
- Báo cáo **giải thích**: vì sao một job chạy tay thì được nhưng chạy bằng cron lại hỏng (PATH khác, không có biến môi trường, thư mục hiện hành khác, `~` khác, quyền user khác…).

**Nộp:** file crontab / cron.d và trích đoạn log chứng minh các lần chạy theo lịch.

---

## Sản phẩm nộp & trình bày (1.5 điểm)

Nộp **một file `.zip`** với cấu trúc:

```
web01-ops/
├── server.py              # web endpoint (có thể dùng nguyên mẫu ở Phần 0)
├── health-check.sh
├── backup.sh
├── restore-test.sh
├── lib/                   # không bắt buộc: send_alert() dùng chung, ...
├── cron/                  # file crontab hoặc cron.d
├── examples/
│   ├── monitoring.env.example
│   └── backup.env.example
├── REPORT.md              # hoặc PDF: bằng chứng cho từng tiêu chí nghiệm thu
└── README.md              # hướng dẫn cài đặt và cách chạy
```

Phần điểm này đánh giá: cấu trúc thư mục đúng; `README.md` đủ để người khác dựng lại môi trường và chạy được các script; `REPORT.md` trình bày rõ ràng, có chú thích cho từng bằng chứng; không lộ thông tin nhạy cảm (mật khẩu, file `.env` thật) trong bài nộp.

**`REPORT.md`** phải có, cho **từng task**, bằng chứng của từng tiêu chí nghiệm thu: ảnh chụp có chú thích (hoặc link video ngắn) gồm email cảnh báo, danh sách archive, kết quả kiểm chứng manifest, email báo lỗi, output `shellcheck` sạch, log cron. **Bằng chứng là thứ mang lại điểm.** Script không có bằng chứng chạy được sẽ nhận rất ít điểm.

---

## Bảng điểm tóm tắt

| Phần | Nội dung | Điểm |
|---|---|---|
| Task 1 | Health-check + cảnh báo email | 2.5 |
| Task 2 | Backup, xoay vòng, restore có kiểm chứng | 2.5 |
| Task 3 | `trap ERR` + `shellcheck` sạch | 2.0 |
| Task 4 | Lập lịch cron | 1.5 |
| Nộp bài | Cấu trúc, README, REPORT | 1.5 |
| **Tổng** | | **10.0** |

## Lỗi thường gặp (đọc trước khi làm)

- **Script dừng ngay ở phép kiểm tra đầu tiên bị lỗi** → quên `|| ALERTS+=(...)`, nên `set -e` thoát luôn.
- **`md5sum -c` báo "No such file"** → manifest dùng đường dẫn tuyệt đối, hoặc manifest có file `.log`/`.tmp` mà archive đã loại trừ.
- **Chạy tay được, cron không chạy** → `PATH` thiếu, dùng `~`, dùng đường dẫn tương đối, hoặc job chạy dưới user không đọc được `/etc/*.env`.
- **Nhận hai email cho một lỗi** → `trap ERR` và `trap EXIT` cùng gửi mail mà không có cờ chặn.
- **`find -delete` xóa nhầm** → quên giới hạn `-name 'web01-backup-*.tar.gz'`.
