"""
ui/panels.py
Eğitmen ve öğrenci panelleri.

Eğitmen paneli: sunucu adresi ve bağlı istemcilerin canlı listesi.
Sonraki aşamalarda eklenecek:
  - Eğitmen: soru bankası, sınav oluşturma, sonuçlar, loglar
  - Öğrenci: sınav listesi ve sınav çözme ekranı
"""

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from common.net_utils import get_local_ip
from ui.change_password_dialog import ChangePasswordDialog
from ui.formatting import format_remaining


class BasePanel(QMainWindow):
    logout_requested = Signal()

    TITLE = ""
    ROLE_LABEL = ""
    HINT = ""

    def __init__(self, service, user, server=None, exam_service=None):
        super().__init__()
        self.service = service
        self.user = user
        self.server = server
        self.exam_service = exam_service
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
        layout.setSpacing(20)
        layout.addWidget(card)
        extras = self._extra_widgets()
        for widget in extras:
            layout.addWidget(widget, stretch=1)
        if not extras:
            layout.addStretch()
        return body

    def _extra_widgets(self):
        """Alt sınıflar karşılama kartının altına eklenecek bileşenleri döner."""
        return []

    def _change_password(self):
        ChangePasswordDialog(self.service, self.user["id"], self).exec()


class InstructorPanel(BasePanel):
    TITLE = "Eğitmen paneli"
    ROLE_LABEL = "Eğitmen"
    HINT = ("Soru bankası ve sınavlar hazır. Sonuçlar ve loglar sonraki "
            "aşamalarda eklenecek.")

    def _build_body(self):
        # Soru bankası yalnızca eğitmen tarafında kullanıldığı için burada içe aktarılır
        # (öğrenci uygulaması veritabanı modüllerini hiç yüklemez).
        from ui.exam_view import ExamView
        from ui.question_bank_view import QuestionBankView

        tabs = QTabWidget()
        tabs.addTab(super()._build_body(), "Genel bakış")
        tabs.addTab(QuestionBankView(self.user["id"]), "Soru bankası")
        tabs.addTab(ExamView(self.user["id"], self.server), "Sınavlar")
        return tabs

    def _extra_widgets(self):
        return [self._build_server_card()]

    def _build_server_card(self):
        card = QFrame()
        card.setObjectName("card")

        title = QLabel("Sunucu")
        title.setObjectName("sectionTitle")
        status = QLabel("● Çalışıyor")
        status.setObjectName("statusOk")
        head = QHBoxLayout()
        head.addWidget(title)
        head.addStretch()
        head.addWidget(status)

        address = QLabel(f"{get_local_ip()}:{self.server.port}")
        address.setObjectName("serverAddress")
        address.setTextInteractionFlags(Qt.TextSelectableByMouse)
        hint = QLabel("Öğrenciler uygulamaya bu adresi girerek bağlanır. "
                      "Hepsinin aynı ağda (LAN/WiFi) olması gerekir.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)

        self.clients_title = QLabel("Bağlı istemciler (0)")
        self.clients_title.setObjectName("sectionTitle")

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["IP adresi", "Kullanıcı", "Bağlanma saati"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(10)
        layout.addLayout(head)
        layout.addWidget(address)
        layout.addWidget(hint)
        layout.addSpacing(10)
        layout.addWidget(self.clients_title)
        layout.addWidget(self.table, stretch=1)

        # Sunucu başka thread'lerde çalışır. Arayüz thread'i listeyi saniyede bir
        # güvenli kopya olarak okur, böylece thread'ler arası sinyal gerekmez.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_clients)
        self._timer.start(1000)
        self._refresh_clients()
        return card

    def _refresh_clients(self):
        clients = self.server.get_clients()
        self.clients_title.setText(f"Bağlı istemciler ({len(clients)})")
        self.table.setRowCount(len(clients))
        for row, c in enumerate(clients):
            values = (c["address"], c["username"] or "giriş yapmadı", c["connected_at"])
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))


class StudentPanel(BasePanel):
    TITLE = "Öğrenci paneli"
    ROLE_LABEL = "Öğrenci"
    HINT = "Eğitmenin yayınladığı sınavlar aşağıda görünür."

    POLL_INTERVAL_MS = 3000

    def _extra_widgets(self):
        if self.exam_service is None:
            return []
        return [self._build_exam_card()]

    def _build_exam_card(self):
        card = QFrame()
        card.setObjectName("card")

        title = QLabel("Aktif sınavlar")
        title.setObjectName("sectionTitle")
        self.error_label = QLabel()
        self.error_label.setObjectName("errorText")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Sınav", "Soru", "Toplam puan", "Kalan süre", "Durum"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, width in ((1, 80), (2, 130), (3, 130), (4, 130)):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)

        self.empty_label = QLabel("Şu an aktif sınav yok.\n"
                                  "Eğitmen bir sınav yayınlayınca burada görünecek.")
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(self.error_label)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self.empty_label, stretch=1)

        self._exams = []
        self._fetched_at = time.monotonic()
        # Sınavlar sunucudan birkaç saniyede bir sorulur (polling). Kalan süre iki
        # sorgu arasında yerel saatle geriye sayılır, her sorguda sunucu değeriyle düzeltilir.
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(self.POLL_INTERVAL_MS)
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._render)
        self._tick_timer.start(1000)
        self._poll()
        return card

    def _poll(self):
        from client.network_exam_service import ServiceError
        try:
            exams = self.exam_service.list_exams()
        except ServiceError as e:
            self.error_label.setText(
                f"{e}. Çıkış yapıp sunucuyu değiştirerek yeniden bağlanabilirsin."
                if e.connection_lost else str(e))
            self.error_label.show()
            if e.connection_lost:
                self._poll_timer.stop()
                self._tick_timer.stop()
                self._exams = []
                self._render()
            return
        self.error_label.hide()
        self._exams = exams
        self._fetched_at = time.monotonic()
        self._render()

    def _render(self):
        elapsed = time.monotonic() - self._fetched_at
        rows = [e for e in self._exams if e["remaining_seconds"] - elapsed > 0]
        self.table.setRowCount(len(rows))
        for row, e in enumerate(rows):
            left = e["remaining_seconds"] - elapsed
            cells = (e["title"], str(e["question_count"]), f"{e['total_points']:g}",
                     format_remaining(left),
                     "Gönderildi" if e["submitted"] else "Çözülmedi")
            for col, value in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.setVisible(bool(rows))
        self.empty_label.setVisible(not rows)
