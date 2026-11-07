"""
db/question_bank.py
Soru bankası: kategoriler ve sorular (ekleme, düzenleme, silme, listeleme).

Soru türleri:
  multiple_choice : options = şık listesi, answer_key = doğru şıkkın SIRASI ("0", "1", ...)
  classic         : options yok, answer_key = beklenen cevap metni
  (code türü final aşamasında eklenecek)

Güvenlik kuralları:
  - Bir sınavda kullanılan soru SİLİNEMEZ (silmek öğrenci cevaplarını da silerdi).
  - Yayınlanmış veya kapanmış bir sınavdaki soru DÜZENLENEMEZ (puanlama bozulurdu).
Tüm doğrulama hataları, kullanıcıya gösterilebilir mesajlı ValueError olarak fırlatılır.
"""

import json
import sqlite3

from db.database import get_connection

TYPE_MULTIPLE_CHOICE = "multiple_choice"
TYPE_CLASSIC = "classic"
QUESTION_TYPES = (TYPE_MULTIPLE_CHOICE, TYPE_CLASSIC)
TYPE_LABELS = {
    TYPE_MULTIPLE_CHOICE: "Çoktan seçmeli",
    TYPE_CLASSIC: "Klasik",
}

MIN_OPTIONS = 2
MAX_OPTIONS = 6
MAX_CATEGORY_NAME = 60
MAX_POINTS = 1000

# list_questions için: kategorisi olmayan soruları süz
UNCATEGORIZED = -1


# --------------------------------------------------------------------------
# Kategoriler
# --------------------------------------------------------------------------

def _clean_category_name(name):
    name = (name or "").strip()
    if not name:
        raise ValueError("Kategori adı boş olamaz.")
    if len(name) > MAX_CATEGORY_NAME:
        raise ValueError(f"Kategori adı en fazla {MAX_CATEGORY_NAME} karakter olabilir.")
    return name


def _category_name_taken(conn, name, exclude_id=None):
    row = conn.execute(
        "SELECT id FROM categories WHERE name = ? COLLATE NOCASE AND id IS NOT ?",
        (name, exclude_id),
    ).fetchone()
    return row is not None


def list_categories():
    """Her kategori için soru sayısıyla birlikte, ada göre sıralı liste."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT c.id, c.name, COUNT(q.id) AS question_count "
            "FROM categories c LEFT JOIN questions q ON q.category_id = c.id "
            "GROUP BY c.id ORDER BY c.name COLLATE NOCASE"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_category(name):
    name = _clean_category_name(name)
    conn = get_connection()
    try:
        if _category_name_taken(conn, name):
            raise ValueError("Bu kategori zaten var.")
        cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def rename_category(category_id, name):
    name = _clean_category_name(name)
    conn = get_connection()
    try:
        if _category_name_taken(conn, name, exclude_id=category_id):
            raise ValueError("Bu kategori zaten var.")
        cur = conn.execute(
            "UPDATE categories SET name = ? WHERE id = ?", (name, category_id)
        )
        if cur.rowcount == 0:
            raise ValueError("Kategori bulunamadı.")
        conn.commit()
    finally:
        conn.close()


def delete_category(category_id):
    """Kategoriyi siler. Sorular silinmez, 'kategorisiz' olur.
    Kategorisiz kalan soru sayısını döner."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM questions WHERE category_id = ?", (category_id,)
        ).fetchone()
        cur = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        if cur.rowcount == 0:
            raise ValueError("Kategori bulunamadı.")
        conn.commit()
        return row["n"]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Sorular
# --------------------------------------------------------------------------

def _validate_question(qtype, text, options, answer_key, points):
    """Doğrular ve veritabanına yazılacak (tür, metin, options_json, anahtar, puan) döner."""
    if qtype not in QUESTION_TYPES:
        raise ValueError("Geçersiz soru türü.")
    text = (text or "").strip()
    if not text:
        raise ValueError("Soru metni boş olamaz.")
    try:
        points = float(points)
    except (TypeError, ValueError):
        raise ValueError("Puan geçerli bir sayı olmalı.")
    if not 0 < points <= MAX_POINTS:
        raise ValueError(f"Puan 0'dan büyük ve en fazla {MAX_POINTS} olmalı.")

    if qtype == TYPE_MULTIPLE_CHOICE:
        opts = [str(o).strip() for o in (options or [])]
        if not MIN_OPTIONS <= len(opts) <= MAX_OPTIONS:
            raise ValueError(f"Şık sayısı {MIN_OPTIONS} ile {MAX_OPTIONS} arasında olmalı.")
        if any(not o for o in opts):
            raise ValueError("Boş şık olamaz. Doldur ya da şıkkı kaldır.")
        if len({o.casefold() for o in opts}) != len(opts):
            raise ValueError("Şıklar birbirinden farklı olmalı.")
        try:
            index = int(answer_key)
        except (TypeError, ValueError):
            raise ValueError("Doğru şıkkı seçmelisin.")
        if not 0 <= index < len(opts):
            raise ValueError("Doğru şıkkı seçmelisin.")
        return (qtype, text, json.dumps(opts, ensure_ascii=False), str(index), points)

    key = (answer_key or "").strip()
    if not key:
        raise ValueError("Beklenen cevap boş olamaz.")
    return (qtype, text, None, key, points)


def _row_to_dict(row):
    q = dict(row)
    q["options"] = json.loads(q["options"]) if q["options"] else None
    return q


_SELECT = (
    "SELECT q.id, q.type, q.category_id, c.name AS category_name, q.text, "
    "q.options, q.answer_key, q.default_points, q.created_by, q.created_at "
    "FROM questions q LEFT JOIN categories c ON c.id = q.category_id "
)


def _exams_using(conn, question_id):
    return conn.execute(
        "SELECT e.id, e.title, e.status FROM exam_questions eq "
        "JOIN exams e ON e.id = eq.exam_id WHERE eq.question_id = ? ORDER BY e.id",
        (question_id,),
    ).fetchall()


def add_question(qtype, text, category_id=None, options=None, answer_key=None,
                 default_points=10, created_by=None):
    """Soru ekler, id'sini döner."""
    values = _validate_question(qtype, text, options, answer_key, default_points)
    conn = get_connection()
    try:
        try:
            cur = conn.execute(
                "INSERT INTO questions (type, text, options, answer_key, default_points, "
                "category_id, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                values + (category_id, created_by),
            )
        except sqlite3.IntegrityError:
            raise ValueError("Kategori bulunamadı.")
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_question(question_id, qtype, text, category_id=None, options=None,
                    answer_key=None, default_points=10):
    values = _validate_question(qtype, text, options, answer_key, default_points)
    conn = get_connection()
    try:
        if conn.execute("SELECT 1 FROM questions WHERE id = ?", (question_id,)).fetchone() is None:
            raise ValueError("Soru bulunamadı.")
        locked = [e for e in _exams_using(conn, question_id) if e["status"] != "draft"]
        if locked:
            titles = ", ".join(e["title"] for e in locked)
            raise ValueError(
                f"Bu soru yayınlanmış veya kapanmış sınavda kullanılıyor ({titles}), "
                "değiştirilemez. İstersen soruyu kopyalayıp yenisini düzenle."
            )
        try:
            conn.execute(
                "UPDATE questions SET type = ?, text = ?, options = ?, answer_key = ?, "
                "default_points = ?, category_id = ? WHERE id = ?",
                values + (category_id, question_id),
            )
        except sqlite3.IntegrityError:
            raise ValueError("Kategori bulunamadı.")
        conn.commit()
    finally:
        conn.close()


def delete_question(question_id):
    conn = get_connection()
    try:
        used = _exams_using(conn, question_id)
        if used:
            titles = ", ".join(e["title"] for e in used)
            raise ValueError(
                f"Bu soru şu sınavlarda kullanılıyor: {titles}. "
                "Silmeden önce sınavlardan çıkarılmalı."
            )
        cur = conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        if cur.rowcount == 0:
            raise ValueError("Soru bulunamadı.")
        conn.commit()
    finally:
        conn.close()


def get_question(question_id):
    conn = get_connection()
    try:
        row = conn.execute(_SELECT + "WHERE q.id = ?", (question_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_questions(category_id=None, qtype=None, search=None):
    """Filtreli soru listesi (yeniden eskiye).
    category_id: None = hepsi, UNCATEGORIZED = kategorisizler, sayı = o kategori."""
    query = _SELECT
    where, params = [], []
    if category_id == UNCATEGORIZED:
        where.append("q.category_id IS NULL")
    elif category_id is not None:
        where.append("q.category_id = ?")
        params.append(category_id)
    if qtype is not None:
        where.append("q.type = ?")
        params.append(qtype)
    if where:
        query += "WHERE " + " AND ".join(where) + " "
    query += "ORDER BY q.id DESC"

    conn = get_connection()
    try:
        questions = [_row_to_dict(r) for r in conn.execute(query, params)]
    finally:
        conn.close()

    needle = (search or "").strip().casefold()
    if needle:
        questions = [q for q in questions if needle in q["text"].casefold()]
    return questions
