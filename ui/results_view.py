"""
ui/results_view.py
Eğitmen panelindeki "Sonuçlar" sekmesi: sınav seç, öğrenci bazlı puanları gör,
bir öğrencinin cevaplarını incele ve klasik soruları elle puanla.
Liste birkaç saniyede bir yenilenir (yeni gönderimler kendiliğinden belirir).
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from db import exams as exam_db
from db import submissions as sub_db
from ui.grading_dialog import GradingDialog

_PENDING_COLOR = "#B45309"


def _button(text, variant=None):
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


class ResultsView(QWidget):
    def __init__(self):
        super().__init__()
        self._rows = {}   # gönderim id -> satır bilgisi

        title = QLabel("Sonuçlar")
        title.setObjectName("pageTitle")
        self.exam_combo = QComboBox()
        self.exam_combo.setMinimumWidth(360)
        head = QHBoxLayout()
        head.setSpacing(16)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(self.exam_combo)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("countLabel")
        self.pending_only = QCheckBox("Yalnızca puanlanmayı bekleyenler")
        summary = QHBoxLayout()
        summary.addWidget(self.summary_label)
        summary.addStretch()
        summary.addWidget(self.pending_only)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Öğrenci", "Sınıf", "Gönderim zamanı", "Puan", "Doğru", "Durum"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, width in ((1, 90), (2, 210), (3, 120), (4, 80), (5, 190)):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.itemDoubleClicked.connect(lambda _item: self._open_selected())

        self.empty_label = QLabel()
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)

        self.open_btn = _button("Cevapları incele ve puanla", "primary")
        self.open_btn.clicked.connect(self._open_selected)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self.open_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.setSpacing(16)
        layout.addLayout(head)
        layout.addLayout(summary)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self.empty_label, stretch=1)
        layout.addLayout(footer)

        self._reload_exams()
        self.exam_combo.currentIndexChanged.connect(self.reload)
        self.pending_only.toggled.connect(self.reload)
        self.reload()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(4000)

    # ------------------------------------------------------------------

    def _reload_exams(self):
        """Taslak olmayan sınavları listeler, seçili sınavı korur."""
        current = self.exam_combo.currentData() if self.exam_combo.count() else None
        exams = [e for e in exam_db.list_exams() if e["status"] != exam_db.STATUS_DRAFT]
        signature = [(e["id"], e["title"], e["status"]) for e in exams]
        if signature == getattr(self, "_exam_signature", None):
            return
        self._exam_signature = signature
        self.exam_combo.blockSignals(True)
        self.exam_combo.clear()
        for e in exams:
            self.exam_combo.addItem(f"{e['title']}  ({exam_db.STATUS_LABELS[e['status']]})", e["id"])
        for i in range(self.exam_combo.count()):
            if self.exam_combo.itemData(i) == current:
                self.exam_combo.setCurrentIndex(i)
                break
        self.exam_combo.blockSignals(False)

    def _refresh(self):
        self._reload_exams()
        self.reload()

    def reload(self):
        selected = self._selected_id()
        exam_id = self.exam_combo.currentData()
        rows = sub_db.list_submissions(exam_id) if exam_id is not None else []
        self._rows = {r["id"]: r for r in rows}
        shown = [r for r in rows if r["pending_count"]] if self.pending_only.isChecked() else rows

        self.table.blockSignals(True)
        self.table.setRowCount(len(shown))
        for row, r in enumerate(shown):
            status = (f"{r['pending_count']} cevap bekliyor" if r["pending_count"]
                      else "Puanlandı")
            cells = (r["full_name"], r["class_name"] or "-", r["submitted_at"],
                     f"{r['total_score']:g} / {r['max_score']:g}", str(r["correct_count"]), status)
            for col, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.UserRole, r["id"])
                if col == 5 and r["pending_count"]:
                    item.setForeground(QColor(_PENDING_COLOR))
                self.table.setItem(row, col, item)
            if r["id"] == selected:
                self.table.selectRow(row)
        self.table.blockSignals(False)

        if exam_id is None:
            message = "Henüz yayınlanmış sınav yok. Sınavlar sekmesinden bir sınav yayınla."
        elif not rows:
            message = "Bu sınava henüz cevap gönderilmedi."
        else:
            message = "Puanlanmayı bekleyen cevap yok." if self.pending_only.isChecked() else ""
        self.table.setVisible(bool(shown))
        self.empty_label.setVisible(not shown)
        self.empty_label.setText(message)
        self._update_summary(exam_id)
        self._update_buttons()

    def _update_summary(self, exam_id):
        if exam_id is None:
            self.summary_label.setText("")
            return
        s = sub_db.results_summary(exam_id)
        parts = [f"{s['submission_count']} gönderim"]
        if s["average_score"] is not None:
            parts.append(f"Ortalama {s['average_score']:.1f} / {s['max_score']:g}")
            parts.append(f"En yüksek {s['highest_score']:g}   En düşük {s['lowest_score']:g}")
        if s["pending_count"]:
            parts.append(f"{s['pending_count']} cevap puanlanmayı bekliyor")
        self.summary_label.setText("     ".join(parts))

    def _selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.table.item(rows[0].row(), 0).data(Qt.UserRole)

    def _update_buttons(self):
        self.open_btn.setEnabled(self._selected_id() is not None)

    def _open_selected(self):
        submission = self._rows.get(self._selected_id())
        if submission is None:
            return
        title = self.exam_combo.currentText().rsplit("  (", 1)[0]
        dialog = GradingDialog(submission, title, self)
        dialog.exec()
        self.reload()
