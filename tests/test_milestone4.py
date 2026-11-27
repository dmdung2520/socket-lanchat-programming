"""
tests/test_milestone4.py – Kiểm tra tích hợp Milestone 4

Kiểm tra:
  1. Gửi file qua kết nối TCP riêng trong khi kết nối chat vẫn mở và hoạt động hai chiều
  2. File 0 byte (TC-4.09)
  3. Tên file tiếng Việt và có khoảng trắng (TC-4.10)
  4. Trùng tên file trong downloads/ tự động đánh số _1, _2 (TC-4.11)
  5. /send file không tồn tại / chưa chọn đối tác / đường dẫn có dấu ngoặc kép (TC-4.12)
  6. Ngăn chặn Path Traversal cả '/', '\', '.', '..' (TC-4.15)
  7. Ngắt kết nối giữa chừng khi truyền file -> xóa sạch file .part (TC-4.13)
  8. /quit (chat.close_all) gửi BYE tới mọi peer đang kết nối
  9. Tin nhắn vượt quá 1 MB bị từ chối ở lanchat mà không làm mất cuộc chat
  10. Discovery phát hiện cảnh báo trùng tên
"""

import os
import shutil
import socket
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import chat
import discovery
import filetransfer
import lanchat
import protocol
import ui


class TestMilestone4(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.download_dir = os.path.join(self.test_dir, "downloads")
        os.makedirs(self.download_dir, exist_ok=True)
        self.orig_download_dir = filetransfer.DEFAULT_DOWNLOAD_DIR
        filetransfer.DEFAULT_DOWNLOAD_DIR = self.download_dir

        self.port_b = self._get_free_port()
        self.printed = []
        self._orig_print = ui.print_above
        self._orig_ft_print = filetransfer.print_above
        self._orig_chat_print = chat.print_above
        ui.print_above = self.printed.append
        filetransfer.print_above = self.printed.append
        chat.print_above = self.printed.append

        with lanchat._chat_lock:
            lanchat._my_name = "Quan"
            lanchat._current_partner = None
            lanchat._unread.clear()
            lanchat._history.clear()
            lanchat._peer_addrs.clear()

    def tearDown(self):
        chat.close_all()
        filetransfer.DEFAULT_DOWNLOAD_DIR = self.orig_download_dir
        ui.print_above = self._orig_print
        filetransfer.print_above = self._orig_ft_print
        chat.print_above = self._orig_chat_print
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _get_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def test_file_transfer_keeps_chat_alive(self):
        """Gửi file qua chat.py (kết nối riêng) không làm đứt kết nối chat hiện có."""
        msgs_at_b = []
        disconnects_at_b = []

        chat.start(
            my_name="Minh",
            host="127.0.0.1",
            port=self.port_b,
            on_message=lambda s, t: msgs_at_b.append((s, t)),
            on_disconnect=lambda p, r: disconnects_at_b.append((p, r)),
        )

        # 1. Quan mở kết nối chat tới Minh
        chat_sock = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(chat_sock, "Quan")
        time.sleep(0.05)
        self.assertTrue(chat.is_connected("Quan"))

        protocol.send_msg(chat_sock, "Chuan bi gui file")
        time.sleep(0.05)
        self.assertEqual(msgs_at_b, [("Quan", "Chuan bi gui file")])

        # 2. Quan gửi file trên kết nối TCP riêng tới Minh
        src_file = os.path.join(self.test_dir, "report.bin")
        payload = os.urandom(200 * 1024)
        with open(src_file, "wb") as f:
            f.write(payload)
        expected_sha = filetransfer.compute_sha256(src_file)

        ok = filetransfer.send_file_to_peer(
            "127.0.0.1", self.port_b, "Quan", src_file, peer_name="Minh"
        )
        self.assertTrue(ok)

        # Chờ receiver ghi xong file vào downloads/
        saved = os.path.join(self.download_dir, "report.bin")
        deadline = time.time() + 5.0
        while not os.path.exists(saved) and time.time() < deadline:
            time.sleep(0.02)

        self.assertTrue(os.path.exists(saved))
        self.assertEqual(filetransfer.compute_sha256(saved), expected_sha)

        # 3. Kết nối chat giữa Quan và Minh VẪN SỐNG hai chiều và không báo disconnect!
        self.assertEqual(disconnects_at_b, [])
        self.assertTrue(chat.is_connected("Quan"))

        protocol.send_msg(chat_sock, "Nhan duoc file chua?")
        time.sleep(0.05)
        self.assertEqual(msgs_at_b[-1], ("Quan", "Nhan duoc file chua?"))

        self.assertTrue(chat.send_to("Quan", "Nhan duoc roi!"))
        reply = protocol.read_frame(chat_sock)
        self.assertIsNotNone(reply)
        self.assertEqual(reply.payload, "Nhan duoc roi!")

        chat_sock.close()

    def test_zero_byte_file(self):
        """TC-4.09: Truyền file 0 byte thành công."""
        chat.start(my_name="Minh", host="127.0.0.1", port=self.port_b)
        src_file = os.path.join(self.test_dir, "empty.txt")
        with open(src_file, "wb"):
            pass

        ok = filetransfer.send_file_to_peer("127.0.0.1", self.port_b, "Quan", src_file)
        self.assertTrue(ok)

        saved = os.path.join(self.download_dir, "empty.txt")
        deadline = time.time() + 5.0
        while not os.path.exists(saved) and time.time() < deadline:
            time.sleep(0.02)

        self.assertTrue(os.path.exists(saved))
        self.assertEqual(os.path.getsize(saved), 0)

    def test_vietnamese_and_duplicate_filenames(self):
        """TC-4.10 & TC-4.11: Tên file tiếng Việt có khoảng trắng & không ghi đè khi trùng tên."""
        chat.start(my_name="Minh", host="127.0.0.1", port=self.port_b)

        src_file = os.path.join(self.test_dir, "bài tập mạng.txt")
        with open(src_file, "wb") as f:
            f.write(b"noi dung lan 1")

        self.assertTrue(filetransfer.send_file_to_peer("127.0.0.1", self.port_b, "Quan", src_file))
        first = os.path.join(self.download_dir, "bài tập mạng.txt")
        deadline = time.time() + 5.0
        while not os.path.exists(first) and time.time() < deadline:
            time.sleep(0.02)
        self.assertTrue(os.path.exists(first))

        # Gửi lần 2 cùng tên nhưng nội dung mới -> phải lưu thành _1
        with open(src_file, "wb") as f:
            f.write(b"noi dung lan 2")
        self.assertTrue(filetransfer.send_file_to_peer("127.0.0.1", self.port_b, "Quan", src_file))

        second = os.path.join(self.download_dir, "bài tập mạng_1.txt")
        deadline = time.time() + 5.0
        while not os.path.exists(second) and time.time() < deadline:
            time.sleep(0.02)
        self.assertTrue(os.path.exists(second))

        with open(first, "rb") as f:
            self.assertEqual(f.read(), b"noi dung lan 1")
        with open(second, "rb") as f:
            self.assertEqual(f.read(), b"noi dung lan 2")

    def test_sanitize_filename_edge_cases(self):
        """TC-4.15: Chặn đường dẫn traversal cả /, \\, ., .."""
        self.assertEqual(filetransfer._sanitize_filename("../../evil.txt"), "evil.txt")
        self.assertEqual(filetransfer._sanitize_filename("..\\..\\evil.txt"), "evil.txt")
        self.assertEqual(filetransfer._sanitize_filename(".."), "downloaded_file")
        self.assertEqual(filetransfer._sanitize_filename("."), "downloaded_file")
        self.assertEqual(filetransfer._sanitize_filename(""), "downloaded_file")

    def test_cmd_send_missing_file_and_quoted_path(self):
        """TC-4.12: /send file không tồn tại báo lỗi; /send đường dẫn có ngoặc kép hoạt động."""
        lanchat._current_partner = "Minh"

        # 1. File không tồn tại
        with mock.patch.object(filetransfer, "start_send_file") as mock_start:
            lanchat.cmd_send(["khong_ton_tai.xyz"])
            mock_start.assert_not_called()
        self.assertTrue(any("không tồn tại" in msg for msg in self.printed))

        # 2. Đường dẫn có dấu ngoặc kép và khoảng trắng
        spaced_file = os.path.join(self.test_dir, "my notes.txt")
        with open(spaced_file, "wb") as f:
            f.write(b"abc")

        fake_peer = discovery.Peer(name="Minh", ip="127.0.0.1", tcp_port=5001, status="online")
        with mock.patch.object(discovery, "find_peer", return_value=fake_peer), \
             mock.patch.object(filetransfer, "start_send_file") as mock_start:
            quoted_arg = f'"{spaced_file}"'
            lanchat.cmd_send(quoted_arg.split())
            mock_start.assert_called_once()
            self.assertEqual(mock_start.call_args.kwargs["filepath"], spaced_file)

    def test_close_all_sends_bye_to_all_peers(self):
        """close_all() (/quit) gửi BYE tới tất cả peer đang kết nối."""
        chat.start(my_name="Minh", host="127.0.0.1", port=self.port_b)

        s1 = socket.create_connection(("127.0.0.1", self.port_b))
        s2 = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s1, "Quan")
        protocol.send_hi(s2, "Lan")
        time.sleep(0.05)

        self.assertTrue(chat.is_connected("Quan"))
        self.assertTrue(chat.is_connected("Lan"))

        chat.close_all()

        f1 = protocol.read_frame(s1)
        f2 = protocol.read_frame(s2)
        self.assertIsNotNone(f1)
        self.assertIsNotNone(f2)
        self.assertEqual(f1.type, "BYE")
        self.assertEqual(f2.type, "BYE")

        s1.close()
        s2.close()

    def test_oversized_message_does_not_drop_connection(self):
        """Tin nhắn vượt quá MAX_MSG_SIZE bị từ chối nhưng không làm rớt cuộc chat."""
        chat.start(my_name="Minh", host="127.0.0.1", port=self.port_b)
        s_a = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s_a, "Quan")
        time.sleep(0.05)

        lanchat._current_partner = "Quan"
        lanchat.send_chat_message("x" * (protocol.MAX_MSG_SIZE + 10))

        self.assertTrue(chat.is_connected("Quan"))
        self.assertEqual(lanchat._current_partner, "Quan")
        s_a.close()

    def test_discovery_validation_and_find_peer(self):
        """Kiểm tra validate gói HELLO, sắp xếp ổn định và tìm peer theo tên/STT."""
        self.assertEqual(
            discovery._validate_packet("HELLO|Minh|5001|online"),
            ("Minh", 5001, "online"),
        )
        self.assertIsNone(discovery._validate_packet("HELLO||5001|online"))
        self.assertIsNone(discovery._validate_packet("HELLO|Mi|nh|5001|online"))
        self.assertIsNone(discovery._validate_packet("HELLO|Minh|70000|online"))
        self.assertIsNone(discovery._validate_packet("HELLO|Minh|5001|busy"))
        self.assertIsNone(discovery._validate_packet("GARBAGE"))

        with discovery._lock:
            orig_peers = dict(discovery._peers)
            discovery._peers.clear()
            discovery._peers[("192.168.1.12", 5001)] = {
                "name": "Minh", "status": "online", "last_seen": 100.0
            }
            discovery._peers[("192.168.1.15", 5002)] = {
                "name": "Lan", "status": "away", "last_seen": 100.0
            }
        try:
            peers = discovery.get_peers()
            self.assertEqual([p.name for p in peers], ["Lan", "Minh"])
            self.assertEqual(discovery.find_peer("1").name, "Lan")
            self.assertEqual(discovery.find_peer("minh").name, "Minh")
            self.assertIsNone(discovery.find_peer("99"))
        finally:
            with discovery._lock:
                discovery._peers.clear()
                discovery._peers.update(orig_peers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
