"""
ui/session.py
Giriş yapmış kullanıcının oturumunu tutar.

Token şimdilik yerel kullanımda bir işe yaramıyor ama Aşama 2'de ağ üzerinden
her istekte sunucuya gönderilecek, o yüzden yapıyı baştan hazır tutuyoruz.
"""

import secrets

from db.database import ROLE_INSTRUCTOR, ROLE_STUDENT


class Session:
    def __init__(self):
        self._user = None
        self._token = None

    def start(self, user, token=None):
        """Giriş başarılı olunca çağrılır. user: authenticate() çıktısı (sözlük)."""
        self._user = dict(user)
        self._token = token or secrets.token_hex(16)

    def end(self):
        """Çıkış yapınca çağrılır, tüm oturum verisi silinir."""
        self._user = None
        self._token = None

    @property
    def is_active(self):
        return self._user is not None

    @property
    def user(self):
        return self._user

    @property
    def token(self):
        return self._token

    @property
    def is_instructor(self):
        return self.is_active and self._user["role"] == ROLE_INSTRUCTOR

    @property
    def is_student(self):
        return self.is_active and self._user["role"] == ROLE_STUDENT
