"""
db/submissions.py
Öğrenci cevaplarının kabulü, puanlama ve eğitmenin elle puanlaması.

Puanlama kuralı:
  çoktan seçmeli : gönderim anında otomatik (şık sırası, cevap anahtarıyla karşılaştırılır)
  klasik         : cevap beklenen cevapla BİREBİR aynıysa (büyük/küçük harf ve fazla boşluk
                   farkı yok sayılır) gönderim anında otomatik TAM PUAN verilir. Dolu ama
                   farklı cevap 0 puanla ve graded = 0 ("bekliyor") kaydedilir, eğitmen
                   grade_answer ile elle puanlar. Boş cevap 0 ve graded = 1'dir.
                   Otomatik verilen puan da eğitmen tarafından değiştirilebilir.
                   (Otomatik puanlanan satırda graded_at boştur, elle puanlananda doludur.)
Toplam puan (submissions.total_score) her puanlamada yeniden hesaplanır.

Gönderim kuralları (hepsi sunucu tarafında, istemciye güvenilmez):
  - Sınav 'published' olmalı ve bitiş zamanı + SUBMIT_GRACE_SECONDS geçmemiş olmalı.
    (Tolerans, son saniyedeki otomatik gönderimin ağ gecikmesiyle kaybolmasını önler.
     Eğitmen sınavı elle sonlandırdıysa tolerans yoktur, sınav 'closed' olur.)
  - Her öğrenci bir sınava yalnızca bir kez cevap gönderebilir.
  - Cevaplar sınavın sorularına ait ve türüne uygun olmalıdır.
  - Öğrenciye puan DÖNMEZ.

Cevap biçimi (answers sözlüğü, anahtar soru id'si):
  çoktan seçmeli : şık sırası (0, 1, 2...) ya da None (boş)
  klasik         : metin ya da None (boş)

Tüm doğrulama hataları, kullanıcıya gösterilebilir mesajlı ValueError olarak fırlatılır.
"""

import json
import math
import sqlite3
from datetime import datetime, timedelta

from db.database import get_connection
from db.exams import SUBMIT_GRACE_SECONDS, _TIME_FMT
from db.question_bank import TYPE_CLASSIC, TYPE_MULTIPLE_CHOICE

MAX_ANSWER_LENGTH = 5000


# --------------------------------------------------------------------------
# Otomatik puanlama (yalnızca çoktan seçmeli) ve ipucu
# --------------------------------------------------------------------------

def is_correct(question, given):
    """Çoktan seçmeli sorunun şıkkı doğru mu? Klasik sorular için her zaman False
    (onlar için matches_expected kullanılır, geri kalanı eğitmen puanlar)."""
    if given is None or question["type"] != TYPE_MULTIPLE_CHOICE:
        return False
    return given == int(question["answer_key"])


def normalize_text(text):
    """Karşılaştırma için: fazla boşlukları sil, Türkçe büyük/küçük harf farkını yok say."""
    text = " ".join(str(text).split())
    return text.replace("İ", "i").replace("I", "ı").lower()


def matches_expected(question, given):
    """Klasik cevap beklenen cevapla birebir aynı mı (büyük/küçük harf ve boşluk önemsiz)?
    Aynıysa gönderim anında otomatik tam puan verilir."""
    if given is None or question["type"] != TYPE_CLASSIC:
        return False
    return normalize_text(given) == normalize_text(question["answer_key"])


# --------------------------------------------------------------------------
# Cevap doğrulama
# --------------------------------------------------------------------------

def _validate_answer(question, value):
    """Cevabı doğrular, temizlenmiş halini döner (boş cevap None olur)."""
    if value is None:
        return None
    if question["type"] == TYPE_MULTIPLE_CHOICE:
        options = json.loads(question["options"])
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < len(options):
            raise ValueError("Geçersiz cevap verisi.")
        return value
    if not isinstance(value, str):
        raise ValueError("Geçersiz cevap verisi.")
    value = value.strip()
    if not value:
        return None
    if len(value) > MAX_ANSWER_LENGTH:
        raise ValueError(f"Bir cevap en fazla {MAX_ANSWER_LENGTH} karakter olabilir.")
    return value


# --------------------------------------------------------------------------
# Gönderim
# --------------------------------------------------------------------------

def submit_exam(exam_id, student_id, answers, now=None):
    """Cevapları kabul eder, otomatik puanlanabilenleri puanlar ve kaydeder.
    Dönen sözlük: submission_id, submitted_at, late (tolerans içinde gelen), total_score,
    max_score, exam_title, correct_count (otomatik doğru sayılanlar), pending_count (elle
    puanlanmayı bekleyen klasik cevap sayısı). Sunucu bunların yalnızca submitted_at kısmını öğrenciye iletir."""
    if not isinstance(answers, dict):
        raise ValueError("Geçersiz cevap verisi.")
    now = now or datetime.now()

    conn = get_connection()
    try:
        exam = conn.execute(
            "SELECT id, title, status, start_time, duration_minutes FROM exams WHERE id = ?",
            (exam_id,),
        ).fetchone()
        if exam is None:
            raise ValueError("Sınav bulunamadı.")
        if exam["status"] == "draft":
            raise ValueError("Bu sınav henüz yayınlanmadı.")
        if exam["status"] != "published" or not exam["start_time"]:
            raise ValueError("Bu sınav kapandığı için cevapların kabul edilmedi.")
        end = datetime.strptime(exam["start_time"], _TIME_FMT) + timedelta(
            minutes=exam["duration_minutes"])
        if now > end + timedelta(seconds=SUBMIT_GRACE_SECONDS):
            raise ValueError("Süre dolduğu için cevapların kabul edilmedi.")
        late = now > end

        questions = conn.execute(
            "SELECT q.id, q.type, q.options, q.answer_key, eq.points "
            "FROM exam_questions eq JOIN questions q ON q.id = eq.question_id "
            "WHERE eq.exam_id = ? ORDER BY eq.position",
            (exam_id,),
        ).fetchall()
        by_id = {q["id"]: q for q in questions}

        clean = {}
        for key, value in answers.items():
            try:
                question_id = int(key)
            except (TypeError, ValueError):
                raise ValueError("Geçersiz cevap verisi.")
            if question_id not in by_id:
                raise ValueError("Geçersiz cevap verisi.")
            clean[question_id] = _validate_answer(by_id[question_id], value)

        rows = []
        total = max_score = 0.0
        correct_count = pending_count = 0
        for q in questions:
            given = clean.get(q["id"])
            # Çoktan seçmeli: şık doğru mu. Klasik: beklenen cevapla birebir aynı mı.
            correct = is_correct(q, given) or matches_expected(q, given)
            score = q["points"] if correct else 0.0
            # Dolu ama beklenen cevapla aynı olmayan klasik cevabın puanını eğitmen verecek
            graded = 0 if (q["type"] == TYPE_CLASSIC and given is not None and not correct) else 1
            total += score
            max_score += q["points"]
            correct_count += 1 if correct else 0
            pending_count += 1 - graded
            rows.append((q["id"], None if given is None else str(given), score,
                         int(correct), graded))

        submitted_at = now.strftime(_TIME_FMT)
        try:
            cur = conn.execute(
                "INSERT INTO submissions (exam_id, student_id, submitted_at, total_score) "
                "VALUES (?, ?, ?, ?)",
                (exam_id, student_id, submitted_at, total),
            )
        except sqlite3.IntegrityError:
            raise ValueError("Bu sınava zaten cevap gönderdin.")
        for question_id, given, score, correct, graded in rows:
            conn.execute(
                "INSERT INTO answers (submission_id, question_id, given_answer, score, "
                "is_correct, graded) VALUES (?, ?, ?, ?, ?, ?)",
                (cur.lastrowid, question_id, given, score, correct, graded),
            )
        conn.execute(
            "INSERT INTO logs (student_id, exam_id, event, created_at) VALUES (?, ?, ?, ?)",
            (student_id, exam_id, "submitted_late" if late else "submitted", submitted_at),
        )
        conn.commit()
        return {
            "submission_id": cur.lastrowid, "submitted_at": submitted_at, "late": late,
            "total_score": total, "max_score": max_score, "exam_title": exam["title"],
            "correct_count": correct_count, "pending_count": pending_count,
        }
    finally:
        conn.close()


def exam_title(exam_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT title FROM exams WHERE id = ?", (exam_id,)).fetchone()
        return row["title"] if row else None
    finally:
        conn.close()


def add_log(student_id, exam_id, event):
    """logs tablosuna bir olay yazar (örn. reddedilen gönderim)."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO logs (student_id, exam_id, event, created_at) VALUES (?, ?, ?, ?)",
            (student_id, exam_id, event, datetime.now().strftime(_TIME_FMT)),
        )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Eğitmen: elle puanlama
# --------------------------------------------------------------------------

def grade_answer(answer_id, points):
    """Klasik bir cevaba eğitmenin verdiği puanı kaydeder ve gönderimin toplamını yeniler.
    Daha önce puanlanmış cevap tekrar puanlanabilir. Yeni toplam puanı döner."""
    try:
        points = float(points)
    except (TypeError, ValueError):
        raise ValueError("Puan geçerli bir sayı olmalı.")
    if not math.isfinite(points):
        raise ValueError("Puan geçerli bir sayı olmalı.")
    points = round(points, 2)

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT a.id, a.submission_id, a.question_id, a.given_answer, q.type, "
            "eq.points AS max_points, s.exam_id, s.student_id "
            "FROM answers a JOIN questions q ON q.id = a.question_id "
            "JOIN submissions s ON s.id = a.submission_id "
            "LEFT JOIN exam_questions eq ON eq.exam_id = s.exam_id AND eq.question_id = a.question_id "
            "WHERE a.id = ?",
            (answer_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Cevap bulunamadı.")
        if row["type"] != TYPE_CLASSIC:
            raise ValueError("Yalnızca klasik sorular elle puanlanır.")
        if row["given_answer"] is None:
            raise ValueError("Boş cevap puanlanamaz.")
        if row["max_points"] is None:
            raise ValueError("Bu soru artık sınavda değil.")
        max_points = row["max_points"]
        if not 0 <= points <= max_points:
            raise ValueError(f"Puan 0 ile {max_points:g} arasında olmalı.")

        now = datetime.now().strftime(_TIME_FMT)
        conn.execute(
            "UPDATE answers SET score = ?, is_correct = ?, graded = 1, graded_at = ? WHERE id = ?",
            (points, int(points >= max_points), now, answer_id),
        )
        conn.execute(
            "UPDATE submissions SET total_score = "
            "(SELECT COALESCE(SUM(score), 0) FROM answers WHERE submission_id = ?) WHERE id = ?",
            (row["submission_id"], row["submission_id"]),
        )
        conn.execute(
            "INSERT INTO logs (student_id, exam_id, event, created_at) VALUES (?, ?, ?, ?)",
            (row["student_id"], row["exam_id"],
             f"graded: soru #{row['question_id']} = {points:g}/{max_points:g}", now),
        )
        conn.commit()
        return conn.execute("SELECT total_score FROM submissions WHERE id = ?",
                            (row["submission_id"],)).fetchone()["total_score"]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Eğitmen: okuma
# --------------------------------------------------------------------------

_SUBMISSION_SQL = (
    "SELECT s.id, s.exam_id, s.student_id, u.username, u.full_name, u.class_name, "
    "s.submitted_at, s.total_score, "
    "(SELECT COUNT(*) FROM answers a WHERE a.submission_id = s.id AND a.is_correct = 1) "
    "AS correct_count, "
    "(SELECT COUNT(*) FROM answers a WHERE a.submission_id = s.id AND a.graded = 0) "
    "AS pending_count, "
    "(SELECT COALESCE(SUM(eq.points), 0) FROM exam_questions eq WHERE eq.exam_id = s.exam_id) "
    "AS max_score "
    "FROM submissions s JOIN users u ON u.id = s.student_id "
)


def list_submissions(exam_id):
    """Bir sınavın gönderimleri: öğrenci, zaman, toplam/maksimum puan, doğru sayısı ve
    puanlanmayı bekleyen cevap sayısı."""
    conn = get_connection()
    try:
        rows = conn.execute(
            _SUBMISSION_SQL + "WHERE s.exam_id = ? ORDER BY s.submitted_at, s.id", (exam_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_submission(submission_id):
    conn = get_connection()
    try:
        row = conn.execute(_SUBMISSION_SQL + "WHERE s.id = ?", (submission_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def results_summary(exam_id):
    """Sınav özeti: gönderim sayısı, ortalama, en yüksek/düşük, bekleyen cevap sayısı."""
    rows = list_submissions(exam_id)
    conn = get_connection()
    try:
        max_score = conn.execute(
            "SELECT COALESCE(SUM(points), 0) AS m FROM exam_questions WHERE exam_id = ?",
            (exam_id,),
        ).fetchone()["m"]
    finally:
        conn.close()
    scores = [r["total_score"] for r in rows]
    return {
        "submission_count": len(rows),
        "average_score": sum(scores) / len(scores) if scores else None,
        "highest_score": max(scores) if scores else None,
        "lowest_score": min(scores) if scores else None,
        "max_score": max_score,
        "pending_count": sum(r["pending_count"] for r in rows),
    }


def get_submission_answers(submission_id):
    """Bir gönderimin soru bazında cevapları (sınav sırasıyla). Her satırda answer_id,
    graded (puanlandı mı), score ve points (sorunun bu sınavdaki puanı) bulunur."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT a.id AS answer_id, a.question_id, eq.position, q.type, q.text, q.options, "
            "q.answer_key, a.given_answer, a.score, a.is_correct, a.graded, a.graded_at, "
            "eq.points "
            "FROM answers a JOIN questions q ON q.id = a.question_id "
            "JOIN submissions s ON s.id = a.submission_id "
            "LEFT JOIN exam_questions eq ON eq.exam_id = s.exam_id AND eq.question_id = a.question_id "
            "WHERE a.submission_id = ? ORDER BY eq.position",
            (submission_id,),
        ).fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        r = dict(r)
        r["options"] = json.loads(r["options"]) if r["options"] else None
        r["is_correct"] = bool(r["is_correct"])
        r["graded"] = bool(r["graded"])
        result.append(r)
    return result
