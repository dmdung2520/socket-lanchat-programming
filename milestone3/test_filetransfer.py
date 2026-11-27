"""
tests/test_filetransfer.py – Unit tests cho filetransfer.py (Milestone 3 / PB-15)

Kiểm tra:
  1. compute_sha256 tính đúng băm file
  2. Gửi và nhận file thành công qua TCP, so khớp SHA-256
  3. Tiến độ progress_callback được gọi
  4. Lỗi ngắt kết nối giữa chừng -> dọn sạch file .part
  5. Chống Directory Traversal: path độc hại bị chuyển thành basename
"""

import hashlib
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import filetransfer


class TestFileTransfer(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.download_dir = os.path.join(self.test_dir, "downloads")
        os.makedirs(self.download_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_compute_sha256(self):
        """Kiểm tra hàm compute_sha256 với file mẫu."""
        test_file = os.path.join(self.test_dir, "sample.bin")
        data = b"Hello LAN Chat! " * 5000  # ~80 KB (vượt 64 KB chunk)
        with open(test_file, "wb") as f:
            f.write(data)

        expected = hashlib.sha256(data).hexdigest()
        actual = filetransfer.compute_sha256(test_file)
        self.assertEqual(actual, expected)

    def test_send_and_receive_file(self):
        """Gửi và nhận file qua socketpair và so sánh mã băm SHA-256."""
        # Tạo file 150 KB (> 2 chunks 64 KB)
        src_file = os.path.join(self.test_dir, "test_send.dat")
        content = os.urandom(150 * 1024)
        with open(src_file, "wb") as f:
            f.write(content)
        expected_sha = filetransfer.compute_sha256(src_file)

        s1, s2 = socket.socketpair()

        progress_records = []

        def on_progress(sent, total):
            progress_records.append((sent, total))

        def receiver_thread():
            return filetransfer.receive_file(s2, download_dir=self.download_dir)

        result_holder = []
        error_holder = []

        def run_receiver():
            try:
                res = receiver_thread()
                result_holder.append(res)
            except Exception as e:
                error_holder.append(e)

        t = threading.Thread(target=run_receiver)
        t.start()

        # Sender gửi file
        filetransfer.send_file(s1, src_file, progress_callback=on_progress)

        t.join(timeout=5.0)
        s1.close()
        s2.close()

        self.assertFalse(error_holder, f"Receiver encountered error: {error_holder}")
        self.assertTrue(result_holder, "Receiver returned no result")

        saved_path, received_sha = result_holder[0]
        self.assertTrue(os.path.exists(saved_path))
        self.assertEqual(received_sha, expected_sha)
        self.assertGreater(len(progress_records), 0)
        # Tiến độ cuối cùng phải đủ 100%
        self.assertEqual(progress_records[-1][0], len(content))

    def test_part_file_cleaned_up_on_error(self):
        """Khi kết nối bị đứt giữa chừng, file .part phải bị xóa sạch."""
        src_file = os.path.join(self.test_dir, "broken.dat")
        content = b"X" * 100_000
        with open(src_file, "wb") as f:
            f.write(content)

        s1, s2 = socket.socketpair()

        error_holder = []

        def run_receiver():
            try:
                filetransfer.receive_file(s2, download_dir=self.download_dir)
            except Exception as e:
                error_holder.append(e)

        t = threading.Thread(target=run_receiver)
        t.start()

        # Sender chỉ gửi header và 1000 byte rồi đóng socket đột ngột
        s1.sendall(f"FILE|broken.dat|{len(content)}|".encode("utf-8"))
        s1.sendall(b"X" * 1000)
        s1.close()

        t.join(timeout=5.0)
        s2.close()

        self.assertTrue(error_holder, "Receiver should have raised ConnectionError")
        # Kiểm tra không còn file .part nào trong download_dir
        part_files = [f for f in os.listdir(self.download_dir) if f.endswith(".part")]
        self.assertEqual(part_files, [])

    def test_path_traversal_prevention(self):
        """Header chứa ../../evil.txt phải được lưu thành evil.txt an toàn."""
        s1, s2 = socket.socketpair()

        def run_receiver():
            return filetransfer.receive_file(s2, download_dir=self.download_dir)

        result_holder = []

        def target():
            res = run_receiver()
            result_holder.append(res)

        t = threading.Thread(target=target)
        t.start()

        data = b"secret safe content"
        # Gửi header có chứa đường dẫn traversal độc hại
        s1.sendall(f"FILE|../../../../evil.txt|{len(data)}|".encode("utf-8") + data)
        t.join(timeout=5.0)
        s1.close()
        s2.close()

        self.assertTrue(result_holder)
        saved_path, _ = result_holder[0]
        # File phải nằm trong self.download_dir, tên là evil.txt
        self.assertEqual(os.path.dirname(saved_path), self.download_dir)
        self.assertEqual(os.path.basename(saved_path), "evil.txt")


if __name__ == "__main__":
    unittest.main()
