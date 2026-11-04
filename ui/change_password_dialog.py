"""
ui/change_password_dialog.py
Giriş yapmış kullanıcının şifresini değiştirdiği küçük diyalog.
"""

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from ui.auth_service import AuthError
from ui.message_box import show_error, show_info


def _password_edit():
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.Password)
    return edit


def _field(label_text, edit):
    box = QVBoxLayout()
    box.setSpacing(6)
    label = QLabel(label_text)
    label.setObjectName("fieldLabel")
    box.addWidget(label)
    box.addWidget(edit)
    return box


class ChangePasswordDialog(QDialog):
    def __init__(self, service, user_id, parent=None):
        super().__init__(parent)
        self.service = service
        self.user_id = user_id
        self.setWindowTitle("Şifre değiştir")
        self.setMinimumWidth(440)

        self.old_edit = _password_edit()
        self.new_edit = _password_edit()
        self.new_edit2 = _password_edit()

        title = QLabel("Şifre değiştir")
        title.setObjectName("formTitle")

        save_btn = QPushButton("Kaydet")
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("Vazgeç")
        cancel_btn.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addLayout(_field("Mevcut şifre", self.old_edit))
        layout.addLayout(_field("Yeni şifre", self.new_edit))
        layout.addLayout(_field("Yeni şifre (tekrar)", self.new_edit2))
        layout.addSpacing(6)
        layout.addLayout(buttons)

    def _on_ok(self):
        if self.new_edit.text() != self.new_edit2.text():
            show_error(self, "Hata", "Yeni şifreler eşleşmiyor.")
            return
        try:
            self.service.change_password(
                self.user_id, self.old_edit.text(), self.new_edit.text()
            )
        except AuthError as e:
            show_error(self, "Hata", str(e))
            return
        show_info(self, "Tamam", "Şifre değiştirildi.")
        self.accept()
