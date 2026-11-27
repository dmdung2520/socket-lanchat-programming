"""
Smoke test tự động cho Milestone 1 (chạy trên MỘT máy, chỉ dùng thư viện chuẩn).

    python smoke_test.py
    python smoke_test.py --bcast 192.168.1.255     # thử broadcast thật thay vì loopback

Kiểm tra:
  - TCP echo: 1 client, tiếng Việt, 2 client xen kẽ, đóng/mở lại, connect khi server tắt
  - Thí nghiệm "dính gói" (tcp_stick_demo.py)
  - UDP echo: mỗi datagram trả về riêng; gửi tới cổng không ai nghe
  - UDP broadcast: 2 listener cùng nhận 1 gói từ sender

Phần cần 2 máy thật và Wireshark vẫn phải kiểm thử thủ công (xem README).
Lần đầu chạy, Windows có thể hiện hộp thoại Firewall: chọn Allow access (mạng Private).
"""
import argparse
import os
import re
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ENV = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
results = []


def check(name, ok, detail="", warn_only=False):
    status = "PASS" if ok else ("WARN" if warn_only else "FAIL")
    results.append(status)
    print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""))
    return ok


def free_port(kind):
    with socket.socket(socket.AF_INET, kind) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(script, *args):
    return subprocess.Popen([PY, os.path.join(HERE, script), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=ENV)


def stop(proc):
    proc.terminate()
    try:
        out = proc.communicate(timeout=5)[0]
    except subprocess.TimeoutExpired:
        proc.kill()
        out = proc.communicate()[0]
    return out.decode("utf-8", errors="replace")


def wait_tcp(port, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return True
        except OSError:
            time.sleep(0.2)
    return False


def recv_n(sock, n):
    """Đọc đúng n byte (hoặc ít hơn nếu hết thời gian), đây chính là recv_exact."""
    sock.settimeout(3)
    buf = b""
    try:
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                break
            buf += chunk
    except socket.timeout:
        pass
    return buf


def test_tcp_echo():
    print("\n--- TCP echo ---")
    port = free_port(socket.SOCK_STREAM)
    srv = start("tcp_echo_server.py", "--port", str(port))
    log = ""
    try:
        if not check("Server TCP khởi động", wait_tcp(port), f"cổng {port}"):
            return
        with socket.create_connection(("127.0.0.1", port), timeout=3) as c:
            c.sendall(b"hello")
            check("T1  echo 'hello'", recv_n(c, 5) == b"hello")

            text = "xin chào"
            data = text.encode("utf-8")
            c.sendall(data)
            check("T2  echo tiếng Việt", recv_n(c, len(data)) == data,
                  f"{len(text)} ký tự = {len(data)} byte")

        a = socket.create_connection(("127.0.0.1", port), timeout=3)
        b = socket.create_connection(("127.0.0.1", port), timeout=3)
        a.sendall(b"from-A")
        b.sendall(b"from-B")
        ok = recv_n(a, 6) == b"from-A" and recv_n(b, 6) == b"from-B"
        check("T3  hai client cùng lúc, mỗi client nhận đúng echo của mình", ok)

        a.close()
        time.sleep(0.3)
        b.sendall(b"still-alive")
        check("T4a đóng client A, client B vẫn dùng được", recv_n(b, 11) == b"still-alive")
        b.close()
        with socket.create_connection(("127.0.0.1", port), timeout=3) as c:
            c.sendall(b"again")
            check("T4b server vẫn phục vụ client mới sau khi các client cũ đóng",
                  recv_n(c, 5) == b"again" and srv.poll() is None)
    finally:
        log = stop(srv)

    try:
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
        refused = False
    except OSError:
        refused = True
    check("T5  connect khi server đã tắt bị từ chối (không treo)", refused)
    check("Log server có kết nối mới, dữ liệu và ngắt kết nối",
          "[+]" in log and "recv 5 bytes" in log and "[-]" in log)


def test_stick():
    print("\n--- Thí nghiệm dính gói ---")
    try:
        p = subprocess.run([PY, os.path.join(HERE, "tcp_stick_demo.py")],
                           capture_output=True, env=ENV, timeout=30)
    except subprocess.TimeoutExpired:
        check("tcp_stick_demo.py chạy xong", False, "quá 30 giây")
        return
    out = p.stdout.decode("utf-8", errors="replace")
    if "[Test 3]" not in out:
        check("tcp_stick_demo.py chạy xong", False, "cổng 5055 đang bận? " + out.strip()[-150:])
        return
    m1 = re.search(r"got: (b'[^']*')", out)
    got = m1.group(1) if m1 else "?"
    check("S1  3 lần send(), recv() đầu tiên nhận được dữ liệu", got.startswith("b'AAAA"),
          f"nhận {got}: " + ("dính nhau" if len(got) > 7 else "chưa dính, hợp lệ, thử chạy lại"))
    m2 = re.search(r"needed (\d+) recv", out)
    calls = int(m2.group(1)) if m2 else 0
    check("S2  1 lần send() 100000 byte cần nhiều lần recv()", calls > 1, f"{calls} lần recv(1024)")
    check("S3  'Xin chào Việt Nam': 17 ký tự nhưng 20 byte",
          "len(chars)=17" in out and "len(bytes)=20" in out)


def test_udp_echo():
    print("\n--- UDP echo ---")
    port = free_port(socket.SOCK_DGRAM)
    srv = start("udp_echo.py", "server", "--port", str(port))
    time.sleep(1.0)
    c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    c.settimeout(2)
    try:
        c.sendto(b"one", ("127.0.0.1", port))
        c.sendto(b"two", ("127.0.0.1", port))
        r1, _ = c.recvfrom(2048)
        r2, _ = c.recvfrom(2048)
        check("U4a gửi 2 datagram, nhận 2 datagram riêng biệt (UDP giữ ranh giới)",
              (r1, r2) == (b"one", b"two"), f"{r1!r}, {r2!r}")
    except socket.timeout:
        check("U4a UDP echo trả lời", False, "không nhận được trả lời, server UDP có chạy không?")

    dead = free_port(socket.SOCK_DGRAM)
    c.settimeout(1)
    c.sendto(b"x", ("127.0.0.1", dead))
    try:
        c.recvfrom(2048)
        outcome, ok = "có trả lời", False
    except socket.timeout:
        outcome, ok = "im lặng (timeout)", True
    except ConnectionResetError:
        outcome, ok = "WinError 10054 (ICMP port unreachable)", True
    check("U4b gửi tới cổng không ai nghe: UDP không báo lỗi như TCP", ok, outcome)
    c.close()
    stop(srv)


def test_broadcast(bcast):
    print(f"\n--- UDP broadcast tới {bcast} ---")
    lst = {n: start("udp_broadcast_demo.py", "listen", "--name", n) for n in ("B", "C")}
    time.sleep(1.0)
    sender = start("udp_broadcast_demo.py", "send", "--name", "A", "--bcast", bcast)
    time.sleep(4.5)                       # sender gửi ngay, rồi 3 giây sau gửi tiếp
    sent = stop(sender)
    outs = {n: stop(p) for n, p in lst.items()}

    counts = {n: o.count("HELLO|A|5001|online") for n, o in outs.items()}
    loopback = bcast.startswith("127.")
    hint = ("thử `--bcast <địa chỉ broadcast của Wi-Fi>`" if loopback
            else "kiểm tra firewall, địa chỉ broadcast, card mạng")
    for n, k in counts.items():
        crashed = "Traceback" in outs[n]
        if k:
            detail = f"{k} gói"
        elif crashed:
            detail = "listener bị lỗi: " + outs[n].strip().splitlines()[-1]
        else:
            detail = f"không nhận được, {hint}"
        check(f"U1  listener {n} nhận được gói HELLO từ A", k >= 1, detail,
              warn_only=loopback and not crashed)
    if all(k >= 1 for k in counts.values()):
        check("U1  CẢ HAI listener cùng nhận 1 gói (SO_REUSEADDR hoạt động)", True)
    elif "Traceback" in sent or "Error" in sent:
        print("      Lỗi từ sender:", sent.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bcast", default="127.255.255.255",
                    help="địa chỉ broadcast để thử (mặc định: loopback)")
    a = ap.parse_args()

    print(f"Python {sys.version.split()[0]} trên {sys.platform}")
    check("Python >= 3.9", sys.version_info >= (3, 9))
    print("Lưu ý: đóng mọi instance udp_broadcast_demo.py đang chạy (cổng UDP 9999).")

    test_tcp_echo()
    test_stick()
    test_udp_echo()
    test_broadcast(a.bcast)

    n_pass, n_warn, n_fail = (results.count(s) for s in ("PASS", "WARN", "FAIL"))
    print(f"\nTổng kết: {n_pass} PASS, {n_warn} WARN, {n_fail} FAIL")
    if n_fail:
        print("-> Có FAIL: sửa trước khi sang phần kiểm thử 2 máy.")
    elif n_warn:
        print("-> Có WARN: xem gợi ý trong dòng WARN, không nhất thiết là lỗi code.")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
