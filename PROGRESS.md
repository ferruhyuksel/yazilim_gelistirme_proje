# İlerleme Durumu

## Teknoloji
Python 3 + PySide6 + SQLite + socket/threading + JSON (Linux)

## Karar Verilenler
- Eğitmen hesabı sabit (egitmen / egitmen123, ilk girişte değiştirilecek).
- Öğrenci hesabı: kayıt ekranı + eğitmenin ekleyebilmesi (eğitmen tarafı henüz yok).
- Mimari: iki ayrı uygulama. Eğitmen uygulaması DB + sunucuyu çalıştırır, öğrenci
  uygulaması DB içermez, sadece sunucuya bağlanır.
- Protokol: TCP, 4 bayt uzunluk başlığı + UTF-8 JSON. Port 5050.
- Kimlik: giriş sonrası token. Token yalnızca girişin yapıldığı bağlantıda geçerli,
  kullanıcı kimliği istemciden değil token'dan bulunur.
- Ağdan gelen kayıt isteği rolü her zaman "öğrenci" yapar (sunucuda sabit).
- Arayüz, servis katmanı üzerinden konuşur: LocalAuthService (eğitmen) ve
  NetworkAuthService (öğrenci) aynı metotlara sahip.

## Tamamlananlar
- [x] Aşama 6: Eğitmen Sonuçlar ekranı, KLASİK SORULARIN ELLE PUANLANMASI, Loglar sekmesi
      (ui/results_view.py, ui/grading_dialog.py, ui/log_view.py; veritabanı migration'ı eklendi)
- [x] Aşama 4: Sınav oluşturma ve dağıtım (db/exams.py; testler: python -m db.test_exams,
      python -m server.test_server_exams; eğitmende 'Sınavlar' sekmesi, öğrencide canlı sınav listesi)
- [x] Aşama 3: Soru bankası (db/question_bank.py, test: python -m db.test_question_bank;
      eğitmen panelinde 'Soru bankası' sekmesi, kategori yönetimi)
- [x] Aşama 2b: main_instructor.py (sunucu + canlı istemci listesi), main_student.py (bağlan + giriş),
      aynı bilgisayarda iki uygulamayla test edildi. Eski main.py silindi.
- [x] Aşama 0: Kurulum ve klasör yapısı
- [x] Aşama 1a: DB şeması + kullanıcı/giriş (db/database.py, test: python -m db.test_db)
- [x] Aşama 1b: Giriş/kayıt ekranları, oturum, rol yönlendirme, ortak tema, uyarı pencereleri
- [x] Aşama 2a: Ağ katmanı (common/protocol.py, server/server.py, client/network_client.py,
      client/network_auth_service.py). Test: python -m server.test_server

## Sıradaki
- [ ] Aşama 7: Rapor (IEEE), diyagramlar, gerçek LAN testi (2+ bilgisayar), son kontroller
- [ ] Aşama 5: Öğrenci sınav çözme ekranı (soruları göster, geri sayım, cevapları gönder)
- [ ] Aşama 6: Cevap toplama, süre kontrolü sunucuda, log dosyaları
- [ ] Aşama 4: Sınav oluşturma ve dağıtım (aşağıdaki eski satırlar geçerli)
- [ ] Aşama 2c (gerçek LAN testi, 2 bilgisayar) ve Aşama 3 (soru bankası). Önce: Arayüzü ağa bağlama: main_instructor.py (sunucuyu başlatır, bağlı
      istemcileri gösterir), main_student.py (sunucuya bağlan ekranı + giriş).
      

## Notlar (rapor için)
- GÜNCEL KURAL (Aşama 6 sonrası): Klasik cevap beklenen cevapla birebir aynıysa (büyük/küçük harf ve boşluk önemsiz) gönderim anında otomatik tam puan; dolu ama farklıysa graded=0 (bekliyor) ve eğitmen elle puanlar; boş cevap 0. Otomatik puanlanan satırda graded_at boş, elle puanlananda dolu. Eğitmen otomatik puanı da değiştirebilir. Bu, vize isteri 7'deki 'cevap anahtarına göre anında puanlama' ile eğitmenin elle puanlaması isteğinin birleşimidir.
- KARAR: Klasik sorular otomatik puanlanmaz. Dolu cevap graded=0 (bekliyor) kaydedilir, eğitmen cevabı beklenen cevapla yan yana görüp elle puanlar (db/submissions.py grade_answer). Puan 0 ile sorunun sınavdaki puanı arasında, 2 ondalığa yuvarlanır, tekrar puanlanabilir. Çoktan seçmeli sorular otomatik puanlanır.
- Boş klasik cevap puanlanmayı beklemez (graded=1, 0 puan).
- 'Beklenen cevapla birebir aynı' notu yalnızca ipucudur, puan vermez (matches_expected).
- Veritabanı: answers.graded ve graded_at sütunları eklendi; db/database.py _migrate eski veritabanlarını açılışta günceller.
- Her puanlama logs tablosuna yazılır. Loglar sekmesi logs/submissions.log dosyasını gösterir.
- Dağıtım: öğrenci uygulaması sunucuya 3 sn'de bir sorar (polling); yayınlanan sınav en geç birkaç saniyede görünür.
- Süre: yayınlanma anı = başlangıç, bitiş = başlangıç + süre. Süreyi sunucu hesaplar (istemci saatine güvenilmez), süre dolunca sınav otomatik kapanır.
- Öğrenci paketi (db/exams.py get_exam_for_student) alanları tek tek seçerek oluşturulur: cevap anahtarı ağa çıkmaz. Testle doğrulanıyor (ham ağ yanıtında 'answer_key' ve beklenen cevap metni aranıyor).
- Yaşam döngüsü: taslak -> yayında -> kapandı. Yalnızca taslak düzenlenir. Gönderimi olan veya yayındaki sınav silinemez.
- list_exams/get_exam istekleri yalnızca öğrenci rolüne açık (rol token'dan bulunur).
- Bilinen sınır: sınavlar tüm öğrencilere gider, sınıfa göre hedefleme yok.
- Çoktan seçmelide doğru cevap şık SIRASI olarak saklanır (answer_key = "2"), öğrenci cevabı da sıra olarak gelecek.
- Sınavda kullanılan soru silinemez, yayınlanmış/kapanmış sınavdaki soru düzenlenemez (cascade ile öğrenci cevaplarının silinmesini önler).
- Kategori silinince sorular kalır, kategorisiz olur.
- Şifreler bcrypt ile hash'li, authenticate() hash döndürmüyor.
- Her DB işlemi kendi bağlantısını açıp kapatıyor (thread güvenliği).
- Sunucu: accept thread + her istemciye ayrı thread, paylaşılan veri Lock ile korunuyor.
- Hata ayıklama: stop() sırasında accept thread beklerken soket kapatılırsa port kısa
  süre açık kalıyordu. Önce shutdown + thread join, sonra close ile çözüldü.
- Güvenlik duvarı: sınıfta 5050/tcp engellenirse "sudo ufw allow 5050/tcp".
- Bilinen eksikler: aynı kullanıcının iki bilgisayardan aynı anda girişi engellenmiyor,
  giriş denemesi sınırlaması yok (sınav aşamasında değerlendirilecek).
