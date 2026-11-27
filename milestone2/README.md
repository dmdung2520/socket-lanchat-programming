# Milestone 2: Phát hiện peer và trạng thái online (UDP)

## 1. Mục tiêu Milestone 2

Các peer **tự thấy nhau** trong mạng LAN và **biến mất đúng lúc** khi tắt chương trình. Người dùng xem được ai đang online (`/list`) và đổi được trạng thái (`/status`). Song song, nhóm chuẩn bị nền cho Milestone 3: viết xong lớp framing TCP (`protocol.py`) và bản đầu của giao diện (`ui.py`).

## 2. Yêu cầu của đề

**3.1 Peer Discovery (UDP)**
- Mỗi peer broadcast một thông báo hiện diện **mỗi 3 giây** trên cổng UDP cố định (9999).
- Mỗi peer lắng nghe cổng đó và giữ danh sách người online gồm: tên, IP, cổng TCP, trạng thái.
- Peer **không nghe thấy trong 10 giây** thì bị xóa khỏi danh sách.
- Màn hình hiện thông báo khi có người **online** hoặc **offline**.

**3.2 Online Status (UDP)**
- Người dùng đặt trạng thái `online` hoặc `away`.
- Trạng thái nằm trong gói hiện diện và hiện trong danh sách online.

## 3. Phạm vi mã nguồn

| File (trong `src/`) | Phụ trách | Nội dung trong milestone này |
|---|---|---|
| `discovery.py` | A | Broadcaster, listener, reaper, bảng peers có lock |
| `lanchat.py` | A | Nối `/list`, `/status`, `/help`, `/quit` vào vòng lặp lệnh |
| `protocol.py` | B | `recv_exact`, `read_token`, `send_msg`, `read_frame` kèm test |
| `chat.py` | B | Khung: acceptor và receiver thread, tạm in dữ liệu thô |
| `ui.py` | C | `print_above()` bản đầu bằng `prompt_toolkit` |
| `tests/test_protocol.py` | B | Test framing bằng `socket.socketpair()` |

## 4. Thiết kế

### 4.1. Gói hiện diện

```
HELLO|<name>|<tcp_port>|<status>      ví dụ:  HELLO|Quan|5000|online
```

Bên nhận **kiểm tra** trước khi tin: đúng 4 phần, phần đầu là `HELLO`, `tcp_port` là số từ 1 đến 65535, `status` là `online` hoặc `away`, tên không rỗng. Gói sai định dạng thì **bỏ qua**, không báo lỗi, không crash.

### 4.2. Mô hình thread

| Thread | Việc | Chu kỳ |
|---|---|---|
| Broadcaster | `sendto(HELLO...)` tới `<bcast>:9999` | 3 giây |
| Listener | `recvfrom()`, kiểm tra gói, cập nhật `peers` | khi có gói |
| Reaper | Xóa peer có `now - last_seen > 10`, in thông báo offline | 1 giây |

Tất cả là `daemon=True` để Ctrl+C thoát sạch.

### 4.3. Bảng peers

```
peers = { (ip, tcp_port): {"name": ..., "status": ..., "last_seen": ...} }
```

- Khóa bằng `(ip, tcp_port)`, **không** bằng IP, vì nhiều instance trên một máy dùng chung IP.
- Mọi truy cập đều qua `threading.Lock`. Lấy dữ liệu ra dưới lock, **in ra ngoài lock**.
- Bỏ qua gói của chính mình: so sánh cả `name` và `tcp_port`.
- Khi `/status` đổi, **broadcast ngay** một gói mới, không chờ chu kỳ 3 giây.

### 4.4. Hợp đồng hàm

| Hàm | Mô tả |
|---|---|
| `discovery.get_peers() -> list[Peer]` | Danh sách peer hiện có, sắp xếp ổn định để số thứ tự không nhảy |
| `discovery.set_status("online" \| "away")` | Đổi trạng thái và broadcast ngay |
| `discovery.find_peer(name_or_number) -> Peer \| None` | Tìm theo tên hoặc số thứ tự trong `/list` |
| `ui.print_above(text)` | In một dòng phía trên dòng nhập |

### 4.5. Định dạng hiển thị

```
> /list
 1. Minh (192.168.1.12) online
 2. Lan  (192.168.1.15) away
[*] Huy is online
[*] Lan went offline
```

## 5. Cách chạy và kiểm tra

Khi `discovery.py` và `lanchat.py` đã có, chạy từ thư mục gốc dự án:

```bash
# Một máy, 3 instance
python src/lanchat.py --name Quan --port 5000 --bcast 127.255.255.255
python src/lanchat.py --name Minh --port 5001 --bcast 127.255.255.255
python src/lanchat.py --name Lan  --port 5002 --bcast 127.255.255.255

# Hai máy (không cần --bcast nếu broadcast mặc định tới được)
python src/lanchat.py --name Quan --port 5000

# Test framing
python -m unittest discover -s tests
```

## 6. Phân công và lịch

| ID | Việc | Phụ trách | Hạn | Xong |
|---|---|---|---|---|
| PB-04 | `discovery.py`: broadcaster 3 giây, listener, bảng peers có lock, in thông báo peer mới | A | T4 4/11 | ☐ |
| PB-05 | Thread reaper xóa peer im lặng quá 10 giây, in thông báo offline | A | T5 5/11 | ☐ |
| PB-05, PB-07 | `/list` có số thứ tự; `/status online\|away` và broadcast ngay khi đổi | A | T6 6/11 | ☐ |
| PB-08 | `protocol.py` và `tests/test_protocol.py` | B | T5 5/11 | ☐ |
| PB-08 | `chat.py` bản khung: acceptor và receiver thread, in dữ liệu thô | B | T6 6/11 | ☐ |
| PB-10 | `ui.py`: `print_above()` bằng `prompt_toolkit`, test độc lập với thread tin giả (gõ dài, Backspace, Enter) | C | T4 4/11 | ☐ |
| PB-13 | Test 3 instance trên 2 máy; chụp Wireshark của **app thật** | C | T6 6/11 | ☐ |
| PB-15 | Bảng test case mẫu và dàn ý báo cáo | C | T7 7/11 | ☐ |
| | Sprint Review, Retrospective, Planning Sprint 3 | Cả nhóm | CN 8/11 20:00 | ☐ |

## 7. Test case

| ID | Làm gì | Kết quả mong đợi | Thực tế | Đạt |
|---|---|---|---|---|
| TC-2.01 | Bật instance 1, rồi bật instance 2 | Instance 1 báo `[*] <tên> is online` trong khoảng 3 giây | | ☐ |
| TC-2.02 | Gõ `/list` | Đúng số thứ tự, tên, IP, trạng thái; **không** có chính mình | | ☐ |
| TC-2.03 | Tắt đột ngột một instance (Ctrl+C hoặc kill) | Khoảng 10 – 11 giây sau các máy khác báo offline và `/list` không còn peer đó | | ☐ |
| TC-2.04 | `/status away` rồi xem máy khác | Máy khác thấy `away` ngay hoặc trong 3 giây | | ☐ |
| TC-2.05 | Tắt rồi bật lại một peer nhiều lần | Online/offline luôn đúng, không bị trùng dòng | | ☐ |
| TC-2.06 | Gửi gói rác tới cổng 9999 (`ncat -u -b 127.0.0.1 9999`) | Bỏ qua, chương trình không crash | | ☐ |
| TC-2.07 | Tên chứa `\|` hoặc rỗng | Bị từ chối khi khởi động, in thông báo rõ ràng | | ☐ |
| TC-2.08 | Chạy 3 instance trên **2 máy thật** | Cả 3 thấy nhau đúng trên mọi máy | | ☐ |
| TC-2.09 | `python -m unittest discover -s tests` | Mọi test `protocol` đều đạt: tin bị chia từng byte, 2 tin dính nhau, tiếng Việt, tin rỗng | | ☐ |
| TC-2.10 | Gõ liên tục lúc có thông báo online/offline | Dòng đang gõ không bị vỡ (kiểm tra sơ bộ với `ui.py`) | | ☐ |

## 8. Bằng chứng cần lưu vào `evidence/`

- [ ] Ảnh chụp `/list` với 3 peer trên 2 máy.
- [ ] Ảnh thông báo `online` và `offline`, có thể kèm thời gian để chứng minh khoảng 10 giây.
- [ ] Wireshark của **ứng dụng thật** (`udp.port == 9999`): các gói HELLO từ nhiều peer, trong đó có một gói `away`.
- [ ] Kết quả `python -m unittest` của `protocol.py`.

## 9. Tiêu chí hoàn thành (Definition of Done)

- [ ] Bật 3 instance: `/list` hiện đúng ở cả 3.
- [ ] Tắt một instance: sau tối đa khoảng 10 – 11 giây các máy khác có thông báo offline.
- [ ] Đổi `/status`: máy khác thấy ngay.
- [ ] Gói UDP sai định dạng không làm chương trình lỗi.
- [ ] Mọi test case trong mục 7 đạt, hoặc lỗi còn lại được ghi lên bảng công việc.
- [ ] Code đã qua Pull Request và review chéo (A xem B, B xem C, C xem A); tạo tag `milestone-2`.

## 10. Rủi ro và lưu ý

| Rủi ro | Cách phòng |
|---|---|
| Deadlock giữa lock màn hình và lock dữ liệu | Không in khi đang giữ lock dữ liệu |
| Trùng tên khi chạy nhiều instance | Kiểm tra cả `name` và `tcp_port` khi lọc gói của chính mình |
| Máy nhiều card mạng gửi broadcast nhầm card | Truyền `--bcast` tường minh; tắt card ảo |
| Số thứ tự trong `/list` nhảy khi peer vào ra | Sắp xếp danh sách ổn định (theo tên rồi theo port) |
| Sprint 3 bị chặn vì `protocol.py` chưa xong | B hoàn thành `protocol.py` trước T5 5/11 |

---

Trước: [Milestone 1](../milestone1/README.md). Sau: [Milestone 3](../milestone3/README.md). Quay lại [README chính](../README.md).
