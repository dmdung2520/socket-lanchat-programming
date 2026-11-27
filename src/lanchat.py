"""
lanchat.py – Entry point của ứng dụng LAN Chat (Milestone 4)

Lệnh hỗ trợ:
  /list            – Xem danh sách peer đang online
  /chat <tên|số>   – Mở hoặc chuyển cuộc chat tới peer
  /leave           – Rời khỏi cuộc chat hiện tại
  /send <file>     – Gửi file cho đối tác đang chat
  /status online   – Đổi trạng thái sang online
  /status away     – Đổi trạng thái sang away
  /help            – Hiện hướng dẫn
  /quit            – Thoát
  <văn bản>        – Gửi tin nhắn tới đối tác chat hiện tại

Cách chạy (từ thư mục gốc dự án):
  python src/lanchat.py --name <name> --port 5000
  python src/lanchat.py --name <name> --port 5001 --bcast 127.255.255.255
"""

import argparse
from collections import defaultdict
import os
import socket
import sys
import threading

# Thêm thư mục src vào sys.path để import được các module cùng cấp
sys.path.insert(0, os.path.dirname(__file__))

import chat
import discovery
import filetransfer
import protocol
import ui

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.patch_stdout import patch_stdout
    _HAS_PROMPT_TOOLKIT = True
except ImportError:
    _HAS_PROMPT_TOOLKIT = False


# ---------------------------------------------------------------------------
# Trạng thái chat & khóa đồng bộ
# ---------------------------------------------------------------------------
_chat_lock = threading.Lock()
_my_name: str = ""
_current_partner: str | None = None
_unread: dict[str, int] = defaultdict(int)
_history: dict[str, list[tuple[str, str]]] = defaultdict(list)
_peer_addrs: dict[str, tuple[str, int]] = {}  # Cache (ip, tcp_port) theo tên peer


# ---------------------------------------------------------------------------
# Callbacks nhận sự kiện từ chat layer
# ---------------------------------------------------------------------------

def on_chat_message(sender_name: str, text: str) -> None:
    """Xử lý khi có tin nhắn chat đến từ sender_name."""
    with _chat_lock:
        is_current = (_current_partner == sender_name)
        _history[sender_name].append((sender_name, text))
        unread_count = 0
        if not is_current:
            _unread[sender_name] += 1
            unread_count = _unread[sender_name]

    # In ra ngoài lock để tránh deadlock với UI
    if is_current:
        ui.print_above(f"[{sender_name}] {text}")
    else:
        ui.print_above(f"[*] New message from {sender_name} ({unread_count} unread)")


def on_peer_disconnected(peer_name: str, reason: str) -> None:
    """Xử lý khi một peer đóng kết nối hoặc bị ngắt đột ngột."""
    global _current_partner
    with _chat_lock:
        was_current = (_current_partner == peer_name)
        if was_current:
            _current_partner = None

    # In ra ngoài lock
    if reason == "bye":
        ui.print_above(f"[*] {peer_name} left the chat")
    else:
        ui.print_above(f"[*] Connection lost with {peer_name}")


def on_peer_connected(peer_name: str) -> None:
    """Xử lý khi có peer mới kết nối TCP tới mình."""
    pass


# ---------------------------------------------------------------------------
# Xử lý lệnh
# ---------------------------------------------------------------------------

def cmd_list() -> None:
    peers = discovery.get_peers()
    if not peers:
        ui.print_above("  (Không có ai online)")
        return
    with _chat_lock:
        unread_copy = dict(_unread)
    for i, p in enumerate(peers, 1):
        unreads = unread_copy.get(p.name, 0)
        unread_str = f" ({unreads} unread)" if unreads > 0 else ""
        ui.print_above(f"  {i:2}. {p.name} ({p.ip}:{p.tcp_port}) {p.status}{unread_str}")


def cmd_status(args: list[str]) -> None:
    if not args:
        current = discovery.get_status()
        ui.print_above(f"  Trạng thái hiện tại: {current}. Dùng: /status online|away")
        return
    new_status = args[0].lower()
    try:
        discovery.set_status(new_status)
        ui.print_above(f"  Trạng thái đã đổi thành: {new_status}")
    except ValueError as e:
        ui.print_above(f"  Lỗi: {e}")


def cmd_chat(args: list[str]) -> None:
    global _current_partner
    if not args:
        ui.print_above("  Cách dùng: /chat <tên|số>")
        return

    target = args[0]
    peer = discovery.find_peer(target)

    peer_name = None
    ip = None
    port = None

    if peer is not None:
        peer_name = peer.name
        ip = peer.ip
        port = peer.tcp_port
        with _chat_lock:
            _peer_addrs[peer_name] = (ip, port)
    else:
        # Nếu không tìm thấy qua discovery, kiểm tra peer đã kết nối TCP tới ta
        for name in chat.get_active_peers():
            if name.lower() == target.lower():
                peer_name = name
                with _chat_lock:
                    cached = _peer_addrs.get(peer_name)
                if cached:
                    ip, port = cached
                break

    if peer_name is None:
        ui.print_above(f"  Không tìm thấy peer: {target!r}. Gõ /list để xem danh sách.")
        return

    if peer_name == _my_name:
        ui.print_above("  Không thể tự chat với chính mình.")
        return

    with _chat_lock:
        if _current_partner == peer_name:
            ui.print_above(f"  Đang trong cuộc chat với {peer_name}.")
            return

    # Nếu chưa có kết nối TCP tới peer này, chủ động kết nối
    if not chat.is_connected(peer_name):
        if ip is None or port is None:
            ui.print_above(f"[!] Không có thông tin IP/cổng của {peer_name} để kết nối.")
            return
        ui.print_above(f"[*] Đang kết nối tới {peer_name} ({ip}:{port})...")
        ok = chat.open_chat(ip, port, peer_name)
        if not ok:
            ui.print_above(f"[!] Không thể kết nối tới {peer_name}.")
            return

    # Chuyển partner và đọc tin nhắn chưa đọc
    unread_msgs = []
    unread_count = 0
    with _chat_lock:
        _current_partner = peer_name
        unread_count = _unread.get(peer_name, 0)
        if unread_count > 0:
            unread_msgs = _history.get(peer_name, [])[-unread_count:]
            _unread[peer_name] = 0

    if unread_count > 0:
        ui.print_above(f"[*] Switched to {peer_name}, {unread_count} unread:")
        for sender, msg in unread_msgs:
            ui.print_above(f"[{sender}] {msg}")
    else:
        ui.print_above(f"[*] Switched to {peer_name}. Gõ tin nhắn để chat, /leave để rời cuộc chat.")


def cmd_leave() -> None:
    global _current_partner
    with _chat_lock:
        partner = _current_partner
        _current_partner = None

    if partner is None:
        ui.print_above("  Bạn chưa tham gia cuộc chat nào.")
        return

    chat.leave(partner)
    ui.print_above(f"[*] Left chat with {partner}.")


def _strip_outer_quotes(path_str: str) -> str:
    """Loại bỏ cặp dấu ngoặc kép/đơn bọc ngoài đường dẫn (trên Windows)."""
    s = path_str.strip()
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    return s


def cmd_send(args: list[str]) -> None:
    """
    /send <đường dẫn file> – Gửi file cho đối tác đang chat.
    Mỗi lần gửi mở kết nối TCP riêng, chạy trong thread riêng.
    Chat vẫn chạy bình thường trong lúc truyền file.
    """
    if not args:
        ui.print_above("  Cách dùng: /send <đường dẫn file>")
        return

    # Cho phép đường dẫn có khoảng trắng hoặc bọc dấu ngoặc kép
    filepath = _strip_outer_quotes(" ".join(args))

    # Kiểm tra đang chat với ai
    with _chat_lock:
        partner = _current_partner

    if partner is None:
        ui.print_above("  Chưa chọn người chat. Dùng: /chat <tên|số> trước khi gửi file.")
        return

    # Kiểm tra file tồn tại trước khi bật thread
    if not os.path.isfile(filepath):
        ui.print_above(f"[!] File không tồn tại: {filepath}")
        return

    filename = os.path.basename(filepath)
    if "|" in filename:
        ui.print_above(f"[!] Tên file không được chứa '|': {filename}")
        return

    # Tìm thông tin peer (ưu tiên discovery mới nhất, fallback cache)
    peer = discovery.find_peer(partner)
    if peer is not None:
        peer_ip = peer.ip
        peer_port = peer.tcp_port
        with _chat_lock:
            _peer_addrs[partner] = (peer_ip, peer_port)
    else:
        with _chat_lock:
            cached = _peer_addrs.get(partner)
        if cached is not None:
            peer_ip, peer_port = cached
        else:
            ui.print_above(f"[!] Không tìm thấy thông tin mạng của {partner}.")
            return

    filesize = os.path.getsize(filepath)

    ui.print_above(
        f"[file] Bắt đầu gửi '{filename}' ({filesize} bytes) tới {partner}..."
    )

    # Gửi file trong thread riêng (không block luồng chat)
    filetransfer.start_send_file(
        peer_ip=peer_ip,
        peer_port=peer_port,
        my_name=_my_name,
        filepath=filepath,
        peer_name=partner,
    )


def cmd_help() -> None:
    ui.print_above("  Lệnh hỗ trợ:")
    ui.print_above("    /list              – Xem danh sách peer online")
    ui.print_above("    /chat <tên|số>     – Bắt đầu chat với một peer")
    ui.print_above("    /leave             – Rời khỏi cuộc chat hiện tại")
    ui.print_above("    /send <file>       – Gửi file cho đối tác đang chat")
    ui.print_above("    /status online     – Đổi trạng thái sang online")
    ui.print_above("    /status away       – Đổi trạng thái sang away")
    ui.print_above("    /help              – Hiện hướng dẫn này")
    ui.print_above("    /quit              – Thoát")


def send_chat_message(line: str) -> None:
    """Gửi một dòng tin nhắn thường tới đối tác chat hiện tại."""
    global _current_partner
    text = line.strip()
    if not text:
        return  # TC-3.05: Tin rỗng (chỉ Enter) bỏ qua, không gửi

    if len(text.encode("utf-8")) > protocol.MAX_MSG_SIZE:
        ui.print_above(
            f"[!] Tin nhắn vượt quá giới hạn tối đa ({protocol.MAX_MSG_SIZE} bytes)."
        )
        return

    with _chat_lock:
        partner = _current_partner

    if partner is None:
        ui.print_above("  Chưa chọn người chat. Dùng: /chat <tên|số>")
        return

    ok = chat.send_to(partner, text)
    if ok:
        with _chat_lock:
            _history[partner].append((_my_name, text))
        ui.print_above(f"[{_my_name}] {text}")
    else:
        ui.print_above(f"[!] Gửi tin thất bại: mất kết nối tới {partner}")
        with _chat_lock:
            if _current_partner == partner:
                _current_partner = None


def handle_line(line: str) -> bool:
    """
    Xử lý một dòng nhập từ người dùng.
    Trả True nếu người dùng muốn thoát.
    """
    trimmed = line.strip()
    if not trimmed:
        return False

    if trimmed.startswith("/"):
        parts = trimmed.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/list":
            cmd_list()
        elif cmd == "/status":
            cmd_status(args)
        elif cmd == "/chat":
            cmd_chat(args)
        elif cmd == "/leave":
            cmd_leave()
        elif cmd == "/send":
            cmd_send(args)
        elif cmd in ("/help", "/?"):
            cmd_help()
        elif cmd in ("/quit", "/exit", "/q"):
            return True
        else:
            ui.print_above(f"  Lệnh không rõ: {cmd!r}. Gõ /help để xem hướng dẫn.")
        return False
    else:
        # Văn bản thường -> gửi tin nhắn chat
        send_chat_message(line)
        return False


# ---------------------------------------------------------------------------
# Vòng lặp chính
# ---------------------------------------------------------------------------

def run_loop_prompt_toolkit() -> None:
    """Vòng lặp dùng prompt_toolkit (không vỡ dòng khi có thông báo)."""
    session = PromptSession()
    with patch_stdout():
        ui.set_prompt_toolkit_session(True)
        try:
            while True:
                try:
                    line = session.prompt("> ")
                except (EOFError, KeyboardInterrupt):
                    break
                if handle_line(line):
                    break
        finally:
            ui.set_prompt_toolkit_session(False)


# ---------------------------------------------------------------------------
# Validation đầu vào
# ---------------------------------------------------------------------------

def _validate_name(name: str) -> None:
    """Kiểm tra tên hợp lệ trước khi khởi động."""
    if not name or not name.strip():
        print("[!] Tên không được để trống.", file=sys.stderr)
        sys.exit(1)
    if "|" in name:
        print(f"[!] Tên không được chứa ký tự '|': {name!r}", file=sys.stderr)
        sys.exit(1)


def _check_port_available(host: str, port: int) -> None:
    """Kiểm tra cổng TCP có bận không trước khi khởi động."""
    if not (1 <= port <= 65535):
        print(f"[!] Cổng TCP không hợp lệ: {port} (phải từ 1 đến 65535)", file=sys.stderr)
        sys.exit(1)
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        test_sock.bind((host, port))
    except OSError as e:
        print(f"[!] Cổng TCP {port} đã bận: {e}", file=sys.stderr)
        print(f"[!] Hãy chọn cổng khác bằng --port <số>", file=sys.stderr)
        sys.exit(1)
    finally:
        test_sock.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="LAN Chat – Milestone 4: Giao diện gõ-khi-nhận và truyền file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python src/lanchat.py --name Quan --port 5000
  python src/lanchat.py --name Minh --port 5001 --bcast 127.255.255.255
        """,
    )
    p.add_argument("--name", required=True,
                   help="Tên hiển thị (không được rỗng hoặc chứa '|')")
    p.add_argument("--port", type=int, default=5000,
                   help="Cổng TCP lắng nghe (mặc định: 5000)")
    p.add_argument("--host", default="0.0.0.0",
                   help="Địa chỉ bind TCP (mặc định: 0.0.0.0)")
    p.add_argument("--bcast", default="255.255.255.255",
                   help="Địa chỉ broadcast UDP (mặc định: 255.255.255.255)")
    return p.parse_args()


def main():
    global _my_name

    # Kiểm tra prompt_toolkit trước khi khởi động chương trình
    if not _HAS_PROMPT_TOOLKIT:
        print("[ERROR] Missing prompt_toolkit.")
        print("[ERROR] Run: pip install -r requirements.txt")
        sys.exit(1)

    args = parse_args()

    # Validate đầu vào (tên rỗng/chứa '|', cổng bận)
    _validate_name(args.name)
    _check_port_available(args.host, args.port)

    _my_name = args.name

    # Tạo thư mục downloads nếu chưa có
    os.makedirs("downloads", exist_ok=True)

    ui.print_above(
        f"[*] Khởi động LAN Chat | tên={args.name} | "
        f"port={args.port} | bcast={args.bcast}"
    )

    # Khởi động TCP acceptor và đăng ký callbacks
    try:
        chat.start(
            my_name=args.name,
            host=args.host,
            port=args.port,
            on_message=on_chat_message,
            on_disconnect=on_peer_disconnected,
            on_connect=on_peer_connected,
        )
    except OSError as e:
        print(f"[!] Không thể mở cổng TCP {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    # Khởi động discovery
    try:
        discovery.start(
            name=args.name,
            tcp_port=args.port,
            bcast=args.bcast,
            on_event=ui.print_above,
        )
    except OSError as e:
        chat.close_all()
        print(f"[!] Không thể mở cổng UDP {discovery.DISCOVERY_PORT}: {e}", file=sys.stderr)
        sys.exit(1)

    ui.print_above("[*] Gõ /help để xem lệnh. Ctrl+C hoặc /quit để thoát.\n")

    try:
        run_loop_prompt_toolkit()
    finally:
        discovery.stop()
        chat.close_all()

    ui.print_above("\n[*] Tạm biệt!")


if __name__ == "__main__":
    main()
