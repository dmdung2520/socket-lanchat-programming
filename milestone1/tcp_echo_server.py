"""
TCP echo server: nhiều client cùng lúc, mỗi client một thread.

Chạy:   python tcp_echo_server.py --port 5000
Thử:    python tcp_echo_client.py --port 5000
        hoặc:  ncat 127.0.0.1 5000
"""
import argparse
import socket
import threading


def handle_client(conn, addr):
    tag = f"{addr[0]}:{addr[1]}"
    print(f"[+] {tag} connected")
    try:
        with conn:
            while True:
                data = conn.recv(1024)           # chặn đến khi có dữ liệu
                if not data:                      # b"" nghĩa là client đã đóng kết nối
                    break
                print(f"[{addr[1]}] recv {len(data)} bytes: {data!r}")
                conn.sendall(data)                # gửi lại nguyên văn (echo)
    except ConnectionError as e:                  # client sập hoặc bị reset
        print(f"[!] {tag} error: {e}")
    print(f"[-] {tag} disconnected")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")   # 0.0.0.0 = nhận từ mọi card mạng
    p.add_argument("--port", type=int, default=5000)
    a = p.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Cho phép chạy lại server ngay sau khi tắt (tránh "Address already in use")
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((a.host, a.port))
    srv.listen()
    srv.settimeout(1.0)       # để Ctrl+C hoạt động trên Windows (accept không chặn vô hạn)
    print(f"[*] Echo server listening on {a.host}:{a.port} (Ctrl+C to stop)")

    try:
        while True:
            try:
                conn, addr = srv.accept()         # trả về socket MỚI cho từng client
            except socket.timeout:
                continue
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        srv.close()


if __name__ == "__main__":
    main()
