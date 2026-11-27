# Milestone 4: Giao diện gõ-khi-nhận và truyền file

## 1. Mục tiêu Milestone 4

1. Dòng người dùng đang gõ **không bị vỡ** khi có tin nhắn đến.
2. Gửi và nhận file có phần trăm tiến độ, lưu vào `downloads/`, trong khi **chat vẫn chạy bình thường**.

## 2. Yêu cầu của đề

**3.4 File Transfer (TCP)**
- `/send <file>` gửi file cho đối tác đang chat.
- Hiện chỉ báo tiến độ (phần trăm).
- File nhận được lưu trong thư mục `downloads/`.
- Chat phải chạy được trong lúc truyền file: **mỗi lần gửi chạy trong một thread riêng**.

**4.3 Gõ khi tin nhắn đến.** Dòng cuối của màn hình luôn là dòng nhập, mọi thứ phía trên là lịch sử chat. Khi một tin đến lúc người dùng đang gõ, chương trình phải:

1. Xóa dòng nhập hiện tại (`\r` rồi mã ANSI `\033[K`).
2. In tin nhắn đến ở dòng đó, kèm xuống dòng.
3. Vẽ lại dấu nhắc `> ` cùng phần chữ người dùng đã gõ.

Một khóa (lock) phải bảo vệ việc in màn hình để hai thread không bao giờ in cùng lúc.

```
[Quan] it's not enough content
> you can che_              ← người dùng đang gõ
        ↓ tin của Minh đến
[Quan] it's not enough content
[Minh] ok, which part?      ← chèn lên trên
> you can che_              ← phần đang gõ được giữ nguyên
```

## 3. Phạm vi mã nguồn

| File (trong `src/`) | Phụ trách | Nội dung trong milestone này |
|---|---|---|
| `ui.py` | C | Hoàn thiện giao diện gõ-khi-nhận |
| `filetransfer.py` | C | `send_file`, `receive_file`, progress, `.part`, dọn file dở |
| `chat.py` | B | Khi receiver gặp gói `FILE` thì chuyển cho `filetransfer`; xử lý lỗi mạng; `/quit` gửi `BYE` |
| `lanchat.py` | A | Nối lệnh `/send`; kiểm tra đầu vào (tên chứa `\|`, tên trùng, cổng bận) |

## 4. Thiết kế

### 4.1. Chọn cách làm giao diện

| | Cách A: `prompt_toolkit` | Cách B: vẽ lại thủ công |
|---|---|---|
| Cách làm | `PromptSession` + `patch_stdout()`, thư viện tự vẽ lại | Đọc từng phím, giữ `typed` buffer, tự in `\r\033[K ... > ` |
| Ưu điểm | Gọn, chạy mọi hệ điều hành, hỗ trợ Backspace, mũi tên, lịch sử | Hiểu rõ bản chất, không phụ thuộc thư viện |
| Nhược điểm | Phụ thuộc thư viện | Windows dùng `msvcrt.getwch()`, Linux/macOS dùng `termios`; phải tự xử lý Backspace, Unicode |

**Quyết định của nhóm:** ☐ Cách A  ☐ Cách B  *(khuyên chọn Cách A trước; làm thêm Cách B nếu còn thời gian)*. Lý do: ...........

Nếu dùng Cách B trên Windows 10 cũ, có thể cần bật hỗ trợ ANSI (ví dụ gọi `os.system("")` một lần khi khởi động).

### 4.2. Truyền file

```
Sender (thread riêng)                       Receiver
─────────────────────                       ────────
create_connection(peer)  ──── SYN... ────►  acceptor
sendall(HI|<name>|)      ──────────────────► nhận ra đây là kết nối gửi file
sendall(FILE|<name>|<size>|) ─────────────► đọc header
đọc file 64 KB một lần, sendall(chunk) ───► ghi vào downloads/<name>.part
đếm sent/size, báo mỗi 10% ...               đủ <size> byte thì đổi .part → tên thật
```

- **Mỗi lần gửi file mở một kết nối TCP riêng**, để byte của file không trộn với luồng chat.
- Bên nhận dùng `os.path.basename()` khi lưu để chặn tên kiểu `../../x`, và xử lý khi file trùng tên (ví dụ thêm `_1`).
- Lỗi giữa chừng (ngắt mạng, peer đóng, nhận thiếu byte): báo lỗi và **xóa file `.part`**.
- Báo tiến độ qua `ui.print_above()`, mỗi 10% là đủ và an toàn. Không dùng `print` thẳng.
- File không tồn tại: báo lỗi ngay ở `/send`, không bật thread.

### 4.3. Hợp đồng hàm

```
filetransfer.send_file(peer, path)
filetransfer.receive_file(sock, name, size)     # B gọi khi receiver gặp gói FILE
```

## 5. Cách chạy và kiểm tra

```bash
python src/lanchat.py --name Quan --port 5000
python src/lanchat.py --name Minh --port 5001
```

Quan `/chat Minh`, rồi `/send <đường dẫn file>` trong khi vẫn gõ chat. Kiểm tra file nhận về bằng hash:

```bash
# Linux/macOS
sha256sum <file gốc> downloads/<file nhận được>
# Windows PowerShell
Get-FileHash <file> -Algorithm SHA256
```

## 6. Phân công và lịch

| ID | Việc | Phụ trách | Hạn | Xong |
|---|---|---|---|---|
| PB-11 | Nối gói `FILE` trong receiver vào `filetransfer.receive_file` | B | T4 18/11 | ☐ |
| PB-11 | `filetransfer.py` hoàn chỉnh: `/send`, thread riêng, kết nối riêng, header `FILE`, chunk 64 KB, progress 10%, `.part`, `basename`, dọn file dở | C | T5 19/11 | ☐ |
| PB-10 | Test giao diện trên máy cả 3 người (gõ dài, dán text, Unicode, nhiều tin cùng lúc); sửa lỗi hiển thị | A | T5 19/11 | ☐ |
| PB-16 | Kiểm tra đầu vào: tên chứa `\|`, tên trùng, cổng bận | A | T5 19/11 | ☐ |
| PB-12 | Giới hạn độ dài `MSG` (ví dụ 1 MB); bắt `ConnectionResetError` và timeout; connect tới peer offline; `/quit` gửi `BYE` tới mọi peer | B | T6 20/11 | ☐ |
| PB-15 | Test tích hợp: vừa chat vừa gửi file 50 MB, so hash | A | T6 20/11 | ☐ |
| PB-14 | Cập nhật nháp báo cáo phần mình | Cả nhóm | T7 21/11 | ☐ |
| | Sprint Review; **đóng băng tính năng**; Retrospective; Planning Sprint 5 | Cả nhóm | CN 22/11 20:00 | ☐ |

## 7. Test case

### 7.1. Giao diện gõ-khi-nhận

| ID | Làm gì | Kết quả mong đợi | Thực tế | Đạt |
|---|---|---|---|---|
| TC-4.01 | Gõ dở `you can che`, trong lúc đó nhận 1 tin | Tin chèn phía trên; `> you can che` còn nguyên | | ☐ |
| TC-4.02 | Đang gõ, nhận 5 tin liên tiếp | Không vỡ dòng, không lẫn ký tự, thứ tự đúng | | ☐ |
| TC-4.03 | Gõ dòng dài hơn chiều rộng cửa sổ, rồi có tin đến | Hiển thị chấp nhận được, không mất chữ | | ☐ |
| TC-4.04 | Backspace, mũi tên trái/phải, dán văn bản nhiều dòng | Buffer đúng sau khi tin đến | | ☐ |
| TC-4.05 | Gõ tiếng Việt có dấu trong lúc có tin đến | Dấu hiển thị đúng | | ☐ |
| TC-4.06 | Tiến độ file (progress) hiện lúc đang gõ | Không phá dòng đang gõ | | ☐ |

### 7.2. Truyền file

| ID | Làm gì | Kết quả mong đợi | Thực tế | Đạt |
|---|---|---|---|---|
| TC-4.07 | `/send` file nhỏ (vài KB) | Có `100% Done`; file trong `downloads/`; hash trùng | | ☐ |
| TC-4.08 | `/send` file 50 MB | Progress tăng dần; hash trùng; chat vẫn chạy trong lúc gửi | | ☐ |
| TC-4.09 | File 0 byte | Xử lý không lỗi, file rỗng được tạo | | ☐ |
| TC-4.10 | File có tên tiếng Việt hoặc khoảng trắng | Lưu đúng tên, không lỗi | | ☐ |
| TC-4.11 | File trùng tên với file đã có trong `downloads/` | Không ghi đè mất dữ liệu | | ☐ |
| TC-4.12 | `/send` file không tồn tại | Báo lỗi, không crash, không bật thread | | ☐ |
| TC-4.13 | Ngắt giữa chừng (kill bên gửi hoặc rút mạng) | Bên nhận báo lỗi và **xóa file `.part`** | | ☐ |
| TC-4.14 | Hai file gửi cùng lúc cho hai peer | Cả hai thành công, hash trùng | | ☐ |
| TC-4.15 | Header giả với tên `../../evil.txt` (kiểm tra bằng `ncat`) | Chỉ lưu `evil.txt` trong `downloads/` | | ☐ |
| TC-4.16 | Gửi file trên **2 máy thật** | Như TC-4.08 | | ☐ |

## 8. Bằng chứng cần lưu vào `evidence/`

- [ ] Ảnh chụp trước và sau khi một tin đến lúc đang gõ (hoặc ảnh GIF/video ngắn).
- [ ] Ảnh progress `10% ... 100% Done` trong lúc vẫn chat.
- [ ] Kết quả so sánh hash giữa file gửi và file nhận.
- [ ] Ảnh Wireshark kết nối TCP riêng của lần gửi file (`FILE|<name>|<size>|`).
- [ ] Ghi chú quyết định chọn Cách A hay B và lý do (vào báo cáo).

## 9. Tiêu chí hoàn thành (Definition of Done)

- [ ] Gõ dở mà tin đến, chữ đang gõ vẫn còn nguyên.
- [ ] File 50 MB nhận về có hash trùng khớp.
- [ ] Chat vẫn chạy trong lúc gửi file.
- [ ] Lỗi cơ bản (file không tồn tại, ngắt giữa chừng) được xử lý, file dở bị xóa.
- [ ] **Từ 22/11 không thêm tính năng mới.**
- [ ] Code đã qua Pull Request và review chéo; tạo tag `milestone-4`.

## 10. Rủi ro và lưu ý

| Rủi ro | Cách phòng |
|---|---|
| Hai thread in cùng lúc làm vỡ giao diện | Mọi đầu ra màn hình đi qua `ui.print_above()` và một lock màn hình |
| Byte file trộn với byte chat | Mỗi lần gửi file dùng kết nối TCP riêng |
| Gửi file lớn làm treo chat | Gửi trong thread riêng; đọc file theo chunk 64 KB |
| Progress in quá dày làm nghẽn giao diện | Chỉ báo mỗi 10% |
| Dồn việc về cuối sprint | Việc nặng xong trước thứ Sáu; thứ Bảy là ngày dự phòng |

---

Trước: [Milestone 3](../milestone3/README.md). Sau: [Milestone 5](../milestone5/README.md). Quay lại [README chính](../README.md).
