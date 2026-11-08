"""
ui/exam_dialog.py
Sınav hazırlama penceresi (yeni sınav veya taslak düzenleme).
Solda soru bankası, sağda sınavdaki sorular. Her soruya sınav içinde ayrı puan verilir.
Kaydedilen sınav TASLAK olur, yayınlama sınav listesinden yapılır.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDoubleSpinBox, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from db import exams as exam_db
from db import question_bank as qb
from ui.message_box import show_error


def _button(text, variant=None):
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


def _field(label_text, widget):
    box = QVBoxLayout()
    box.setSpacing(6)
    label = QLabel(label_text)
    label.setObjectName("fieldLabel")
    box.addWidget(label)
    box.addWidget(widget)
    return box


def _make_table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(46)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setShowGrid(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return table


class ExamDialog(QDialog):
    def __init__(self, user_id, exam=None, parent=None):
        """exam: db.exams.get_exam() çıktısı (düzenleme) ya da None (yeni sınav)."""
        super().__init__(parent)
        self.user_id = user_id
        self.exam = exam
        self.items = []   # sınavdaki sorular: {question_id, text, type, points}
        self.setWindowTitle("Sınavı düzenle" if exam else "Yeni sınav")
        self.resize(1200, 780)
        self.setMinimumSize(1000, 620)

        heading = QLabel(self.windowTitle())
        heading.setObjectName("pageTitle")

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("örn. Vize 1: Diziler ve işaretçiler")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(exam_db.MIN_DURATION, exam_db.MAX_DURATION)
        self.duration_spin.setValue(30)
        self.duration_spin.setSuffix(" dakika")
        self.duration_spin.setMinimumWidth(170)

        top = QHBoxLayout()
        top.setSpacing(16)
        top.addLayout(_field("Sınav başlığı", self.title_edit), stretch=1)
        top.addLayout(_field("Süre", self.duration_spin))

        columns = QHBoxLayout()
        columns.setSpacing(20)
        columns.addWidget(self._build_bank_card(), stretch=1)
        columns.addWidget(self._build_exam_card(), stretch=1)

        cancel_btn = _button("Vazgeç")
        cancel_btn.clicked.connect(self.reject)
        save_btn = _button("Taslak olarak kaydet", "primary")
        save_btn.clicked.connect(self._on_save)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(cancel_btn)
        footer.addWidget(save_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(heading)
        layout.addLayout(top)
        layout.addLayout(columns, stretch=1)
        layout.addLayout(footer)

        if exam:
            self.title_edit.setText(exam["title"])
            self.duration_spin.setValue(exam["duration_minutes"])
            self.items = [
                {"question_id": q["question_id"], "text": q["text"],
                 "type": q["type"], "points": q["points"]}
                for q in exam["questions"]
            ]
        self._rebuild_items()
        self._refresh_bank()

    # ------------------------------------------------------------------
    # Arayüz parçaları
    # ------------------------------------------------------------------

    def _build_bank_card(self):
        card = QFrame()
        card.setObjectName("card")
        title = QLabel("Soru bankası")
        title.setObjectName("sectionTitle")

        self.category_filter = QComboBox()
        self.category_filter.addItem("Tüm kategoriler", None)
        self.category_filter.addItem("Kategorisiz", qb.UNCATEGORIZED)
        for c in qb.list_categories():
            self.category_filter.addItem(c["name"], c["id"])
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Soru metninde ara...")
        self.search_edit.setClearButtonEnabled(True)
        filters = QHBoxLayout()
        filters.setSpacing(10)
        filters.addWidget(self.category_filter)
        filters.addWidget(self.search_edit, stretch=1)

        self.bank_table = _make_table(["Tür", "Soru", "Puan"])
        self.bank_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header = self.bank_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.bank_table.setColumnWidth(0, 130)
        self.bank_table.setColumnWidth(2, 70)
        self.bank_table.itemDoubleClicked.connect(lambda _item: self._add_selected())

        self.bank_empty = QLabel("Eklenecek soru kalmadı.")
        self.bank_empty.setObjectName("emptyState")
        self.bank_empty.setAlignment(Qt.AlignCenter)

        add_btn = _button("Seçilenleri sınava ekle  →", "primary")
        add_btn.clicked.connect(self._add_selected)
        hint = QLabel("Birden fazla soru seçmek için Ctrl veya Shift ile tıkla.")
        hint.setObjectName("countLabel")
        footer = QHBoxLayout()
        footer.addWidget(hint)
        footer.addStretch()
        footer.addWidget(add_btn)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addLayout(filters)
        layout.addWidget(self.bank_table, stretch=1)
        layout.addWidget(self.bank_empty, stretch=1)
        layout.addLayout(footer)

        self.category_filter.currentIndexChanged.connect(self._refresh_bank)
        self.search_edit.textChanged.connect(self._refresh_bank)
        return card

    def _build_exam_card(self):
        card = QFrame()
        card.setObjectName("card")
        title = QLabel("Sınavdaki sorular")
        title.setObjectName("sectionTitle")
        self.total_label = QLabel()
        self.total_label.setObjectName("countLabel")
        head = QHBoxLayout()
        head.addWidget(title)
        head.addStretch()
        head.addWidget(self.total_label)

        self.items_table = _make_table(["#", "Tür", "Soru", "Puan"])
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.items_table.setColumnWidth(0, 44)
        self.items_table.setColumnWidth(1, 130)
        self.items_table.setColumnWidth(3, 110)
        self.items_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.items_table.itemSelectionChanged.connect(self._update_item_buttons)

        self.items_empty = QLabel("Henüz soru eklenmedi.\nSoldaki listeden soru seç.")
        self.items_empty.setObjectName("emptyState")
        self.items_empty.setAlignment(Qt.AlignCenter)

        self.up_btn = _button("↑ Yukarı")
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn = _button("↓ Aşağı")
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.remove_btn = _button("Çıkar")
        self.remove_btn.clicked.connect(self._remove_selected)
        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addWidget(self.up_btn)
        footer.addWidget(self.down_btn)
        footer.addWidget(self.remove_btn)
        footer.addStretch()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addLayout(head)
        layout.addWidget(self.items_table, stretch=1)
        layout.addWidget(self.items_empty, stretch=1)
        layout.addLayout(footer)
        return card

    # ------------------------------------------------------------------
    # Soru bankası listesi (sınavda olmayanlar)
    # ------------------------------------------------------------------

    def _refresh_bank(self):
        used = {it["question_id"] for it in self.items}
        questions = [
            q for q in qb.list_questions(self.category_filter.currentData(), None,
                                         self.search_edit.text())
            if q["id"] not in used
        ]
        self.bank_table.setRowCount(len(questions))
        for row, q in enumerate(questions):
            cells = (qb.TYPE_LABELS[q["type"]], " ".join(q["text"].split()),
                     f"{q['default_points']:g}")
            for col, value in enumerate(cells):
                item = QTableWidgetItem(value)
                item.setToolTip(q["text"])
                if col == 0:
                    item.setData(Qt.UserRole, q["id"])
                self.bank_table.setItem(row, col, item)
        self.bank_table.setVisible(bool(questions))
        self.bank_empty.setVisible(not questions)

    def _add_selected(self):
        rows = sorted({i.row() for i in self.bank_table.selectedIndexes()})
        if not rows:
            return
        for row in rows:
            question = qb.get_question(self.bank_table.item(row, 0).data(Qt.UserRole))
            if question is None:
                continue
            self.items.append({
                "question_id": question["id"], "text": question["text"],
                "type": question["type"], "points": question["default_points"],
            })
        self._rebuild_items(select=len(self.items) - 1)
        self._refresh_bank()

    # ------------------------------------------------------------------
    # Sınavdaki sorular
    # ------------------------------------------------------------------

    def _rebuild_items(self, select=None):
        self.items_table.setRowCount(len(self.items))
        for i, it in enumerate(self.items):
            self.items_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.items_table.setItem(i, 1, QTableWidgetItem(qb.TYPE_LABELS[it["type"]]))
            text = QTableWidgetItem(" ".join(it["text"].split()))
            text.setToolTip(it["text"])
            self.items_table.setItem(i, 2, text)

            spin = QDoubleSpinBox()
            spin.setRange(0.5, qb.MAX_POINTS)
            spin.setDecimals(1)
            spin.setValue(it["points"])
            spin.setStyleSheet("QDoubleSpinBox { padding: 4px 8px; min-height: 20px; }")
            spin.valueChanged.connect(lambda value, index=i: self._on_points(index, value))
            self.items_table.setCellWidget(i, 3, spin)

        has = bool(self.items)
        self.items_table.setVisible(has)
        self.items_empty.setVisible(not has)
        self._update_total()
        if select is not None and 0 <= select < len(self.items):
            self.items_table.selectRow(select)
        self._update_item_buttons()

    def _on_points(self, index, value):
        self.items[index]["points"] = value
        self._update_total()

    def _update_total(self):
        total = sum(it["points"] for it in self.items)
        self.total_label.setText(f"{len(self.items)} soru, toplam {total:g} puan")

    def _selected_item_row(self):
        rows = self.items_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _update_item_buttons(self):
        row = self._selected_item_row()
        self.up_btn.setEnabled(row is not None and row > 0)
        self.down_btn.setEnabled(row is not None and row < len(self.items) - 1)
        self.remove_btn.setEnabled(row is not None)

    def _move(self, delta):
        row = self._selected_item_row()
        if row is None:
            return
        target = row + delta
        if not 0 <= target < len(self.items):
            return
        self.items[row], self.items[target] = self.items[target], self.items[row]
        self._rebuild_items(select=target)

    def _remove_selected(self):
        row = self._selected_item_row()
        if row is None:
            return
        del self.items[row]
        self._rebuild_items(select=min(row, len(self.items) - 1))
        self._refresh_bank()

    # ------------------------------------------------------------------

    def _on_save(self):
        items = [(it["question_id"], it["points"]) for it in self.items]
        try:
            if self.exam:
                exam_db.update_exam(self.exam["id"], self.title_edit.text(),
                                    self.duration_spin.value(), items)
            else:
                exam_db.create_exam(self.title_edit.text(), self.duration_spin.value(),
                                    items, self.user_id)
        except ValueError as e:
            show_error(self, "Sınav kaydedilemedi", str(e))
            return
        self.accept()
