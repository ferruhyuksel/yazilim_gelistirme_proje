"""
server/server.py
Eğitmen bilgisayarında çalışan TCP sunucusu.

- Ana thread dışında bir "accept" thread'i yeni bağlantıları kabul eder.
- Her istemci için ayrı bir thread istekleri okur, işler ve yanıtlar.
- Kimlik doğrulama TOKEN ile yapılır. Token yalnızca girişin yapıldığı bağlantıda
  geçerlidir. Kullanıcı kimliği istemciden alınmaz, token'dan sunucu bulur.
- Rol sunucuda sabitlenir: ağdan gelen kayıt isteği her zaman ÖĞRENCİ oluşturur.
"""

import logging
import secrets
import socket
import threading
from datetime import datetime

from common import protocol as p
from db import database as db

log = logging.getLogger("sinav.server")


class RequestError(Exception):
    """İsteğin reddedilme sebebi. Mesajı istemciye aynen iletilir."""


class ExamServer:
    def __init__(self, host="0.0.0.0", port=p.DEFAULT_PORT):
        self.host = host
        self.port = port
        self._sock = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()   # _clients, _conns, _sessions için
        self._clients = {}   # client_id -> bilgi sözlüğü (arayüzde gösterilir)
        self._conns = {}     # client_id -> soket
        self._sessions = {}  # token -> {"user": {...}, "cid": client_id}
        self._next_id = 1
        self._handlers = {
            p.PING: self._h_ping,
            p.LOGIN: self._h_login,
            p.REGISTER: self._h_register,
            p.CHANGE_PASSWORD: self._h_change_password,
            p.LOGOUT: self._h_logout,
        }

    # ------------------------------------------------------------------
    # Başlat / durdur
    # ------------------------------------------------------------------

    @property
    def is_running(self):
        return self._running

    def start(self):
        """Dinlemeye başlar. Port kullanımdaysa OSError fırlatır."""
        if self._running:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self.host, self.port))
            sock.listen(50)
        except OSError:
            sock.close()
            raise
        sock.settimeout(0.5)  # accept() periyodik uyanıp durdurma bayrağına baksın
        self.port = sock.getsockname()[1]
        self._sock = sock
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True, name="accept")
        self._thread.start()
        log.info("Sunucu başladı: %s:%s", self.host, self.port)

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False
            conns = list(self._conns.values())
            self._sessions.clear()
        # accept() beklerken soketi doğrudan kapatmak portu hemen serbest bırakmaz.
        # Önce uyandır, thread bitsin, sonra kapat: stop() döndüğünde port kapalıdır.
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        try:
            self._sock.close()
        except OSError:
            pass
        for conn in conns:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()
        log.info("Sunucu durduruldu.")

    def get_clients(self):
        """Bağlı istemcilerin anlık kopyasını döner (arayüz için)."""
        with self._lock:
            return [dict(c) for c in self._clients.values()]

    # ------------------------------------------------------------------
    # Bağlantı yönetimi
    # ------------------------------------------------------------------

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.settimeout(None)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            with self._lock:
                cid = self._next_id
                self._next_id += 1
                self._conns[cid] = conn
                self._clients[cid] = {
                    "address": addr[0],
                    "port": addr[1],
                    "username": None,
                    "connected_at": datetime.now().strftime("%H:%M:%S"),
                }
            log.info("Bağlandı: %s:%s (#%d)", addr[0], addr[1], cid)
            threading.Thread(
                target=self._handle_client, args=(conn, cid), daemon=True,
                name=f"client-{cid}",
            ).start()

    def _handle_client(self, conn, cid):
        try:
            while self._running:
                try:
                    request = p.recv_message(conn)
                except (OSError, p.ProtocolError):  # ConnectionError de OSError'dır
                    break
                response = self._dispatch(request, cid)
                try:
                    p.send_message(conn, response)
                except OSError:
                    break
        finally:
            self._drop_client(cid)

    def _drop_client(self, cid):
        with self._lock:
            conn = self._conns.pop(cid, None)
            info = self._clients.pop(cid, None)
            for token in [t for t, s in self._sessions.items() if s["cid"] == cid]:
                del self._sessions[token]
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
        if info:
            log.info("Ayrıldı: %s:%s (#%d)", info["address"], info["port"], cid)

    # ------------------------------------------------------------------
    # İstek işleme
    # ------------------------------------------------------------------

    def _dispatch(self, request, cid):
        if not isinstance(request, dict) or not isinstance(request.get("type"), str):
            return p.error_response("Geçersiz istek.")
        data = request.get("data") or {}
        if not isinstance(data, dict):
            return p.error_response("Geçersiz istek verisi.")
        handler = self._handlers.get(request["type"])
        if handler is None:
            return p.error_response("Bilinmeyen istek türü.")
        try:
            return p.ok_response(handler(data, request.get("token"), cid))
        except (RequestError, ValueError) as e:  # ValueError: veritabanı doğrulama hataları
            return p.error_response(str(e))
        except Exception:
            log.exception("İstek işlenirken beklenmeyen hata")
            return p.error_response("Sunucuda beklenmeyen bir hata oluştu.")

    @staticmethod
    def _str(data, key):
        value = data.get(key)
        if not isinstance(value, str):
            raise RequestError(f"Eksik veya geçersiz alan: {key}")
        return value

    def _auth(self, token, cid):
        """Token geçerliyse oturumu döner. Token başka bir bağlantıdan geldiyse reddedilir."""
        with self._lock:
            session = self._sessions.get(token) if isinstance(token, str) else None
        if session is None or session["cid"] != cid:
            raise RequestError("Oturum geçersiz, lütfen tekrar giriş yap.")
        return session

    # --- işleyiciler (handler) ---

    def _h_ping(self, data, token, cid):
        return {}

    def _h_login(self, data, token, cid):
        username = self._str(data, "username")
        password = self._str(data, "password")
        if not username.strip() or not password:
            raise RequestError("Kullanıcı adı ve şifre boş olamaz.")
        user = db.authenticate(username, password)
        if user is None:
            raise RequestError("Kullanıcı adı veya şifre hatalı.")
        new_token = secrets.token_hex(16)
        with self._lock:
            for old in [t for t, s in self._sessions.items() if s["cid"] == cid]:
                del self._sessions[old]
            self._sessions[new_token] = {"user": user, "cid": cid}
            if cid in self._clients:
                self._clients[cid]["username"] = user["username"]
        log.info("Giriş: %s (#%d)", user["username"], cid)
        return {"user": user, "token": new_token}

    def _h_register(self, data, token, cid):
        class_name = data.get("class_name")
        if class_name is not None and not isinstance(class_name, str):
            raise RequestError("Eksik veya geçersiz alan: class_name")
        # Rol burada SABİTLENİR. İstemci ne gönderirse göndersin öğrenci oluşur.
        db.create_user(
            self._str(data, "username"),
            self._str(data, "password"),
            db.ROLE_STUDENT,
            self._str(data, "full_name"),
            (class_name or "").strip() or None,
        )
        return {}

    def _h_change_password(self, data, token, cid):
        session = self._auth(token, cid)
        ok = db.change_password(
            session["user"]["id"],  # kimlik token'dan gelir, istemciye güvenilmez
            self._str(data, "old_password"),
            self._str(data, "new_password"),
        )
        if not ok:
            raise RequestError("Mevcut şifre hatalı.")
        return {}

    def _h_logout(self, data, token, cid):
        with self._lock:
            for t in [t for t, s in self._sessions.items() if s["cid"] == cid]:
                del self._sessions[t]
            if cid in self._clients:
                self._clients[cid]["username"] = None
        return {}
