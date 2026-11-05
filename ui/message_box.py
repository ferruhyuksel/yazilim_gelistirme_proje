"""
ui/message_box.py
Uygulamanın uyarı ve bilgi pencereleri. Qt'nin hazır QMessageBox'ı yerine
kullanılır: geniş, Türkçe düğmeli ve tema ile uyumlu.

Kullanım:
    show_error(self, "Giriş başarısız", "Kullanıcı adı veya şifre hatalı.")
    show_info(self, "Kayıt tamam", "Kayıt oluşturuldu.")
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class MessageDialog(QDialog):
    def __init__(self, parent, kind, title, text):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setMaximumWidth(620)

        title_label = QLabel(title)
        title_label.setObjectName("msgTitle")
        title_label.setProperty("kind", kind)
        title_label.setWordWrap(True)

        text_label = QLabel(text)
        text_label.setObjectName("msgText")
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        ok_btn = QPushButton("Tamam")
        ok_btn.setProperty("variant", "primary")
        ok_btn.setMinimumWidth(110)
        ok_btn.setDefault(True)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(ok_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(12)
        layout.addWidget(title_label)
        layout.addWidget(text_label)
        layout.addSpacing(10)
        layout.addLayout(buttons)


def show_error(parent, title, text):
    MessageDialog(parent, "error", title, text).exec()


def show_info(parent, title, text):
    MessageDialog(parent, "info", title, text).exec()
