"""
ui/log_view.py
Eğitmen panelindeki "Loglar" sekmesi: sunucunun yazdığı gönderim log dosyasını
(logs/submissions.log) salt okunur gösterir. Dosya değiştikçe kendiliğinden yenilenir.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

LOG_FILE_NAME = "submissions.log"
MAX_LINES = 2000   # çok büyük log dosyasında arayüz yavaşlamasın diye son satırlar


class LogView(QWidget):
    def __init__(self, log_dir):
        super().__init__()
        self.log_path = log_dir / LOG_FILE_NAME
        self._signature = None

        title = QLabel("Gönderim logları")
        title.setObjectName("pageTitle")
        self.path_label = QLabel(str(self.log_path))
        self.path_label.setObjectName("countLabel")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        refresh_btn = QPushButton("Yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(lambda: self.reload(force=True))

        head = QHBoxLayout()
        head.addWidget(title)
        head.addStretch()
        head.addWidget(refresh_btn)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.text.setStyleSheet("QPlainTextEdit { font-size: 13px; }")

        hint = QLabel("Kabul edilen ve reddedilen tüm gönderimler, zaman damgasıyla "
                      "(GONDERIM / REDDEDILDI).")
        hint.setObjectName("countLabel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.setSpacing(12)
        layout.addLayout(head)
        layout.addWidget(hint)
        layout.addWidget(self.text, stretch=1)
        layout.addWidget(self.path_label)

        self.reload(force=True)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.reload)
        self._timer.start(3000)

    def reload(self, force=False):
        try:
            stat = self.log_path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            signature = None
        if not force and signature == self._signature:
            return
        self._signature = signature

        if signature is None:
            self.text.setPlainText("Henüz kayıt yok. Öğrenciler sınav gönderdikçe satırlar burada belirir.")
            return
        try:
            lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            self.text.setPlainText(f"Log dosyası okunamadı: {e}")
            return
        bar = self.text.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 4
        self.text.setPlainText("\n".join(lines[-MAX_LINES:]))
        if at_bottom or force:
            bar.setValue(bar.maximum())
