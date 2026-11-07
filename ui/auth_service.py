"""
ui/auth_service.py
Arayüzün kimlik doğrulama için konuştuğu TEK nokta.

Şimdilik LocalAuthService veritabanına doğrudan bağlanıyor. Aşama 2'de aynı
metotlara sahip bir NetworkAuthService yazıp öğrenci tarafında onu kullanacağız;
arayüz kodunda hiçbir değişiklik gerekmeyecek.

Tüm hatalar AuthError olarak fırlatılır, mesajı doğrudan kullanıcıya gösterilebilir.
"""

from db import database as db


class AuthError(Exception):
    pass


class LocalAuthService:
    def login(self, username, password):
        """Başarılıysa kullanıcı sözlüğünü döner, değilse AuthError fırlatır."""
        if not username.strip() or not password:
            raise AuthError("Kullanıcı adı ve şifre boş olamaz.")
        user = db.authenticate(username, password)
        if user is None:
            raise AuthError("Kullanıcı adı veya şifre hatalı.")
        return user

    def register_student(self, username, password, full_name, class_name):
        """Öğrenci kaydı. Rol burada SABİTLENİR: arayüzden gelen hiçbir değer
        kullanıcıyı eğitmen yapamaz."""
        try:
            db.create_user(
                username, password, db.ROLE_STUDENT, full_name,
                class_name.strip() or None,
            )
        except ValueError as e:
            raise AuthError(str(e))

    def change_password(self, user_id, old_password, new_password):
        try:
            ok = db.change_password(user_id, old_password, new_password)
        except ValueError as e:
            raise AuthError(str(e))
        if not ok:
            raise AuthError("Mevcut şifre hatalı.")

    def logout(self):
        """Yerel serviste kapatılacak bir bağlantı yok. NetworkAuthService ile aynı arayüz."""
        pass
