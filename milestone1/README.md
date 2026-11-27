# Milestone 1: Nền móng (TCP echo và UDP send/receive)


## 1. Mục tiêu của Milestone 1

Cả nhóm cài xong môi trường và **hiểu TCP, UDP bằng code chạy được**, để các milestone sau không vướng lỗi mạng và lỗi cơ bản. Sau milestone này, mỗi thành viên phải tự giải thích được:

- `accept()` vì sao trả về socket mới, và `recv()` trả `b""` nghĩa là gì.
- Vì sao TCP là dòng byte và phải tự đóng khung tin nhắn.
- `SO_REUSEADDR`, `SO_BROADCAST` làm gì trong `udp_broadcast_demo.py`.
- Vì sao broadcast chỉ đi trong một subnet.

## 2. Nội dung thư mục

| File | Tác dụng |
|---|---|
| `tcp_echo_server.py` | Echo server TCP, nhiều client cùng lúc (mỗi client một thread) |
| `tcp_echo_client.py` | Client TCP: gõ chữ, nhận lại chữ |
| `tcp_stick_demo.py` | Thí nghiệm "TCP không có ranh giới tin nhắn" (chạy một lệnh) |
| `udp_echo.py` | UDP echo unicast, để so sánh với TCP |
| `udp_broadcast_demo.py` | Demo broadcast của giảng viên: 3 instance chung cổng UDP 9999 |
| `evidence/` | Ảnh chụp, log, file `.pcapng` làm bằng chứng |

Chạy các lệnh dưới đây từ thư mục `milestone1/`. Trên Windows có thể dùng `py` thay cho `python`.

## 3. Chuẩn bị môi trường

- [ ] Python 3.9+ (`python --version`)
- [ ] Git, repo chung trên GitHub (private), bảng Scrum (Backlog / In Progress / Review / Done)
- [ ] Wireshark kèm Npcap (cài từ wireshark.org)
- [ ] `ncat` (đi kèm Nmap trên Windows) hoặc `nc` (Linux/macOS)
- [ ] Windows Firewall: cho phép `python.exe` trên mạng **Private**; Wi-Fi đặt ở profile Private
- [ ] Biết IP và subnet mask của máy mình (`ipconfig` hoặc `ip addr`)
- [ ] Tắt VPN, và tạm vô hiệu card ảo (VMware, VirtualBox, WSL) khi test broadcast

## 4. Phần 1: TCP echo

Luồng gọi hàm:

```
SERVER                              CLIENT
socket() → bind() → listen()        socket()
accept()  ◄── SYN, SYN-ACK, ACK ──  connect()
recv()    ◄───── dữ liệu ─────────  sendall()
sendall() ────── dữ liệu ─────────► recv()
recv() = b""  ◄───── FIN ─────────  close()
```

### Chạy

```bash
# Terminal 1
python tcp_echo_server.py --port 5000

# Terminal 2
python tcp_echo_client.py --port 5000

# Terminal 3 (client thứ hai, bằng netcat)
ncat 127.0.0.1 5000
```

### Kịch bản kiểm tra

| # | Làm gì | Kết quả mong đợi | Kết quả của nhóm |
|---|---|---|---|
| T1 | Client gõ `hello` | Client in `echo: hello`; server in `recv 5 bytes: b'hello'` | |
| T2 | Client gõ `xin chào` | Server thấy `b'xin ch\xc3\xa0o'`: 9 byte cho 8 ký tự | |
| T3 | Hai client (Python và ncat) cùng gõ | Cả hai đều nhận echo; mỗi client có cổng nguồn khác nhau | |
| T4 | Đóng một client | Server in `disconnected`; client còn lại không ảnh hưởng | |
| T5 | Chạy client khi server chưa bật | Báo `Cannot connect ... Connection refused`, không crash | |
| T6 | Tắt server khi client đang nối, rồi gõ thêm | Client báo lỗi hoặc `Server closed the connection` | |
| T7 | Server ở máy 1, client ở máy 2: `--host <IP máy 1>` | Chạy như T1. Nếu không được, kiểm tra firewall và `Test-NetConnection <IP> -Port 5000` | |

### Những điểm cần hiểu trong code

1. `accept()` trả về một socket mới (`conn`) cho từng client. Socket `srv` vẫn tiếp tục lắng nghe.
2. Mỗi client một thread; nếu không, server kẹt ở client đầu tiên.
3. `recv()` trả `b""` nghĩa là bên kia đã đóng kết nối. Đây là cách duy nhất để biết peer đã thoát.
4. `SO_REUSEADDR` ở server giúp chạy lại ngay sau khi tắt, không bị "Address already in use" do trạng thái TIME_WAIT.
5. `settimeout(1.0)` trên socket nghe để Ctrl+C hoạt động được trên Windows.

## 5. Phần 2: thí nghiệm "dính gói"

```bash
python tcp_stick_demo.py
```

Kết quả tham khảo (Python 3.12 trên Linux; số liệu trên máy em có thể khác, và điều đó cũng là kết quả hợp lệ):

```
[Test 1] client send() 3 times -> server recv() once got: b'AAAABBBBCCCC'
[Test 2] client send() once (100000 bytes) -> server needed 98 recv() calls
[Test 3] 'Xin chào Việt Nam': len(chars)=17  len(bytes)=20
```

| Quan sát | Kết quả của nhóm | Hệ quả cho thiết kế giao thức |
|---|---|---|
| Test 1: 3 lần `send()`, `recv()` được mấy tin, dính thế nào? | | Phải có header `MSG\|<len>\|` để tách tin |
| Test 2: 1 lần `send()` 100 KB, cần bao nhiêu lần `recv()`? | | Phải có vòng lặp `recv_exact()` |
| Test 3: độ dài ký tự và độ dài byte | | Độ dài trong header tính bằng **byte** |

## 6. Phần 3: UDP

### 6.1. Ba terminal trên một máy

```bash
python udp_broadcast_demo.py listen --name B
python udp_broadcast_demo.py listen --name C
python udp_broadcast_demo.py send   --name A
```

Nếu máy không có mạng, thêm `--bcast 127.255.255.255` cho lệnh `send`. Kết quả mong đợi: A gửi `HELLO|A|5001|online` mỗi 3 giây, B và C **cùng** nhận được. Nếu `127.255.255.255` không hoạt động trên máy Windows của em, dùng địa chỉ broadcast thật của Wi-Fi (mục 6.2).

### 6.2. Hai máy thật

Tính địa chỉ broadcast theo công thức `broadcast = IP OR (NOT mask)`, hoặc để Python tính:

```bash
python -c "import ipaddress; print(ipaddress.ip_interface('192.168.1.5/24').network.broadcast_address)"
# kết quả: 192.168.1.255
```

Wi-Fi trường có thể dùng mask khác `/24`, nên đừng mặc định đuôi `.255`.

```bash
# Máy 1
python udp_broadcast_demo.py listen --name B

# Máy 2
python udp_broadcast_demo.py send --name A --bcast 192.168.1.255
```

Sau đó **đổi vai và chạy lại**. Firewall cấu hình riêng từng máy, nên chạy được một chiều chưa chứng minh chiều ngược lại.

### 6.3. UDP echo unicast (để so sánh với TCP)

```bash
python udp_echo.py server --port 6000
python udp_echo.py client --port 6000
```

Tắt server rồi gõ tiếp ở client: sẽ thấy `No reply` (hoặc WinError 10054 trên Windows). UDP không có "connection refused" rõ ràng như TCP. Đó là lý do đề dùng timeout 10 giây để biết peer đã offline.

### 6.4. Bốn thí nghiệm hiểu bản chất

Làm trên **bản sao** của `udp_broadcast_demo.py`, hoặc dùng Git để quay lại bản gốc.

| # | Làm gì | Kết quả mong đợi | Kết quả của nhóm |
|---|---|---|---|
| 1 | Xóa dòng `SO_REUSEADDR` (và `SO_REUSEPORT` trên macOS), chạy 2 listener | Listener thứ hai báo "Address already in use" | |
| 2 | Xóa dòng `SO_BROADCAST`, chạy `send` | Lỗi quyền khi `sendto` tới địa chỉ broadcast | |
| 3 | Bind vào một IP cụ thể thay vì `""` | Có thể không nhận được gói broadcast | |
| 4 | Mở Wireshark với `udp.port == 9999` | Thấy IP đích broadcast, MAC đích `ff:ff:ff:ff:ff:ff`, payload `HELLO\|A\|5001\|online` | |

### 6.5. Gỡ lỗi nhanh

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Không máy nào nhận | Firewall chặn UDP vào | Cho phép `python.exe` trên mạng Private |
| Chỉ một chiều chạy | Firewall hai máy khác nhau | Kiểm tra lại máy "không nhận" |
| `ping` giữa 2 máy không thông | Wi-Fi có client isolation | Dùng hotspot điện thoại |
| Gói đi ra nhưng không tới | Sai địa chỉ broadcast, hoặc chọn nhầm card (VPN, VMware, WSL) | Tắt card ảo, truyền `--bcast` đúng subnet |
| `Network is unreachable` | Không có mạng cho `255.255.255.255` | Dùng `127.255.255.255` hoặc kết nối Wi-Fi |

Mẹo: mở Wireshark trên máy nhận. Gói hiện trong Wireshark nhưng Python không nhận được thường là do firewall. Gói không hiện thì lỗi nằm ở mạng.

## 7. Phần 4: tập dượt Wireshark (khoảng 30 phút)

Mục đích: chụp sẵn các ảnh cho Deliverable 3 và làm quen công cụ.

| Lab | Làm gì | Ảnh/bằng chứng lưu vào `evidence/` |
|---|---|---|
| 1. ICMP | Bắt `ping` tới máy bên cạnh, tìm gói request và reply | `w0_icmp.png` |
| 2. TCP | Chạy echo trên loopback, tìm 3 gói SYN, SYN-ACK, ACK; gói chứa `hello`; chuỗi FIN | `w3_tcp_handshake.png`, `w3_tcp_handshake.pcapng` |
| 3. UDP | Chạy `send` giữa 2 máy, tìm MAC đích và khoảng cách thời gian 3 giây | `w1_udp_broadcast.png`, `w2_udp_interval.png`, `w1_udp_broadcast.pcapng` |

Chọn đúng card mạng khi bắt gói:

| Tình huống | Card cần chọn |
|---|---|
| Chạy trên một máy, địa chỉ `127.0.0.1` | Loopback (bản Npcap mới: "Adapter for loopback traffic capture", bản cũ: "Npcap Loopback Adapter") |
| Hai máy qua Wi-Fi | Wi-Fi |
| Hai máy qua dây | Ethernet |
| UDP broadcast `255.255.255.255` hoặc `192.168.x.255` | Card thật (Wi-Fi hoặc Ethernet) |

Bộ lọc hiển thị dùng cho milestone này: `udp.port == 9999`, `tcp.port == 5000`. Để thấy khoảng 3 giây giữa các gói: *View → Time Display Format → Seconds Since Previous Displayed Packet*.

Ảnh nào cũng phải có khung đỏ khoanh trường quan trọng và chú thích 3–4 dòng. Luôn lưu kèm file `.pcapng` để chụp lại khi cần.

## 8. Bảng so sánh TCP và UDP (điền bằng quan sát của nhóm)

| Tiêu chí | TCP | UDP | Nhóm quan sát được |
|---|---|---|---|
| Thiết lập kết nối | `connect()`/`accept()`, bắt tay 3 bước | Không có, cứ `sendto()` | |
| Ranh giới tin | Không có (dòng byte) | Mỗi `recvfrom()` là 1 datagram | |
| Khi bên kia tắt | `recv()` trả `b""` hoặc `Connection refused` | Im lặng | |
| Nhiều socket cùng cổng | Không (`accept()` tạo socket mới) | Được với broadcast (`SO_REUSEADDR`) | |
| Dùng trong đồ án cho | Chat, file | Discovery, status | |

## 9. Phân công và lịch

| ID | Việc | Phụ trách | Hạn | Xong |
|---|---|---|---|---|
| PB-01 | Tạo repo, quy ước nhánh; mỗi người cài môi trường | A (repo), cả nhóm | CN 25/10 | ☐ |
| PB-06 | Khung `src/lanchat.py`: `--name --port --bcast`, vòng lặp lệnh, `/help`, `/quit`, lệnh sai thì in gợi ý | A | T4 28/10 | ☐ |
| PB-03 | Kiểm tra mạng 2 máy thật (ping, firewall), chạy UDP demo giữa 2 máy, ghi cách xử lý nếu hỏng | C | T4 28/10 | ☐ |
| PB-02 | TCP echo server/client (kiểm tra cả bằng `ncat`) | B | T5 29/10 | ☐ |
| PB-03 | Chạy 3 terminal và 4 thí nghiệm UDP, ghi kết quả | A | T5 29/10 | ☐ |
| PB-13 | Chụp Wireshark UDP broadcast kèm chú thích | C | T5 29/10 | ☐ |
| PB-02 | Thí nghiệm "dính gói": 2 tin liên tiếp, tin 100 KB, tiếng Việt có dấu | B | T6 30/10 | ☐ |
| | Thử nhanh `prompt_toolkit` + `patch_stdout()` với một thread in tin giả mỗi 2 giây | C | T6 30/10 | ☐ |

## 10. Tiêu chí hoàn thành (Definition of Done)

- [ ] python milestone1/smoke_test.py báo 0 FAIL trên máy của từng thành viên (WARN phải có lời giải thích).
- [ ] TCP echo chạy với 2 client cùng lúc, và chạy giữa **2 máy thật**.
- [ ] UDP broadcast demo chạy giữa 2 máy thật, **cả hai chiều**.
- [ ] Bảng kết quả ở mục 4, 5, 6.4 và 8 đã điền bằng số liệu thật của nhóm.
- [ ] Có ít nhất ảnh Wireshark UDP broadcast và TCP handshake, có khung đỏ và chú thích, trong `evidence/`.
- [ ] Mỗi thành viên giải thích được 4 ý ở mục 1.
- [ ] Code đã qua Pull Request và có người review; tạo tag `milestone-1`.

---

Milestone tiếp theo: [Milestone 2](../milestone2/README.md). Quay lại [README chính](../README.md).
