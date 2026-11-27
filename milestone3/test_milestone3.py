"""
tests/test_milestone3.py – Kiểm tra toàn diện Milestone 3 (TC-3.01 -> TC-3.13)

Chạy: python3 -m unittest tests/test_milestone3.py
"""

import os
import socket
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import chat
import discovery
import lanchat
import protocol
import ui


class TestMilestone3(unittest.TestCase):

    def setUp(self):
        # Chọn các port ngẫu nhiên khả dụng trên loopback
        self.port_a = self._get_free_port()
        self.port_b = self._get_free_port()
        self.port_c = self._get_free_port()

    def tearDown(self):
        chat.close_all()

    def _get_free_port(self) -> int:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def test_tc_3_01_two_way_chat(self):
        """TC-3.01: A và B chat hai chiều qua lại."""
        msgs_at_b = []
        msgs_at_a = []

        # Khởi động Node B
        chat.start(
            my_name="Minh",
            host="127.0.0.1",
            port=self.port_b,
            on_message=lambda sender, text: msgs_at_b.append((sender, text)),
        )

        # Giả lập Node A kết nối tới Node B
        s_a = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s_a, "Quan")
        time.sleep(0.05)

        # A gửi tin cho B
        protocol.send_msg(s_a, "Xin chao Minh")
        time.sleep(0.05)

        self.assertEqual(len(msgs_at_b), 1)
        self.assertEqual(msgs_at_b[0], ("Quan", "Xin chao Minh"))

        # B gửi tin lại cho A
        ok = chat.send_to("Quan", "Chao Quan, minh day")
        self.assertTrue(ok)

        frame = protocol.read_frame(s_a)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.payload, "Chao Quan, minh day")

        s_a.close()

    def test_tc_3_02_100_rapid_messages(self):
        """TC-3.02: Gửi 100 tin liên tiếp rất nhanh không dính, không mất."""
        received = []

        chat.start(
            my_name="Minh",
            host="127.0.0.1",
            port=self.port_b,
            on_message=lambda sender, text: received.append(text),
        )

        s_a = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s_a, "Quan")
        time.sleep(0.05)

        sent_messages = [f"Message #{i:03d} content" for i in range(100)]
        for m in sent_messages:
            protocol.send_msg(s_a, m)

        # Chờ nhận đủ 100 tin
        start_wait = time.time()
        while len(received) < 100 and time.time() - start_wait < 5.0:
            time.sleep(0.02)

        s_a.close()
        self.assertEqual(len(received), 100)
        self.assertEqual(received, sent_messages)

    def test_tc_3_03_vietnamese_and_emoji(self):
        """TC-3.03: Tin tiếng Việt có dấu và emoji."""
        received = []

        chat.start(
            my_name="Minh",
            host="127.0.0.1",
            port=self.port_b,
            on_message=lambda sender, text: received.append(text),
        )

        s_a = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s_a, "Quan")
        time.sleep(0.05)

        sample = "Chào bạn! Chúc một ngày tốt lành 🇻🇳 🎉 ✨"
        protocol.send_msg(s_a, sample)

        time.sleep(0.05)
        s_a.close()

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], sample)

    def test_tc_3_04_large_message(self):
        """TC-3.04: Tin dài 100 KB nhận đủ, đúng nội dung."""
        received = []

        chat.start(
            my_name="Minh",
            host="127.0.0.1",
            port=self.port_b,
            on_message=lambda sender, text: received.append(text),
        )

        s_a = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s_a, "Quan")
        time.sleep(0.05)

        large_text = "ABCDEFGHIJ" * 10_000  # 100,000 ký tự (100 KB)
        protocol.send_msg(s_a, large_text)

        start_wait = time.time()
        while not received and time.time() - start_wait < 5.0:
            time.sleep(0.02)

        s_a.close()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], large_text)

    def test_tc_3_06_and_3_07_unread_and_switch(self):
        """TC-3.06 & TC-3.07: A đang chat B; C nhắn A hiện unread, chuyển sang C hiện đủ và về 0."""
        printed_lines = []
        original_print = ui.print_above
        ui.print_above = lambda text: printed_lines.append(text)

        try:
            # Khởi tạo trạng thái
            lanchat._my_name = "Quan"
            lanchat._current_partner = "Minh"
            lanchat._unread.clear()
            lanchat._history.clear()

            # Minh nhắn (đang là đối tác hiện tại)
            lanchat.on_chat_message("Minh", "Hello Quan")
            self.assertEqual(lanchat._unread["Minh"], 0)
            self.assertIn("[Minh] Hello Quan", printed_lines)

            # TC-3.06: Lan nhắn tin 1 (không phải đối tác hiện tại)
            lanchat.on_chat_message("Lan", "Tin 1 tu Lan")
            self.assertEqual(lanchat._unread["Lan"], 1)
            self.assertIn("[*] New message from Lan (1 unread)", printed_lines)

            # TC-3.07: Lan nhắn tiếp tin 2
            lanchat.on_chat_message("Lan", "Tin 2 tu Lan")
            self.assertEqual(lanchat._unread["Lan"], 2)
            self.assertIn("[*] New message from Lan (2 unread)", printed_lines)

            # Giả lập Lan đã có kết nối trong chat
            with chat._connections_lock:
                # Mock socket
                chat._connections["Lan"] = mock.MagicMock()

            # Quan chuyển sang chat với Lan: /chat Lan
            lanchat.cmd_chat(["Lan"])

            # Sau khi switch: current_partner là Lan, unread về 0
            self.assertEqual(lanchat._current_partner, "Lan")
            self.assertEqual(lanchat._unread["Lan"], 0)

            # Kiểm tra các thông báo switch và hiển thị tin chưa đọc
            switch_header_found = any("[*] Switched to Lan, 2 unread:" in line for line in printed_lines)
            self.assertTrue(switch_header_found, f"Missing switch header in {printed_lines}")
            self.assertIn("[Lan] Tin 1 tu Lan", printed_lines)
            self.assertIn("[Lan] Tin 2 tu Lan", printed_lines)

            with chat._connections_lock:
                chat._connections.clear()

        finally:
            ui.print_above = original_print

    def test_tc_3_05_empty_message(self):
        """TC-3.05: Tin rỗng không bị crash."""
        received = []

        chat.start(
            my_name="Minh",
            host="127.0.0.1",
            port=self.port_b,
            on_message=lambda sender, text: received.append(text),
        )

        s_a = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s_a, "Quan")
        time.sleep(0.05)

        protocol.send_msg(s_a, "")
        time.sleep(0.05)
        s_a.close()

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], "")

    def test_tc_3_08_leave_chat(self):
        """TC-3.08: /leave gửi BYE, đóng kết nối sạch cả 2 phía."""
        disconnect_events = []

        chat.start(
            my_name="Minh",
            host="127.0.0.1",
            port=self.port_b,
            on_disconnect=lambda name, reason: disconnect_events.append((name, reason)),
        )

        s_a = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s_a, "Quan")
        time.sleep(0.05)

        self.assertTrue(chat.is_connected("Quan"))

        # Quan gửi BYE
        protocol.send_bye(s_a)
        s_a.close()

        time.sleep(0.1)
        self.assertFalse(chat.is_connected("Quan"))
        self.assertEqual(len(disconnect_events), 1)
        self.assertEqual(disconnect_events[0], ("Quan", "bye"))

    def test_tc_3_09_kill_peer_abruptly(self):
        """TC-3.09: Ngắt kết nối đột ngột -> báo lost, dọn kết nối, không crash."""
        disconnect_events = []

        chat.start(
            my_name="Minh",
            host="127.0.0.1",
            port=self.port_b,
            on_disconnect=lambda name, reason: disconnect_events.append((name, reason)),
        )

        s_a = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s_a, "Quan")
        time.sleep(0.05)
        self.assertTrue(chat.is_connected("Quan"))

        # Sập đột ngột (đóng socket mà không gửi BYE)
        s_a.close()

        time.sleep(0.1)
        self.assertFalse(chat.is_connected("Quan"))
        self.assertEqual(len(disconnect_events), 1)
        self.assertEqual(disconnect_events[0], ("Quan", "lost"))

    def test_tc_3_10_chat_to_offline_peer(self):
        """TC-3.10: /chat tới peer offline -> trả về False / báo lỗi, không crash."""
        chat.start(my_name="Quan", host="127.0.0.1", port=self.port_a)
        unused_port = self._get_free_port()
        ok = chat.open_chat("127.0.0.1", unused_port, "GhostPeer")
        self.assertFalse(ok)
        self.assertFalse(chat.is_connected("GhostPeer"))

    def test_tc_3_11_simultaneous_chat(self):
        """TC-3.11: Hai bên cùng lúc kết nối -> áp dụng quy tắc giữ kết nối mới nhất."""
        chat.start(my_name="Minh", host="127.0.0.1", port=self.port_b)

        # Kết nối thứ nhất từ Quan
        s_a1 = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s_a1, "Quan")
        time.sleep(0.05)

        # Kết nối thứ hai từ Quan (kết nối mới hơn)
        s_a2 = socket.create_connection(("127.0.0.1", self.port_b))
        protocol.send_hi(s_a2, "Quan")
        time.sleep(0.05)

        # Kết nối cũ s_a1 phải bị đóng
        with self.assertRaises(ConnectionError):
            protocol.recv_exact(s_a1, 1)

        # Kết nối mới s_a2 vẫn hoạt động bình thường
        ok = chat.send_to("Quan", "Hello on new conn")
        self.assertTrue(ok)
        frame = protocol.read_frame(s_a2)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.payload, "Hello on new conn")

        s_a2.close()

    def test_tc_3_13_manual_framing_check(self):
        """TC-3.13: Giả lập ncat gửi thủ công MSG|5|hello, header sai bị đóng kết nối."""
        received = []
        disconnects = []

        chat.start(
            my_name="Minh",
            host="127.0.0.1",
            port=self.port_b,
            on_message=lambda sender, text: received.append(text),
            on_disconnect=lambda name, reason: disconnects.append((name, reason)),
        )

        # 1. Gửi đúng format thủ công
        s1 = socket.create_connection(("127.0.0.1", self.port_b))
        s1.sendall(b"HI|Tester|\n")
        s1.sendall(b"MSG|5|hello\n")
        time.sleep(0.05)
        self.assertIn("hello", received)
        s1.close()

        # 2. Gửi header sai -> phía server tự đóng kết nối
        s2 = socket.create_connection(("127.0.0.1", self.port_b))
        s2.sendall(b"HI|Attacker|\n")
        s2.sendall(b"INVALID_HEADER|abc\n")
        time.sleep(0.05)

        # Kiểm tra server đã đóng socket s2 (trả b"" hoặc ConnectionResetError)
        try:
            chunk = s2.recv(1024)
            self.assertEqual(chunk, b"")
        except (ConnectionResetError, ConnectionError):
            pass  # Kết nối đã bị đóng bởi server
        s2.close()


if __name__ == "__main__":
    unittest.main()
