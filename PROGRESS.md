# İlerleme Durumu

## Teknoloji
Python 3 + PySide6 + SQLite + socket/threading + JSON (Linux)

## Karar Verilenler
- Eğitmen hesabı sabit, sadece biz oluşturuyoruz.
- Öğrenci hesabı: hem kayıt ekranı hem eğitmenin ekleyebilmesi.


## Tamamlananlar
- [x] Aşama 0: Kurulum ve klasör yapısı
- [x] Aşama 1a: DB şeması + kullanıcı/giriş fonksiyonları (db/database.py, test: python -m db.test_db)

## Sıradaki
- [ ] Aşama 1b: Giriş ve kayıt ekranları (PySide6), rol yönlendirmesi

## Notlar (rapor için)
- Varsayılan eğitmen: egitmen / egitmen123 (ilk girişte değiştirilecek)
- Şifreler bcrypt ile hash'li saklanıyor, authenticate() hash döndürmüyor
- Her DB işlemi kendi bağlantısını açıp kapatıyor (sunucu thread güvenliği için)