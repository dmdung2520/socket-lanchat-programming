"""
protocol.py – TCP framing layer (Milestone 4)

Định dạng frame:
    HI|<name>|                          gói đầu tiên sau khi kết nối
    MSG|<độ_dài_byte>|<nội dung UTF-8>\n  tin nhắn chat
    BYE|                                kết thúc cuộc chat
    FILE|<filename>|<filesize>|<raw bytes>  truyền file (kết nối riêng)

Hàm:
  recv_exact(sock, n)          -> bytes          đọc đúng n byte
  read_token(sock, delim)      -> str            đọc đến ký tự delim
  send_hi(sock, name)                            gửi frame HI
  send_msg(sock, text)                           gửi frame MSG
  send_bye(sock)                                 gửi frame BYE
  read_frame(sock)             -> Frame | None   nhận và bóc gói; None = kết nối đóng
"""

import socket

MAX_MSG_SIZE = 1_000_000  # 1 MB theo mục 4.3
MAX_TOKEN_LEN = 65_536    # Giới hạn độ dài token header để tránh tràn bộ nhớ


class Frame:
    """
    Biểu diễn một frame TCP nhận được.
    Hỗ trợ:
      - frame.type: "HI" | "MSG" | "BYE" | "FILE"
      - frame.payload: nội dung (str)
      - unpacking: msg_type, payload = frame
      - so sánh với str (tương thích ngược với test Milestone 2)
      - so sánh với tuple: frame == ("MSG", "hello")
    """
    def __init__(self, msg_type: str, payload: str = ""):
        self.type = msg_type
        self.payload = payload

    def __eq__(self, other):
        if isinstance(other, Frame):
            return self.type == other.type and self.payload == other.payload
        if isinstance(other, tuple) and len(other) == 2:
            return (self.type, self.payload) == other
        if isinstance(other, str):
            # Tương thích ngược với unit test Milestone 2 (kỳ vọng read_frame trả về str payload)
            return self.payload == other
        return False

    def __iter__(self):
        # Cho phép unpack: msg_type, payload = read_frame(sock)
        return iter((self.type, self.payload))

    def __getitem__(self, item):
        return (self.type, self.payload)[item]

    def __str__(self):
        return self.payload

    def __repr__(self):
        return f"Frame({self.type!r}, {self.payload!r})"


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
        if len(buf) > MAX_TOKEN_LEN:
            raise ValueError(f"Header token exceeds {MAX_TOKEN_LEN} bytes")


def send_hi(sock: socket.socket, name: str) -> None:
    """
    Gói đầu tiên sau khi kết nối để bên nhận biết danh tính người gọi.
    Format: HI|<name>|
    """
    if not name or "|" in name:
        raise ValueError(f"Invalid peer name: {name!r}")
    frame = f"HI|{name}|".encode("utf-8")
    sock.sendall(frame)


def send_bye(sock: socket.socket) -> None:
    """
    Gói thông báo kết thúc cuộc chat.
    Format: BYE|
    """
    sock.sendall(b"BYE|")


def send_msg(sock: socket.socket, text: str) -> None:
    """
    Đóng gói và gửi một tin nhắn chat.
    Format: MSG|<byte_length>|<payload>\n
    """
    payload = text.encode("utf-8")
    if len(payload) > MAX_MSG_SIZE:
        raise ValueError(
            f"Message size ({len(payload)} bytes) exceeds maximum limit ({MAX_MSG_SIZE} bytes)"
        )
    header = f"MSG|{len(payload)}|".encode("utf-8")
    sock.sendall(header + payload + b"\n")


def read_frame(sock: socket.socket) -> Frame | None:
    """
    Nhận và bóc một frame từ socket.
    Hỗ trợ các loại frame: HI, MSG, BYE, FILE.
    Trả về Frame nếu thành công, None nếu kết nối đóng sạch.
    Ném ValueError nếu frame sai định dạng hoặc vượt quá kích thước tối đa.
    """
    try:
        # Bỏ qua các byte newline còn sót lại từ frame trước (nếu có)
        delim_byte = b"|"
        buf = bytearray()
        first_byte = True

        while True:
            b = sock.recv(1)
            if not b:
                if first_byte and not buf:
                    return None  # Kết nối đóng bình thường trước khi có frame mới
                raise ConnectionError("Connection closed while reading frame header")
            if first_byte and b in (b"\n", b"\r"):
                continue  # Bỏ qua leading newlines
            first_byte = False
            if b == delim_byte:
                break
            buf.extend(b)
            if len(buf) > MAX_TOKEN_LEN:
                raise ValueError(f"Frame header exceeds {MAX_TOKEN_LEN} bytes")

        keyword = buf.decode("utf-8")

        if keyword == "HI":
            name = read_token(sock, "|")
            if not name:
                raise ValueError("Empty name in HI frame")
            return Frame("HI", name)

        elif keyword == "BYE":
            return Frame("BYE", "")

        elif keyword == "FILE":
            # Chỉ đọc tới 'FILE|' – phần <filename>|<size>|<raw bytes> do filetransfer.receive_file đọc
            return Frame("FILE", "")

        elif keyword == "MSG":
            length_str = read_token(sock, "|")
            try:
                length = int(length_str)
                if length < 0:
                    raise ValueError()
            except ValueError:
                raise ValueError(f"Bad length field in MSG: {length_str!r}")

            if length > MAX_MSG_SIZE:
                raise ValueError(
                    f"Message length ({length} bytes) exceeds limit of {MAX_MSG_SIZE} bytes"
                )

            payload = recv_exact(sock, length)

            # Đọc byte '\n' cuối frame nếu có (tolerant)
            try:
                newline = sock.recv(1)
                if newline not in (b"\n", b"\r", b""):
                    pass
            except (BlockingIOError, socket.timeout):
                pass

            return Frame("MSG", payload.decode("utf-8"))

        else:
            raise ValueError(f"Unknown frame type: {keyword!r}")

    except ConnectionError:
        return None
