"""
client/network_auth_service.py
Öğrenci uygulamasının kimlik doğrulama servisi. ui.auth_service.LocalAuthService ile
AYNI metotlara sahiptir, bu yüzden arayüz kodu hangisini kullandığını bilmez.
"""

from client.network_client import ServerError
from common import protocol
from ui.auth_service import AuthError


class NetworkAuthService:
    def __init__(self, client):
        self.client = client

    def _call(self, type_, data=None):
        try:
            return self.client.request(type_, data)
        except (ServerError, ConnectionError) as e:
            raise AuthError(str(e))

    def login(self, username, password):
        if not username.strip() or not password:
            raise AuthError("Kullanıcı adı ve şifre boş olamaz.")
        result = self._call(protocol.LOGIN, {"username": username, "password": password})
        self.client.token = result["token"]
        return result["user"]

    def register_student(self, username, password, full_name, class_name):
        self._call(protocol.REGISTER, {
            "username": username,
            "password": password,
            "full_name": full_name,
            "class_name": class_name,
        })

    def change_password(self, user_id, old_password, new_password):
        # user_id kullanılmaz: sunucu kimliği token'dan belirler.
        self._call(protocol.CHANGE_PASSWORD, {
            "old_password": old_password,
            "new_password": new_password,
        })

    def logout(self):
        try:
            self._call(protocol.LOGOUT)
        except AuthError:
            pass
        self.client.token = None
