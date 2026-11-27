"""
chat.py – Khung TCP acceptor / receiver (Milestone 2, bản sơ bộ)

Milestone này chỉ cần:
  - Thread acceptor: lắng nghe kết nối TCP đến
  - Thread receiver: đọc dữ liệu thô từ mỗi kết nối và in ra

Chức năng gửi/nhận tin nhắn thật sự sẽ hoàn chỉnh ở Milestone 3.
"""

import socket
import threading

from protocol import read_frame
from ui import print_above


# ---------------------------------------------------------------------------
# Trạng thái nội bộ
# ---------------------------------------------------------------------------
_host: str = "0.0.0.0"
_port: int = 5000
_srv_sock: socket.socket | None = None


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

def _handle_connection(conn: socket.socket, addr: tuple) -> None:
    """Thread xử lý một kết nối TCP đến (receiver)."""
    tag = f"{addr[0]}:{addr[1]}"
    print_above(f"[chat] {tag} connected")
    try:
        while True:
            frame = read_frame(conn)
            if frame is None:
                break
            # Milestone 2: chỉ in dữ liệu thô — Milestone 3 sẽ hiện đúng UI
            print_above(f"[raw from {tag}] {frame!r}")
    except Exception as e:
        print_above(f"[chat] {tag} error: {e}")
    finally:
        conn.close()
        print_above(f"[chat] {tag} disconnected")


def _acceptor() -> None:
    """Thread nhận kết nối TCP đến."""
    global _srv_sock
    while True:
        try:
            conn, addr = _srv_sock.accept()
        except OSError:
            break                           # server socket đã đóng
        t = threading.Thread(
            target=_handle_connection,
            args=(conn, addr),
            daemon=True,
            name=f"receiver-{addr[1]}",
        )
        t.start()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start(host: str = "0.0.0.0", port: int = 5000) -> None:
    """
    Khởi động TCP acceptor trên host:port.
    Gọi một lần khi khởi động ứng dụng.
    """
    global _srv_sock, _host, _port
    _host = host
    _port = port

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen()
    srv.settimeout(1.0)
    _srv_sock = srv

    t = threading.Thread(target=_acceptor, daemon=True, name="tcp-acceptor")
    t.start()
    print_above(f"[chat] TCP acceptor listening on {host}:{port}")
