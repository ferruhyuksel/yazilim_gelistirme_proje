"""
main_student.py
ÖĞRENCİ uygulaması. Veritabanı İÇERMEZ, her şey eğitmenin sunucusu üzerinden yapılır.
Çalıştırma (proje kök klasöründen):
    python main_student.py

Akış: sunucuya bağlan -> giriş/kayıt -> öğrenci paneli -> çıkış -> giriş
"""

import sys

from PySide6.QtWidgets import QApplication

from client.network_auth_service import NetworkAuthService
from client.network_client import NetworkClient
from db.database import ROLE_STUDENT
from ui.auth_service import AuthError
from ui.connect_window import ConnectWindow
from ui.login_window import LoginWindow
from ui.message_box import show_error
from ui.panels import StudentPanel
from ui.session import Session
from ui.theme import STYLESHEET


class StudentController:
    def __init__(self):
        self.client = NetworkClient()
        self.service = NetworkAuthService(self.client)
        self.session = Session()
        self.connect_window = None
        self.login_window = None
        self.panel = None

    # --- bağlantı ---

    def show_connect(self):
        self.connect_window = ConnectWindow(self._connect)
        self.connect_window.connected.connect(self.on_connected)
        self.connect_window.show()

    def _connect(self, host, port):
        try:
            self.client.connect(host, port)
        except ConnectionError as e:
            raise AuthError(str(e))

    def on_connected(self):
        self.show_login()
        self.connect_window.close()
        self.connect_window = None

    def back_to_connect(self):
        """Giriş ekranındaki 'Sunucuyu değiştir' bağlantısı (bağlantı koptuysa da buradan dönülür)."""
        self.client.close()
        self.show_connect()
        self.login_window.close()
        self.login_window = None

    # --- giriş ---

    def show_login(self):
        self.login_window = LoginWindow(
            self.service, allow_register=True,
            change_server_callback=self.back_to_connect,
        )
        self.login_window.login_success.connect(self.on_login_success)
        self.login_window.show()

    def on_login_success(self, user):
        if user["role"] != ROLE_STUDENT:
            self.service.logout()
            show_error(
                self.login_window, "Yetkisiz giriş",
                "Bu uygulama yalnızca öğrenci hesapları içindir. "
                "Eğitmenler eğitmen uygulamasını kullanmalı.",
            )
            return

        self.session.start(user, token=self.client.token)
        self.panel = StudentPanel(self.service, self.session.user)
        self.panel.logout_requested.connect(self.on_logout)
        self.panel.show()
        self.login_window.close()
        self.login_window = None

    def on_logout(self):
        self.service.logout()
        self.session.end()
        old_panel = self.panel
        self.panel = None
        self.show_login()   # önce yeni pencereyi aç, sonra eskisini kapat
        old_panel.close()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    controller = StudentController()
    app.aboutToQuit.connect(controller.client.close)
    controller.show_connect()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
