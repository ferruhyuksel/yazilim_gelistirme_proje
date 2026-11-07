"""
ui/connect_window.py
Öğrenci uygulamasının ilk ekranı: eğitmen bilgisayarının IP adresi ve portu girilir.
Son girilen adres hatırlanır.
"""

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from common.protocol import DEFAULT_PORT
from ui.auth_service import AuthError
from ui.login_window import _button, _field, _heading, build_brand_panel
from ui.message_box import show_error


class ConnectWindow(QWidget):
    connected = Signal()

    def __init__(self, connect_func):
        """connect_func(host, port): başarısızsa AuthError fırlatır."""
        super().__init__()
        self.connect_func = connect_func
        self.setWindowTitle("Sınav Sistemi - Sunucuya bağlan")
        self.setFixedSize(900, 620)

        settings = QSettings("SinavSistemi", "ogrenci")
        self.host_edit = QLineEdit(str(settings.value("last_host", "")))
        self.host_edit.setPlaceholderText("örn. 192.168.1.20")
        self.port_edit = QLineEdit(str(settings.value("last_port", DEFAULT_PORT)))
        self.port_edit.setFixedWidth(110)
        self.host_edit.returnPressed.connect(self._on_connect)
        self.port_edit.returnPressed.connect(self._on_connect)

        title, hint = _heading(
            "Sunucuya bağlan",
            "Eğitmenin ekranında görünen IP adresini ve portu gir.",
        )
        self.connect_btn = _button("Bağlan", "primary")
        self.connect_btn.clicked.connect(self._on_connect)
        note = QLabel("Bilgisayarın eğitmenle aynı ağda (LAN/WiFi) olmalı.")
        note.setObjectName("formHint")
        note.setWordWrap(True)

        row = QHBoxLayout()
        row.setSpacing(16)
        row.addLayout(_field("Sunucu IP adresi", self.host_edit), stretch=1)
        row.addLayout(_field("Port", self.port_edit))

        form_area = QFrame()
        form_area.setObjectName("formArea")
        layout = QVBoxLayout(form_area)
        layout.setContentsMargins(56, 40, 56, 40)
        layout.setSpacing(18)
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(10)
        layout.addLayout(row)
        layout.addSpacing(6)
        layout.addWidget(self.connect_btn)
        layout.addWidget(note)
        layout.addStretch()

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(build_brand_panel())
        root.addWidget(form_area, stretch=1)

    def _on_connect(self):
        if not self.connect_btn.isEnabled():
            return
        host = self.host_edit.text().strip()
        if not host:
            show_error(self, "Eksik bilgi", "Sunucu IP adresini gir.")
            return
        try:
            port = int(self.port_edit.text().strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            show_error(self, "Geçersiz port", "Port 1 ile 65535 arasında bir sayı olmalı.")
            return

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Bağlanılıyor...")
        QApplication.processEvents()
        try:
            self.connect_func(host, port)
        except AuthError as e:
            show_error(self, "Bağlantı kurulamadı", str(e))
            return
        finally:
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("Bağlan")

        settings = QSettings("SinavSistemi", "ogrenci")
        settings.setValue("last_host", host)
        settings.setValue("last_port", port)
        self.connected.emit()
