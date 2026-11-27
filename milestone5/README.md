# Milestone 5: Xử lý lỗi, kiểm thử, báo cáo và demo

## 1. Mục tiêu Milestone 5

Hệ thống **không sập khi có sự cố**, tài liệu đầy đủ, nhóm tập demo xong trên 2 máy thật. Tính năng đã **đóng băng từ 22/11**: sprint này chỉ sửa lỗi, kiểm thử và viết tài liệu.

## 2. Hạng mục nộp theo đề

| # | Hạng mục | Yêu cầu | Phụ trách chính | Xong |
|---|---|---|---|---|
| 1 | Mã nguồn kèm `README.md` | Cách cài đặt, chạy, kiểm thử | A | ☐ |
| 2 | Báo cáo | 5 – 10 trang: kiến trúc, thread model, định dạng giao thức, vấn đề gặp phải và cách giải quyết | Cả nhóm (theo chương) | ☐ |
| 3 | Ảnh Wireshark | UDP broadcast và TCP three-way handshake, kèm giải thích ngắn | C | ☐ |
| 4 | Demo trực tiếp | 10 phút, trên ít nhất 2 máy | Cả nhóm | ☐ |

Hình thức nộp: *[điền: nộp qua ..., định dạng ..., hạn giờ ...]*.

## 3. Xử lý lỗi (đề, mục 5.3)

| Tình huống | Hành vi mong đợi | Phụ trách | Đạt |
|---|---|---|---|
| Peer đóng kết nối hoặc sập | Báo thông báo, quay về prompt, dọn `connections` | B | ☐ |
| Kết nối tới peer đã offline | Báo lỗi rõ ràng, không crash | B | ☐ |
| File không tồn tại | Báo lỗi, không bật thread | C | ☐ |
| Truyền file bị ngắt | Báo lỗi, **xóa file dở** (`.part`) | C | ☐ |
| Lệnh không hợp lệ | In gợi ý ngắn (`/help`) | A | ☐ |
| Gói UDP rác hoặc sai định dạng | Bỏ qua | A | ☐ |
| `MSG` quá dài hoặc header sai | Đóng kết nối, không crash | B | ☐ |
| Tên rỗng hoặc chứa `\|`; tên trùng; cổng TCP bận | Từ chối khi khởi động, thông báo rõ ràng | A | ☐ |
| `/quit` hoặc Ctrl+C | Gửi `BYE` tới mọi peer, đóng socket, thoát sạch, không còn thread treo | B | ☐ |

## 4. Kịch bản thử lỗi

Mỗi kịch bản ghi lại bước làm, kết quả mong đợi và kết quả thực tế; kết quả vào báo cáo.

| ID | Kịch bản | Kết quả mong đợi | Thực tế | Đạt |
|---|---|---|---|---|
| TC-5.01 | Rút dây mạng hoặc tắt Wi-Fi giữa lúc đang chat | Bên kia báo `connection lost`, không crash; sau khi có mạng lại vẫn `/chat` được | | ☐ |
| TC-5.02 | Kill một peer khi đang chat | Peer còn lại báo, về prompt; sau khoảng 10 giây peer biến khỏi `/list` | | ☐ |
| TC-5.03 | Kill bên gửi giữa lúc truyền file | Bên nhận báo lỗi, xóa `.part` | | ☐ |
| TC-5.04 | Rút mạng giữa lúc truyền file | Cả hai bên báo lỗi, không treo vĩnh viễn | | ☐ |
| TC-5.05 | `/chat` tới peer vừa tắt | Báo lỗi, không crash | | ☐ |
| TC-5.06 | `/send` file không tồn tại; `/send` khi chưa `/chat` ai | Báo lỗi, không crash | | ☐ |
| TC-5.07 | Gửi rác tới cổng TCP bằng `ncat`; gửi header sai | Chương trình đóng kết nối đó, các kết nối khác không ảnh hưởng | | ☐ |
| TC-5.08 | Gõ lệnh lạ, `/chat` không đối số, `/status xyz` | In gợi ý, không crash | | ☐ |
| TC-5.09 | Bật 5 instance cùng lúc; vào ra liên tục | `/list` luôn đúng, không lỗi | | ☐ |
| TC-5.10 | Chạy 30 phút liên tục, chat và gửi file xen kẽ | Không rò thread, không tăng bộ nhớ bất thường | | ☐ |
| TC-5.11 | Kiểm tra bằng bảng test của Milestone 2 – 4 (hồi quy) | Mọi test cũ vẫn đạt | | ☐ |
| TC-5.12 | **Clone repo vào một máy sạch** và chạy theo README | Chạy được, không thiếu file hay thư viện | | ☐ |

## 5. Tự chấm theo rubric

| Tiêu chí | Điểm | Căn cứ để tự kiểm | Tự chấm |
|---|---|---|---|
| UDP discovery, online list, status | 15 | Milestone 2: TC-2.01 ... TC-2.10 | |
| TCP chat (gửi/nhận bất cứ lúc nào, nhiều peer) | 20 | Milestone 3: TC-3.01 ... TC-3.13 | |
| Truyền file có progress, lưu đúng | 15 | Milestone 4: TC-4.07 ... TC-4.16 | |
| Giao diện: gõ không bị vỡ khi tin đến | 15 | Milestone 4: TC-4.01 ... TC-4.06 | |
| Thiết kế giao thức và framing | 10 | Mục "Giao thức" trong README gốc và báo cáo | |
| Xử lý lỗi và ổn định | 10 | Mục 3 và 4 của tài liệu này | |
| Báo cáo | 10 | Mục 7 | |
| Demo và chất lượng code | 5 | Mục 8, 9 | |
| **Tổng** | **100** | | |

## 6. Lịch từng ngày

| Ngày | Ai | Việc |
|---|---|---|
| **T2 23/11** | Cả nhóm | **Bug bash 2 giờ:** A test phần của B, B test phần của C, C test phần của A theo bảng test. Ghi lỗi lên bảng công việc |
| **T3 – T4 24 – 25/11** | A | README gốc (cài đặt, chạy, kiểm thử trên 1 và 2 máy, `--port`, `--bcast`); báo cáo chương Giới thiệu, Kiến trúc, Discovery; hoàn chỉnh bảng test case |
| **T3 – T5 24 – 26/11** | B | Chạy kịch bản lỗi mục 4, sửa bug; viết chương Giao thức, Chat, Xử lý lỗi, Vấn đề gặp phải |
| **T3 – T5 24 – 26/11** | C | Chốt ảnh Wireshark có chú thích; viết chương Giao diện, File, Wireshark; soạn kịch bản demo |
| **T5 26/11** | Cả nhóm | Ghép báo cáo v1 (5 – 10 trang). **Khóa code cứng:** chỉ sửa lỗi nghiêm trọng, mỗi lỗi một PR nhỏ |
| **T6 27/11** | Cả nhóm | **Tập demo lần 1** trên 2 máy, bấm giờ 10 phút. Mỗi người đọc phần của hai bạn kia để trả lời vấn đáp |
| **T7 28/11** | Cả nhóm | **Tập demo lần 2.** Clone repo vào máy sạch, chạy theo README |
| **CN 29/11** | Cả nhóm | Dự phòng. Đóng gói, kiểm tra đủ tệp nộp. **Không viết code mới** |
| **T2 30/11** | Cả nhóm | **Nộp bài** |

## 7. Báo cáo (5 – 10 trang)

| Chương | Nội dung | Phụ trách | Ước lượng |
|---|---|---|---|
| 1 | Giới thiệu, mục tiêu, phân công thành viên | A | 0,5 trang |
| 2 | Kiến trúc tổng thể và **thread model** (sơ đồ) | A | 1 trang |
| 3 | **Giao thức ứng dụng**: `HELLO` (UDP); `HI`, `MSG`, `FILE`, `BYE` (TCP); vì sao cần framing, ví dụ từ thí nghiệm "dính gói" | B | 1,5 trang |
| 4 | Discovery và trạng thái (UDP): broadcast, timeout, reaper, lock | A | 1 trang |
| 5 | Chat TCP: kết nối, receiver thread, unread, quy tắc hai bên cùng `/chat` | B | 1 trang |
| 6 | Truyền file: kết nối riêng, chunk, progress, `.part` | C | 1 trang |
| 7 | Giao diện gõ-khi-nhận: cách chọn (A hay B), cơ chế vẽ lại, lock màn hình | C | 0,5 trang |
| 8 | Xử lý lỗi: bảng mục 3 và kết quả mục 4 | B | 0,5 trang |
| 9 | **Wireshark**: ảnh UDP broadcast và TCP handshake có giải thích | C | 1 trang |
| 10 | Kiểm thử: tóm tắt các bảng test, cách kiểm thử trên 1 và 2 máy | A | 0,5 trang |
| 11 | **Vấn đề gặp phải và giải pháp** (lấy từ mục "Vấn đề gặp phải" của 5 milestone) | Cả nhóm | 1 trang |
| 12 | Kết luận, hạn chế, hướng phát triển | A | 0,5 trang |

Nguyên tắc: báo cáo được viết dần từ Sprint 1, không dồn về cuối. Nguồn nháp nằm trong README của từng milestone và `docs/report/`.


## 8. Checklist nộp bài

- [ ] Mã nguồn đầy đủ, chạy được theo README trên máy sạch (TC-5.12).
- [ ] `README.md` gốc có: cài đặt, chạy, kiểm thử, lệnh, kiến trúc, giao thức.
- [ ] Báo cáo (5 – 10 trang) đã xuất PDF.
- [ ] Ảnh Wireshark (UDP broadcast, TCP handshake) có chú thích, trong `docs/wireshark/`.
- [ ] Không còn file rác: `__pycache__`, `downloads/*`, `.part`, `.venv`.
- [ ] Đã tạo tag `milestone-5` và `v1.0` trên `main`.
- [ ] Tất cả thành viên đã xem lại bản nộp trước khi gửi.
- [ ] Đã tập demo ít nhất 2 lần có bấm giờ.

---

Trước: [Milestone 4](../milestone4/README.md). Quay lại [README chính](../README.md).
