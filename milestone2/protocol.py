"""
protocol.py – TCP framing layer (Milestone 2, dùng từ Milestone 3 trở đi)

Định dạng frame:
    MSG|<length>|<payload>\n
    ví dụ: MSG|11|hello world\n

Hàm:
  recv_exact(sock, n)          -> bytes          đọc đúng n byte
  read_token(sock, delim)      -> str            đọc đến ký tự delim
  send_msg(sock, text)                           đóng gói và gửi
  read_frame(sock)             -> str | None     nhận và bóc gói; None = kết nối đóng
"""

import socket


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """
    Đọc đúng n byte từ socket.
    Ném ConnectionError nếu kết nối đóng trước khi đủ n byte.
    """
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed while reading")
        buf.extend(chunk)
    return bytes(buf)


def read_token(sock: socket.socket, delim: str = "|") -> str:
    """
    Đọc từng byte cho đến khi gặp ký tự delim.
    Trả về chuỗi KHÔNG bao gồm delim.
    """
    delim_byte = delim.encode("utf-8")
    buf = bytearray()
    while True:
        b = sock.recv(1)
        if not b:
            raise ConnectionError("Connection closed while reading token")
        if b == delim_byte:
            return buf.decode("utf-8")
        buf.extend(b)


def send_msg(sock: socket.socket, text: str) -> None:
    """
    Đóng gói và gửi một tin nhắn.
    Format: MSG|<byte_length>|<payload>\n
    """
    payload = text.encode("utf-8")
    header = f"MSG|{len(payload)}|".encode("utf-8")
    sock.sendall(header + payload + b"\n")


def read_frame(sock: socket.socket) -> str | None:
    """
    Nhận và bóc một frame từ socket.
    Trả về nội dung (str) nếu thành công, None nếu kết nối đóng.
    Ném ValueError nếu frame sai định dạng.
    """
    try:
        keyword = read_token(sock, "|")
        if keyword != "MSG":
            raise ValueError(f"Unknown frame type: {keyword!r}")

        length_str = read_token(sock, "|")
        try:
            length = int(length_str)
            if length < 0:
                raise ValueError()
        except ValueError:
            raise ValueError(f"Bad length field: {length_str!r}")

        payload = recv_exact(sock, length)

        # Đọc byte '\n' cuối frame
        newline = sock.recv(1)
        if newline not in (b"\n", b""):
            pass  # bỏ qua nếu không có newline (tolerant)

        return payload.decode("utf-8")

    except ConnectionError:
        return None
