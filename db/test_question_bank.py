"""
db/test_question_bank.py
Soru bankası testi. Geçici veritabanı kullanır, gerçek veriye dokunmaz.

Çalıştırma (proje kök klasöründen):
    python -m db.test_question_bank
"""

import tempfile
from pathlib import Path

from db import database as d
from db import question_bank as qb


def expect_error(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except ValueError as e:
        return str(e)
    raise AssertionError("ValueError bekleniyordu")


def add_exam(title, status):
    conn = d.get_connection()
    cur = conn.execute(
        "INSERT INTO exams (title, duration_minutes, status) VALUES (?, 30, ?)", (title, status)
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def attach(exam_id, question_id):
    conn = d.get_connection()
    conn.execute(
        "INSERT INTO exam_questions (exam_id, question_id, points, position) VALUES (?, ?, 10, 1)",
        (exam_id, question_id),
    )
    conn.commit()
    conn.close()


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d.DB_PATH = Path(tmp) / "test.db"
        d.init_db()

        # --- kategoriler
        c_c = qb.add_category("  C Dili  ")
        c_algo = qb.add_category("Algoritmalar")
        assert [c["name"] for c in qb.list_categories()] == ["Algoritmalar", "C Dili"]
        print("[OK] Kategori ekleme, boşluklar temizlendi, ada göre sıralı")
        print("[OK] Aynı kategori (büyük/küçük harf farkıyla):", expect_error(qb.add_category, "c dili"))
        print("[OK] Boş kategori:", expect_error(qb.add_category, "   "))
        qb.rename_category(c_algo, "Algoritma Analizi")
        print("[OK] Yeniden adlandırma:", qb.list_categories()[0]["name"])
        print("[OK] Başka kategorinin adına yeniden adlandırma:", expect_error(qb.rename_category, c_algo, "C Dili"))
        qb.rename_category(c_algo, "Algoritma Analizi")  # kendi adına geçiş hata vermemeli

        # --- çoktan seçmeli
        q1 = qb.add_question(qb.TYPE_MULTIPLE_CHOICE, "int kaç bayttır?", c_c,
                             options=["1", "2", "4", "8"], answer_key=2, default_points=5)
        q = qb.get_question(q1)
        assert q["options"] == ["1", "2", "4", "8"] and q["answer_key"] == "2"
        assert q["category_name"] == "C Dili" and q["default_points"] == 5
        print("[OK] Çoktan seçmeli soru eklendi, şıklar JSON'dan geri okundu")

        print("[OK] Tek şık:", expect_error(qb.add_question, qb.TYPE_MULTIPLE_CHOICE, "x", None, ["a"], 0))
        print("[OK] Yedi şık:", expect_error(qb.add_question, qb.TYPE_MULTIPLE_CHOICE, "x", None, list("abcdefg"), 0))
        print("[OK] Boş şık:", expect_error(qb.add_question, qb.TYPE_MULTIPLE_CHOICE, "x", None, ["a", " "], 0))
        print("[OK] Aynı şıklar:", expect_error(qb.add_question, qb.TYPE_MULTIPLE_CHOICE, "x", None, ["a", "A"], 0))
        print("[OK] Doğru şık seçilmemiş:", expect_error(qb.add_question, qb.TYPE_MULTIPLE_CHOICE, "x", None, ["a", "b"], None))
        print("[OK] Doğru şık aralık dışı:", expect_error(qb.add_question, qb.TYPE_MULTIPLE_CHOICE, "x", None, ["a", "b"], 5))
        print("[OK] Boş soru metni:", expect_error(qb.add_question, qb.TYPE_CLASSIC, "  ", None, None, "cevap"))
        print("[OK] Sıfır puan:", expect_error(qb.add_question, qb.TYPE_CLASSIC, "x", None, None, "c", 0))
        print("[OK] Geçersiz puan:", expect_error(qb.add_question, qb.TYPE_CLASSIC, "x", None, None, "c", "abc"))
        print("[OK] Geçersiz tür:", expect_error(qb.add_question, "code", "x", None, None, "c"))
        print("[OK] Olmayan kategori:", expect_error(qb.add_question, qb.TYPE_CLASSIC, "x", 999, None, "c"))

        # --- klasik
        q2 = qb.add_question(qb.TYPE_CLASSIC, "Pointer nedir?", c_c, answer_key="  Adres tutan değişken ")
        assert qb.get_question(q2)["answer_key"] == "Adres tutan değişken"
        assert qb.get_question(q2)["options"] is None
        print("[OK] Klasik soru eklendi")
        print("[OK] Beklenen cevap boş:", expect_error(qb.add_question, qb.TYPE_CLASSIC, "x", None, None, " "))
        q3 = qb.add_question(qb.TYPE_CLASSIC, "Big-O nedir?", None, answer_key="Üst sınır")

        # --- filtreleme
        assert len(qb.list_questions()) == 3
        assert len(qb.list_questions(category_id=c_c)) == 2
        assert len(qb.list_questions(category_id=qb.UNCATEGORIZED)) == 1
        assert len(qb.list_questions(qtype=qb.TYPE_CLASSIC)) == 2
        assert len(qb.list_questions(category_id=c_c, qtype=qb.TYPE_CLASSIC)) == 1
        assert len(qb.list_questions(search="POINTER")) == 1
        assert len(qb.list_questions(search="yok böyle")) == 0
        assert [x["id"] for x in qb.list_questions()] == [q3, q2, q1]
        print("[OK] Kategori, tür ve arama filtreleri, yeniden eskiye sıralama")
        counts = {c["name"]: c["question_count"] for c in qb.list_categories()}
        assert counts == {"Algoritma Analizi": 0, "C Dili": 2}
        print("[OK] Kategori başına soru sayısı")

        # --- düzenleme
        qb.update_question(q1, qb.TYPE_MULTIPLE_CHOICE, "int genelde kaç bayttır?", c_algo,
                           options=["2", "4", "8"], answer_key=1, default_points=7.5)
        q = qb.get_question(q1)
        assert q["text"] == "int genelde kaç bayttır?" and q["options"] == ["2", "4", "8"]
        assert q["category_name"] == "Algoritma Analizi" and q["default_points"] == 7.5
        print("[OK] Soru düzenlendi")
        qb.update_question(q1, qb.TYPE_CLASSIC, "Türü değişti", None, answer_key="cevap")
        q = qb.get_question(q1)
        assert q["type"] == qb.TYPE_CLASSIC and q["options"] is None and q["category_id"] is None
        print("[OK] Tür değiştirme (çoktan seçmeli -> klasik)")
        print("[OK] Olmayan soruyu düzenleme:", expect_error(qb.update_question, 999, qb.TYPE_CLASSIC, "x", None, None, "c"))

        # --- sınavda kullanılan sorular
        draft = add_exam("Taslak sınav", "draft")
        live = add_exam("Vize 1", "published")
        attach(draft, q2)
        attach(live, q2)
        print("[OK] Yayınlanmış sınavdaki soruyu düzenleme:", expect_error(
            qb.update_question, q2, qb.TYPE_CLASSIC, "Değişti", None, None, "c"))
        print("[OK] Sınavdaki soruyu silme:", expect_error(qb.delete_question, q2))
        attach(draft, q3)
        qb.update_question(q3, qb.TYPE_CLASSIC, "Sadece taslakta: düzenlenebilir", None, None, "x")
        print("[OK] Sadece taslak sınavdaki soru düzenlenebiliyor")
        print("[OK] Taslak sınavdaki soruyu silme:", expect_error(qb.delete_question, q3))

        # --- silme
        qb.delete_question(q1)
        assert qb.get_question(q1) is None
        print("[OK] Kullanılmayan soru silindi")
        print("[OK] Olmayan soruyu silme:", expect_error(qb.delete_question, q1))

        # --- kategori silme: sorular kalır, kategorisiz olur
        n = qb.delete_category(c_c)
        assert n == 1 and qb.get_question(q2)["category_id"] is None
        print(f"[OK] Kategori silindi, {n} soru kategorisiz kaldı, soru silinmedi")
        print("[OK] Olmayan kategoriyi silme:", expect_error(qb.delete_category, c_c))

    print("\nTüm testler geçti.")


if __name__ == "__main__":
    main()
