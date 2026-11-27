"""
lanchat.py – Entry point của ứng dụng LAN Chat (Milestone 3)

Lệnh hỗ trợ:
  /list            – Xem danh sách peer đang online
  /chat <tên|số>   – Mở hoặc chuyển cuộc chat tới peer
  /leave           – Rời khỏi cuộc chat hiện tại
  /status online   – Đổi trạng thái sang online
  /status away     – Đổi trạng thái sang away
  /help            – Hiện hướng dẫn
  /quit            – Thoát
  <văn bản>        – Gửi tin nhắn tới đối tác chat hiện tại

Cách chạy (từ thư mục gốc dự án):
  python src/lanchat.py --name Quan --port 5000
  python src/lanchat.py --name Minh --port 5001 --bcast 127.255.255.255
"""

import argparse
from collections import defaultdict
import os
import sys
import threading

# Thêm thư mục src vào sys.path để import được các module cùng cấp
sys.path.insert(0, os.path.dirname(__file__))

import chat
import discovery
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
        current = discovery._my_status
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
    else:
        # Nếu không tìm thấy qua discovery, kiểm tra peer đã kết nối TCP tới ta
        for name in chat.get_active_peers():
            if name.lower() == target.lower():
                peer_name = name
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


def cmd_help() -> None:
    ui.print_above("  Lệnh hỗ trợ:")
    ui.print_above("    /list              – Xem danh sách peer online")
    ui.print_above("    /chat <tên|số>     – Bắt đầu chat với một peer")
    ui.print_above("    /leave             – Rời khỏi cuộc chat hiện tại")
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


def run_loop_simple() -> None:
    """Vòng lặp fallback (không có prompt_toolkit)."""
    try:
        while True:
            try:
                line = input("> ")
            except EOFError:
                break
            if handle_line(line):
                break
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="LAN Chat – Milestone 3: Chat TCP",
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
    args = parse_args()

    # Validate tên trước khi khởi động
    if not args.name or "|" in args.name:
        ui.print_above(f"[!] Tên không hợp lệ: {args.name!r}  (không được rỗng hoặc chứa '|')")
        sys.exit(1)

    _my_name = args.name

    ui.print_above(f"[*] Khởi động LAN Chat | tên={args.name} | port={args.port} | bcast={args.bcast}")

    # Khởi động TCP acceptor và đăng ký callbacks
    chat.start(
        my_name=args.name,
        host=args.host,
        port=args.port,
        on_message=on_chat_message,
        on_disconnect=on_peer_disconnected,
        on_connect=on_peer_connected,
    )

    # Khởi động discovery (broadcaster + listener + reaper)
    discovery.start(
        name=args.name,
        tcp_port=args.port,
        bcast=args.bcast,
        on_event=ui.print_above,
    )

    ui.print_above("[*] Gõ /help để xem lệnh. Ctrl+C hoặc /quit để thoát.\n")

    try:
        if _HAS_PROMPT_TOOLKIT:
            run_loop_prompt_toolkit()
        else:
            ui.print_above("[!] prompt_toolkit không cài – dòng nhập có thể bị vỡ khi có thông báo.")
            ui.print_above("[!] Cài bằng: pip install prompt_toolkit\n")
            run_loop_simple()
    finally:
        chat.close_all()

    ui.print_above("\n[*] Tạm biệt!")


if __name__ == "__main__":
    main()
