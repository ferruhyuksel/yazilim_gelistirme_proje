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
- [x] Aşama 2b: main_instructor.py (sunucu + canlı istemci listesi), main_student.py (bağlan + giriş),
      aynı bilgisayarda iki uygulamayla test edildi. Eski main.py silindi.
- [x] Aşama 0: Kurulum ve klasör yapısı
- [x] Aşama 1a: DB şeması + kullanıcı/giriş (db/database.py, test: python -m db.test_db)
- [x] Aşama 1b: Giriş/kayıt ekranları, oturum, rol yönlendirme, ortak tema, uyarı pencereleri
- [x] Aşama 2a: Ağ katmanı (common/protocol.py, server/server.py, client/network_client.py,
      client/network_auth_service.py). Test: python -m server.test_server

## Sıradaki
- [ ] Aşama 2c (gerçek LAN testi, 2 bilgisayar) ve Aşama 3 (soru bankası). Önce: Arayüzü ağa bağlama: main_instructor.py (sunucuyu başlatır, bağlı
      istemcileri gösterir), main_student.py (sunucuya bağlan ekranı + giriş).
      

## Notlar (rapor için)
- Şifreler bcrypt ile hash'li, authenticate() hash döndürmüyor.
- Her DB işlemi kendi bağlantısını açıp kapatıyor (thread güvenliği).
- Sunucu: accept thread + her istemciye ayrı thread, paylaşılan veri Lock ile korunuyor.
- Hata ayıklama: stop() sırasında accept thread beklerken soket kapatılırsa port kısa
  süre açık kalıyordu. Önce shutdown + thread join, sonra close ile çözüldü.
- Güvenlik duvarı: sınıfta 5050/tcp engellenirse "sudo ufw allow 5050/tcp".
- Bilinen eksikler: aynı kullanıcının iki bilgisayardan aynı anda girişi engellenmiyor,
  giriş denemesi sınırlaması yok (sınav aşamasında değerlendirilecek).
