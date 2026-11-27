"""
Thí nghiệm: TCP là dòng byte, KHÔNG có ranh giới tin nhắn.

Chạy một lệnh:  python tcp_stick_demo.py
Server và client chạy chung trong một file (127.0.0.1) để quan sát cho dễ.
"""
import socket
import threading
import time

HOST, PORT = "127.0.0.1", 5055


def server(ready):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen()
    ready.set()
    conn, _ = srv.accept()
    with conn:
        # Test 1: client gọi send() 3 lần, server chỉ recv() 1 lần
        time.sleep(0.5)                           # đợi client gửi xong cả 3 lần
        data = conn.recv(4096)
        print(f"[Test 1] client send() 3 times -> server recv() once got: {data!r}")

        # Test 2: client gọi send() 1 lần với 100000 byte, server recv(1024) nhiều lần
        total, calls = 0, 0
        while total < 100_000:
            chunk = conn.recv(min(1024, 100_000 - total))
            if not chunk:
                break
            total += len(chunk)
            calls += 1
        print(f"[Test 2] client send() once ({total} bytes) -> server needed {calls} recv() calls")

        # Test 3: độ dài tính bằng KÝ TỰ khác độ dài tính bằng BYTE
        data = conn.recv(1024)
        text = data.decode("utf-8")
        print(f"[Test 3] {text!r}: len(chars)={len(text)}  len(bytes)={len(data)}")
    srv.close()


def client():
    with socket.create_connection((HOST, PORT)) as s:
        for m in (b"AAAA", b"BBBB", b"CCCC"):
            s.sendall(m)
        time.sleep(1)
        s.sendall(b"x" * 100_000)
        time.sleep(0.5)
        s.sendall("Xin chào Việt Nam".encode("utf-8"))
        time.sleep(0.5)


if __name__ == "__main__":
    ready = threading.Event()
    t = threading.Thread(target=server, args=(ready,))
    t.start()
    ready.wait()
    client()
    t.join()
    print("\nConclusion: recv() does NOT return one message per send().")
    print("-> The protocol needs a header (MSG|<len>|...) and a recv_exact() loop.")
