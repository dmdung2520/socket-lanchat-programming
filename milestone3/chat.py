"""
chat.py – Quản lý kết nối TCP, Acceptor và Receiver threads (Milestone 3)

Chức năng:
  - Thread acceptor lắng nghe kết nối TCP đến, nhận frame HI và gán receiver thread.
  - Bảng `connections` lưu socket theo tên peer, được bảo vệ bởi lock.
  - Mỗi peer có một receiver thread đọc các frame MSG / BYE.
  - Phát hiện đóng kết nối sạch hoặc ngắt kết nối đột ngột (sập).
  - Xử lý quy tắc hai bên cùng lúc kết nối: giữ kết nối mới nhất, đóng kết nối cũ.
  - Các hàm public: start, open_chat, send_to, send, leave, close_all, is_connected.
"""

import socket
import threading
from typing import Callable

import protocol
from ui import print_above


# ---------------------------------------------------------------------------
# Trạng thái nội bộ
# ---------------------------------------------------------------------------
_connections_lock = threading.Lock()
# {peer_name: socket}
_connections: dict[str, socket.socket] = {}

_host: str = "0.0.0.0"
_port: int = 5000
_my_name: str = ""
_srv_sock: socket.socket | None = None
_running: bool = False

# Callbacks đăng ký từ lanchat.py
# on_message(sender_name: str, text: str)
_on_message: Callable[[str, str], None] | None = None
# on_disconnect(peer_name: str, reason: str)  # reason: "bye" | "lost"
_on_disconnect: Callable[[str, str], None] | None = None
# on_connect(peer_name: str)
_on_connect: Callable[[str], None] | None = None


# ---------------------------------------------------------------------------
# Helpers nội bộ
# ---------------------------------------------------------------------------

def _register_connection(peer_name: str, conn: socket.socket) -> socket.socket | None:
    """
    Lưu kết nối vào bảng _connections dưới lock.
    Nếu đã có kết nối cũ với peer này, đóng kết nối cũ (quy tắc: giữ kết nối mới nhất).
    Trả về old_conn nếu có để đóng ngoài lock.
    """
    with _connections_lock:
        old_conn = _connections.get(peer_name)
        _connections[peer_name] = conn

    if old_conn is not None and old_conn is not conn:
        try:
            old_conn.close()
        except Exception:
            pass
    return old_conn


def _unregister_connection(peer_name: str, conn: socket.socket) -> bool:
    """
    Xóa kết nối khỏi bảng nếu socket hiện tại vẫn là conn.
    Tránh trường hợp receiver thread cũ xóa mất kết nối mới hơn.
    """
    with _connections_lock:
        if _connections.get(peer_name) is conn:
            del _connections[peer_name]
            return True
        return False


def _get_connection(peer_name: str) -> socket.socket | None:
    """Lấy socket của peer dưới lock."""
    with _connections_lock:
        return _connections.get(peer_name)


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

def _receiver_loop(peer_name: str, conn: socket.socket) -> None:
    """
    Thread đọc các frame từ một peer đã xác thực HI.
    Chạy đến khi nhận BYE, EOF (đóng kết nối), hoặc lỗi mạng.
    """
    disconnect_reason = "lost"
    try:
        while _running:
            try:
                frame = protocol.read_frame(conn)
            except (ConnectionError, OSError):
                disconnect_reason = "lost"
                break
            except ValueError as e:
                # Frame sai định dạng hoặc tin quá lớn (> 1 MB) -> đóng kết nối
                print_above(f"[chat] Gói tin từ {peer_name} không hợp lệ: {e}")
                disconnect_reason = "lost"
                break

            if frame is None:
                # Đối tác đóng kết nối (EOF)
                disconnect_reason = "lost"
                break

            if frame.type == "BYE":
                disconnect_reason = "bye"
                break

            elif frame.type == "MSG":
                if _on_message:
                    try:
                        _on_message(peer_name, frame.payload)
                    except Exception as e:
                        print_above(f"[chat] Lỗi khi xử lý tin nhắn từ {peer_name}: {e}")
            else:
                # Bỏ qua hoặc xử lý các frame khác
                pass

    except Exception as e:
        disconnect_reason = "lost"
    finally:
        try:
            conn.close()
        except Exception:
            pass

        removed = _unregister_connection(peer_name, conn)
        # Chỉ thông báo disconnect nếu đây là kết nối hiện hành bị gỡ bỏ
        if removed and _running and _on_disconnect:
            try:
                _on_disconnect(peer_name, disconnect_reason)
            except Exception:
                pass


def _handle_incoming_connection(conn: socket.socket, addr: tuple) -> None:
    """
    Xử lý một kết nối TCP vừa được chấp nhận:
    1. Đọc frame đầu tiên (phải là HI|<name>|).
    2. Đăng ký vào bảng _connections.
    3. Khởi chạy receiver thread.
    """
    conn.settimeout(5.0)  # Chờ HI tối đa 5 giây
    try:
        frame = protocol.read_frame(conn)
        if frame is None or frame.type != "HI":
            # Không phải frame HI hợp lệ -> đóng kết nối
            conn.close()
            return
        peer_name = frame.payload.strip()
        if not peer_name or "|" in peer_name:
            conn.close()
            return

        # Đặt lại chế độ blocking bình thường
        conn.settimeout(None)

        _register_connection(peer_name, conn)

        if _on_connect:
            try:
                _on_connect(peer_name)
            except Exception:
                pass

        t = threading.Thread(
            target=_receiver_loop,
            args=(peer_name, conn),
            daemon=True,
            name=f"receiver-{peer_name}",
        )
        t.start()

    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def _acceptor() -> None:
    """Thread lắng nghe và chấp nhận các kết nối TCP đến."""
    global _srv_sock
    while _running:
        try:
            conn, addr = _srv_sock.accept()
        except (OSError, socket.timeout):
            if not _running:
                break
            continue

        t = threading.Thread(
            target=_handle_incoming_connection,
            args=(conn, addr),
            daemon=True,
            name=f"acceptor-{addr[0]}:{addr[1]}",
        )
        t.start()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start(
    my_name: str = "",
    host: str = "0.0.0.0",
    port: int = 5000,
    on_message: Callable[[str, str], None] | None = None,
    on_disconnect: Callable[[str, str], None] | None = None,
    on_connect: Callable[[str], None] | None = None,
) -> None:
    """
    Khởi động TCP acceptor trên host:port.
    Gọi khi khởi động ứng dụng.
    """
    global _srv_sock, _host, _port, _my_name, _running
    global _on_message, _on_disconnect, _on_connect

    _host = host
    _port = port
    _my_name = my_name
    _on_message = on_message
    _on_disconnect = on_disconnect
    _on_connect = on_connect
    _running = True

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    srv.bind((host, port))
    srv.listen(10)
    srv.settimeout(1.0)
    _srv_sock = srv

    t = threading.Thread(target=_acceptor, daemon=True, name="tcp-acceptor")
    t.start()


def set_my_name(name: str) -> None:
    """Cập nhật tên của mình."""
    global _my_name
    _my_name = name


def set_callbacks(
    on_message: Callable[[str, str], None] | None = None,
    on_disconnect: Callable[[str, str], None] | None = None,
    on_connect: Callable[[str], None] | None = None,
) -> None:
    """Cập nhật các hàm callback."""
    global _on_message, _on_disconnect, _on_connect
    if on_message is not None:
        _on_message = on_message
    if on_disconnect is not None:
        _on_disconnect = on_disconnect
    if on_connect is not None:
        _on_connect = on_connect


def open_chat(ip: str, port: int, peer_name: str) -> bool:
    """
    Chủ động mở kết nối TCP tới peer:
    1. socket.create_connection((ip, port), timeout=3).
    2. Gửi frame HI|<my_name>|.
    3. Đăng ký vào bảng _connections.
    4. Bật receiver thread.
    Trả về True nếu thành công, False nếu lỗi kết nối (không crash).
    """
    try:
        s = socket.create_connection((ip, port), timeout=3.0)
        # Bỏ timeout sau khi kết nối thành công để đọc blocking
        s.settimeout(None)

        # Gói đầu tiên sau khi kết nối: HI|<my_name>|
        protocol.send_hi(s, _my_name)

        _register_connection(peer_name, s)

        t = threading.Thread(
            target=_receiver_loop,
            args=(peer_name, s),
            daemon=True,
            name=f"receiver-{peer_name}",
        )
        t.start()
        return True

    except (ConnectionError, OSError, TimeoutError) as e:
        return False


def send_to(peer_name: str, text: str) -> bool:
    """
    Gửi tin nhắn MSG tới peer_name.
    Trả về True nếu gửi thành công, False nếu lỗi mạng.
    """
    conn = _get_connection(peer_name)
    if conn is None:
        return False

    try:
        protocol.send_msg(conn, text)
        return True
    except (ConnectionError, OSError, ValueError) as e:
        # Đóng kết nối hỏng
        try:
            conn.close()
        except Exception:
            pass
        _unregister_connection(peer_name, conn)
        return False


def send(text: str, peer_name: str) -> bool:
    """Alias cho send_to để tương thích giao diện."""
    return send_to(peer_name, text)


def leave(peer_name: str) -> None:
    """
    Rời khỏi cuộc chat với peer_name:
    Gửi frame BYE|, đóng socket và gỡ khỏi danh sách _connections.
    """
    conn = _get_connection(peer_name)
    if conn is None:
        return

    try:
        protocol.send_bye(conn)
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
        _unregister_connection(peer_name, conn)


def is_connected(peer_name: str) -> bool:
    """Kiểm tra xem hiện có kết nối hoạt động với peer_name không."""
    with _connections_lock:
        return peer_name in _connections


def get_active_peers() -> list[str]:
    """Trả về danh sách tên các peer hiện đang có kết nối TCP mở."""
    with _connections_lock:
        return list(_connections.keys())


def close_all() -> None:
    """Đóng tất cả kết nối TCP và dừng acceptor."""
    global _running, _srv_sock
    _running = False

    with _connections_lock:
        conns = list(_connections.items())
        _connections.clear()

    for name, conn in conns:
        try:
            protocol.send_bye(conn)
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    if _srv_sock:
        try:
            _srv_sock.close()
        except Exception:
            pass
        _srv_sock = None
