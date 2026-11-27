"""
filetransfer.py – Truyền file qua TCP (Milestone 4)

Đặc tả kỹ thuật:
  - Mỗi lần gửi file mở MỘT KẾT NỐI TCP RIÊNG (không trộn với luồng chat)
  - Chunk size: 64 KB (65536 bytes)
  - Giao thức: HI|<name>| rồi FILE|<tên_file>|<kích_thước_byte>| rồi raw bytes
  - Bên nhận: lưu dưới dạng .part → đổi tên khi nhận xong
  - Lỗi giữa chừng → xóa file .part
  - Gọi progress_callback mỗi 10% để báo tiến độ qua ui.print_above
  - Hỗ trợ file 0 byte, file trùng tên, basename chống path traversal
"""

import hashlib
import os
import socket
import threading
from typing import Callable

import protocol
from ui import print_above

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


def _sanitize_filename(raw_filename: str) -> str:
    """Chống Path Traversal trên cả Windows và POSIX, chặn '.' và '..'."""
    normalized = raw_filename.replace("\\", "/")
    base_name = os.path.basename(normalized.split("/")[-1]).strip()
    if not base_name or base_name in (".", ".."):
        return "downloaded_file"
    return base_name


def _get_unique_filepath(directory: str, filename: str) -> str:
    """Tạo đường dẫn file không bị trùng lặp trong thư mục đích."""
    base_name = _sanitize_filename(filename)
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


def _make_progress_callback(
    peer_label: str, filename: str, direction: str
) -> Callable[[int, int], None]:
    """
    Tạo hàm callback in tiến độ mỗi 10%.
    direction: "Sending" hoặc "Receiving"
    """
    last_percent = [-1]  # mutable để closure cập nhật

    def _callback(done: int, total: int) -> None:
        if total == 0:
            return
        pct = done * 100 // total
        # Chỉ in mỗi 10% để không nghẽn giao diện
        step = (pct // 10) * 10
        if step > last_percent[0]:
            last_percent[0] = step
            prep = "to" if direction == "Sending" else "from"
            if pct >= 100:
                print_above(
                    f"[file] {direction} '{filename}' {prep} {peer_label}: 100% Done"
                )
            else:
                print_above(
                    f"[file] {direction} '{filename}' {prep} {peer_label}: {step}%"
                )

    return _callback


# ---------------------------------------------------------------------------
# Gửi file (chạy trong thread riêng, kết nối TCP riêng)
# ---------------------------------------------------------------------------

def send_file_to_peer(
    peer_ip: str,
    peer_port: int,
    my_name: str,
    filepath: str,
    peer_name: str | None = None,
) -> bool:
    """
    Gửi file tới peer qua kết nối TCP RIÊNG (thread-safe).
    Hàm này nên được gọi trong thread riêng.

    Luồng:
      1. Mở kết nối TCP mới tới peer_ip:peer_port
      2. Gửi HI|<my_name>|FILE|<filename>|<filesize>| trong cùng 1 segment
      3. Gửi raw bytes theo chunk 64 KB
      4. Đóng kết nối
    """
    if not os.path.isfile(filepath):
        print_above(f"[!] File không tồn tại: {filepath}")
        return False

    if not my_name or "|" in my_name:
        print_above(f"[!] Tên người gửi không hợp lệ: {my_name!r}")
        return False

    filesize = os.path.getsize(filepath)
    filename = os.path.basename(filepath)

    if "|" in filename:
        print_above(f"[!] Tên file không được chứa '|': {filename}")
        return False

    target_label = peer_name or f"{peer_ip}:{peer_port}"
    progress = _make_progress_callback(target_label, filename, "Sending")
    conn = None

    try:
        # 1. Mở kết nối TCP riêng
        conn = socket.create_connection((peer_ip, peer_port), timeout=5.0)
        conn.settimeout(None)

        # 2. Gửi HI + FILE header trong 1 sendall để bên nhận nhận diện FILE ngay lập tức
        intro_header = f"HI|{my_name}|FILE|{filename}|{filesize}|".encode("utf-8")
        conn.sendall(intro_header)

        # 3. Gửi raw bytes
        sent_bytes = 0
        if filesize == 0:
            print_above(f"[file] Sending '{filename}' to {target_label}: 100% Done (0 bytes)")
        else:
            with open(filepath, "rb") as f:
                while sent_bytes < filesize:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    conn.sendall(chunk)
                    sent_bytes += len(chunk)
                    progress(sent_bytes, filesize)

        # Thành công
        sha = compute_sha256(filepath)
        print_above(
            f"[file] File sent successfully: {filename} "
            f"({filesize} bytes, SHA256: {sha[:16]}...)"
        )
        return True

    except (ConnectionError, OSError, TimeoutError) as e:
        print_above(f"[!] Lỗi khi gửi file '{filename}': {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def start_send_file(
    peer_ip: str,
    peer_port: int,
    my_name: str,
    filepath: str,
    peer_name: str | None = None,
) -> threading.Thread:
    """
    Bắt đầu gửi file trong một thread riêng (không block luồng chat).
    """
    t = threading.Thread(
        target=send_file_to_peer,
        args=(peer_ip, peer_port, my_name, filepath, peer_name),
        daemon=True,
        name=f"file-send-{os.path.basename(filepath)}",
    )
    t.start()
    return t


# ---------------------------------------------------------------------------
# Nhận file (gọi bởi chat.py khi receiver phát hiện gói FILE)
# ---------------------------------------------------------------------------

def receive_file(
    conn: socket.socket,
    sender_name: str,
    download_dir: str | None = None,
) -> str | None:
    """
    Nhận file từ socket TCP (gọi khi đã đọc keyword 'FILE|' rồi).

    Luồng:
      1. Đọc tiếp header: <filename>|<filesize>|
      2. Lưu tạm vào downloads/<file>.part
      3. Đọc đúng filesize byte theo chunk
      4. Đủ → rename .part thành file chính thức
      5. Lỗi → xóa file .part
    Trả về đường dẫn file đã lưu nếu thành công, None nếu lỗi.
    """
    if download_dir is None:
        download_dir = DEFAULT_DOWNLOAD_DIR
    part_path = None
    try:
        # Đọc phần còn lại của header FILE
        raw_filename = protocol.read_token(conn, "|")
        size_str = protocol.read_token(conn, "|")

        try:
            filesize = int(size_str)
            if filesize < 0:
                raise ValueError()
        except ValueError:
            print_above(f"[!] Header file không hợp lệ từ {sender_name}: size={size_str!r}")
            return None

        # Chống Path Traversal trên mọi HĐH
        safe_filename = _sanitize_filename(raw_filename)

        os.makedirs(download_dir, exist_ok=True)
        final_path = _get_unique_filepath(download_dir, safe_filename)
        part_path = final_path + ".part"

        progress = _make_progress_callback(sender_name, safe_filename, "Receiving")

        print_above(
            f"[file] Receiving '{safe_filename}' from {sender_name} ({filesize} bytes)..."
        )

        received_bytes = 0
        if filesize == 0:
            with open(part_path, "wb"):
                pass
            print_above(f"[file] Receiving '{safe_filename}' from {sender_name}: 100% Done")
        else:
            with open(part_path, "wb") as f:
                while received_bytes < filesize:
                    to_read = min(CHUNK_SIZE, filesize - received_bytes)
                    chunk = conn.recv(to_read)
                    if not chunk:
                        raise ConnectionError(
                            "Connection lost while receiving file payload"
                        )
                    f.write(chunk)
                    received_bytes += len(chunk)
                    progress(received_bytes, filesize)

        # Đổi tên .part → file hoàn chỉnh
        os.replace(part_path, final_path)
        sha = compute_sha256(final_path)
        print_above(
            f"[file] File received: {safe_filename} -> {final_path} "
            f"({filesize} bytes, SHA256: {sha[:16]}...)"
        )
        part_path = None  # Đã rename thành công, không cần xóa .part
        return final_path

    except (ConnectionError, OSError, ValueError) as e:
        print_above(f"[!] Lỗi khi nhận file từ {sender_name}: {e}")
        return None
    finally:
        # Dọn file dở .part nếu chưa thành công
        if part_path and os.path.exists(part_path):
            try:
                os.remove(part_path)
                print_above(f"[file] Đã xóa file dở: {part_path}")
            except OSError:
                pass
