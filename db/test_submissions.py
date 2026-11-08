"""
db/test_submissions.py
Cevap kabulü, otomatik (çoktan seçmeli) ve elle (klasik) puanlama testi.
Geçici veritabanı kullanır.

Çalıştırma (proje kök klasöründen):
    python -m db.test_submissions
"""

import math
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from db import database as d
from db import exams as ex
from db import question_bank as qb
from db import submissions as sub

FMT = "%Y-%m-%d %H:%M:%S"
GRACE_PLUS = ex.SUBMIT_GRACE_SECONDS + 2


def expect_error(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except ValueError as e:
        return str(e)
    raise AssertionError("ValueError bekleniyordu")


def set_start(exam_id, start):
    conn = d.get_connection()
    conn.execute("UPDATE exams SET start_time = ? WHERE id = ?", (start.strftime(FMT), exam_id))
    conn.commit()
    conn.close()


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d.DB_PATH = Path(tmp) / "test.db"
        d.init_db()
        teacher = d.get_user_by_username("egitmen")["id"]
        s1 = d.create_user("ogr1", "sifre123", d.ROLE_STUDENT, "Ali Veli", "1A")
        s2 = d.create_user("ogr2", "sifre123", d.ROLE_STUDENT, "Ayşe Kaya", "1A")
        s3 = d.create_user("ogr3", "sifre123", d.ROLE_STUDENT, "Can Er", "1B")

        q_mc = qb.add_question(qb.TYPE_MULTIPLE_CHOICE, "int kaç bayttır?", None,
                               options=["1", "2", "4", "8"], answer_key=2)
        q_cl = qb.add_question(qb.TYPE_CLASSIC, "Pointer nedir?", None, answer_key="Adres tutar")
        q_mc2 = qb.add_question(qb.TYPE_MULTIPLE_CHOICE, "Hangisi O(n log n)?", None,
                                options=["Bubble sort", "Merge sort"], answer_key=1)
        exam = ex.create_exam("Vize 1", 30, [(q_mc, 40), (q_cl, 35), (q_mc2, 25)], teacher)

        # --- yayında olmayan sınava gönderim
        assert "henüz yayınlanmadı" in expect_error(sub.submit_exam, exam, s1, {})
        print("[OK] Taslağa gönderim: henüz yayınlanmadı uyarısı")
        ex.publish_exam(exam)
        print("[OK] Olmayan sınava gönderim:", expect_error(sub.submit_exam, 999, s1, {}))

        # --- gönderim: çoktan seçmeli otomatik, klasik BEKLİYOR
        r = sub.submit_exam(exam, s1, {str(q_mc): 2, str(q_cl): "  Bellekte adres tutar  ", str(q_mc2): 0})
        assert r["total_score"] == 40 and r["max_score"] == 100
        assert r["correct_count"] == 1 and r["pending_count"] == 1 and r["late"] is False
        print("[OK] Gönderim: doğru şık 40 puan, yanlış şık 0, klasik cevap puanlanmayı BEKLİYOR (toplam 40/100)")

        details = sub.get_submission_answers(r["submission_id"])
        assert [x["question_id"] for x in details] == [q_mc, q_cl, q_mc2]
        assert [x["given_answer"] for x in details] == ["2", "Bellekte adres tutar", "0"]
        assert [x["graded"] for x in details] == [True, False, True]
        assert [x["score"] for x in details] == [40, 0, 0]
        assert [x["is_correct"] for x in details] == [True, False, False]
        assert [x["points"] for x in details] == [40, 35, 25]
        print("[OK] Cevap satırları: klasik cevap graded=False, çoktan seçmeliler puanlanmış")

        # boş klasik cevap puanlanmayı BEKLEMEZ
        r2 = sub.submit_exam(exam, s2, {str(q_mc): None, str(q_cl): "   "})
        assert r2["total_score"] == 0 and r2["pending_count"] == 0
        details2 = sub.get_submission_answers(r2["submission_id"])
        assert [x["given_answer"] for x in details2] == [None, None, None] and len(details2) == 3
        assert all(x["graded"] for x in details2)
        print("[OK] Boş cevaplar 0 puan ve bekleme yok, yine de her soru için satır var")

        # --- tek gönderim
        print("[OK] İkinci gönderim:", expect_error(sub.submit_exam, exam, s1, {str(q_mc): 2}))
        assert len(sub.list_submissions(exam)) == 2

        # --- cevap doğrulama (kayıt bırakmamalı)
        bad_answers = [
            ("başka sınavın sorusu", {"99999": 1}),
            ("sayı olmayan anahtar", {"abc": 1}),
            ("şık aralık dışı", {str(q_mc): 4}),
            ("negatif şık", {str(q_mc): -1}),
            ("bool şık", {str(q_mc): True}),
            ("metin şık", {str(q_mc): "2"}),
            ("kesirli şık", {str(q_mc): 1.5}),
            ("klasik soruya sayı", {str(q_cl): 5}),
            ("çok uzun cevap", {str(q_cl): "a" * (sub.MAX_ANSWER_LENGTH + 1)}),
        ]
        for name, answers in bad_answers:
            print(f"[OK] Geçersiz cevap ({name}):", expect_error(sub.submit_exam, exam, s3, answers))
        print("[OK] Cevaplar sözlük değil:", expect_error(sub.submit_exam, exam, s3, [1, 2]))
        assert len(sub.list_submissions(exam)) == 2
        print("[OK] Hatalı denemeler kayıt bırakmadı, öğrenci hâlâ gönderebilir")

        # --- süre kuralları
        now = datetime.now()
        set_start(exam, now - timedelta(minutes=30, seconds=3))   # süre 3 sn önce doldu
        r3 = sub.submit_exam(exam, s3, {str(q_mc): 2})
        assert r3["late"] is True and r3["total_score"] == 40
        print("[OK] Süre dolduktan 3 sn sonra (tolerans içinde) kabul edildi, 'late' işaretlendi")
        assert ex.list_active_exams(s3) == []
        print("[OK] Tolerans süresince sınav öğrencilere görünmüyor")

        exam2 = ex.create_exam("Quiz", 10, [(q_mc, 10)], teacher)
        ex.publish_exam(exam2)
        set_start(exam2, now - timedelta(minutes=10, seconds=GRACE_PLUS))
        print("[OK] Tolerans dışında gönderim:", expect_error(sub.submit_exam, exam2, s1, {str(q_mc): 2}))
        assert sub.list_submissions(exam2) == []

        exam3 = ex.create_exam("Elle kapanan", 60, [(q_mc, 10)], teacher)
        ex.publish_exam(exam3)
        ex.close_exam(exam3)
        print("[OK] Elle sonlandırılan sınava gönderim:", expect_error(sub.submit_exam, exam3, s1, {str(q_mc): 2}))

        set_start(exam, now - timedelta(minutes=30, seconds=GRACE_PLUS))
        assert ex.get_exam(exam)["status"] == "closed"
        print("[OK] Tolerans bitince sınav otomatik 'kapandı' oldu")

        # --- eğitmen listesi ve özeti (puanlamadan önce)
        rows = sub.list_submissions(exam)
        assert [(x["username"], x["total_score"], x["pending_count"], x["max_score"]) for x in rows] == [
            ("ogr1", 40, 1, 100), ("ogr2", 0, 0, 100), ("ogr3", 40, 0, 100)]
        summary = sub.results_summary(exam)
        assert summary["submission_count"] == 3 and summary["pending_count"] == 1
        assert summary["highest_score"] == 40 and summary["lowest_score"] == 0
        assert abs(summary["average_score"] - 80 / 3) < 1e-9 and summary["max_score"] == 100
        print("[OK] Liste ve özet: ogr1 40 (1 cevap bekliyor), ogr2 0, ogr3 40, ortalama 26.7")
        empty = sub.results_summary(exam3)
        assert empty["submission_count"] == 0 and empty["average_score"] is None and empty["max_score"] == 10
        print("[OK] Gönderimsiz sınavın özeti boş değerlerle döndü")

        # --- ELLE PUANLAMA
        classic_answer = [x for x in sub.get_submission_answers(r["submission_id"]) if x["type"] == qb.TYPE_CLASSIC][0]
        aid = classic_answer["answer_id"]

        total = sub.grade_answer(aid, 20)
        assert total == 60
        info = sub.get_submission(r["submission_id"])
        assert info["total_score"] == 60 and info["pending_count"] == 0 and info["correct_count"] == 1
        detail = [x for x in sub.get_submission_answers(r["submission_id"]) if x["answer_id"] == aid][0]
        assert detail["graded"] and detail["score"] == 20 and not detail["is_correct"] and detail["graded_at"]
        print("[OK] Elle puanlama: klasik cevaba 20/35 verildi, toplam 40 -> 60, bekleyen kalmadı")

        assert sub.grade_answer(aid, 35) == 75
        detail = [x for x in sub.get_submission_answers(r["submission_id"]) if x["answer_id"] == aid][0]
        assert detail["is_correct"] and detail["score"] == 35
        print("[OK] Yeniden puanlama: tam puan 35 verildi, toplam 75, cevap 'doğru' sayıldı")
        assert sub.grade_answer(aid, 12.345) == 40 + 12.35
        print("[OK] Ondalıklı puan iki basamağa yuvarlanıyor (12.345 -> 12.35)")
        assert sub.grade_answer(aid, 0) == 40
        assert sub.grade_answer(aid, 35) == 75
        print("[OK] Sıfır puan verilebiliyor, sonra tekrar tam puan")

        print("[OK] Üst sınırı aşan puan:", expect_error(sub.grade_answer, aid, 36))
        print("[OK] Negatif puan:", expect_error(sub.grade_answer, aid, -1))
        print("[OK] Sayı olmayan puan:", expect_error(sub.grade_answer, aid, "abc"))
        print("[OK] NaN puan:", expect_error(sub.grade_answer, aid, math.nan))
        print("[OK] Sonsuz puan:", expect_error(sub.grade_answer, aid, math.inf))
        print("[OK] Boş puan:", expect_error(sub.grade_answer, aid, None))
        assert sub.get_submission(r["submission_id"])["total_score"] == 75   # hatalı denemeler değiştirmedi

        mc_answer = [x for x in sub.get_submission_answers(r["submission_id"]) if x["type"] == qb.TYPE_MULTIPLE_CHOICE][0]
        print("[OK] Çoktan seçmeliyi elle puanlama:", expect_error(sub.grade_answer, mc_answer["answer_id"], 5))
        blank = [x for x in sub.get_submission_answers(r2["submission_id"]) if x["type"] == qb.TYPE_CLASSIC][0]
        print("[OK] Boş klasik cevabı puanlama:", expect_error(sub.grade_answer, blank["answer_id"], 5))
        print("[OK] Olmayan cevabı puanlama:", expect_error(sub.grade_answer, 999999, 5))

        summary = sub.results_summary(exam)
        assert summary["pending_count"] == 0
        assert abs(summary["average_score"] - (75 + 0 + 40) / 3) < 1e-9
        print("[OK] Puanlama sonrası özet: bekleyen 0, ortalama", round(summary["average_score"], 1))

        # --- log kayıtları
        conn = d.get_connection()
        events = [r_["event"] for r_ in conn.execute("SELECT event FROM logs ORDER BY id")]
        conn.close()
        assert events[:3] == ["submitted", "submitted", "submitted_late"]
        graded = [e for e in events if e.startswith("graded")]
        assert len(graded) == 5 and graded[1] == f"graded: soru #{q_cl} = 35/35", graded
        print("[OK] logs tablosu: gönderimler ve her puanlama kaydedildi")

        # --- ipucu fonksiyonu (puan vermez)
        q = {"type": qb.TYPE_CLASSIC, "answer_key": "Işık hızı"}
        assert sub.matches_expected(q, "IŞIK   HIZI") and sub.matches_expected(q, "ışık hızı")
        assert not sub.matches_expected(q, "isik hizi") and not sub.matches_expected(q, None)
        assert not sub.matches_expected({"type": qb.TYPE_MULTIPLE_CHOICE, "answer_key": "1"}, "1")
        assert sub.is_correct({"type": qb.TYPE_CLASSIC, "answer_key": "x"}, "x") is False   # klasik için matches_expected kullanılır
        print("[OK] Cevap karşılaştırma fonksiyonu: Türkçe büyük/küçük harf ve boşluklar önemsiz, harf farkı önemli")

        # --- KLASİK CEVAP BİREBİR AYNIYSA OTOMATİK TAM PUAN
        exam4 = ex.create_exam("Otomatik klasik", 30, [(q_cl, 50), (q_mc, 50)], teacher)
        ex.publish_exam(exam4)

        ra = sub.submit_exam(exam4, s2, {str(q_cl): "  ADRES    tutar ", str(q_mc): 2})
        assert ra["total_score"] == 100 and ra["pending_count"] == 0 and ra["correct_count"] == 2
        da = sub.get_submission_answers(ra["submission_id"])
        cl = [x for x in da if x["type"] == qb.TYPE_CLASSIC][0]
        assert cl["graded"] and cl["is_correct"] and cl["score"] == 50 and cl["graded_at"] is None
        print("[OK] Klasik cevap beklenen cevapla birebir aynı: anında tam puan (toplam 100), bekleme yok, graded_at boş (otomatik)")

        rb = sub.submit_exam(exam4, s1, {str(q_cl): "adres tutar kadar", str(q_mc): 2})
        assert rb["total_score"] == 50 and rb["pending_count"] == 1 and rb["correct_count"] == 1
        db_ = [x for x in sub.get_submission_answers(rb["submission_id"]) if x["type"] == qb.TYPE_CLASSIC][0]
        assert not db_["graded"] and db_["score"] == 0
        print("[OK] Farklı klasik cevap: 0 puan ve 'bekliyor', yalnızca çoktan seçmeli puan aldı (50)")

        rc = sub.submit_exam(exam4, s3, {str(q_mc): 2})
        assert rc["pending_count"] == 0 and rc["total_score"] == 50   # boş klasik cevap: bekleme yok
        print("[OK] Boş klasik cevap: 0 puan, bekleme yok")

        # otomatik verilen puan eğitmen tarafından değiştirilebilir
        assert sub.grade_answer(cl["answer_id"], 10) == 60
        cl2 = [x for x in sub.get_submission_answers(ra["submission_id"]) if x["type"] == qb.TYPE_CLASSIC][0]
        assert cl2["score"] == 10 and not cl2["is_correct"] and cl2["graded_at"]
        print("[OK] Otomatik tam puan, eğitmen tarafından 10'a düşürüldü (toplam 60, graded_at doldu)")

        # bekleyen cevabı eğitmen puanlar
        assert sub.grade_answer(db_["answer_id"], 30) == 80
        print("[OK] Bekleyen cevap elle puanlandı (50 -> 80)")
        summary4 = sub.results_summary(exam4)
        assert summary4["pending_count"] == 0 and summary4["submission_count"] == 3
        print("[OK] Özet: 3 gönderim, bekleyen 0")

    print("\nTüm testler geçti.")


if __name__ == "__main__":
    main()
