# Milestone 3: Chat TCP (framing, `/chat`, `/leave`, threads)

## 1. Mục tiêu Milestone 3

Hai người chat qua TCP theo cả hai chiều, và chương trình xử lý được **nhiều peer cùng lúc**: tin của người không phải đối tác hiện tại được lưu lại, hiện thông báo kèm số tin chưa đọc. Đây là **sprint có phụ thuộc lẫn nhau nhiều nhất**, nên B giao bản tối thiểu sớm để A và C nối vào.

## 2. Yêu cầu của đề

**3.3 Chat (TCP)**
- Người dùng chọn một peer đang online, chương trình mở **kết nối TCP** tới peer đó.
- Gửi tin bất cứ lúc nào, mỗi dòng một tin, không giới hạn số dòng.
- Tin nhận được hiện **ngay**, kể cả khi người dùng đang gõ.
- Tin từ peer **không phải đối tác hiện tại** được lưu lại và hiện thông báo kèm **số tin chưa đọc**.

**Thread model (đề, mục 5.1):** acceptor chờ kết nối mới, mỗi peer một receiver thread; dữ liệu dùng chung (danh sách online, lịch sử, bộ đếm unread) phải có lock.

**Lệnh:** `/chat <tên|số>`, `<văn bản>`, `/leave`.

## 3. Phạm vi mã nguồn

| File (trong `src/`) | Phụ trách | Nội dung trong milestone này |
|---|---|---|
| `protocol.py` | B | Hoàn thiện `HI`, `MSG`, `BYE` (đã có framing từ Milestone 2) |
| `chat.py` | B | Acceptor, receiver thread mỗi peer, bảng `connections` có lock, `open_chat`, `send`, `leave`, phát hiện peer đóng hoặc sập |
| `lanchat.py` | A | `current_partner`, lịch sử, bộ đếm `unread`, nối `/chat`, `/leave` và văn bản thường |
| `ui.py` | C | Thay mọi `print` bằng `print_above`, nối dòng nhập `> ` vào vòng lệnh |
| `filetransfer.py` | C | **Bản nháp độc lập** (chunk 64 KB, `.part`, so sha256), chưa nối vào `/send` |

## 4. Thiết kế

### 4.1. Gói TCP trong milestone này

```
HI|<name>|                             gói đầu tiên sau khi kết nối
MSG|<độ_dài_byte>|<nội dung UTF-8>     tin nhắn
BYE|                                   kết thúc cuộc chat
```

Gói đầu tiên `HI` là bắt buộc vì bên nhận (acceptor) chỉ thấy IP và cổng tạm của người gọi, không biết đó là ai.

### 4.2. Luồng chạy

| Bước | Diễn biến |
|---|---|
| `/chat Minh` | Tìm peer trong bảng `peers`; `socket.create_connection((ip, port), timeout=3)`; gửi `HI`; lưu vào `connections`; bật receiver thread; đặt `current_partner`. Kết nối lỗi thì báo, **không crash** |
| Có kết nối đến | Acceptor đọc `HI`, lưu kết nối, bật receiver thread cho peer đó |
| Nhận tin từ đối tác hiện tại | In ngay bằng `print_above` |
| Nhận tin từ người khác | Lưu vào lịch sử, `unread[name] += 1`, in `[*] New message from <tên> (<n> unread)` |
| `/chat X` khi X có tin chưa đọc | In `[*] Switched to X, n unread:` cùng các tin đó, rồi xóa bộ đếm |
| `/leave` | Gửi `BYE`, đóng socket, `current_partner = None` |
| Nhận `BYE` hoặc `recv()` trả `b""` | Báo `<tên> left` hoặc `connection lost`, dọn `connections`, quay về prompt |

### 4.3. Quy tắc cần chốt và ghi vào báo cáo

| Tình huống | Quyết định của nhóm |
|---|---|
| Hai bên **cùng lúc** `/chat` nhau (sinh ra 2 kết nối cho một cặp) | Giữ kết nối mới nhất theo tên peer, đóng kết nối cũ (áp dụng ở hàm `_register_connection` trong `chat.py`). |
| Một người nhắn tới khi mình chưa `/chat` ai | Tính là unread (`unread[name] += 1`), lưu vào lịch sử, không tự đặt làm đối tác. Khi người dùng gõ `/chat <name>` sẽ hiển thị số tin unread và nội dung các tin đó rồi xóa bộ đếm. |
| Tin nhắn dài tối đa | 1 MB (1,000,000 bytes); vượt quá thì từ chối gửi hoặc đóng kết nối. |

### 4.4. Lưu ý lập trình

- Dùng `sendall()`, không dùng `send()`.
- Độ dài trong header là **byte** UTF-8.
- Mọi đọc socket đều nằm trong `try/except` cho `ConnectionError`, `OSError`, `ValueError`.
- Không in màn hình khi đang giữ lock dữ liệu.
- Mọi thread nền là `daemon=True`.

## 5. Cách chạy và kiểm tra

```bash
# Một máy, 3 instance
python src/lanchat.py --name Quan --port 5000 --bcast 127.255.255.255
python src/lanchat.py --name Minh --port 5001 --bcast 127.255.255.255
python src/lanchat.py --name Lan  --port 5002 --bcast 127.255.255.255
```

Kịch bản nhanh: ở Quan gõ `/list`, `/chat Minh`, rồi nhắn vài dòng. Ở Lan gõ `/chat Quan`; Quan đang chat với Minh sẽ thấy `[*] New message from Lan (1 unread)`.

## 6. Phân công và lịch

| ID | Việc | Phụ trách | Hạn | Xong |
|---|---|---|---|---|
| PB-08 | **Bản tối thiểu:** connect, gửi `HI`, gửi và nhận một chiều (để A nối vào) | B | **T3 10/11** | ☑ |
| PB-10 | Thay mọi `print` bằng `ui.print_above`; phối hợp A nối dòng nhập vào vòng lệnh | C | T4 11/11 | ☑ |
| PB-08 | `chat.py` đầy đủ: `connections` có lock, `/chat` (timeout 3 giây), receiver thread mỗi peer, `BYE`, phát hiện peer đóng hoặc sập | B | T5 12/11 | ☑ |
| PB-13 | Chụp Wireshark **TCP three-way handshake** (`tcp.port == 5000`) kèm giải thích | C | T5 12/11 | ☐ |
| PB-09 | Logic chat: `current_partner`, lịch sử, `unread`, thông báo; nối `/chat`, `/leave`, văn bản thường vào `lanchat.py` | A | T6 13/11 | ☑ |
| PB-09 | Chốt quy tắc hai bên cùng `/chat` nhau và ghi vào mục 4.3 | A | T6 13/11 | ☑ |
| PB-15 | Test chat 2 máy theo bảng test case; viết prototype gửi file độc lập (chunk 64 KB, `.part`, so sha256) | C | T6 13/11 – T7 14/11 | ☑ |
| | Sprint Review, Retrospective, Planning Sprint 4 | Cả nhóm | CN 15/11 20:00 | ☑ |

> **Điểm nghẽn:** nếu đến **T4 11/11** mà B chưa có bản gửi nhận tối thiểu, họp khẩn ngay hôm đó, đừng chờ Chủ Nhật.

## 7. Test case

| ID | Làm gì | Kết quả mong đợi | Thực tế | Đạt |
|---|---|---|---|---|
| TC-3.01 | A `/chat B`, A nhắn, B nhắn lại | Cả hai thấy tin ngay, đúng chiều | Nhận ngay, đúng chiều hai phía | ☑ |
| TC-3.02 | Gửi 100 tin liên tiếp rất nhanh | Đủ 100 tin, đúng thứ tự, không dính, không mất | Nhận đủ 100 tin đúng thứ tự | ☑ |
| TC-3.03 | Tin tiếng Việt có dấu và emoji | Hiển thị đúng, độ dài header tính bằng byte | Hiển thị đúng font, ký tự UTF-8 và emoji | ☑ |
| TC-3.04 | Tin dài (ví dụ 100 KB) | Nhận đủ, đúng nội dung | Nhận đủ 100 KB không thiếu byte | ☑ |
| TC-3.05 | Tin rỗng (chỉ Enter) | Không gửi, hoặc xử lý rõ ràng, không crash | Bỏ qua không gửi, không crash | ☑ |
| TC-3.06 | A đang chat B; C nhắn A | A thấy `New message from C (1 unread)`, không lẫn vào cuộc chat với B | Hiện đúng thông báo kèm số unread | ☑ |
| TC-3.07 | C nhắn thêm 2 tin, rồi A `/chat C` | Hiện `2 unread` đủ nội dung rồi xóa bộ đếm; về `0` | In lại 2 tin unread, reset bộ đếm về 0 | ☑ |
| TC-3.08 | `/leave` | Bên kia nhận được thông báo; hai bên đóng socket sạch | Bên kia nhận `<tên> left the chat`, socket đóng sạch | ☑ |
| TC-3.09 | Kill đột ngột một peer khi đang chat | Peer còn lại báo `connection lost`, quay về prompt, không crash | Báo `connection lost`, dọn kết nối | ☑ |
| TC-3.10 | `/chat` tới peer vừa offline (còn trong bảng) | Báo lỗi kết nối, không crash | Báo không thể kết nối, không crash | ☑ |
| TC-3.11 | A và B cùng lúc gõ `/chat` nhau | Áp dụng đúng quy tắc ở mục 4.3; vẫn chat được | Giữ kết nối mới nhất, đóng kết nối cũ | ☑ |
| TC-3.12 | Chat trên **2 máy thật**, cả hai chiều | Như TC-3.01 | Hoạt động bình thường qua LAN | ☑ |
| TC-3.13 | Kiểm tra framing bằng `ncat`: gửi `MSG\|5\|hello` thủ công tới cổng TCP | Hiện đúng `hello`; gửi header sai thì bị đóng kết nối, không crash | Nhận đúng payload, đóng kết nối khi header sai | ☑ |

## 8. Bằng chứng cần lưu vào `evidence/`

- [ ] Ảnh chat hai chiều trên 2 máy (chụp cả hai màn hình).
- [ ] Ảnh thông báo unread và cảnh chuyển đối tác (`Switched to ... n unread`).
- [ ] **Wireshark TCP handshake**: ba gói SYN, SYN-ACK, ACK có cờ rõ ràng, kèm *Statistics → Flow Graph*; lưu cả file `.pcapng`.
- [ ] **Follow TCP Stream** cho thấy `HI|...|` và `MSG|5|hello` ngay trên dây (bằng chứng cho phần framing trong báo cáo).
- [ ] Ảnh chụp bảng quy tắc "hai bên cùng `/chat`" kèm giải thích.

## 9. Tiêu chí hoàn thành (Definition of Done)

- [x] Hai người chat qua lại hai chiều trên **2 máy thật**, không mất hay dính tin.
- [x] Tin tiếng Việt và tin dài đều đúng.
- [x] Chat với A trong khi B nhắn tới thì có thông báo unread; chuyển đối tác thì hiện lại tin chưa đọc.
- [x] `/leave` đóng kết nối đúng ở cả hai bên; peer sập thì bên còn lại không crash.
- [ ] Có ảnh Wireshark TCP handshake và giải thích.
- [x] Code đã qua Pull Request và review chéo; tạo tag `milestone-3`.

## 10. Rủi ro và lưu ý

| Rủi ro | Cách phòng |
|---|---|
| `recv()` trả nửa tin hoặc 2 tin dính nhau | Mọi đọc đi qua `recv_exact` và `read_frame`; test bằng `socketpair` từ Milestone 2 |
| Deadlock giữa lock `connections` và lock màn hình | Lấy dữ liệu ra dưới lock, in ra ngoài lock |
| Thread rò rỉ khi peer sập | Receiver thread kết thúc khi `recv` lỗi và tự gỡ khỏi `connections` |
| Hai bên cùng `/chat` sinh ra kết nối kép | Áp dụng quy tắc đã chốt ở mục 4.3 |
| Một người nắm hết phần chat | A và C đọc code `chat.py`, B đọc phần UI để chéo kiến thức |

---

Trước: [Milestone 2](../milestone2/README.md). Sau: [Milestone 4](../milestone4/README.md). Quay lại [README chính](../README.md).
