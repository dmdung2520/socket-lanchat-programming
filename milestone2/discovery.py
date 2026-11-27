"""
discovery.py – Peer Discovery qua UDP broadcast (Milestone 2)

Giao thức: HELLO|<name>|<tcp_port>|<status>  trên UDP port 9999
  - Broadcaster gửi mỗi 3 giây
  - Listener cập nhật bảng peers
  - Reaper xóa peer im lặng > 10 giây và thông báo offline
"""

import socket
import threading
import time
from typing import NamedTuple

DISCOVERY_PORT = 9999
BROADCAST_INTERVAL = 3      # giây
PEER_TIMEOUT = 10           # giây – peer im lặng bao lâu thì coi là offline

VALID_STATUSES = {"online", "away"}


class Peer(NamedTuple):
    name: str
    ip: str
    tcp_port: int
    status: str


# ---------------------------------------------------------------------------
# Trạng thái nội bộ (module-level singletons)
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_peers: dict[tuple[str, int], dict] = {}   # (ip, tcp_port) -> {name, status, last_seen}

_my_name: str = ""
_my_port: int = 0
_my_status: str = "online"
_bcast_addr: str = "255.255.255.255"

_sock: socket.socket | None = None          # socket UDP dùng chung cho cả gửi và nhận
_on_event = None                            # callback(msg: str) khi có sự kiện


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hello() -> bytes:
    return f"HELLO|{_my_name}|{_my_port}|{_my_status}".encode("utf-8")


def _is_mine(name: str, tcp_port: int) -> bool:
    """Trả True nếu gói này là của chính mình (tránh echo)."""
    return name == _my_name and tcp_port == _my_port


def _validate_packet(raw: str) -> tuple[str, int, str] | None:
    """
    Kiểm tra định dạng gói HELLO.
    Trả về (name, tcp_port, status) nếu hợp lệ, None nếu không.
    """
    parts = raw.strip().split("|")
    if len(parts) != 4:
        return None
    keyword, name, port_str, status = parts
    if keyword != "HELLO":
        return None
    if not name or "|" in name:
        return None
    if status not in VALID_STATUSES:
        return None
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            return None
    except ValueError:
        return None
    return name, port, status


def _notify(msg: str) -> None:
    """Gọi callback sự kiện (nếu có) NGOÀI lock."""
    if _on_event:
        try:
            _on_event(msg)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

def _broadcaster() -> None:
    """Thread gửi HELLO mỗi 3 giây."""
    while True:
        try:
            msg = _make_hello()
            _sock.sendto(msg, (_bcast_addr, DISCOVERY_PORT))
        except Exception:
            pass
        time.sleep(BROADCAST_INTERVAL)


def _listener() -> None:
    """Thread nhận gói UDP, kiểm tra, cập nhật bảng peers."""
    while True:
        try:
            data, addr = _sock.recvfrom(2048)
        except Exception:
            continue

        raw = data.decode("utf-8", errors="replace")
        parsed = _validate_packet(raw)
        if parsed is None:
            continue                        # gói rác – bỏ qua

        name, tcp_port, status = parsed
        ip = addr[0]

        if _is_mine(name, tcp_port):
            continue                        # gói của chính mình

        key = (ip, tcp_port)
        now = time.monotonic()

        with _lock:
            is_new = key not in _peers
            _peers[key] = {
                "name": name,
                "status": status,
                "last_seen": now,
            }
            notify_msg = f"[*] {name} is online" if is_new else None

        if notify_msg:
            _notify(notify_msg)


def _reaper() -> None:
    """Thread kiểm tra mỗi giây, xóa peer im lặng > PEER_TIMEOUT giây."""
    while True:
        time.sleep(1)
        now = time.monotonic()
        expired = []

        with _lock:
            for key, info in list(_peers.items()):
                if now - info["last_seen"] > PEER_TIMEOUT:
                    expired.append((key, info["name"]))
                    del _peers[key]

        for _, name in expired:
            _notify(f"[*] {name} went offline")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start(name: str, tcp_port: int, bcast: str = "255.255.255.255",
          on_event=None) -> None:
    """
    Khởi động discovery: broadcaster, listener, reaper.
    Phải gọi trước khi dùng bất kỳ hàm nào khác.

    on_event(msg: str) được gọi khi có peer mới online / offline.
    """
    global _my_name, _my_port, _bcast_addr, _sock, _on_event, _my_status

    # Validate tên
    if not name or "|" in name:
        raise ValueError(f"Tên không hợp lệ: {name!r}  (không được rỗng hoặc chứa '|')")

    _my_name = name
    _my_port = tcp_port
    _bcast_addr = bcast
    _my_status = "online"
    _on_event = on_event

    # Tạo UDP socket dùng chung
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.bind(("", DISCOVERY_PORT))
    _sock = s

    for target in (_broadcaster, _listener, _reaper):
        t = threading.Thread(target=target, daemon=True, name=target.__name__)
        t.start()


def get_peers() -> list[Peer]:
    """Trả danh sách peer hiện tại, sắp xếp ổn định (tên rồi tcp_port)."""
    with _lock:
        snapshot = list(_peers.items())
    snapshot.sort(key=lambda item: (item[1]["name"].lower(), item[0][1]))
    return [
        Peer(name=info["name"], ip=ip, tcp_port=port, status=info["status"])
        for (ip, port), info in snapshot
    ]


def set_status(new_status: str) -> None:
    """Đổi trạng thái và broadcast ngay (không chờ 3 giây)."""
    global _my_status
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Trạng thái phải là 'online' hoặc 'away', không phải {new_status!r}")
    _my_status = new_status
    if _sock:
        try:
            _sock.sendto(_make_hello(), (_bcast_addr, DISCOVERY_PORT))
        except Exception:
            pass


def find_peer(name_or_number: str) -> Peer | None:
    """
    Tìm peer theo tên (khớp chính xác, case-insensitive)
    hoặc theo số thứ tự trong /list (bắt đầu từ 1).
    """
    peers = get_peers()
    # Thử parse số thứ tự
    try:
        idx = int(name_or_number) - 1
        if 0 <= idx < len(peers):
            return peers[idx]
        return None
    except ValueError:
        pass
    # Tìm theo tên
    target = name_or_number.lower()
    for p in peers:
        if p.name.lower() == target:
            return p
    return None
