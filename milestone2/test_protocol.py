"""
tests/test_protocol.py – Unit tests cho protocol.py (Milestone 2)

Chạy:  python -m pytest tests/
       hoặc: python -m unittest discover -s tests

Test cases (TC-2.09):
  a) Tin bị chia nhỏ từng byte
  b) Hai tin dính nhau
  c) Tiếng Việt (multi-byte UTF-8)
  d) Tin rỗng (payload = "")
  e) Nhiều tin liên tiếp
  f) Kết nối đóng giữa chừng -> trả None

Lưu ý: Tất cả test dùng FakeSocket (BytesIO) thay vì network thực,
        nên chạy được trong mọi môi trường kể cả sandbox/CI.
        Test mạng thực được cung cấp riêng trong test_protocol_net.py
        nếu muốn chạy tay.
"""

import sys
import os
import io
import threading
import time
import unittest

# Thêm thư mục hiện tại (ưu tiên) và src vào path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from protocol import send_msg, read_frame, recv_exact, read_token


# ---------------------------------------------------------------------------
# FakeSocket: giả lập socket bằng BytesIO (không cần network)
# ---------------------------------------------------------------------------

class FakeSocket:
    """
    Socket giả: đọc từ BytesIO (recv), ghi vào BytesIO khác (sendall/send).
    Dùng cho test không cần network.
    """
    def __init__(self, data: bytes = b""):
        self._in = io.BytesIO(data)
        self._out = io.BytesIO()
        self._closed = False

    def recv(self, n: int) -> bytes:
        if self._closed:
            return b""
        chunk = self._in.read(n)
        return chunk   # b"" khi hết -> giống socket đóng

    def sendall(self, data: bytes) -> None:
        self._out.write(data)

    def send(self, data: bytes) -> int:
        self._out.write(data)
        return len(data)

    def get_sent(self) -> bytes:
        return self._out.getvalue()

    def close(self):
        self._closed = True


def _build_frame(text: str) -> bytes:
    """Tạo frame MSG|<len>|<payload>\\n từ text."""
    payload = text.encode("utf-8")
    return f"MSG|{len(payload)}|".encode() + payload + b"\n"


class SlowFakeSocket:
    """
    Socket giả trả về data từng byte một (TC-2.09 a).
    Giả lập TCP fragmentation – không cần network thực.
    """
    def __init__(self, data: bytes, chunk_size: int = 1):
        self._data = data
        self._pos = 0
        self._chunk = chunk_size

    def recv(self, n: int) -> bytes:
        end = min(self._pos + self._chunk, len(self._data))
        chunk = self._data[self._pos:end]
        self._pos = end
        return chunk   # b"" khi hết

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Tests cho recv_exact
# ---------------------------------------------------------------------------

class TestRecvExact(unittest.TestCase):

    def test_simple(self):
        """recv_exact đọc đúng n byte."""
        s = FakeSocket(b"hello world")
        result = recv_exact(s, 5)
        self.assertEqual(result, b"hello")

    def test_reads_remainder(self):
        """recv_exact tiếp tục từ vị trí hiện tại."""
        s = FakeSocket(b"hello world")
        recv_exact(s, 5)
        result = recv_exact(s, 1)   # đọc khoảng trắng
        self.assertEqual(result, b" ")

    def test_chunked_byte_by_byte(self):
        """TC-2.09 a) recv_exact phải ghép đủ dù nhận từng byte."""
        s = SlowFakeSocket(b"world", chunk_size=1)
        result = recv_exact(s, 5)
        self.assertEqual(result, b"world")

    def test_eof_raises_connection_error(self):
        """TC-2.09 f) EOF sớm -> ConnectionError."""
        s = FakeSocket(b"ab")       # chỉ 2 byte, yêu cầu 5
        with self.assertRaises(ConnectionError):
            recv_exact(s, 5)

    def test_empty_socket_raises(self):
        """Socket hoàn toàn rỗng -> ConnectionError."""
        s = FakeSocket(b"")
        with self.assertRaises(ConnectionError):
            recv_exact(s, 1)


# ---------------------------------------------------------------------------
# Tests cho read_frame / send_msg qua FakeSocket
# ---------------------------------------------------------------------------

class TestReadFrame(unittest.TestCase):

    def test_simple_message(self):
        """Đọc một tin đơn giản."""
        s = FakeSocket(_build_frame("hello world"))
        self.assertEqual(read_frame(s), "hello world")

    def test_empty_message(self):
        """TC-2.09 d) Tin rỗng."""
        s = FakeSocket(_build_frame(""))
        self.assertEqual(read_frame(s), "")

    def test_vietnamese_text(self):
        """TC-2.09 c) Tiếng Việt (multi-byte UTF-8)."""
        text = "Xin chào Việt Nam"
        s = FakeSocket(_build_frame(text))
        self.assertEqual(read_frame(s), text)

    def test_emoji(self):
        """Emoji 4-byte UTF-8."""
        text = "Hello 🇻🇳 World 🎉"
        s = FakeSocket(_build_frame(text))
        self.assertEqual(read_frame(s), text)

    def test_two_frames_back_to_back(self):
        """TC-2.09 b) Hai tin dính nhau trong buffer."""
        data = _build_frame("first") + _build_frame("second")
        s = FakeSocket(data)
        self.assertEqual(read_frame(s), "first")
        self.assertEqual(read_frame(s), "second")

    def test_many_frames(self):
        """TC-2.09 e) Nhiều tin liên tiếp."""
        messages = [f"msg_{i}" for i in range(50)]
        data = b"".join(_build_frame(m) for m in messages)
        s = FakeSocket(data)
        for m in messages:
            self.assertEqual(read_frame(s), m)

    def test_frame_split_byte_by_byte(self):
        """TC-2.09 a) Frame bị chia nhỏ từng byte."""
        frame = _build_frame("slow message")
        s = SlowFakeSocket(frame, chunk_size=1)
        result = read_frame(s)
        self.assertEqual(result, "slow message")

    def test_connection_closed_returns_none(self):
        """TC-2.09 f) EOF trước khi có frame -> None."""
        s = FakeSocket(b"")
        self.assertIsNone(read_frame(s))

    def test_long_message(self):
        """Tin dài hơn 1024 byte."""
        text = "x" * 10_000
        s = FakeSocket(_build_frame(text))
        self.assertEqual(read_frame(s), text)

    def test_unicode_char_vs_byte_length(self):
        """len(chars) != len(bytes) với ký tự multi-byte."""
        text = "café"      # 4 chars, 5 bytes UTF-8
        self.assertNotEqual(len(text), len(text.encode("utf-8")),
                            "Tiền điều kiện test: café phải khác length")
        s = FakeSocket(_build_frame(text))
        self.assertEqual(read_frame(s), text)

    def test_pipe_char_in_payload(self):
        """Ký tự | trong payload không phá vỡ frame."""
        text = "hello|world|foo|bar"
        s = FakeSocket(_build_frame(text))
        self.assertEqual(read_frame(s), text)

    def test_newline_in_payload(self):
        """Ký tự \\n trong payload không phá vỡ frame."""
        text = "line1\nline2\nline3"
        s = FakeSocket(_build_frame(text))
        self.assertEqual(read_frame(s), text)


# ---------------------------------------------------------------------------
# Tests cho send_msg (kiểm tra bytes được ghi ra)
# ---------------------------------------------------------------------------

class TestSendMsg(unittest.TestCase):

    def test_frame_format(self):
        """send_msg tạo đúng format MSG|<len>|<payload>\\n."""
        s = FakeSocket()
        send_msg(s, "hello")
        sent = s.get_sent()
        self.assertTrue(sent.startswith(b"MSG|"), f"Expected MSG|... got {sent!r}")
        self.assertTrue(sent.endswith(b"\n"), f"Expected trailing newline, got {sent!r}")

    def test_byte_length_in_header(self):
        """Header phải chứa số byte (không phải số ký tự) của payload."""
        s = FakeSocket()
        text = "café"      # 4 chars, 5 bytes
        send_msg(s, text)
        sent = s.get_sent()
        # Parse header
        parts = sent.split(b"|", 2)
        self.assertEqual(parts[0], b"MSG")
        byte_len = int(parts[1])
        self.assertEqual(byte_len, len(text.encode("utf-8")))   # phải là 5, không phải 4

    def test_roundtrip(self):
        """send_msg rồi read_frame trả lại đúng text."""
        sender = FakeSocket()
        text = "Xin chào 🇻🇳"
        send_msg(sender, text)
        # Đọc lại từ những gì đã gửi
        receiver = FakeSocket(sender.get_sent())
        self.assertEqual(read_frame(receiver), text)

    def test_empty_roundtrip(self):
        """Tin rỗng roundtrip."""
        sender = FakeSocket()
        send_msg(sender, "")
        receiver = FakeSocket(sender.get_sent())
        self.assertEqual(read_frame(receiver), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
