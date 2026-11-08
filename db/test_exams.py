"""
db/test_exams.py
Sınav katmanı testi. Geçici veritabanı kullanır, gerçek veriye dokunmaz.

Çalıştırma (proje kök klasöründen):
    python -m db.test_exams
"""

import json
import tempfile
from pathlib import Path

from db import database as d
from db import exams as ex
from db import question_bank as qb


def expect_error(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except ValueError as e:
        return str(e)
    raise AssertionError("ValueError bekleniyordu")


def set_start(exam_id, start_time):
    conn = d.get_connection()
    conn.execute("UPDATE exams SET start_time = ? WHERE id = ?", (start_time, exam_id))
    conn.commit()
    conn.close()


def add_submission(exam_id, student_id):
    conn = d.get_connection()
    conn.execute("INSERT INTO submissions (exam_id, student_id) VALUES (?, ?)", (exam_id, student_id))
    conn.commit()
    conn.close()


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d.DB_PATH = Path(tmp) / "test.db"
        d.init_db()
        teacher = d.get_user_by_username("egitmen")["id"]
        student = d.create_user("ogr1", "sifre123", d.ROLE_STUDENT, "Ali Veli", "1A")
        student2 = d.create_user("ogr2", "sifre123", d.ROLE_STUDENT, "Ayşe Kaya", "1A")

        cat = qb.add_category("C Dili")
        q1 = qb.add_question(qb.TYPE_MULTIPLE_CHOICE, "int kaç bayttır?", cat,
                             options=["1", "2", "4", "8"], answer_key=2, default_points=5)
        q2 = qb.add_question(qb.TYPE_CLASSIC, "Pointer nedir?", cat,
                             answer_key="GİZLİ-BEKLENEN-CEVAP", default_points=20)
        q3 = qb.add_question(qb.TYPE_CLASSIC, "Big-O nedir?", None, answer_key="Üst sınır")

        # --- oluşturma ve doğrulama
        e1 = ex.create_exam("  Vize 1  ", 45, [(q1, 30), (q2, 70)], teacher)
        e = ex.get_exam(e1)
        assert e["title"] == "Vize 1" and e["status"] == ex.STATUS_DRAFT
        assert e["question_count"] == 2 and e["total_points"] == 100
        assert [q["question_id"] for q in e["questions"]] == [q1, q2]
        assert e["start_time"] is None and e["remaining_seconds"] is None
        print("[OK] Taslak sınav oluşturuldu: 2 soru, toplam 100 puan, sıra korundu")

        print("[OK] Boş başlık:", expect_error(ex.create_exam, " ", 30, []))
        print("[OK] Sıfır süre:", expect_error(ex.create_exam, "x", 0, []))
        print("[OK] Çok uzun süre:", expect_error(ex.create_exam, "x", 601, []))
        print("[OK] Geçersiz süre:", expect_error(ex.create_exam, "x", "abc", []))
        print("[OK] Aynı soru iki kez:", expect_error(ex.create_exam, "x", 30, [(q1, 5), (q1, 5)]))
        print("[OK] Sıfır puanlı soru:", expect_error(ex.create_exam, "x", 30, [(q1, 0)]))
        print("[OK] Olmayan soru:", expect_error(ex.create_exam, "x", 30, [(999, 5)]))
        assert len(ex.list_exams()) == 1  # hatalı denemeler kayıt bırakmadı
        print("[OK] Hatalı denemeler veritabanında kayıt bırakmadı")

        # --- güncelleme (soru sırası ve puanlar)
        ex.update_exam(e1, "Vize 1 (güncel)", 60, [(q2, 50), (q3, 25), (q1, 25)])
        e = ex.get_exam(e1)
        assert e["title"] == "Vize 1 (güncel)" and e["duration_minutes"] == 60
        assert [q["question_id"] for q in e["questions"]] == [q2, q3, q1]
        assert [q["points"] for q in e["questions"]] == [50, 25, 25]
        print("[OK] Taslak güncellendi: sıra ve puan ağırlıkları değişti")

        # --- yayınlama kuralları
        empty = ex.create_exam("Boş sınav", 10, [])
        print("[OK] Boş sınavı yayınlama:", expect_error(ex.publish_exam, empty))
        print("[OK] Olmayan sınavı yayınlama:", expect_error(ex.publish_exam, 999))

        # taslak öğrenciye görünmez
        assert ex.list_active_exams(student) == []
        print("[OK] Taslak sınav öğrencilere görünmüyor")
        print("[OK] Taslağı öğrenci olarak açma:", expect_error(ex.get_exam_for_student, e1, student))

        pub = ex.publish_exam(e1)
        assert pub["status"] == ex.STATUS_PUBLISHED and pub["start_time"]
        assert 3590 <= pub["remaining_seconds"] <= 3600  # 60 dk
        print(f"[OK] Yayınlandı: {pub['remaining_seconds']} sn kaldı, bitiş {pub['end_time']}")
        print("[OK] Yayınlananı tekrar yayınlama:", expect_error(ex.publish_exam, e1))
        print("[OK] Yayındaki sınavı düzenleme:", expect_error(ex.update_exam, e1, "x", 10, []))
        print("[OK] Yayındaki sınavı silme:", expect_error(ex.delete_exam, e1))

        # --- öğrenci görünümü: cevap anahtarı sızmamalı
        active = ex.list_active_exams(student)
        assert len(active) == 1 and active[0]["id"] == e1 and active[0]["submitted"] is False
        assert active[0]["question_count"] == 3 and active[0]["total_points"] == 100
        assert "answer_key" not in json.dumps(active)
        package = ex.get_exam_for_student(e1, student)
        blob = json.dumps(package, ensure_ascii=False)
        assert "answer_key" not in blob, "cevap anahtarı alanı sızdı"
        assert "GİZLİ-BEKLENEN-CEVAP" not in blob, "klasik sorunun beklenen cevabı sızdı"
        assert "Üst sınır" not in blob
        for q in package["questions"]:
            assert set(q) == {"id", "position", "type", "text", "options", "points"}
        assert [q["id"] for q in package["questions"]] == [q2, q3, q1]
        mc = [q for q in package["questions"] if q["type"] == qb.TYPE_MULTIPLE_CHOICE][0]
        assert mc["options"] == ["1", "2", "4", "8"]
        print("[OK] Öğrenci paketinde cevap anahtarı yok (alan ve metin olarak), şıklar var")

        # eğitmen görünümünde anahtar var
        assert ex.get_exam(e1)["questions"][0]["answer_key"] == "GİZLİ-BEKLENEN-CEVAP"
        print("[OK] Eğitmen görünümünde cevap anahtarı duruyor")

        # gönderim bayrağı öğrenciye özel
        add_submission(e1, student)
        assert ex.list_active_exams(student)[0]["submitted"] is True
        assert ex.list_active_exams(student2)[0]["submitted"] is False
        assert ex.get_exam_for_student(e1, student)["already_submitted"] is True
        print("[OK] 'Gönderildi' bayrağı öğrenciye özel")

        # --- sonlandırma
        ex.close_exam(e1)
        assert ex.get_exam(e1)["status"] == ex.STATUS_CLOSED
        assert ex.list_active_exams(student2) == []
        print("[OK] Sınav sonlandırıldı, öğrencilerden kayboldu")
        print("[OK] Kapanmış sınavı sonlandırma:", expect_error(ex.close_exam, e1))
        print("[OK] Kapanmış sınavı açma:", expect_error(ex.get_exam_for_student, e1, student2))
        print("[OK] Gönderimi olan sınavı silme:", expect_error(ex.delete_exam, e1))

        # --- süre dolunca otomatik kapanma
        e2 = ex.create_exam("Quiz", 10, [(q1, 10)])
        ex.publish_exam(e2)
        assert len(ex.list_active_exams(student2)) == 1
        set_start(e2, "2000-01-01 10:00:00")   # çok eskiye al
        assert ex.list_active_exams(student2) == []
        assert ex.get_exam(e2)["status"] == ex.STATUS_CLOSED
        print("[OK] Süresi dolan sınav otomatik kapandı ve öğrencilerden kayboldu")

        # sınır: süre dolmasına az kala hâlâ açık
        e3 = ex.create_exam("Sınırda", 10, [(q1, 10)])
        ex.publish_exam(e3)
        from datetime import datetime, timedelta
        set_start(e3, (datetime.now() - timedelta(minutes=9, seconds=50)).strftime("%Y-%m-%d %H:%M:%S"))
        left = ex.list_active_exams(student2)[0]["remaining_seconds"]
        assert 0 < left <= 10, left
        print(f"[OK] Süre dolmadan {left} sn önce sınav hâlâ açık")
        set_start(e3, (datetime.now() - timedelta(minutes=10, seconds=1)).strftime("%Y-%m-%d %H:%M:%S"))
        assert ex.list_active_exams(student2) == []
        print("[OK] Süre dolduktan 1 sn sonra sınav kapalı")
        print("[OK] Süresi dolmuş sınavı açma:", expect_error(ex.get_exam_for_student, e3, student2))

        # --- kopyalama
        e4 = ex.duplicate_exam(e1, teacher)
        c = ex.get_exam(e4)
        assert c["status"] == ex.STATUS_DRAFT and c["title"] == "Vize 1 (güncel) (kopya)"
        assert [(q["question_id"], q["points"]) for q in c["questions"]] == [(q2, 50), (q3, 25), (q1, 25)]
        assert c["start_time"] is None and c["submission_count"] == 0
        print("[OK] Kopya taslak olarak oluştu, sorular ve puanlar aynı, gönderim yok")
        print("[OK] Olmayan sınavı kopyalama:", expect_error(ex.duplicate_exam, 999))

        # --- silme
        ex.delete_exam(e4)
        assert ex.get_exam(e4) is None
        ex.delete_exam(e2)   # süresi dolmuş, gönderimi yok
        print("[OK] Taslak ve gönderimsiz kapalı sınav silindi")
        print("[OK] Olmayan sınavı silme:", expect_error(ex.delete_exam, e4))

        # --- sınavdaki soru banka tarafında korunuyor (Aşama 3 kuralı)
        print("[OK] Sınavdaki soruyu bankadan silme:", expect_error(qb.delete_question, q1)[:60] + "...")

        # --- liste sırası
        ids = [x["id"] for x in ex.list_exams()]
        assert ids == sorted(ids, reverse=True)
        print("[OK] Liste yeniden eskiye sıralı")

    print("\nTüm testler geçti.")


if __name__ == "__main__":
    main()
