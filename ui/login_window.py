"""
ui/login_window.py
Giriş ve öğrenci kayıt ekranları (tek pencerede, iki sayfa).
Başarılı girişte login_success sinyali kullanıcı sözlüğüyle yayılır.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ui.auth_service import AuthError
from ui.message_box import show_error, show_info


def _password_edit():
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.Password)
    return edit


def _field(label_text, edit):
    """Etiketi alanın üstünde gösteren küçük düzen."""
    box = QVBoxLayout()
    box.setSpacing(6)
    label = QLabel(label_text)
    label.setObjectName("fieldLabel")
    box.addWidget(label)
    box.addWidget(edit)
    return box


def _button(text, variant=None):
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


def _heading(title, hint):
    t = QLabel(title)
    t.setObjectName("formTitle")
    h = QLabel(hint)
    h.setObjectName("formHint")
    h.setWordWrap(True)
    return t, h


class LoginWindow(QWidget):
    login_success = Signal(dict)

    PAGE_LOGIN = 0
    PAGE_REGISTER = 1

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.setWindowTitle("Sınav Sistemi - Giriş")
        self.setFixedSize(900, 620)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_brand_panel())

        form_area = QFrame()
        form_area.setObjectName("formArea")
        form_layout = QVBoxLayout(form_area)
        form_layout.setContentsMargins(56, 40, 56, 40)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_login_page())
        self.stack.addWidget(self._build_register_page())
        form_layout.addWidget(self.stack)
        root.addWidget(form_area, stretch=1)

    # ------------------------------------------------------------------
    # Parçalar
    # ------------------------------------------------------------------

    def _build_brand_panel(self):
        panel = QFrame()
        panel.setObjectName("brandPanel")
        panel.setFixedWidth(330)

        title = QLabel("Sınav\nSistemi")
        title.setObjectName("brandTitle")
        text = QLabel(
            "Çoktan seçmeli ve klasik sorular, yerel ağda eğitmen "
            "bilgisayarından öğrencilere dağıtılır. İnternet gerekmez."
        )
        text.setObjectName("brandText")
        text.setWordWrap(True)
        foot = QLabel("Yazılım Geliştirme I dönem projesi")
        foot.setObjectName("brandFoot")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(40, 56, 40, 40)
        layout.setSpacing(18)
        layout.addWidget(title)
        layout.addWidget(text)
        layout.addStretch()
        layout.addWidget(foot)
        return panel

    def _build_login_page(self):
        page = QWidget()
        title, hint = _heading("Giriş yap", "Kullanıcı adın ve şifrenle devam et.")

        self.login_username = QLineEdit()
        self.login_password = _password_edit()
        self.login_username.returnPressed.connect(self.login_password.setFocus)
        self.login_password.returnPressed.connect(self._on_login)

        login_btn = _button("Giriş yap", "primary")
        login_btn.clicked.connect(self._on_login)
        register_btn = _button("Hesabın yok mu? Öğrenci kaydı oluştur", "link")
        register_btn.clicked.connect(lambda: self._show_page(self.PAGE_REGISTER))

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(10)
        layout.addLayout(_field("Kullanıcı adı", self.login_username))
        layout.addLayout(_field("Şifre", self.login_password))
        layout.addSpacing(6)
        layout.addWidget(login_btn)
        layout.addWidget(register_btn)
        layout.addStretch()
        return page

    def _build_register_page(self):
        page = QWidget()
        title, hint = _heading(
            "Öğrenci kaydı",
            "Eğitmen hesapları yalnızca eğitmen tarafından oluşturulur.",
        )

        self.reg_full_name = QLineEdit()
        self.reg_class = QLineEdit()
        self.reg_class.setPlaceholderText("örn. 1A")
        self.reg_username = QLineEdit()
        self.reg_password = _password_edit()
        self.reg_password2 = _password_edit()
        self.reg_password2.returnPressed.connect(self._on_register)

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addLayout(_field("Ad soyad", self.reg_full_name), stretch=2)
        row1.addLayout(_field("Sınıf/Şube (isteğe bağlı)", self.reg_class), stretch=1)

        row3 = QHBoxLayout()
        row3.setSpacing(16)
        row3.addLayout(_field("Şifre", self.reg_password))
        row3.addLayout(_field("Şifre (tekrar)", self.reg_password2))

        save_btn = _button("Kayıt ol", "primary")
        save_btn.clicked.connect(self._on_register)
        back_btn = _button("Girişe dön", "link")
        back_btn.clicked.connect(lambda: self._show_page(self.PAGE_LOGIN))

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(6)
        layout.addLayout(row1)
        layout.addLayout(_field("Kullanıcı adı", self.reg_username))
        layout.addLayout(row3)
        layout.addSpacing(6)
        layout.addWidget(save_btn)
        layout.addWidget(back_btn)
        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Olaylar
    # ------------------------------------------------------------------

    def _show_page(self, index):
        self.stack.setCurrentIndex(index)
        self.setWindowTitle(
            "Sınav Sistemi - Giriş" if index == self.PAGE_LOGIN
            else "Sınav Sistemi - Kayıt"
        )

    def _on_login(self):
        try:
            user = self.service.login(
                self.login_username.text(), self.login_password.text()
            )
        except AuthError as e:
            show_error(self, "Giriş başarısız", str(e))
            self.login_password.clear()
            self.login_password.setFocus()
            return
        self.login_password.clear()
        self.login_success.emit(user)

    def _on_register(self):
        if self.reg_password.text() != self.reg_password2.text():
            show_error(self, "Kayıt başarısız", "Şifreler eşleşmiyor.")
            return
        try:
            self.service.register_student(
                self.reg_username.text(),
                self.reg_password.text(),
                self.reg_full_name.text(),
                self.reg_class.text(),
            )
        except AuthError as e:
            show_error(self, "Kayıt başarısız", str(e))
            return

        username = self.reg_username.text().strip()
        for edit in (self.reg_full_name, self.reg_class, self.reg_username,
                     self.reg_password, self.reg_password2):
            edit.clear()
        show_info(self, "Kayıt tamam", "Kayıt oluşturuldu, giriş yapabilirsin.")
        self._show_page(self.PAGE_LOGIN)
        self.login_username.setText(username)
        self.login_password.setFocus()
