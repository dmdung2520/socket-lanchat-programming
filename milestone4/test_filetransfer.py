
"""
Unit tests cho filetransfer.py.

Kiểm tra:
1. Tính SHA-256 chính xác.
2. Gửi và nhận file qua TCP.
3. Dọn file .part khi kết nối bị ngắt.
4. Ngăn chặn Path Traversal.
"""

import hashlib
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import filetransfer
import protocol


class TestFileTransfer(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.download_dir = os.path.join(self.test_dir, "downloads")
        os.makedirs(self.download_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_compute_sha256(self):
        """Kiểm tra hàm tính SHA-256."""
        test_file = os.path.join(self.test_dir, "sample.bin")
        data = b"Hello LAN Chat! " * 5000

        with open(test_file, "wb") as f:
            f.write(data)

        expected = hashlib.sha256(data).hexdigest()
        actual = filetransfer.compute_sha256(test_file)

        self.assertEqual(actual, expected)

    def test_send_and_receive_file(self):
        """Kiểm tra gửi và nhận file qua TCP."""
        src_file = os.path.join(self.test_dir, "test_send.dat")
        content = os.urandom(150 * 1024)

        with open(src_file, "wb") as f:
            f.write(content)

        expected_sha = filetransfer.compute_sha256(src_file)

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)

        peer_port = server.getsockname()[1]
        error_holder = []

        def receiver():
            conn = None
            try:
                conn, _ = server.accept()

                # Đọc frame HI để xác định người gửi.
                frame = protocol.read_frame(conn)

                if frame is None or frame.type != "HI":
                    raise AssertionError("Missing or invalid HI frame")

                # Đọc keyword FILE.
                keyword = protocol.read_token(conn, "|")

                if keyword != "FILE":
                    raise AssertionError(
                        f"Expected FILE, received {keyword}"
                    )

                # receive_file đọc tiếp filename, filesize và dữ liệu.
                filetransfer.receive_file(
                    conn,
                    frame.payload,
                    download_dir=self.download_dir,
                )

            except Exception as e:
                error_holder.append(e)

            finally:
                if conn:
                    conn.close()

        thread = threading.Thread(target=receiver)
        thread.start()

        try:
            filetransfer.send_file_to_peer(
                "127.0.0.1",
                peer_port,
                "TestSender",
                src_file,
            )
        finally:
            thread.join(timeout=10)
            server.close()

        self.assertFalse(thread.is_alive(), "Receiver thread did not finish")
        self.assertFalse(error_holder, f"Receiver error: {error_holder}")

        saved_file = os.path.join(self.download_dir, "test_send.dat")

        self.assertTrue(os.path.exists(saved_file))

        received_sha = filetransfer.compute_sha256(saved_file)

        self.assertEqual(received_sha, expected_sha)

    def test_part_file_cleaned_up_on_error(self):
        """Kiểm tra file .part được xóa khi kết nối bị ngắt."""
        s1, s2 = socket.socketpair()

        content = b"X" * 100_000

        def receiver():
            filetransfer.receive_file(
                s2,
                "TestSender",
                download_dir=self.download_dir,
            )

        thread = threading.Thread(target=receiver)
        thread.start()

        try:
            # Giả lập trạng thái FILE| đã được đọc.
            # Chỉ gửi filename, filesize và một phần dữ liệu.
            header = f"broken.dat|{len(content)}|".encode("utf-8")

            s1.sendall(header + b"X" * 1000)

            # Ngắt kết nối trước khi gửi đủ dữ liệu.
            s1.close()

            thread.join(timeout=5)

        finally:
            s2.close()

        self.assertFalse(thread.is_alive(), "Receiver thread did not finish")

        part_files = [
            name
            for name in os.listdir(self.download_dir)
            if name.endswith(".part")
        ]

        self.assertEqual(part_files, [])

        self.assertFalse(
            os.path.exists(os.path.join(self.download_dir, "broken.dat"))
        )

    def test_path_traversal_prevention(self):
        """Kiểm tra tên file chứa đường dẫn traversal."""
        s1, s2 = socket.socketpair()

        data = b"secret safe content"

        def receiver():
            filetransfer.receive_file(
                s2,
                "TestSender",
                download_dir=self.download_dir,
            )

        thread = threading.Thread(target=receiver)
        thread.start()

        try:
            # Giả lập trạng thái FILE| đã được đọc.
            header = (
                f"../../../../evil.txt|{len(data)}|".encode("utf-8")
            )

            s1.sendall(header + data)
            s1.shutdown(socket.SHUT_WR)

            thread.join(timeout=5)

        finally:
            s1.close()
            s2.close()

        self.assertFalse(thread.is_alive(), "Receiver thread did not finish")

        saved_file = os.path.join(self.download_dir, "evil.txt")

        self.assertTrue(os.path.exists(saved_file))

        with open(saved_file, "rb") as f:
            received_data = f.read()

        self.assertEqual(received_data, data)

        # Đảm bảo file nằm trong download_dir.
        self.assertEqual(
            os.path.dirname(os.path.abspath(saved_file)),
            os.path.abspath(self.download_dir),
        )


if __name__ == "__main__":
    unittest.main()
