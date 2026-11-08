"""
server/test_server_exams.py
Sınav isteklerinin ağ testi: yetki kontrolü ve CEVAP ANAHTARININ AĞA ÇIKMAMASI.
Geçici veritabanı ve 127.0.0.1 kullanır, gerçek veriye dokunmaz.

Çalıştırma (proje kök klasöründen):
    python -m server.test_server_exams
"""

import json
import tempfile
from pathlib import Path

from client.network_auth_service import NetworkAuthService
from client.network_client import NetworkClient
from client.network_exam_service import NetworkExamService, ServiceError
from common import protocol
from db import database as d
from db import exams as ex
from db import question_bank as qb
from server.server import ExamServer
from ui.auth_service import AuthError


def expect_service_error(func, *args):
    try:
        func(*args)
    except ServiceError as e:
        return str(e)
    raise AssertionError("ServiceError bekleniyordu")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d.DB_PATH = Path(tmp) / "test.db"
        d.init_db()
        teacher = d.get_user_by_username("egitmen")["id"]
        d.create_user("ogr1", "sifre123", d.ROLE_STUDENT, "Ali Veli", "1A")

        q1 = qb.add_question(qb.TYPE_MULTIPLE_CHOICE, "int kaç bayttır?", None,
                             options=["1", "2", "4", "8"], answer_key=2, default_points=5)
        q2 = qb.add_question(qb.TYPE_CLASSIC, "Pointer nedir?", None,
                             answer_key="GİZLİ-BEKLENEN-CEVAP", default_points=20)
        exam_id = ex.create_exam("Vize 1", 30, [(q1, 40), (q2, 60)], teacher)

        server = ExamServer(host="127.0.0.1", port=0)
        server.start()

        student_client, teacher_client, anon_client = NetworkClient(), NetworkClient(), NetworkClient()
        for c in (student_client, teacher_client, anon_client):
            c.connect("127.0.0.1", server.port)
        student_auth = NetworkAuthService(student_client)
        teacher_auth = NetworkAuthService(teacher_client)
        student_exams = NetworkExamService(student_client)
        teacher_exams = NetworkExamService(teacher_client)
        anon_exams = NetworkExamService(anon_client)

        # giriş yapmadan
        print("[OK] Girişsiz sınav listesi:", expect_service_error(anon_exams.list_exams))
        print("[OK] Girişsiz sınav paketi:", expect_service_error(anon_exams.get_exam, exam_id))

        student_auth.login("ogr1", "sifre123")
        teacher_auth.login("egitmen", "egitmen123")

        # eğitmen hesabı öğrenci isteklerini kullanamaz
        print("[OK] Eğitmen hesabıyla sınav listesi:", expect_service_error(teacher_exams.list_exams))
        print("[OK] Eğitmen hesabıyla sınav paketi:", expect_service_error(teacher_exams.get_exam, exam_id))

        # taslak öğrenciye görünmez
        assert student_exams.list_exams() == []
        print("[OK] Taslak sınav ağdan da görünmüyor")
        print("[OK] Taslağı ağdan açma:", expect_service_error(student_exams.get_exam, exam_id))

        # eğitmen yayınlar -> öğrenci görür
        ex.publish_exam(exam_id)
        listed = student_exams.list_exams()
        assert len(listed) == 1 and listed[0]["title"] == "Vize 1"
        assert listed[0]["question_count"] == 2 and listed[0]["total_points"] == 100
        assert 1790 <= listed[0]["remaining_seconds"] <= 1800 and listed[0]["submitted"] is False
        print(f"[OK] Yayınlanan sınav öğrenciye göründü ({listed[0]['remaining_seconds']} sn kaldı)")

        # paket: ham ağ yanıtında anahtar yok
        protocol.send_message(student_client._sock, {
            "type": protocol.GET_EXAM, "data": {"exam_id": exam_id}, "token": student_client.token})
        raw = protocol.recv_message(student_client._sock)
        blob = json.dumps(raw, ensure_ascii=False)
        assert raw["ok"] is True
        assert "answer_key" not in blob, "cevap anahtarı alanı ağa çıktı"
        assert "GİZLİ-BEKLENEN-CEVAP" not in blob, "beklenen cevap ağa çıktı"
        package = raw["data"]["exam"]
        assert [q["id"] for q in package["questions"]] == [q1, q2]
        assert package["questions"][0]["options"] == ["1", "2", "4", "8"]
        assert [q["points"] for q in package["questions"]] == [40, 60]
        print("[OK] Ham ağ yanıtında cevap anahtarı yok, sorular, şıklar ve puanlar var")

        # geçersiz istekler
        for bad in (None, "1", True, 1.5, 999):
            try:
                student_exams._call(protocol.GET_EXAM, {"exam_id": bad})
                raise AssertionError(f"exam_id={bad!r} kabul edildi")
            except ServiceError:
                pass
        print("[OK] Geçersiz veya olmayan exam_id reddedildi")

        # eğitmen sonlandırır -> öğrenciden kaybolur
        ex.close_exam(exam_id)
        assert student_exams.list_exams() == []
        print("[OK] Eğitmen sonlandırınca sınav öğrencilerden kayboldu")
        print("[OK] Kapanmış sınavı ağdan açma:", expect_service_error(student_exams.get_exam, exam_id))

        # sunucu durunca
        server.stop()
        try:
            student_exams.list_exams()
            raise AssertionError("ServiceError bekleniyordu")
        except ServiceError as e:
            assert e.connection_lost
            print("[OK] Sunucu durunca connection_lost=True:", e)

    print("\nTüm testler geçti.")


if __name__ == "__main__":
    main()
