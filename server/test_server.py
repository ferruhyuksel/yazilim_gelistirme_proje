"""
server/test_server.py
Sunucu-istemci katmanı testi. Geçici veritabanı ve yerel (127.0.0.1) bağlantı kullanır,
gerçek veritabanına dokunmaz.

Çalıştırma (proje kök klasöründen):
    python -m server.test_server
"""

import socket
import tempfile
import time
from pathlib import Path

from client.network_auth_service import NetworkAuthService
from client.network_client import NetworkClient, ServerError
from common import protocol
from db import database as d
from server.server import ExamServer
from ui.auth_service import AuthError


def expect_auth_error(func, *args):
    try:
        func(*args)
    except AuthError as e:
        return str(e)
    raise AssertionError("AuthError bekleniyordu")


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d.DB_PATH = Path(tmp) / "test.db"
        d.init_db()

        server = ExamServer(host="127.0.0.1", port=0)  # port=0: boş bir port seç
        server.start()
        port = server.port
        print(f"[OK] Sunucu başladı (port {port})")

        c1, c2 = NetworkClient(), NetworkClient()
        c1.connect("127.0.0.1", port)
        c2.connect("127.0.0.1", port)
        s1, s2 = NetworkAuthService(c1), NetworkAuthService(c2)
        assert wait_for(lambda: len(server.get_clients()) == 2)
        print("[OK] İki istemci aynı anda bağlandı")

        assert c1.request(protocol.PING) == {}
        print("[OK] ping")

        # Kayıt: istemci rol göndermeye çalışsa bile öğrenci oluşur
        c1.request(protocol.REGISTER, {
            "username": "ogr1", "password": "sifre123", "full_name": "Ali Veli",
            "class_name": "1A", "role": "instructor",
        })
        assert d.get_user_by_username("ogr1")["role"] == d.ROLE_STUDENT
        print("[OK] Kayıt oluştu, rol sunucuda öğrenciye sabitlendi")

        print("[OK] Tekrar eden kullanıcı adı:", expect_auth_error(
            s1.register_student, "ogr1", "baska123", "Başka", ""))
        print("[OK] Kısa şifre:", expect_auth_error(
            s1.register_student, "ogr2", "123", "Ayşe", ""))

        print("[OK] Yanlış şifre:", expect_auth_error(s1.login, "ogr1", "yanlis"))

        user = s1.login("ogr1", "sifre123")
        assert user["username"] == "ogr1" and "password_hash" not in user
        assert c1.token
        assert wait_for(lambda: any(c["username"] == "ogr1" for c in server.get_clients()))
        print("[OK] Giriş, token alındı, sunucu listesinde kullanıcı adı göründü")

        # Giriş yapmadan şifre değiştirme reddedilmeli
        print("[OK] Girişsiz şifre değiştirme:", expect_auth_error(
            s2.change_password, 0, "sifre123", "yeni1234"))

        # c1'in token'ı başka bağlantıdan kullanılamaz (token çalma denemesi)
        stolen = c1.token
        c2.token = stolen
        try:
            c2.request(protocol.CHANGE_PASSWORD,
                       {"old_password": "sifre123", "new_password": "hack1234"})
            raise AssertionError("çalıntı token kabul edildi")
        except ServerError as e:
            print("[OK] Başka bağlantıdan token kullanımı reddedildi:", e)
        c2.token = None

        # Şifre değiştirme (user_id istemciden değil token'dan gelir)
        s1.change_password(9999, "sifre123", "yeni1234")
        assert expect_auth_error(s1.login, "ogr1", "sifre123")
        assert s1.login("ogr1", "yeni1234")["username"] == "ogr1"
        print("[OK] Şifre değiştirme (sahte user_id yok sayıldı)")

        print("[OK] Yanlış mevcut şifre:", expect_auth_error(
            s1.change_password, 0, "yanlis", "yeni5678"))

        # Bozuk istekler sunucuyu düşürmemeli
        for bad in ({"type": "yok_boyle"}, {"data": 5}, [1, 2], {"type": "login", "data": {"username": 5}}):
            protocol.send_message(c2._sock, bad)
            resp = protocol.recv_message(c2._sock)
            assert resp["ok"] is False, bad
        print("[OK] Bozuk istekler hata yanıtı döndü, sunucu ayakta")

        # Ham soket: bozuk JSON gönderen istemci atılır, sunucu yaşamaya devam eder
        raw = socket.create_connection(("127.0.0.1", port))
        raw.sendall((5).to_bytes(4, "big") + b"{bozuk")
        time.sleep(0.3)
        raw.close()
        assert c1.request(protocol.PING) == {}
        print("[OK] Bozuk JSON gönderen bağlantı atıldı, diğerleri etkilenmedi")

        # Çıkış sonrası token geçersiz
        s1.logout()
        assert wait_for(lambda: all(c["username"] is None for c in server.get_clients()))
        print("[OK] Çıkış yapıldı, kullanıcı listeden düştü")

        # Bağlantı koparma
        c2.close()
        assert wait_for(lambda: len(server.get_clients()) == 1)
        print("[OK] İstemci ayrılınca sunucu listesinden silindi")

        # Sunucu durunca istemci anlaşılır hata alır
        server.stop()
        try:
            c1.request(protocol.PING)
            raise AssertionError("ConnectionError bekleniyordu")
        except ConnectionError as e:
            print("[OK] Sunucu durunca istemci hatası:", e)

        # Kapalı porta bağlanma mesajı
        try:
            NetworkClient().connect("127.0.0.1", port)
            raise AssertionError("ConnectionError bekleniyordu")
        except ConnectionError as e:
            print("[OK] Kapalı porta bağlanma:", e)

    print("\nTüm testler geçti.")


if __name__ == "__main__":
    main()
