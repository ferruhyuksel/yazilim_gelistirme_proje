"""
client/network_client.py
Öğrenci tarafında sunucuyla konuşan düşük seviyeli istemci.
"""

import socket
import threading

from common import protocol


class ServerError(Exception):
    """Sunucu isteği reddetti. Mesajı kullanıcıya gösterilebilir."""


class NetworkClient:
    CONNECT_TIMEOUT = 4.0   # bağlanma bekleme süresi (sn)
    REQUEST_TIMEOUT = 15.0  # bir isteğin yanıt bekleme süresi (sn)

    def __init__(self):
        self._sock = None
        self._lock = threading.Lock()
        self.token = None

    @property
    def is_connected(self):
        return self._sock is not None

    def connect(self, host, port):
        """Bağlanır. Başarısız olursa kullanıcıya gösterilebilir mesajlı ConnectionError fırlatır."""
        self.close()
        try:
            sock = socket.create_connection((host, port), timeout=self.CONNECT_TIMEOUT)
        except socket.timeout:
            raise ConnectionError(
                "Sunucuya bağlanılamadı (zaman aşımı). IP adresini ve aynı ağda olduğunu kontrol et."
            )
        except ConnectionRefusedError:
            raise ConnectionError(
                "Sunucu bağlantıyı reddetti. Eğitmen uygulaması açık ve giriş yapılmış mı?"
            )
        except socket.gaierror:
            raise ConnectionError("Geçersiz sunucu adresi.")
        except OSError as e:
            raise ConnectionError(f"Sunucuya bağlanılamadı: {e}")
        sock.settimeout(self.REQUEST_TIMEOUT)
        self._sock = sock
        self.token = None

    def close(self):
        with self._lock:
            self._close_unlocked()

    def _close_unlocked(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self.token = None

    def request(self, type_, data=None):
        """İstek gönderip yanıtın 'data' kısmını döner.
        Sunucu reddederse ServerError, bağlantı sorunu olursa ConnectionError fırlatır."""
        with self._lock:
            if self._sock is None:
                raise ConnectionError("Sunucuya bağlı değilsin.")
            try:
                protocol.send_message(
                    self._sock, {"type": type_, "data": data or {}, "token": self.token}
                )
                response = protocol.recv_message(self._sock)
            except socket.timeout:
                self._close_unlocked()
                raise ConnectionError("Sunucu yanıt vermedi, bağlantı kapatıldı.")
            except (OSError, protocol.ProtocolError):
                self._close_unlocked()
                raise ConnectionError("Sunucuyla bağlantı koptu.")
        if not isinstance(response, dict) or not response.get("ok"):
            message = response.get("error") if isinstance(response, dict) else None
            raise ServerError(message or "Bilinmeyen sunucu hatası.")
        return response.get("data") or {}
