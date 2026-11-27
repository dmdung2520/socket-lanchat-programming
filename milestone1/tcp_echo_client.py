"""
TCP echo client.

Chạy:   python tcp_echo_client.py --host 127.0.0.1 --port 5000
Gõ chữ rồi Enter để gửi; Enter dòng trống hoặc Ctrl+C để thoát.
"""
import argparse
import socket


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    a = p.parse_args()

    try:
        s = socket.create_connection((a.host, a.port), timeout=3)
    except OSError as e:                          # server chưa chạy, sai IP, bị firewall chặn...
        print(f"[!] Cannot connect to {a.host}:{a.port}: {e}")
        return
    s.settimeout(None)
    print(f"[*] Connected to {a.host}:{a.port}. Empty line or Ctrl+C to quit.")

    try:
        with s:
            while True:
                line = input("> ")
                if not line:
                    break
                s.sendall(line.encode("utf-8"))   # gửi BYTE, không gửi str
                data = s.recv(1024)
                if not data:
                    print("[!] Server closed the connection")
                    break
                print("echo:", data.decode("utf-8", errors="replace"))
    except (KeyboardInterrupt, EOFError):
        print()
    except ConnectionError as e:
        print(f"[!] Connection lost: {e}")


if __name__ == "__main__":
    main()
