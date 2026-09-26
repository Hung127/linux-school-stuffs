# DANH SÁCH ĐỀ TÀI SEMINAR

---

### 1. Nginx Web Server & Reverse Proxy
**Yêu cầu hạ tầng:** 1 VM (512MB RAM)

**A. Nội dung lý thuyết**
* Vai trò của Web Server và Reverse Proxy trong kiến trúc Web; lý do không để backend nhận request trực tiếp từ Internet.
* Kiến trúc xử lý sự kiện (Event-driven) của Nginx so với mô hình tiến trình/luồng (Process/Thread) của Apache; hệ quả khi số kết nối đồng thời lớn.
* Cơ chế Server Block (Virtual Host): Cách Nginx phân biệt nhiều site trên cùng 1 IP.
* Vị trí, cấu trúc và cách phân tích `access.log`, `error.log`; phân biệt các mã lỗi 502, 503, 504.

**B. Các demo bắt buộc**
1. **Virtual Host:** Cấu hình 2 Server Block phục vụ 2 trang HTML tĩnh ứng với 2 tên miền khác nhau trên cùng một IP.
2. **Reverse Proxy & HTTPS:** Cấu hình Nginx làm Reverse Proxy chuyển tiếp traffic về ứng dụng Node.js/Python (chạy trên `127.0.0.1`) + Bật HTTPS bằng Self-signed Certificate.
3. **Rate Limiting & Benchmark:** Cấu hình Rate Limit (dùng `burst` và `nodelay`), dùng công cụ `ab` hoặc `wrk` gửi 100 request đồng thời để kiểm tra thống kê mã HTTP 200 và 503.
4. **Demo sự cố (Troubleshooting):** Tắt dịch vụ backend, chụp hình trang lỗi tùy chỉnh trên trình duyệt và xuất dòng log lỗi tương ứng trong `error.log`.

---

### 2. MongoDB Document Database Server
**Yêu cầu hạ tầng:** 1 VM (1GB RAM)

**A. Nội dung lý thuyết**
* Mô hình NoSQL dạng Document (JSON/BSON) so với mô hình quan hệ (RDBMS); trường hợp nên và không nên sử dụng NoSQL.
* Cơ chế kiểm soát truy cập và xác thực trong MongoDB: Cấu hình `bindIp`, bật Authentication, phân quyền dựa trên vai trò (Role-Based Access Control - RBAC).
* Nguyên lý Index trong MongoDB (Single Field, Compound Index); cách đọc Kế hoạch thực thi truy vấn với `.explain()`.
* So sánh các phương pháp sao lưu/phục hồi trong MongoDB: Logical Backup (`mongodump`/`mongorestore`) và phương pháp sao lưu tầng tập tin (Filesystem Snapshot).

**B. Các demo bắt buộc**
1. **Kiểm soát kết nối & Phân quyền:** Bật Authentication trong file cấu hình `/etc/mongod.conf`, tạo tài khoản Admin và tài khoản User thường chỉ có quyền đọc/ghi trên 1 Database cụ thể; cấu hình `bindIp` cho phép kết nối từ máy Host và kiểm chứng xác thực.
2. **Tối ưu truy vấn (Indexing):** Viết script (Python hoặc JavaScript) chèn 100.000 document dữ liệu mẫu; thực thi `.explain("executionStats")` cho một truy vấn tìm kiếm trước và sau khi tạo Index, so sánh thời gian thực thi và kiểu quét (`COLLSCAN` so với `IXSCAN`).
3. **Sao lưu & Phục hồi:** Thực hiện sao lưu dữ liệu bằng `mongodump` ra file BSON, xóa một Collection hoặc Database, sau đó dùng `mongorestore` để khôi phục và đối chiếu lại số lượng document.
4. **Demo sự cố (Troubleshooting):** Cố tình cấu hình sai định dạng file `/etc/mongod.conf` (lỗi indentation dạng YAML) hoặc gán sai quyền sở hữu thư mục dữ liệu `/var/lib/mongodb`, quan sát dịch vụ `mongod` không khởi động được, đọc file `/var/log/mongodb/mongod.log` để tìm nguyên nhân và khắc phục.

---

### 3. MySQL Database Server
**Yêu cầu hạ tầng:** 1 VM (1GB RAM)

**A. Nội dung lý thuyết**
* Kiến trúc MySQL: Phân biệt Server Layer và Storage Engine (so sánh InnoDB và MyISAM).
* Cơ chế quản lý người dùng và phân quyền (Privileges System) trong MySQL (`GRANT`/`REVOKE`).
* Cơ chế lưu trữ nhật ký: Binary Log (binlog) và Slow Query Log.
* Nguyên lý giao dịch (Transaction) và tính chất ACID cơ bản trong InnoDB.

**B. Các demo bắt buộc**
1. **Cài đặt & Bảo mật:** Cài đặt MySQL, chạy `mysql_secure_installation`, cấu hình cho phép kết nối từ xa an toàn cho một User cụ thể.
2. **Phân tích truy vấn chậm:** Bật `slow_query_log`, tạo một truy vấn cố tình chạy chậm, dùng công cụ `mysqldumpslow` để phân tích file log.
3. **Sao lưu & Phục hồi:** Thực hiện sao lưu logic bằng `mysqldump` và khôi phục lại dữ liệu trên một database sạch.
4. **Demo sự cố (Troubleshooting):** Cố tình sửa sai quyền sở hữu thư mục dữ liệu `/var/lib/mysql`, quan sát dịch vụ không khởi động được, đọc file `/var/log/mysql/error.log` để tìm nguyên nhân và khắc phục.

---

### 4. Docker CE (Single Node)
**Yêu cầu hạ tầng:** 1 VM (1GB RAM)

**A. Nội dung lý thuyết**
* Container so với Máy ảo (VM): Khác biệt kiến trúc, vai trò của Namespace và Cgroup trong Kernel Linux.
* Cơ chế Layer của Docker Image và cách hoạt động của Build Cache.
* Tác dụng của Multi-stage Build trong việc tối ưu dung lượng Image.
* Quản lý dữ liệu Container: Phân biệt Bind Mount và Named Volume.

**B. Các demo bắt buộc**
1. **Multi-stage Build:** Viết `Dockerfile` cho ứng dụng web bằng Multi-stage Build; so sánh dung lượng Image đầu ra với cách build thông thường.
2. **Thử nghiệm Layer Cache:** Sửa đổi mã nguồn ứng dụng, thực hiện `docker build` ở hai vị trí lệnh `COPY` khác nhau trong Dockerfile và so sánh thời gian build.
3. **Đóng gói Đa dịch vụ:** Dùng `docker-compose.yml` để khởi chạy Web + Database kết nối qua Docker Network, đọc mật khẩu từ file `.env` và chạy ứng dụng dưới quyền Non-root User.
4. **Demo sự cố (Troubleshooting):** Xóa Container Database không gắn Volume (chứng minh mất dữ liệu); lặp lại thao tác với Container có gắn Named Volume (chứng minh dữ liệu được giữ lại).

---

### 5. Docker Swarm Orchestration
**Yêu cầu hạ tầng:** 2 VM (Mỗi máy 1GB RAM)

**A. Nội dung lý thuyết**
* Khái niệm Container Orchestration: Lý do Docker đơn lẻ không đủ đáp ứng môi trường Production.
* Phân định vai trò Manager Node và Worker Node; cơ chế Desired State và Reconciliation.
* Cơ chế Routing Mesh: Mạng Overlay và cách truy cập Service từ IP của bất kỳ Node nào.
* Chiến lược Rolling Update và ý nghĩa các tham số `update-parallelism`, `update-delay`.

**B. Các demo bắt buộc**
1. **Khởi tạo Cụm & Routing Mesh:** Khởi tạo Swarm, join Worker Node, deploy một Web Service với 3 Replicas; chứng minh Routing Mesh bằng cách truy cập IP của cả 2 VM.
2. **Rolling Update Zero-Downtime:** Cập nhật Service từ Image v1 lên v2; chạy script `curl` liên tục để ghi log kiểm tra tỉ lệ request và chứng minh không đứt gãy dịch vụ.
3. **Quản lý Bí mật (Secrets):** Dùng `docker secret` để truyền mật khẩu Database vào Service thay vì dùng biến môi trường.
4. **Demo sự cố (Troubleshooting):** Tắt đột ngột VM Worker, quan sát trên VM Manager quá trình Swarm phát hiện và tự động khởi tạo lại các Task bị mất sang Node còn sống.

---

### 6. HAProxy Load Balancer
**Yêu cầu hạ tầng:** 3 VM (Mỗi máy 512MB RAM — 1 HAProxy, 2 Backend Web)

**A. Nội dung lý thuyết**
* Khái niệm Cân bằng tải (Load Balancing) và Tính sẵn sàng cao (High Availability).
* So sánh các thuật toán cân bằng tải: `roundrobin`, `leastconn`, `source`.
* Vấn đề Sticky Session khi ứng dụng lưu Session trong RAM và giải pháp xử lý.
* Cơ chế Health Check: Ý nghĩa các tham số `inter`, `rise`, `fall`.

**B. Các demo bắt buộc**
1. **Cân bằng tải cơ bản:** Cấu hình HAProxy phân phối traffic theo thuật toán `roundrobin` tới 2 Backend Web có giao diện nhận diện riêng + Bật trang HAProxy Stats.
2. **Thuật toán IP Hash:** Đổi thuật toán sang `source`, thực hiện truy cập từ nhiều Client khác nhau để chứng minh IP cố định luôn vào đúng 1 Backend.
3. **Tối ưu Health Check:** Cấu hình Health Check; tắt 1 Backend Web, dùng đồng hồ đo thời gian HAProxy cô lập Node hỏng dưới bộ tham số mặc định và bộ tham số rút ngắn (`inter 1s rise 2 fall 2`).
4. **Demo sự cố (Troubleshooting):** Tắt đồng thời cả 2 Backend Web, quan sát mã lỗi 503 trả về Client, cấu hình HAProxy hiển thị trang lỗi tùy chỉnh (Custom Error Page).

---

### 7. Redis In-Memory Data Store
**Yêu cầu hạ tầng:** 1 VM (512MB RAM)

**A. Nội dung lý thuyết**
* Vai trò của Caching trong kiến trúc hệ thống; mô hình Cache-Aside.
* Lý do Redis hoạt động Đơn luồng (Single-threaded) nhưng vẫn đạt hiệu năng cao.
* So sánh 2 cơ chế lưu trữ bền vững (Persistence): RDB (Snapshotting) và AOF (Append-Only File).
* Các chính sách loại bỏ dữ liệu (Eviction Policies) khi hết bộ nhớ (`noeviction`, `allkeys-lru`, `volatile-ttl`).

**B. Các demo bắt buộc**
1. **Cấu trúc dữ liệu & TTL:** Thao tác các kiểu dữ liệu String, List, Hash, Sorted Set (làm bảng xếp hạng) và thiết lập thời gian sống (TTL) cho Key.
2. **Tích hợp Cache-Aside:** Viết script Python/PHP mô phỏng truy vấn CSDL chậm (~300ms); thêm lớp Cache Redis và đo thời gian phản hồi ở lần Cache Miss (đầu tiên) và Cache Hit (các lần sau).
3. **Thử nghiệm Eviction Policy:** Giới hạn `maxmemory` nhỏ (ví dụ 10MB) + cấu hình `allkeys-lru`, ghi dữ liệu tràn dung lượng và quan sát các Key cũ bị tự động xóa.
4. **Demo sự cố (Troubleshooting):** Giả lập sập nguồn đột ngột (`kill -9` tiến trình Redis) sau khi vừa ghi dữ liệu; so sánh mức độ mất mát dữ liệu giữa hai cấu hình bật RDB thuần túy và bật AOF (`appendfsync everysec`).

---

### 8. NFS Network File System
**Yêu cầu hạ tầng:** 2 VM (Mỗi máy 512MB RAM — 1 Server, 1 Client)

**A. Nội dung lý thuyết**
* Khái niệm Network File System; so sánh NFS và SMB/CIFS.
* Cơ chế phân quyền trong NFS dựa trên UID/GID của hệ điều hành Linux; rủi ro khi lệch UID.
* Ý nghĩa của các tùy chọn Export: `root_squash`, `no_root_squash` và rủi ro bảo mật.
* Phân biệt chế độ Mount: `hard mount` và `soft mount`.

**B. Các demo bắt buộc**
1. **Chia sẻ & Tự động Mount:** Export thư mục trên Server, cấu hình Client tự động mount qua `/etc/fstab` với quyền đọc/ghi (`rw`).
2. **Kiểm tra Phân quyền & Squash:** Thực nghiệm tạo file từ tài khoản `root` trên Client khi bật `root_squash` (file bị chuyển thành `nobody`) và khi bật `no_root_squash`.
3. **Thử nghiệm Lệch UID:** Tạo User `sv1` trên Server (UID 1001) và User `sv2` trên Client (UID 1002); tạo file từ Client và quan sát quyền sở hữu hiển thị trên Server.
4. **Demo sự cố (Troubleshooting):** Thực hiện lệnh ghi file dung lượng lớn (`dd`) từ Client, trong lúc ghi ngắt kết nối mạng NFS Server; so sánh hiện tượng treo hệ thống giữa `hard mount` và `soft mount`.

---

### 9. Ansible Configuration Management
**Yêu cầu hạ tầng:** 2 VM (Mỗi máy 512MB RAM — 1 Control Node, 1 Managed Node)

**A. Nội dung lý thuyết**
* Khái niệm **Idempotent** (Tính toàn vẹn/độc lập với số lần chạy) — nguyên lý cốt lõi của Configuration Management.
* Kiến trúc Agentless của Ansible qua kết nối SSH; so sánh với các công cụ dùng Agent.
* Các thành phần cơ bản: Inventory, Playbook, Task, Role, Handler, Template (Jinja2).
* Lý do nên dùng Module chuyên dụng (`copy`, `lineinfile`, `systemd`) thay vì dùng module `shell`/`command`.

**B. Các demo bắt buộc**
1. **Khởi tạo & Role cơ bản:** Thiết lập SSH Key-based authentication; viết Playbook dạng Structure Role để tự động cài đặt và cấu hình Nginx.
2. **Template & Handler:** Dùng Jinja2 Template để sinh file cấu hình Nginx theo biến; dùng `handlers` để chỉ restart dịch vụ Nginx khi file cấu hình thực sự có sự thay đổi.
3. **Mã hóa Bảo mật:** Dùng `ansible-vault` để mã hóa các biến chứa thông tin nhạy cảm (mật khẩu, secret key) trong Playbook.
4. **Demo sự cố & Idempotency:** Viết 1 Task không có tính Idempotent (`shell: echo "data" >> /file.txt`), chạy Playbook 3 lần để cho thấy file bị ghi lặp; sửa lại Task dùng module `lineinfile` và chạy lại để chứng minh trạng thái `changed=0`.

---

### 10. Prometheus & Grafana Monitoring
**Yêu cầu hạ tầng:** 2 VM (1 VM 1.5GB RAM chạy Prometheus+Grafana, 1 VM 512MB RAM làm Target)

**A. Nội dung lý thuyết**
* Mô hình **Pull** (Prometheus kéo dữ liệu) so với mô hình **Push**; ưu nhược điểm.
* Các loại Metric cơ bản: Counter, Gauge, Histogram, Summary. Lý do Counter luôn cần dùng kèm hàm `rate()`.
* Vòng đời của một Cảnh báo (Alert Lifecycle): Inactive -> Pending -> Firing.
* Cách Prometheus lưu trữ dữ liệu chuỗi thời gian (Time-Series Database).

**B. Các demo bắt buộc**
1. **Thu thập & Hiển thị:** Cài đặt Node Exporter trên Target, cấu hình Prometheus scrape dữ liệu; dựng Grafana Dashboard hiển thị biểu đồ CPU, RAM, Disk theo thời gian thực.
2. **Truy vấn PromQL:** Viết và giải thích 3 câu truy vấn PromQL lấy thông tin hệ thống (bắt buộc có 1 câu sử dụng hàm `rate()` để tính tốc độ tăng trưởng).
3. **Cấu hình Alerting:** Cấu hình Alertmanager gửi cảnh báo khi CPU > 80% trong 1 phút; dùng lệnh `stress-ng` ép tải CPU để minh họa trạng thái chuyển từ `Pending` sang `Firing`.
4. **Demo sự cố (Troubleshooting):** Tắt dịch vụ Node Exporter (Target VM vẫn sống) và tắt hẳn Target VM; phân tích sự khác biệt về dữ liệu metric nhận được trên Prometheus để phân biệt lỗi "mất Exporter" và "sập Server".

---

### 11. ELK Stack (Centralized Logging)
**Yêu cầu hạ tầng:** 1 VM (3GB RAM - Java Heap set 1GB, dùng Filebeat đẩy thẳng Elasticsearch, tắt X-Pack Security)

**A. Nội dung lý thuyết**
* Bài toán Quản lý Log tập trung trong hệ thống nhiều máy chủ.
* Vai trò của Filebeat, Elasticsearch và Kibana trong chuỗi xử lý Log.
* Nguyên lý Bảng chỉ mục đảo (Inverted Index) của Elasticsearch.
* Tầm quan trọng của việc Parse Log (biến Unstructured Text thành Structured JSON Fields).

**B. Các demo bắt buộc**
1. **Đẩy & Parse Log:** Cấu hình Filebeat đọc `/var/log/nginx/access.log`, dùng Ingest Pipeline hoặc Filebeat Nginx Module để bóc tách thành các trường: `client_ip`, `status_code`, `request_url`.
2. **Dựng Dashboard Kibana:** Tạo biểu đồ tổng số Request theo thời gian, biểu đồ tròn phân bố các mã trạng thái HTTP (200, 404, 500).
3. **Điều tra Sự cố (Log Analysis):** Dùng lệnh `curl` lặp lại các đường dẫn không tồn tại để giả lập hành vi quét lỗ hổng; truy vấn trên Kibana để lọc ra IP phát sinh nhiều lỗi 404 nhất và các URL bị quét.
4. **Demo sự cố (Troubleshooting):** Dừng Elasticsearch trong 3 phút trong khi Web Server vẫn nhận traffic; bật lại Elasticsearch và kiểm tra cơ chế Registry của Filebeat để chứng minh dữ liệu log được gửi bù đầy đủ, không bị mất.

---

### 12. BorgBackup (Deduplicated Backup)
**Yêu cầu hạ tầng:** 2 VM (Mỗi máy 512MB RAM — 1 Production Node, 1 Backup Server)

**A. Nội dung lý thuyết**
* Phân loại Sao lưu: Full, Incremental, Differential; cơ chế Deduplication (Khử trùng lặp) của BorgBackup.
* Quy tắc sao lưu 3-2-1 và cách triển khai trong môi trường Linux thực tế.
* Khái niệm RPO (Recovery Point Objective) và RTO (Recovery Time Objective).
* Chế độ `--append-only` và kịch bản chống tấn công mã hóa dữ liệu (Ransomware).

**B. Các demo bắt buộc**
1. **Khởi tạo & Khử trùng lặp:** Khai báo Repository từ xa qua SSH; thực hiện sao lưu dữ liệu qua 3 "ngày" (mỗi ngày sửa đổi một phần nhỏ dữ liệu); đọc thông số `borg info` để chứng minh hiệu quả tiết kiệm dung lượng của Deduplication.
2. **Bảo mật Append-Only:** Cấu hình quyền `command="borg serve --append-only"` trong file `authorized_keys` trên Backup Server; từ Production Node thực hiện lệnh `borg delete` để chứng minh thao tác xóa backup bị từ chối.
3. **Phục hồi Dữ liệu:** Dùng `borg mount` (FUSE) để mount bản sao lưu thành một thư mục trên hệ thống, duyệt tập tin và khôi phục lại 1 file bị xóa nhầm.
4. **Demo sự cố (Kịch bản Thảm họa):** Xóa toàn bộ thư mục dữ liệu gốc trên Production Node; thực hiện quy trình khôi phục đầy đủ (Full Restore) từ Backup Server, bấm giờ từng bước để tính toán chỉ số RTO thực tế.

---

### 13. BIND9 Domain Name System (DNS)
**Yêu cầu hạ tầng:** 2 VM (Mỗi máy 512MB RAM — 1 Primary DNS, 1 Secondary DNS / Client)

**A. Nội dung lý thuyết**
* Cấu trúc và nguyên lý phân giải tên miền DNS; phân biệt Recursive DNS và Authoritative DNS.
* Các bản ghi DNS cơ bản (A, AAAA, CNAME, MX, PTR, NS, SOA) và cấu trúc một Zone File.
* Cơ chế đồng bộ dữ liệu Zone Transfer (AXFR/IXFR) giữa Primary DNS và Secondary DNS.
* Quy trình tra cứu tên miền trên Linux (`/etc/resolv.conf`, `/etc/hosts`, DNS Caching).

**B. Các demo bắt buộc**
1. **Primary DNS Setup:** Cấu hình Forward Zone và Reverse Zone cho tên miền nội bộ; dùng `dig` hoặc `nslookup` để kiểm tra phân giải xuôi và ngược.
2. **Zone Transfer:** Cấu hình Secondary DNS Server tự động đồng bộ dữ liệu Zone Data từ Primary DNS khi có cập nhật.
3. **Tích hợp Client:** Cấu hình máy Client trỏ DNS về BIND9 Server, kiểm tra truy cập dịch vụ web nội bộ thông qua tên miền vừa cấu hình.
4. **Demo sự cố (Troubleshooting):** Cố tình viết sai cú pháp trong file Zone (thiếu dấu chấm cuối, sai Serial Number); dùng `named-checkzone` và đọc `/var/log/syslog` để chẩn đoán nguyên nhân dịch vụ không reload được.