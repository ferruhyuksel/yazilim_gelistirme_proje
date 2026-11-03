"""
db/database.py
SQLite veritabanı katmanı: şema, kullanıcı yönetimi, giriş doğrulama.

Bu dosya sadece EĞİTMEN bilgisayarında kullanılır. Öğrenci uygulaması
veritabanına doğrudan erişmez, sunucu üzerinden konuşur.
"""

import sqlite3
from pathlib import Path

import bcrypt

# Veritabanı dosyası proje içindeki db/ klasöründe durur (.gitignore *.db'yi dışlar)
DB_PATH = Path(__file__).resolve().parent / "exam_system.db"

# Rol sabitleri (diğer modüller de bunları kullanacak)
ROLE_INSTRUCTOR = "instructor"
ROLE_STUDENT = "student"

# Varsayılan eğitmen hesabı. İlk girişten sonra mutlaka değiştirilmeli.
DEFAULT_INSTRUCTOR_USERNAME = "egitmen"
DEFAULT_INSTRUCTOR_PASSWORD = "egitmen123"

MIN_PASSWORD_LENGTH = 6

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash BLOB    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('instructor', 'student')),
    full_name     TEXT    NOT NULL,
    class_name    TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- type: 'multiple_choice' | 'classic' | 'code' (code, final aşamasında kullanılacak)
-- options: çoktan seçmeli için şıklar (JSON listesi), diğer tiplerde NULL
-- answer_key: çoktan seçmelide doğru şık, klasikte beklenen cevap
CREATE TABLE IF NOT EXISTS questions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    type           TEXT    NOT NULL CHECK (type IN ('multiple_choice', 'classic', 'code')),
    category_id    INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    text           TEXT    NOT NULL,
    options        TEXT,
    answer_key     TEXT,
    default_points REAL    NOT NULL DEFAULT 10,
    created_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- status: 'draft' | 'published' | 'closed'
CREATE TABLE IF NOT EXISTS exams (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT    NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    start_time       TEXT,
    status           TEXT    NOT NULL DEFAULT 'draft'
                             CHECK (status IN ('draft', 'published', 'closed')),
    created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS exam_questions (
    exam_id     INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    points      REAL    NOT NULL,
    position    INTEGER NOT NULL,
    PRIMARY KEY (exam_id, question_id)
);

-- Bir öğrenci bir sınava yalnızca bir kez gönderim yapabilir
CREATE TABLE IF NOT EXISTS submissions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id      INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    student_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    submitted_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    total_score  REAL    NOT NULL DEFAULT 0,
    UNIQUE (exam_id, student_id)
);

CREATE TABLE IF NOT EXISTS answers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    question_id   INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    given_answer  TEXT,
    score         REAL    NOT NULL DEFAULT 0,
    is_correct    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    exam_id    INTEGER REFERENCES exams(id) ON DELETE SET NULL,
    event      TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


# --------------------------------------------------------------------------
# Bağlantı ve kurulum
# --------------------------------------------------------------------------

def get_connection():
    """Her çağrıda yeni bağlantı döner. Sunucu thread'leri bağlantıyı paylaşmasın diye
    her işlem kendi bağlantısını açıp kapatır."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Tabloları oluşturur ve yoksa varsayılan eğitmen hesabını ekler.
    Birden fazla kez çağrılması güvenlidir."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    if get_user_by_username(DEFAULT_INSTRUCTOR_USERNAME) is None:
        create_user(
            DEFAULT_INSTRUCTOR_USERNAME,
            DEFAULT_INSTRUCTOR_PASSWORD,
            ROLE_INSTRUCTOR,
            "Eğitmen",
        )


# --------------------------------------------------------------------------
# Şifre işlemleri
# --------------------------------------------------------------------------

def _validate_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Şifre en az {MIN_PASSWORD_LENGTH} karakter olmalı.")
    # bcrypt en fazla 72 bayt destekler
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Şifre çok uzun (en fazla 72 bayt).")


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def verify_password(password, password_hash):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), bytes(password_hash))
    except ValueError:
        return False


# --------------------------------------------------------------------------
# Kullanıcı işlemleri
# --------------------------------------------------------------------------

def create_user(username, password, role, full_name, class_name=None):
    """Yeni kullanıcı ekler, kullanıcı id'sini döner.
    Kullanıcı adı alınmışsa veya veri geçersizse ValueError fırlatır."""
    username = username.strip()
    full_name = full_name.strip()

    if not username:
        raise ValueError("Kullanıcı adı boş olamaz.")
    if not full_name:
        raise ValueError("Ad soyad boş olamaz.")
    if role not in (ROLE_INSTRUCTOR, ROLE_STUDENT):
        raise ValueError("Geçersiz rol.")
    _validate_password(password)

    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name, class_name) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, hash_password(password), role, full_name, class_name),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Bu kullanıcı adı zaten kullanılıyor.")
    finally:
        conn.close()


def get_user_by_username(username):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
    finally:
        conn.close()


def authenticate(username, password):
    """Giriş doğrulama. Başarılıysa kullanıcıyı sözlük olarak (şifre hash'i HARİÇ),
    başarısızsa None döner. Hangisinin yanlış olduğu bilerek belli edilmez."""
    user = get_user_by_username(username)
    if user is None or not verify_password(password, user["password_hash"]):
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
        "class_name": user["class_name"],
    }


def change_password(user_id, old_password, new_password):
    """Eski şifre doğruysa şifreyi değiştirir. Başarılıysa True döner."""
    _validate_password(new_password)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None or not verify_password(old_password, row["password_hash"]):
            return False
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), user_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def list_students(class_name=None):
    """Öğrencileri listeler (eğitmen ekranı için). Şifre hash'i dönmez."""
    conn = get_connection()
    try:
        query = ("SELECT id, username, full_name, class_name FROM users "
                 "WHERE role = 'student'")
        params = ()
        if class_name:
            query += " AND class_name = ?"
            params = (class_name,)
        return [dict(r) for r in conn.execute(query + " ORDER BY full_name", params)]
    finally:
        conn.close()
