"""
ui/panels.py
Eğitmen ve öğrenci panellerinin iskeleti. Şimdilik üst çubuk (kullanıcı bilgisi,
şifre değiştirme, çıkış) ve karşılama kartı var. Sonraki aşamalarda doldurulacak:
  - Eğitmen: soru bankası, sınav oluşturma, sonuçlar, loglar
  - Öğrenci: sınav listesi ve sınav çözme ekranı
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget,
)

from ui.change_password_dialog import ChangePasswordDialog


class BasePanel(QMainWindow):
    logout_requested = Signal()

    TITLE = ""
    ROLE_LABEL = ""
    HINT = ""

    def __init__(self, service, user):
        super().__init__()
        self.service = service
        self.user = user
        self.setWindowTitle(f"{self.TITLE} - {user['full_name']}")
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_body(), stretch=1)
        self.setCentralWidget(central)

    def _role_text(self):
        text = self.ROLE_LABEL
        if self.user.get("class_name"):
            text += f" ({self.user['class_name']})"
        return text

    def _build_top_bar(self):
        bar = QFrame()
        bar.setObjectName("topBar")

        app_name = QLabel("Sınav Sistemi")
        app_name.setObjectName("appName")

        name = QLabel(self.user["full_name"])
        name.setObjectName("userName")
        name.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        role = QLabel(self._role_text())
        role.setObjectName("userRole")
        role.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        info = QVBoxLayout()
        info.setSpacing(0)
        info.addWidget(name)
        info.addWidget(role)

        pw_btn = QPushButton("Şifre değiştir")
        pw_btn.setCursor(Qt.PointingHandCursor)
        pw_btn.clicked.connect(self._change_password)
        logout_btn = QPushButton("Çıkış yap")
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.clicked.connect(self.logout_requested.emit)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 14, 28, 14)
        layout.setSpacing(14)
        layout.addWidget(app_name)
        layout.addStretch()
        layout.addLayout(info)
        layout.addSpacing(8)
        layout.addWidget(pw_btn)
        layout.addWidget(logout_btn)
        return bar

    def _build_body(self):
        body = QWidget()
        card = QFrame()
        card.setObjectName("card")

        welcome = QLabel(f"Hoş geldin, {self.user['full_name']}")
        welcome.setObjectName("welcome")
        hint = QLabel(self.HINT)
        hint.setObjectName("hint")
        hint.setWordWrap(True)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(12)
        card_layout.addWidget(welcome)
        card_layout.addWidget(hint)

        layout = QVBoxLayout(body)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.addWidget(card)
        layout.addStretch()
        return body

    def _change_password(self):
        ChangePasswordDialog(self.service, self.user["id"], self).exec()


class InstructorPanel(BasePanel):
    TITLE = "Eğitmen paneli"
    ROLE_LABEL = "Eğitmen"
    HINT = ("Soru bankası, sınav oluşturma, sonuçlar ve loglar sonraki "
            "aşamalarda bu panele eklenecek.")


class StudentPanel(BasePanel):
    TITLE = "Öğrenci paneli"
    ROLE_LABEL = "Öğrenci"
    HINT = "Eğitmenin yayınladığı sınavlar sonraki aşamalarda burada görünecek."
