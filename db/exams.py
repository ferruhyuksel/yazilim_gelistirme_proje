"""
db/exams.py
Sınavlar: oluşturma, düzenleme, yayınlama, sonlandırma ve öğrenciye sunulan görünüm.

Yaşam döngüsü:  draft (taslak) -> published (yayında) -> closed (kapandı)
  - Yalnızca taslak sınav düzenlenebilir.
  - Yayınlanma anı sınavın başlangıcıdır, bitiş = başlangıç + süre.
  - Süre dolan sınav, SUBMIT_GRACE_SECONDS sonra otomatik 'closed' olur (her okumada kontrol
    edilir). O arada öğrencilere görünmez ama son gönderimler kabul edilir.
  - Öğrenci gönderimi olan sınav silinemez, yayındaki sınav silinemez.

ÖĞRENCİYE CEVAP ANAHTARI GİTMEZ: öğrenci görünümü (list_active_exams,
get_exam_for_student) alanları tek tek seçerek oluşturulur. Yeni bir veritabanı sütunu
eklense bile kendiliğinden öğrenciye sızmaz.

Zamanlar sunucunun yerel saatiyle, "YYYY-MM-DD HH:MM:SS" biçiminde saklanır.
Tüm doğrulama hataları, kullanıcıya gösterilebilir mesajlı ValueError olarak fırlatılır.
"""

import json
from datetime import datetime, timedelta

from db.database import get_connection
from db.question_bank import MAX_POINTS

STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_CLOSED = "closed"
STATUS_LABELS = {
    STATUS_DRAFT: "Taslak",
    STATUS_PUBLISHED: "Yayında",
    STATUS_CLOSED: "Kapandı",
}

# Süresi dolan sınav, öğrencilerin son saniyedeki gönderimleri kabul edilebilsin diye
# bu kadar saniye daha "yayında" kalır (öğrencilere görünmez). Ayrıntı: db/submissions.py
SUBMIT_GRACE_SECONDS = 5

MAX_TITLE = 120
MIN_DURATION = 1
MAX_DURATION = 600  # dakika

_TIME_FMT = "%Y-%m-%d %H:%M:%S"


# --------------------------------------------------------------------------
# Yardımcılar
# --------------------------------------------------------------------------

def _clean_title(title):
    title = (title or "").strip()
    if not title:
        raise ValueError("Sınav başlığı boş olamaz.")
    if len(title) > MAX_TITLE:
        raise ValueError(f"Sınav başlığı en fazla {MAX_TITLE} karakter olabilir.")
    return title


def _clean_duration(duration):
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        raise ValueError("Süre geçerli bir sayı olmalı.")
    if not MIN_DURATION <= duration <= MAX_DURATION:
        raise ValueError(f"Süre {MIN_DURATION} ile {MAX_DURATION} dakika arasında olmalı.")
    return duration


def _normalize_items(conn, items):
    """items: (soru_id, puan) çiftleri, sınavdaki sıraya göre. Doğrulayıp normalleştirir."""
    result, seen = [], set()
    for item in items or []:
        try:
            question_id, points = item
            question_id = int(question_id)
        except (TypeError, ValueError):
            raise ValueError("Geçersiz soru.")
        try:
            points = float(points)
        except (TypeError, ValueError):
            raise ValueError("Puan geçerli bir sayı olmalı.")
        if not 0 < points <= MAX_POINTS:
            raise ValueError(f"Her sorunun puanı 0'dan büyük ve en fazla {MAX_POINTS} olmalı.")
        if question_id in seen:
            raise ValueError("Aynı soru sınava iki kez eklenemez.")
        seen.add(question_id)
        result.append((question_id, points))
    if result:
        marks = ",".join("?" * len(result))
        found = {r["id"] for r in conn.execute(
            f"SELECT id FROM questions WHERE id IN ({marks})", [q for q, _ in result])}
        if len(found) != len(result):
            raise ValueError("Seçilen sorulardan biri artık soru bankasında yok.")
    return result


def _write_items(conn, exam_id, items):
    conn.execute("DELETE FROM exam_questions WHERE exam_id = ?", (exam_id,))
    for position, (question_id, points) in enumerate(items, start=1):
        conn.execute(
            "INSERT INTO exam_questions (exam_id, question_id, points, position) "
            "VALUES (?, ?, ?, ?)",
            (exam_id, question_id, points, position),
        )


def _status_of(conn, exam_id):
    row = conn.execute("SELECT status FROM exams WHERE id = ?", (exam_id,)).fetchone()
    if row is None:
        raise ValueError("Sınav bulunamadı.")
    return row["status"]


def _close_expired(conn):
    cur = conn.execute(
        "UPDATE exams SET status = 'closed' "
        "WHERE status = 'published' AND start_time IS NOT NULL "
        "AND datetime(start_time, '+' || duration_minutes || ' minutes', "
        "'+' || ? || ' seconds') <= datetime('now', 'localtime')",
        (SUBMIT_GRACE_SECONDS,),
    )
    conn.commit()
    return cur.rowcount


def close_expired_exams():
    """Süresi dolan yayındaki sınavları kapatır, kapatılan sayısını döner."""
    conn = get_connection()
    try:
        return _close_expired(conn)
    finally:
        conn.close()


_SUMMARY_SQL = (
    "SELECT e.id, e.title, e.duration_minutes, e.start_time, e.status, e.created_at, "
    "(SELECT COUNT(*) FROM exam_questions eq WHERE eq.exam_id = e.id) AS question_count, "
    "(SELECT COALESCE(SUM(eq.points), 0) FROM exam_questions eq WHERE eq.exam_id = e.id) AS total_points, "
    "(SELECT COUNT(*) FROM submissions s WHERE s.exam_id = e.id) AS submission_count "
    "FROM exams e "
)


def _decorate(row, now):
    """Bitiş zamanı ve (yayındaysa) kalan saniyeyi ekler."""
    exam = dict(row)
    exam["end_time"] = None
    exam["remaining_seconds"] = None
    if exam["start_time"]:
        end = datetime.strptime(exam["start_time"], _TIME_FMT) + timedelta(
            minutes=exam["duration_minutes"])
        exam["end_time"] = end.strftime(_TIME_FMT)
        if exam["status"] == STATUS_PUBLISHED:
            exam["remaining_seconds"] = max(0, int((end - now).total_seconds()))
    return exam


# --------------------------------------------------------------------------
# Eğitmen işlemleri
# --------------------------------------------------------------------------

def create_exam(title, duration_minutes, items, created_by=None):
    """Taslak sınav oluşturur, id'sini döner. items: [(soru_id, puan), ...]"""
    title = _clean_title(title)
    duration = _clean_duration(duration_minutes)
    conn = get_connection()
    try:
        items = _normalize_items(conn, items)
        cur = conn.execute(
            "INSERT INTO exams (title, duration_minutes, status, created_by) "
            "VALUES (?, ?, 'draft', ?)",
            (title, duration, created_by),
        )
        _write_items(conn, cur.lastrowid, items)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_exam(exam_id, title, duration_minutes, items):
    """Taslak sınavı günceller. Yayınlanmış veya kapanmış sınav düzenlenemez."""
    title = _clean_title(title)
    duration = _clean_duration(duration_minutes)
    conn = get_connection()
    try:
        _close_expired(conn)
        if _status_of(conn, exam_id) != STATUS_DRAFT:
            raise ValueError("Yalnızca taslak sınav düzenlenebilir. "
                             "Yayınlanmış sınavın kopyasını alıp onu düzenleyebilirsin.")
        items = _normalize_items(conn, items)
        conn.execute("UPDATE exams SET title = ?, duration_minutes = ? WHERE id = ?",
                     (title, duration, exam_id))
        _write_items(conn, exam_id, items)
        conn.commit()
    finally:
        conn.close()


def duplicate_exam(exam_id, created_by=None):
    """Sınavın sorularını ve puanlarını yeni bir taslağa kopyalar, yeni id'yi döner."""
    conn = get_connection()
    try:
        exam = conn.execute(
            "SELECT title, duration_minutes FROM exams WHERE id = ?", (exam_id,)
        ).fetchone()
        if exam is None:
            raise ValueError("Sınav bulunamadı.")
        rows = conn.execute(
            "SELECT question_id, points FROM exam_questions WHERE exam_id = ? ORDER BY position",
            (exam_id,),
        ).fetchall()
        suffix = " (kopya)"
        title = exam["title"][: MAX_TITLE - len(suffix)] + suffix
        cur = conn.execute(
            "INSERT INTO exams (title, duration_minutes, status, created_by) "
            "VALUES (?, ?, 'draft', ?)",
            (title, exam["duration_minutes"], created_by),
        )
        _write_items(conn, cur.lastrowid, [(r["question_id"], r["points"]) for r in rows])
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_exam(exam_id):
    conn = get_connection()
    try:
        _close_expired(conn)
        if _status_of(conn, exam_id) == STATUS_PUBLISHED:
            raise ValueError("Yayındaki sınav silinemez. Önce sınavı sonlandır.")
        n = conn.execute("SELECT COUNT(*) AS n FROM submissions WHERE exam_id = ?",
                         (exam_id,)).fetchone()["n"]
        if n:
            raise ValueError(f"Bu sınava {n} öğrenci gönderimi var, silinemez.")
        conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
        conn.commit()
    finally:
        conn.close()


def publish_exam(exam_id):
    """Taslağı yayınlar: şu an başlar, süre dolunca kapanır. Güncel sınav bilgisini döner."""
    conn = get_connection()
    try:
        if _status_of(conn, exam_id) != STATUS_DRAFT:
            raise ValueError("Yalnızca taslak sınav yayınlanabilir.")
        n = conn.execute("SELECT COUNT(*) AS n FROM exam_questions WHERE exam_id = ?",
                         (exam_id,)).fetchone()["n"]
        if n == 0:
            raise ValueError("Sınavda en az bir soru olmalı.")
        conn.execute(
            "UPDATE exams SET status = 'published', start_time = ? WHERE id = ?",
            (datetime.now().strftime(_TIME_FMT), exam_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_exam(exam_id)


def close_exam(exam_id):
    """Yayındaki sınavı süresi dolmadan sonlandırır."""
    conn = get_connection()
    try:
        _close_expired(conn)
        if _status_of(conn, exam_id) != STATUS_PUBLISHED:
            raise ValueError("Yalnızca yayındaki sınav sonlandırılabilir.")
        conn.execute("UPDATE exams SET status = 'closed' WHERE id = ?", (exam_id,))
        conn.commit()
    finally:
        conn.close()


def list_exams():
    """Tüm sınavlar (yeniden eskiye), soru sayısı ve toplam puanla."""
    conn = get_connection()
    try:
        _close_expired(conn)
        rows = conn.execute(_SUMMARY_SQL + "ORDER BY e.id DESC").fetchall()
    finally:
        conn.close()
    now = datetime.now()
    return [_decorate(r, now) for r in rows]


def get_exam(exam_id):
    """EĞİTMEN görünümü: sorular cevap anahtarlarıyla birlikte. Yoksa None."""
    conn = get_connection()
    try:
        _close_expired(conn)
        row = conn.execute(_SUMMARY_SQL + "WHERE e.id = ?", (exam_id,)).fetchone()
        if row is None:
            return None
        questions = conn.execute(
            "SELECT eq.position, eq.points, q.id AS question_id, q.type, q.text, "
            "q.options, q.answer_key, c.name AS category_name "
            "FROM exam_questions eq JOIN questions q ON q.id = eq.question_id "
            "LEFT JOIN categories c ON c.id = q.category_id "
            "WHERE eq.exam_id = ? ORDER BY eq.position",
            (exam_id,),
        ).fetchall()
    finally:
        conn.close()
    exam = _decorate(row, datetime.now())
    exam["questions"] = []
    for q in questions:
        q = dict(q)
        q["options"] = json.loads(q["options"]) if q["options"] else None
        exam["questions"].append(q)
    return exam


# --------------------------------------------------------------------------
# Öğrenci görünümü (cevap anahtarı YOK)
# --------------------------------------------------------------------------

def list_active_exams(student_id):
    """Öğrencinin şu an görebileceği, süresi dolmamış yayındaki sınavlar."""
    conn = get_connection()
    try:
        _close_expired(conn)
        rows = conn.execute(
            _SUMMARY_SQL.replace(
                "FROM exams e ",
                ", EXISTS(SELECT 1 FROM submissions s WHERE s.exam_id = e.id "
                "AND s.student_id = ?) AS submitted FROM exams e ",
            ) + "WHERE e.status = 'published' ORDER BY e.id DESC",
            (student_id,),
        ).fetchall()
    finally:
        conn.close()
    now = datetime.now()
    result = []
    for row in rows:
        exam = _decorate(row, now)
        if not exam["remaining_seconds"]:
            continue
        result.append({
            "id": exam["id"],
            "title": exam["title"],
            "duration_minutes": exam["duration_minutes"],
            "question_count": exam["question_count"],
            "total_points": exam["total_points"],
            "remaining_seconds": exam["remaining_seconds"],
            "submitted": bool(exam["submitted"]),
        })
    return result


def get_exam_for_student(exam_id, student_id):
    """Öğrenciye gönderilecek sınav paketi. Cevap anahtarı içermez."""
    exam = get_exam(exam_id)
    if exam is None or exam["status"] != STATUS_PUBLISHED or not exam["remaining_seconds"]:
        raise ValueError("Bu sınav şu an açık değil.")
    conn = get_connection()
    try:
        submitted = conn.execute(
            "SELECT 1 FROM submissions WHERE exam_id = ? AND student_id = ?",
            (exam_id, student_id),
        ).fetchone() is not None
    finally:
        conn.close()
    return {
        "id": exam["id"],
        "title": exam["title"],
        "duration_minutes": exam["duration_minutes"],
        "remaining_seconds": exam["remaining_seconds"],
        "total_points": exam["total_points"],
        "already_submitted": submitted,
        "questions": [
            {
                "id": q["question_id"],
                "position": q["position"],
                "type": q["type"],
                "text": q["text"],
                "options": q["options"],
                "points": q["points"],
            }
            for q in exam["questions"]
        ],
    }
