"""
server/test_server_submit.py
Cevap göndermenin ağ testi: yetki, süre kontrolü, puanın öğrenciye DÖNMEMESİ ve log dosyası.
Geçici veritabanı ve log klasörü, 127.0.0.1 kullanır.

Çalıştırma (proje kök klasöründen):
    python -m server.test_server_submit
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from client.network_auth_service import NetworkAuthService
from client.network_client import NetworkClient
from client.network_exam_service import NetworkExamService, ServiceError
from common import protocol
from db import database as d
from db import exams as ex
from db import question_bank as qb
from db import submissions as sub
from server.server import ExamServer


def expect_service_error(func, *args):
    try:
        func(*args)
    except ServiceError as e:
        return str(e)
    raise AssertionError("ServiceError bekleniyordu")


def connect(port, username, password):
    client = NetworkClient()
    client.connect("127.0.0.1", port)
    NetworkAuthService(client).login(username, password)
    return client, NetworkExamService(client)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d.DB_PATH = Path(tmp) / "test.db"
        log_dir = Path(tmp) / "logs"
        d.init_db()
        teacher = d.get_user_by_username("egitmen")["id"]
        s1 = d.create_user("ogr1", "sifre123", d.ROLE_STUDENT, "Ali Veli", "1A")
        d.create_user("ogr2", "sifre123", d.ROLE_STUDENT, "Ayşe Kaya", "1A")
        d.create_user("ogr3", "sifre123", d.ROLE_STUDENT, "Can Er", "1B")

        q_mc = qb.add_question(qb.TYPE_MULTIPLE_CHOICE, "int kaç bayttır?", None,
                               options=["1", "2", "4", "8"], answer_key=2)
        q_cl = qb.add_question(qb.TYPE_CLASSIC, "Pointer nedir?", None, answer_key="Adres tutar")
        exam = ex.create_exam("Vize 1", 30, [(q_mc, 60), (q_cl, 40)], teacher)

        server = ExamServer(host="127.0.0.1", port=0, log_dir=log_dir)
        server.start()

        c1, e1 = connect(server.port, "ogr1", "sifre123")
        c2, e2 = connect(server.port, "ogr2", "sifre123")
        c3, e3 = connect(server.port, "ogr3", "sifre123")
        ct, et = connect(server.port, "egitmen", "egitmen123")
        anon = NetworkClient(); anon.connect("127.0.0.1", server.port)

        # yetki
        print("[OK] Girişsiz gönderim:", expect_service_error(NetworkExamService(anon).submit_exam, exam, {}))
        print("[OK] Eğitmen hesabıyla gönderim:", expect_service_error(et.submit_exam, exam, {}))
        print("[OK] Taslak sınava gönderim:", expect_service_error(e1.submit_exam, exam, {}))
        ex.publish_exam(exam)

        # geçersiz yük
        for bad in (None, "1", True, 1.5):
            try:
                e1._call(protocol.SUBMIT_EXAM, {"exam_id": bad, "answers": {}})
                raise AssertionError("kabul edildi")
            except ServiceError:
                pass
        for bad in (None, [1], "x", 5):
            try:
                e1._call(protocol.SUBMIT_EXAM, {"exam_id": exam, "answers": bad})
                raise AssertionError("kabul edildi")
            except ServiceError:
                pass
        print("[OK] Geçersiz exam_id ve answers biçimleri reddedildi")

        # başarılı gönderim: yanıtta puan yok
        protocol.send_message(c1._sock, {
            "type": protocol.SUBMIT_EXAM, "token": c1.token,
            "data": {"exam_id": exam, "answers": {str(q_mc): 2, str(q_cl): "adres TUTAR"}}})
        raw = protocol.recv_message(c1._sock)
        assert raw["ok"] is True
        blob = json.dumps(raw, ensure_ascii=False).lower()
        for forbidden in ("score", "puan", "correct", "answer_key", "total"):
            assert forbidden not in blob, f"yanıtta '{forbidden}' var: {blob}"
        assert set(raw["data"]) == {"submitted_at"}
        print("[OK] Gönderim kabul edildi, yanıtta puan/doğruluk bilgisi yok:", raw["data"])

        rows = sub.list_submissions(exam)
        assert len(rows) == 1 and rows[0]["username"] == "ogr1"
        assert rows[0]["total_score"] == 60 and rows[0]["pending_count"] == 1
        print("[OK] Sunucu kaydetti: ogr1 = 60 (çoktan seçmeli otomatik, klasik cevap puanlanmayı bekliyor)")
        answer = [a for a in sub.get_submission_answers(rows[0]["id"]) if a["type"] == qb.TYPE_CLASSIC][0]
        assert sub.grade_answer(answer["answer_id"], 40) == 100
        print("[OK] Eğitmen klasik cevabı puanladı: ogr1 = 100")

        print("[OK] İkinci gönderim:", expect_service_error(e1.submit_exam, exam, {str(q_mc): 1}))
        assert sub.list_submissions(exam)[0]["total_score"] == 100   # ilk puan değişmedi
        listed = e1.list_exams()
        assert listed[0]["submitted"] is True
        print("[OK] Öğrenci listesinde 'gönderildi' işaretli, ilk puan değişmedi")

        # başka öğrenci kendi adına gönderir, başkasının adına gönderemez (kimlik token'dan)
        r = e2.submit_exam(exam, {str(q_mc): 0})
        assert [x["username"] for x in sub.list_submissions(exam)] == ["ogr1", "ogr2"]
        assert sub.list_submissions(exam)[1]["total_score"] == 0
        print("[OK] Başka öğrenci kendi adına gönderdi:", r["submitted_at"])

        # süre kuralları (sunucu saatine göre)
        set_start = lambda dt: _set_start(exam, dt)
        set_start(datetime.now() - timedelta(minutes=30, seconds=2))
        e3.submit_exam(exam, {str(q_mc): 2})
        print("[OK] Süre dolduktan 2 sn sonra (tolerans) kabul edildi")
        assert [x["username"] for x in sub.list_submissions(exam)][-1] == "ogr3"

        exam2 = ex.create_exam("Quiz", 10, [(q_mc, 10)], teacher)
        ex.publish_exam(exam2)
        _set_start(exam2, datetime.now() - timedelta(minutes=10, seconds=ex.SUBMIT_GRACE_SECONDS + 3))
        print("[OK] Tolerans dışı gönderim:", expect_service_error(e1.submit_exam, exam2, {str(q_mc): 2}))
        assert sub.list_submissions(exam2) == []

        exam3 = ex.create_exam("Elle kapanan", 60, [(q_mc, 10)], teacher)
        ex.publish_exam(exam3)
        ex.close_exam(exam3)
        print("[OK] Elle sonlandırılan sınava gönderim:", expect_service_error(e2.submit_exam, exam3, {str(q_mc): 2}))

        # log dosyası
        text = (log_dir / "submissions.log").read_text(encoding="utf-8")
        lines = text.strip().splitlines()
        print("  log dosyası:")
        for line in lines:
            print("   ", line)
        kinds = [l.split(" | ")[1] for l in lines]
        # sıra: taslak(red), ogr1(kabul), ogr1 tekrar(red), ogr2(kabul), ogr3 tolerans(kabul),
        #       süresi geçmiş quiz(red), elle kapanan(red)
        assert kinds == ["REDDEDILDI", "GONDERIM", "REDDEDILDI", "GONDERIM", "GONDERIM",
                         "REDDEDILDI", "REDDEDILDI"], kinds
        accepted = [l for l in lines if " | GONDERIM | " in l]
        assert len(accepted) == 3
        assert 'sinav=#1 "Vize 1"' in accepted[0] and "ogrenci=ogr1 (Ali Veli)" in accepted[0]
        assert "ip=127.0.0.1" in accepted[0]
        assert datetime.strptime(accepted[0].split(" | ")[0], "%Y-%m-%d %H:%M:%S")
        assert "gec=evet" in accepted[2]
        rejected = [l for l in lines if " | REDDEDILDI | " in l]
        assert any("zaten cevap" in l for l in rejected)
        assert any("Süre dolduğu" in l for l in rejected)
        assert any("kapandığı" in l for l in rejected)
        assert any("henüz yayınlanmadı" in l for l in rejected)
        assert "password" not in text.lower() and "sifre123" not in text
        print("[OK] Log dosyası: 3 kabul (zaman, sınav, öğrenci, IP), reddedilenler nedeniyle yazıldı, şifre yok")

        conn = d.get_connection()
        events = [r["event"] for r in conn.execute("SELECT event FROM logs ORDER BY id")]
        conn.close()
        assert sum(e.startswith("rejected") for e in events) >= 3 and "submitted" in events
        print("[OK] logs tablosunda hem kabuller hem redler var")

        server.stop()

    print("\nTüm testler geçti.")


def _set_start(exam_id, start):
    conn = d.get_connection()
    conn.execute("UPDATE exams SET start_time = ? WHERE id = ?",
                 (start.strftime("%Y-%m-%d %H:%M:%S"), exam_id))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
