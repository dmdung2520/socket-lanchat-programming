"""
UDP echo (unicast), dùng để so sánh với TCP: không có connect/accept, mỗi gói là một datagram.

    python udp_echo.py server --port 6000
    python udp_echo.py client --host 127.0.0.1 --port 6000
"""
import argparse
import socket


def server(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", port))
    s.settimeout(1.0)                             # để Ctrl+C hoạt động trên Windows
    print(f"[*] UDP echo server on port {port} (Ctrl+C to stop)")
    while True:
        try:
            data, addr = s.recvfrom(2048)         # mỗi lần gọi = đúng 1 datagram
        except socket.timeout:
            continue
        print(f"recv {len(data)} bytes from {addr[0]}:{addr[1]}: {data!r}")
        s.sendto(data, addr)                      # trả lời đúng địa chỉ vừa gửi tới


def client(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2)
    print(f"[*] Sending to {host}:{port}. Empty line to quit.")
    while True:
        line = input("> ")
        if not line:
            break
        s.sendto(line.encode("utf-8"), (host, port))   # không cần connect()
        try:
            data, _ = s.recvfrom(2048)
            print("echo:", data.decode("utf-8", errors="replace"))
        except socket.timeout:
            print("[!] No reply (server down or packet lost). UDP does not tell you.")
        except ConnectionResetError:
            # Windows: ICMP "port unreachable" hiện ra thành lỗi 10054 ở lần recvfrom kế tiếp
            print("[!] Connection reset (WinError 10054): nobody listens on that port.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("role", choices=["server", "client"])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=6000)
    a = p.parse_args()
    try:
        server(a.port) if a.role == "server" else client(a.host, a.port)
    except (KeyboardInterrupt, EOFError):
        print("\nbye")
