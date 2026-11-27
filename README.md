# socket-lanchat
# Ứng dụng Chat P2P Thời Gian Thực (LAN Chat)

Đồ án môn học: Mạng Máy Tính  
Đề tài: Xây dựng ứng dụng Chat ngang hàng (Peer-to-Peer) trên mạng nội bộ (LAN) hỗ trợ truyền tệp và khám phá thiết bị tự động.

---

## 1. Tổng quan đồ án

Ứng dụng cho phép các máy tính trong cùng mạng nội bộ (LAN) tự động phát hiện lẫn nhau, thiết lập kết nối TCP trực tiếp để trò chuyện (chat) hai chiều, truyền tệp tin (file transfer) và hiển thị trạng thái hoạt động (Online/Away) mà không cần thông qua máy chủ trung tâm (Server-client truyền thống).

### Tính năng chính
- **Tự động khám phá (Discovery):** Sử dụng UDP Broadcast để quảng bá sự tồn tại và tự động cập nhật danh sách các peer đang hoạt động trong mạng LAN.
- **Quản lý Peer & Trạng thái:** Hiển thị danh sách peer kèm trạng thái (`Online`, `Away`) và tự động xóa peer nếu mất kết nối quá thời gian quy định (Timeout).
- **Giao diện dòng lệnh (CLI) tương tác cao:** Tích hợp thư viện `prompt_toolkit` để hỗ trợ vùng nhập lệnh mượt mà, không bị che khuất hoặc xáo trộn khi có tin nhắn mới đến từ các peer khác.
- **Chat trực tiếp (TCP):** Thiết lập kết nối TCP riêng biệt với từng peer, hỗ trợ đếm tin nhắn chưa đọc (`unread`), lệnh chuyển đổi hội thoại và thông báo khi đối phương ngắt kết nối.
- **Truyền tệp tin (File Transfer):** Gửi file qua kênh TCP độc lập, chia nhỏ file thành các chunk (64 KB), hiển thị tiến trình (`progress bar`) và cơ chế chống lỗi (lưu file tạm `.part` trước khi đổi tên chính thức).
- **Phân tích mạng (Wireshark):** Hỗ trợ kiểm chứng và bắt gói tin cho UDP Broadcast, TCP Three-way Handshake và gói tin ứng dụng.

---

## 2. Cấu trúc thư mục dự án

```text
lan-chat-project/
=======
| Tính năng | Giao thức | Milestone | Trạng thái |
|---|---|---|---|
| Phát hiện peer, danh sách online (`/list`), tự xóa sau 10 giây im lặng, thông báo online/offline | UDP | [2](milestone2/README.md) | ⬜ |
| Trạng thái `online` / `away` (`/status`) | UDP | [2](milestone2/README.md) | ⬜ |
| Chat TCP với nhiều peer, tin của người khác lưu lại kèm bộ đếm chưa đọc | TCP | [3](milestone3/README.md) | ⬜ |
| Gõ dở vẫn không bị vỡ dòng khi có tin đến | (giao diện) | [4](milestone4/README.md) | ⬜ |
| Gửi file có phần trăm tiến độ, lưu vào `downloads/`, chat vẫn chạy trong lúc gửi | TCP | [4](milestone4/README.md) | ⬜ |
| Xử lý lỗi: peer sập, peer offline, file không tồn tại, truyền file bị ngắt | TCP và UDP | [5](milestone5/README.md) | ⬜ |

## 3. Thành viên nhóm

| Vai | Họ tên | MSSV | Phụ trách chính | Module sở hữu |
|---|---|---|---|---|
| **A**: Discovery và điều phối (Product Owner) | Doãn Mạnh Dũng | 25127303 | UDP discovery, `/list`, `/status`, vòng lặp lệnh, trạng thái chat, README | `discovery.py`, `lanchat.py` |
| **B**: TCP chat và xử lý lỗi | Phạm Lâm Viên | 25127171 | Framing, acceptor, receiver, `/chat`, `/leave`, mọi lỗi mạng | `protocol.py`, `chat.py` |
| **C**: Giao diện, file và Wireshark | Lý Ngọc Minh Thi | 25127142 | `print_above`, `/send`, progress, ảnh Wireshark, kịch bản demo | `ui.py`, `filetransfer.py` |


## 4. Yêu cầu hệ thống

- **Python 3.9+** (`python --version`). Phần socket chỉ dùng thư viện chuẩn: `socket`, `threading`, `argparse`, `time`, `os`, `sys`.
- **`prompt_toolkit`** cho giao diện gõ-khi-nhận (xem `requirements.txt`).
- **Môi trường chạy:** từ 2 máy trở lên trong cùng LAN/Wi-Fi, hoặc nhiều instance trên một máy.
- **Công cụ kiểm thử:** Wireshark (kèm Npcap), `ncat` hoặc `nc`.
- **Windows Firewall:** cho phép `python.exe` trên mạng **Private**, nếu không broadcast từ máy khác sẽ không tới.

## 5. Cài đặt

```bash
git clone <url-repo>
cd  socket-lanchat

python -m venv .venv
# Windows:      .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate

pip install -r requirements.txt
```

## 6. Cách chạy

> Ứng dụng hoàn chỉnh được xây dần qua các milestone (xem mục 13). Các lệnh dưới đây là **thiết kế đích**. Code của Milestone 1 chạy độc lập, xem [milestone1/README.md](milestone1/README.md).

### 6.1. Nhiều instance trên một máy (không cần mạng)

Mỗi instance cần **tên riêng** và **cổng TCP riêng**:

```bash
python src/lanchat.py --name Quan --port 5000 --bcast 127.255.255.255
python src/lanchat.py --name Minh --port 5001 --bcast 127.255.255.255
python src/lanchat.py --name Lan  --port 5002 --bcast 127.255.255.255
```

### 6.2. Nhiều máy trong cùng LAN

Trên mỗi máy:

```bash
python src/lanchat.py --name Quan --port 5000
```

Nếu không thấy nhau, chạy kèm địa chỉ broadcast của mạng, ví dụ `--bcast 192.168.1.255` (cách tính ở [milestone1/README.md](milestone1/README.md)).

### 6.3. Tham số dòng lệnh

| Tham số | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|
| `--name` | Có | | Tên hiển thị. Không chứa ký tự `\|` |
| `--port` | Không | `5000` | Cổng TCP để nhận chat và file |
| `--bcast` | Không | `255.255.255.255` | Địa chỉ broadcast cho gói UDP (cổng UDP cố định là `9999`) |

### 6.4. Các lệnh trong chương trình

Văn bản thường được gửi như tin nhắn tới người đang chat. Văn bản bắt đầu bằng `/` là lệnh.

| Lệnh | Mô tả |
|---|---|
| `/list` | Hiện người đang online: số thứ tự, tên, IP, trạng thái |
| `/chat <tên\|số>` | Mở chat với người được chọn (kết nối TCP) |
| `<văn bản>` | Gửi tin nhắn cho người đang chat |
| `/send <file>` | Gửi file cho người đang chat |
| `/leave` | Đóng cuộc chat hiện tại |
| `/status <online\|away>` | Đổi trạng thái (gửi qua UDP) |
| `/help` | Hiện danh sách lệnh |
| `/quit` | Thoát chương trình |

## 7. Kiến trúc

```
 Bàn phím ─► Main thread ─► phân tích lệnh /list /chat /send ...
 UDP 9999 ─► Listener  ─► cập nhật bảng peers ◄─ Reaper (xóa peer im lặng > 10 giây)
             Broadcaster ─► gửi HELLO tới địa chỉ broadcast mỗi 3 giây
 TCP port ─► Acceptor  ─► Receiver thread (mỗi peer một thread) ─► ui.print_above()
             File sender thread (mỗi lần gửi một thread, kết nối TCP riêng)
```

Dữ liệu dùng chung (bảng peers, kết nối, lịch sử chat, bộ đếm unread, người đang chat) được bảo vệ bằng `threading.Lock`. Quy tắc để tránh deadlock: lấy dữ liệu ra dưới lock, **in ra màn hình ngoài lock**.

Phân công module và hàm giao tiếp giữa các module:

| Module | Hàm chính |
|---|---|
| `ui.py` | `print_above(text)` |
| `discovery.py` | `get_peers()`, `set_status(s)`, `find_peer(name_or_number)` |
| `protocol.py` | `send_msg(sock, text)`, `read_frame(sock)`, `recv_exact(sock, n)` |
| `chat.py` | `open_chat(peer)`, `send(text)`, `leave()` |
| `filetransfer.py` | `send_file(peer, path)`, `receive_file(sock, name, size)` |

## 8. Giao thức ứng dụng

> Phiên bản **dự kiến**. Mọi thay đổi khi cài đặt phải được cập nhật tại đây và trong báo cáo.

**UDP: gói hiện diện** (văn bản, một datagram, gửi mỗi 3 giây tới `<bcast>:9999`):

```
HELLO|<name>|<tcp_port>|<status>
ví dụ:  HELLO|Quan|5000|online
```

**TCP: khung tin** (TCP là dòng byte nên mỗi tin phải có header cho biết loại và độ dài):

```
HI|<name>|                                  gói đầu tiên sau khi kết nối, để bên nhận biết ai gọi tới
MSG|<độ_dài_byte>|<nội dung UTF-8>          tin nhắn chat
FILE|<tên_file>|<kích_thước_byte>|<byte>    gửi file (qua kết nối TCP riêng)
BYE|                                        đóng cuộc chat
```

Quy tắc:
- `<độ_dài_byte>` tính bằng **byte** sau khi mã hóa UTF-8 (`len(text.encode("utf-8"))`), không tính bằng ký tự.
- Bên nhận đọc đúng số byte bằng vòng lặp `recv()` (`recv_exact`).
- Giới hạn độ dài một `MSG` (dự kiến 1 MB). Header sai hoặc quá lớn thì đóng kết nối.
- Tên file khi lưu luôn đi qua `os.path.basename()` để chặn tên kiểu `../../x`.
- Bảng peers khóa bằng `(ip, tcp_port)`, vì nhiều instance trên một máy dùng chung IP.

## 9. Cấu trúc thư mục

```
lanchat/
├── README.md                  # Tài liệu này
├── requirements.txt           # prompt_toolkit
├── .gitignore
│
├── lanchat.py          # Điểm khởi đầu (Entry point), phân tích tham số dòng lệnh và vòng lặp lệnh chính
├── discovery.py        # Module quản lý UDP Broadcast, lắng nghe và duy trì bảng danh sách peer
├── protocol.py         # Định nghĩa cấu trúc khung tin (Framing), đóng/mở gói dữ liệu TCP an toàn
├── chat.py             # Quản lý kết nối TCP, chấp nhận kết nối (Acceptor) và luồng nhận tin (Receiver)
├── ui.py               # Xử lý giao diện CLI bằng prompt_toolkit (in tin nhắn phía trên dòng nhập)
├── filetransfer.py     # Xử lý logic gửi/nhận file qua TCP với cơ chế chunk và file tạm
└── README.md           # Tài liệu hướng dẫn sử dụng đồ án