"""
ui/exam_view.py
Eğitmen panelindeki "Sınavlar" sekmesi: oluşturma, düzenleme, kopyalama, silme,
yayınlama ve sonlandırma. Liste birkaç saniyede bir kendini yeniler (kalan süre,
süresi dolan sınavın otomatik kapanması).
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from db import exams as exam_db
from ui.exam_dialog import ExamDialog
from ui.formatting import format_remaining
from ui.message_box import ask_confirm, show_error

_STATUS_COLORS = {
    exam_db.STATUS_DRAFT: "#5B6677",
    exam_db.STATUS_PUBLISHED: "#1E7A46",
    exam_db.STATUS_CLOSED: "#8A93A3",
}


def _button(text, variant=None):
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


class ExamView(QWidget):
    def __init__(self, user_id, server):
        super().__init__()
        self.user_id = user_id
        self.server = server
        self._exams = {}   # id -> son okunan sınav bilgisi

        title = QLabel("Sınavlar")
        title.setObjectName("pageTitle")
        new_btn = _button("Yeni sınav", "primary")
        new_btn.clicked.connect(self._new_exam)
        head = QHBoxLayout()
        head.addWidget(title)
        head.addStretch()
        head.addWidget(new_btn)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Sınav", "Süre", "Soru", "Toplam puan", "Durum", "Kalan süre"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, width in ((1, 90), (2, 70), (3, 120), (4, 110), (5, 130)):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.itemDoubleClicked.connect(lambda _item: self._edit_exam())

        self.empty_label = QLabel(
            "Henüz sınav yok. Sağ üstteki \"Yeni sınav\" düğmesiyle ilk sınavı hazırla.")
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)

        self.edit_btn = _button("Düzenle")
        self.edit_btn.clicked.connect(self._edit_exam)
        self.copy_btn = _button("Kopyala")
        self.copy_btn.clicked.connect(self._copy_exam)
        self.delete_btn = _button("Sil")
        self.delete_btn.clicked.connect(self._delete_exam)
        self.close_btn = _button("Sınavı sonlandır")
        self.close_btn.clicked.connect(self._close_exam)
        self.publish_btn = _button("Yayınla", "primary")
        self.publish_btn.clicked.connect(self._publish_exam)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addWidget(self.edit_btn)
        footer.addWidget(self.copy_btn)
        footer.addWidget(self.delete_btn)
        footer.addStretch()
        footer.addWidget(self.close_btn)
        footer.addWidget(self.publish_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.setSpacing(16)
        layout.addLayout(head)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self.empty_label, stretch=1)
        layout.addLayout(footer)

        self.reload()
        # Süre ilerledikçe kalan süreyi güncellemek ve süresi dolanı kapatmak için
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.reload)
        self._timer.start(3000)

    # ------------------------------------------------------------------

    def reload(self):
        selected = self._selected_id()
        exams = exam_db.list_exams()
        self._exams = {e["id"]: e for e in exams}
        self.table.blockSignals(True)
        self.table.setRowCount(len(exams))
        for row, e in enumerate(exams):
            remaining = (format_remaining(e["remaining_seconds"])
                         if e["status"] == exam_db.STATUS_PUBLISHED else "—")
            cells = (e["title"], f"{e['duration_minutes']} dk", str(e["question_count"]),
                     f"{e['total_points']:g}", exam_db.STATUS_LABELS[e["status"]], remaining)
            for col, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.UserRole, e["id"])
                if col == 4:
                    item.setForeground(QColor(_STATUS_COLORS[e["status"]]))
                self.table.setItem(row, col, item)
            if e["id"] == selected:
                self.table.selectRow(row)
        self.table.blockSignals(False)
        has_rows = bool(exams)
        self.table.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)
        self._update_buttons()

    def _selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.table.item(rows[0].row(), 0).data(Qt.UserRole)

    def _selected_exam(self):
        return self._exams.get(self._selected_id())

    def _update_buttons(self):
        e = self._selected_exam()
        status = e["status"] if e else None
        self.edit_btn.setEnabled(status == exam_db.STATUS_DRAFT)
        self.copy_btn.setEnabled(e is not None)
        self.delete_btn.setEnabled(status in (exam_db.STATUS_DRAFT, exam_db.STATUS_CLOSED))
        self.publish_btn.setEnabled(status == exam_db.STATUS_DRAFT and e["question_count"] > 0)
        self.close_btn.setEnabled(status == exam_db.STATUS_PUBLISHED)

    # ------------------------------------------------------------------

    def _new_exam(self):
        if ExamDialog(self.user_id, parent=self).exec():
            self.reload()

    def _edit_exam(self):
        e = self._selected_exam()
        if e is None or e["status"] != exam_db.STATUS_DRAFT:
            return
        exam = exam_db.get_exam(e["id"])
        if exam is None:
            self.reload()
            return
        if ExamDialog(self.user_id, exam, parent=self).exec():
            self.reload()

    def _copy_exam(self):
        e = self._selected_exam()
        if e is None:
            return
        try:
            exam_db.duplicate_exam(e["id"], self.user_id)
        except ValueError as ex:
            show_error(self, "Sınav kopyalanamadı", str(ex))
        self.reload()

    def _delete_exam(self):
        e = self._selected_exam()
        if e is None:
            return
        if not ask_confirm(self, "Sınavı sil", f"“{e['title']}” sınavı kalıcı olarak silinecek.",
                           "Sil", danger=True):
            return
        try:
            exam_db.delete_exam(e["id"])
        except ValueError as ex:
            show_error(self, "Sınav silinemedi", str(ex))
        self.reload()

    def _logged_in_count(self):
        return sum(1 for c in self.server.get_clients() if c["username"])

    def _publish_exam(self):
        e = self._selected_exam()
        if e is None:
            return
        n = self._logged_in_count()
        text = (f"“{e['title']}” sınavı hemen başlayacak ve {e['duration_minutes']} dakika "
                f"sürecek. Şu an giriş yapmış {n} kullanıcı var, yayınlanınca birkaç saniye "
                f"içinde sınavı görecekler.\n\nYayınlandıktan sonra sınav düzenlenemez.")
        if not ask_confirm(self, "Sınavı yayınla", text, "Yayınla"):
            return
        try:
            exam_db.publish_exam(e["id"])
        except ValueError as ex:
            show_error(self, "Sınav yayınlanamadı", str(ex))
        self.reload()

    def _close_exam(self):
        e = self._selected_exam()
        if e is None:
            return
        text = (f"“{e['title']}” sınavı süresi dolmadan bitirilecek. Öğrenciler bundan sonra "
                f"cevap gönderemez.")
        if not ask_confirm(self, "Sınavı sonlandır", text, "Sonlandır", danger=True):
            return
        try:
            exam_db.close_exam(e["id"])
        except ValueError as ex:
            show_error(self, "Sınav sonlandırılamadı", str(ex))
        self.reload()
