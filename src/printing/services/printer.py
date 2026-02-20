import socket


class PrintError(Exception):
    pass


class PrinterService:
    def __init__(self, ip_address: str, port: int = 9100, timeout: int = 8):
        self.ip_address = ip_address
        self.port = port
        self.timeout = timeout

    def send(self, data: bytes) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.ip_address, self.port))
            sock.sendall(data)
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            raise PrintError(
                f"Failed to connect to {self.ip_address}:{self.port}: {e}"
            )
        finally:
            sock.close()
