"""
main.py
Uygulamanın giriş noktası. Çalıştırma (proje kök klasöründen):
    python main.py

Akış: giriş ekranı -> rol kontrolü -> eğitmen/öğrenci paneli -> çıkış -> giriş ekranı
"""

import sys

from PySide6.QtWidgets import QApplication

from db import database as db
from ui.auth_service import LocalAuthService
from ui.login_window import LoginWindow
from ui.panels import InstructorPanel, StudentPanel
from ui.session import Session
from ui.theme import STYLESHEET


class AppController:
    def __init__(self):
        db.init_db()
        self.service = LocalAuthService()
        self.session = Session()
        self.login_window = None
        self.panel = None

    def show_login(self):
        self.login_window = LoginWindow(self.service)
        self.login_window.login_success.connect(self.on_login_success)
        self.login_window.show()

    def on_login_success(self, user):
        self.session.start(user)

        panel_class = InstructorPanel if self.session.is_instructor else StudentPanel
        self.panel = panel_class(self.service, self.session.user)
        self.panel.logout_requested.connect(self.on_logout)
        self.panel.show()

        # Panel açıldıktan sonra giriş penceresini kapat (sırası önemli:
        # son pencere kapanırsa uygulama biter)
        self.login_window.close()
        self.login_window = None

    def on_logout(self):
        self.session.end()
        old_panel = self.panel
        self.panel = None
        self.show_login()  # önce yeni pencereyi aç
        old_panel.close()  # sonra eskisini kapat


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    controller = AppController()
    controller.show_login()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
