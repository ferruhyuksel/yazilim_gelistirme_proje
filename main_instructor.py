"""
main_instructor.py
EĞİTMEN uygulaması. Veritabanını ve sunucuyu çalıştırır.
Çalıştırma (proje kök klasöründen):
    python main_instructor.py

Akış: giriş (yalnızca eğitmen) -> sunucu başlar -> eğitmen paneli -> çıkış -> sunucu durur
"""

import logging
import sys

from PySide6.QtWidgets import QApplication

from common.protocol import DEFAULT_PORT
from db import database as db
from server.server import ExamServer
from ui.auth_service import LocalAuthService
from ui.login_window import LoginWindow
from ui.message_box import show_error
from ui.panels import InstructorPanel
from ui.session import Session
from ui.theme import STYLESHEET


class InstructorController:
    def __init__(self):
        db.init_db()
        self.service = LocalAuthService()
        self.session = Session()
        self.server = None
        self.login_window = None
        self.panel = None

    def show_login(self):
        self.login_window = LoginWindow(self.service, allow_register=False)
        self.login_window.login_success.connect(self.on_login_success)
        self.login_window.show()

    def on_login_success(self, user):
        if user["role"] != db.ROLE_INSTRUCTOR:
            show_error(
                self.login_window, "Yetkisiz giriş",
                "Bu uygulama yalnızca eğitmen hesapları içindir. "
                "Öğrenciler öğrenci uygulamasını kullanmalı.",
            )
            return

        server = ExamServer()
        try:
            server.start()
        except OSError as e:
            show_error(
                self.login_window, "Sunucu başlatılamadı",
                f"{DEFAULT_PORT} numaralı port kullanılamıyor. Uygulamanın başka bir "
                f"kopyası açık olabilir.\n\nAyrıntı: {e}",
            )
            return

        self.server = server
        self.session.start(user)
        self.panel = InstructorPanel(self.service, self.session.user, server)
        self.panel.logout_requested.connect(self.on_logout)
        self.panel.show()
        self.login_window.close()
        self.login_window = None

    def on_logout(self):
        self.shutdown()
        self.session.end()
        old_panel = self.panel
        self.panel = None
        self.show_login()   # önce yeni pencereyi aç, sonra eskisini kapat
        old_panel.close()

    def shutdown(self):
        if self.server is not None:
            self.server.stop()
            self.server = None


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    controller = InstructorController()
    app.aboutToQuit.connect(controller.shutdown)
    controller.show_login()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
