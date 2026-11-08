"""
db/test_db.py
Veritabanı katmanı testi. GERÇEK veritabanına dokunmaz, geçici dosya kullanır.

Çalıştırma (proje kök klasöründen):
    python -m db.test_db
"""

import sqlite3
import tempfile
from pathlib import Path

from db import database as d


def expect_error(func, *args):
    try:
        func(*args)
    except ValueError as e:
        return str(e)
    raise AssertionError("ValueError bekleniyordu ama fırlatılmadı")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d.DB_PATH = Path(tmp) / "test.db"

        d.init_db()
        d.init_db()  # ikinci çağrı hata vermemeli, eğitmen tekrar eklenmemeli
        print("[OK] init_db iki kez çalıştı")

        # Varsayılan eğitmen ile giriş
        user = d.authenticate(d.DEFAULT_INSTRUCTOR_USERNAME, d.DEFAULT_INSTRUCTOR_PASSWORD)
        assert user and user["role"] == d.ROLE_INSTRUCTOR
        assert "password_hash" not in user
        print("[OK] Varsayılan eğitmen girişi:", user["username"])

        # Yanlış şifre / olmayan kullanıcı
        assert d.authenticate("egitmen", "yanlis_sifre") is None
        assert d.authenticate("yok_boyle_biri", "123456") is None
        print("[OK] Yanlış şifre ve olmayan kullanıcı reddedildi")

        # Öğrenci ekleme ve giriş
        sid = d.create_user("ogr1", "sifre123", d.ROLE_STUDENT, "Ali Veli", "1A")
        student = d.authenticate("ogr1", "sifre123")
        assert student and student["id"] == sid and student["role"] == d.ROLE_STUDENT
        print("[OK] Öğrenci eklendi ve giriş yaptı")

        # Aynı kullanıcı adı
        print("[OK] Tekrar eden kullanıcı adı:", expect_error(
            d.create_user, "ogr1", "baska123", d.ROLE_STUDENT, "Başka Biri"))

        # Kısa şifre, boş kullanıcı adı, geçersiz rol
        print("[OK] Kısa şifre:", expect_error(
            d.create_user, "ogr2", "123", d.ROLE_STUDENT, "Ayşe"))
        print("[OK] Boş kullanıcı adı:", expect_error(
            d.create_user, "  ", "sifre123", d.ROLE_STUDENT, "Ayşe"))
        print("[OK] Geçersiz rol:", expect_error(
            d.create_user, "ogr3", "sifre123", "admin", "Ayşe"))

        # Şifre değiştirme
        assert d.change_password(sid, "yanlis", "yeni1234") is False
        assert d.change_password(sid, "sifre123", "yeni1234") is True
        assert d.authenticate("ogr1", "sifre123") is None
        assert d.authenticate("ogr1", "yeni1234") is not None
        print("[OK] Şifre değiştirme")

        # Şifre düz metin saklanmıyor
        row = d.get_user_by_username("ogr1")
        assert b"yeni1234" not in bytes(row["password_hash"])
        print("[OK] Şifre hash olarak saklanıyor")

        # Öğrenci listesi
        d.create_user("ogr4", "sifre123", d.ROLE_STUDENT, "Zeynep Kaya", "1B")
        assert len(d.list_students()) == 2
        assert len(d.list_students("1A")) == 1
        print("[OK] Öğrenci listeleme")

    # Eski şemada oluşturulmuş veritabanı otomatik güncellenmeli (migration)
    with tempfile.TemporaryDirectory() as tmp:
        d.DB_PATH = Path(tmp) / "old.db"
        raw = sqlite3.connect(d.DB_PATH)
        raw.execute(
            "CREATE TABLE answers (id INTEGER PRIMARY KEY AUTOINCREMENT, submission_id INTEGER NOT NULL, "
            "question_id INTEGER NOT NULL, given_answer TEXT, score REAL NOT NULL DEFAULT 0, "
            "is_correct INTEGER NOT NULL DEFAULT 0)"
        )
        raw.execute("INSERT INTO answers (submission_id, question_id, given_answer, score, is_correct) "
                    "VALUES (1, 1, 'eski cevap', 5, 1)")
        raw.commit()
        raw.close()

        d.init_db()
        d.init_db()   # ikinci çağrı hata vermemeli
        conn = d.get_connection()
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(answers)")}
        row = conn.execute("SELECT * FROM answers").fetchone()
        conn.close()
        assert {"graded", "graded_at"} <= columns
        assert row["given_answer"] == "eski cevap" and row["score"] == 5 and row["graded"] == 1
        print("[OK] Eski şemalı veritabanı güncellendi, eski cevap satırı korundu (graded = 1)")

    print("\nTüm testler geçti.")


if __name__ == "__main__":
    main()
