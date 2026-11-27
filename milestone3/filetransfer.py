"""
filetransfer.py – Bản prototype độc lập truyền file qua TCP (Milestone 3 / Milestone 4)

Đặc tả kỹ thuật:
  - Chunk size: 64 KB (65536 bytes)
  - Định dạng header: FILE|<tên_file>|<kích_thước_byte>|
  - Tên file lưu luôn đi qua os.path.basename() để ngăn chặn Directory Traversal
  - File đang nhận lưu dưới dạng .part (ví dụ: downloads/abc.txt.part)
  - Nếu lỗi mạng hoặc ngắt kết nối giữa chừng: xóa file .part ngay lập tức
  - Nhận đủ số byte: đổi tên .part thành file chính thức
  - Hỗ trợ hàm tính hash SHA-256 để so khớp toàn vẹn dữ liệu
"""

import hashlib
import os
import socket
from typing import Callable

import protocol

CHUNK_SIZE = 64 * 1024  # 64 KB
DEFAULT_DOWNLOAD_DIR = "downloads"


def compute_sha256(filepath: str) -> str:
    """Tính mã băm SHA-256 của file theo từng chunk 64 KB."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def _get_unique_filepath(directory: str, filename: str) -> str:
    """Tạo đường dẫn file không bị trùng lặp trong thư mục đích."""
    base_name = os.path.basename(filename)
    dest_path = os.path.join(directory, base_name)
    if not os.path.exists(dest_path):
        return dest_path

    name, ext = os.path.splitext(base_name)
    counter = 1
    while True:
        new_name = f"{name}_{counter}{ext}"
        new_path = os.path.join(directory, new_name)
        if not os.path.exists(new_path):
            return new_path
        counter += 1


def send_file(
    sock: socket.socket,
    filepath: str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """
    Gửi file qua socket TCP:
    1. Kiểm tra file tồn tại, lấy kích thước byte và tên file.
    2. Gửi header: FILE|<filename>|<filesize>|
    3. Đọc và gửi từng chunk 64 KB qua sock.sendall().
    4. Báo tiến độ qua progress_callback(bytes_sent, total_bytes).
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    filesize = os.path.getsize(filepath)
    filename = os.path.basename(filepath)

    if "|" in filename:
        raise ValueError("Filename cannot contain '|'")

    header = f"FILE|{filename}|{filesize}|".encode("utf-8")
    sock.sendall(header)

    sent_bytes = 0
    with open(filepath, "rb") as f:
        while sent_bytes < filesize:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sock.sendall(chunk)
            sent_bytes += len(chunk)
            if progress_callback:
                progress_callback(sent_bytes, filesize)


def receive_file(
    sock: socket.socket,
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[str, str]:
    """
    Nhận file từ socket TCP:
    1. Đọc header FILE|<filename>|<filesize>| (nếu chưa đọc keyword FILE thì đọc).
    2. Lưu tạm vào <dest_file>.part.
    3. Đọc đúng filesize byte theo từng chunk.
    4. Nếu lỗi giữa chừng, xóa file .part.
    5. Đủ dữ liệu thì rename .part thành file đích.
    Trả về (đường_dẫn_file_đã_lưu, sha256_hash).
    """
    keyword = protocol.read_token(sock, "|")
    if keyword != "FILE":
        raise ValueError(f"Expected FILE frame, got: {keyword!r}")

    raw_filename = protocol.read_token(sock, "|")
    size_str = protocol.read_token(sock, "|")
    try:
        filesize = int(size_str)
        if filesize < 0:
            raise ValueError()
    except ValueError:
        raise ValueError(f"Bad file size in header: {size_str!r}")

    # Chống Path Traversal bằng os.path.basename
    safe_filename = os.path.basename(raw_filename)
    if not safe_filename:
        safe_filename = "downloaded_file"

    os.makedirs(download_dir, exist_ok=True)
    final_path = _get_unique_filepath(download_dir, safe_filename)
    part_path = final_path + ".part"

    received_bytes = 0
    try:
        with open(part_path, "wb") as f:
            while received_bytes < filesize:
                to_read = min(CHUNK_SIZE, filesize - received_bytes)
                chunk = sock.recv(to_read)
                if not chunk:
                    raise ConnectionError("Connection lost while receiving file payload")
                f.write(chunk)
                received_bytes += len(chunk)
                if progress_callback:
                    progress_callback(received_bytes, filesize)

        # Đổi tên .part thành file hoàn chỉnh
        os.replace(part_path, final_path)
        sha256_val = compute_sha256(final_path)
        return final_path, sha256_val

    except Exception:
        # Dọn dẹp file dở .part khi lỗi
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except OSError:
                pass
        raise
