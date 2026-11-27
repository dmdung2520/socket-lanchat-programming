"""
ui.py – Giao diện terminal không bị vỡ dòng (Milestone 3)

Hàm print_above(text):
  In một dòng thông báo ngay TRÊN dòng đang gõ,
  nhờ prompt_toolkit's patch_stdout.

Một khóa (lock) bảo vệ việc in màn hình để nhiều thread không bao giờ in cùng lúc.
Nếu prompt_toolkit không có (môi trường tối giản), dùng fallback đơn giản.
"""

import sys
import threading

try:
    from prompt_toolkit import print_formatted_text as _pt_print
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.patch_stdout import patch_stdout as _patch_stdout
    _HAS_PROMPT_TOOLKIT = True
except ImportError:
    _HAS_PROMPT_TOOLKIT = False

# Lock đồng bộ in ấn màn hình giữa các receiver threads và main thread
_print_lock = threading.Lock()

# patch_stdout context manager được lưu để ui.py biết có đang chạy trong PT không
_in_pt_session = False
_pt_patch = None


def set_prompt_toolkit_session(active: bool, patch=None) -> None:
    """
    Gọi từ lanchat.py khi bắt đầu / kết thúc phiên prompt_toolkit.
    patch: đối tượng patch_stdout đang hoạt động (nếu có).
    """
    global _in_pt_session, _pt_patch
    _in_pt_session = active
    _pt_patch = patch


def print_above(text: str) -> None:
    """
    In text lên màn hình mà không làm vỡ dòng đang gõ.
    Được bảo vệ bởi _print_lock để an toàn đa luồng.
    Nếu đang trong phiên prompt_toolkit, dùng print_formatted_text.
    Nếu không, dùng ANSI escape (hoặc fallback đơn giản).
    """
    with _print_lock:
        if _HAS_PROMPT_TOOLKIT and _in_pt_session:
            try:
                _pt_print(ANSI(text))
                return
            except Exception:
                pass

        # Fallback: ghi trực tiếp ra stderr / stdout
        try:
            print(f"\r{text}", flush=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Standalone test (python src/ui.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import time

    if not _HAS_PROMPT_TOOLKIT:
        print("prompt_toolkit không cài. Chạy: pip install prompt_toolkit")
        sys.exit(1)

    from prompt_toolkit import PromptSession
    from prompt_toolkit.patch_stdout import patch_stdout

    session = PromptSession()

    def _fake_events():
        messages = [
            "[*] Minh is online",
            "[*] Lan went offline",
            "[*] Huy is online",
            "[*] Minh went offline",
        ]
        time.sleep(1.5)
        for msg in messages:
            print_above(msg)
            time.sleep(2)

    with patch_stdout():
        set_prompt_toolkit_session(True)
        t = threading.Thread(target=_fake_events, daemon=True)
        t.start()

        print("Nhập văn bản tùy ý. Thông báo sẽ xuất hiện phía trên dòng bạn đang gõ.")
        print("Ctrl+C để thoát.\n")
        try:
            while True:
                line = session.prompt("> ")
                if line.strip() in ("/quit", "/exit", ""):
                    break
                print(f"Bạn gõ: {line!r}")
        except (KeyboardInterrupt, EOFError):
            pass

    set_prompt_toolkit_session(False)
    print("bye")
