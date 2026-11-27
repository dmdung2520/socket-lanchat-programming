"""
lanchat.py – Entry point của ứng dụng LAN Chat (Milestone 2)

Lệnh hỗ trợ:
  /list            – Xem danh sách peer đang online
  /status online   – Đổi trạng thái sang online
  /status away     – Đổi trạng thái sang away
  /help            – Hiện hướng dẫn
  /quit            – Thoát

Cách chạy (từ thư mục gốc dự án):
  python src/lanchat.py --name <name> --port 5000
  python src/lanchat.py --name <name> --port 5001 --bcast 127.255.255.255
"""

import argparse
import sys
import os

# Thêm thư mục src vào sys.path để import được các module cùng cấp
sys.path.insert(0, os.path.dirname(__file__))

import discovery
import chat
import ui

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.patch_stdout import patch_stdout
    _HAS_PROMPT_TOOLKIT = True
except ImportError:
    _HAS_PROMPT_TOOLKIT = False


# ---------------------------------------------------------------------------
# Xử lý lệnh
# ---------------------------------------------------------------------------

def cmd_list() -> None:
    peers = discovery.get_peers()
    if not peers:
        ui.print_above("  (Không có ai online)")
        return
    for i, p in enumerate(peers, 1):
        ui.print_above(f"  {i:2}. {p.name} ({p.ip}) {p.status}")


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


def cmd_help() -> None:
    ui.print_above("  Lệnh hỗ trợ:")
    ui.print_above("    /list              – Xem danh sách peer online")
    ui.print_above("    /status online     – Đổi trạng thái sang online")
    ui.print_above("    /status away       – Đổi trạng thái sang away")
    ui.print_above("    /help              – Hiện hướng dẫn này")
    ui.print_above("    /quit              – Thoát")


def handle_command(line: str) -> bool:
    """
    Xử lý một dòng lệnh.
    Trả True nếu muốn thoát.
    """
    parts = line.strip().split()
    if not parts:
        return False
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "/list":
        cmd_list()
    elif cmd == "/status":
        cmd_status(args)
    elif cmd in ("/help", "/?"):
        cmd_help()
    elif cmd in ("/quit", "/exit", "/q"):
        return True
    else:
        ui.print_above(f"  Lệnh không rõ: {cmd!r}. Gõ /help để xem hướng dẫn.")
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
                if handle_command(line):
                    break
        finally:
            ui.set_prompt_toolkit_session(False)



# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="LAN Chat – Milestone 2: Peer Discovery",
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
    args = parse_args()

    # Validate tên trước khi khởi động
    if not args.name or "|" in args.name:
        print(f"[!] Tên không hợp lệ: {args.name!r}  (không được rỗng hoặc chứa '|')",
              file=sys.stderr)
        sys.exit(1)

    print(f"[*] Khởi động LAN Chat | tên={args.name} | port={args.port} | bcast={args.bcast}")

    if not _HAS_PROMPT_TOOLKIT:
        print("[ERROR] Missing prompt_toolkit.")
        print("[ERROR] Run: pip install -r requirements.txt")
        sys.exit(1)
    
        
    # Khởi động TCP acceptor (chat.py)
    chat.start(host=args.host, port=args.port)

    # Khởi động discovery (broadcaster + listener + reaper)
    discovery.start(
        name=args.name,
        tcp_port=args.port,
        bcast=args.bcast,
        on_event=ui.print_above,
    )

    print(f"[*] Gõ /help để xem lệnh. Ctrl+C hoặc /quit để thoát.\n")

    run_loop_prompt_toolkit()
    
    print("\n[*] Tạm biệt!")


if __name__ == "__main__":
    main()
