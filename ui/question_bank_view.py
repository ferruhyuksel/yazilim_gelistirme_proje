"""
ui/question_bank_view.py
Eğitmen panelindeki "Soru bankası" sekmesi: filtreleme, ekleme, düzenleme, kopyalama, silme.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from db import question_bank as qb
from ui.category_dialog import CategoryDialog
from ui.message_box import ask_confirm, show_error
from ui.question_dialog import QuestionDialog


def _button(text, variant=None):
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


class QuestionBankView(QWidget):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

        title = QLabel("Soru bankası")
        title.setObjectName("pageTitle")
        categories_btn = _button("Kategoriler")
        categories_btn.clicked.connect(self._manage_categories)
        new_btn = _button("Yeni soru", "primary")
        new_btn.clicked.connect(self._new_question)

        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(categories_btn)
        head.addWidget(new_btn)

        # --- filtreler
        self.category_filter = QComboBox()
        self.category_filter.setMinimumWidth(220)
        self.type_filter = QComboBox()
        self.type_filter.setMinimumWidth(170)
        self.type_filter.addItem("Tüm türler", None)
        for t in qb.QUESTION_TYPES:
            self.type_filter.addItem(qb.TYPE_LABELS[t], t)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Soru metninde ara...")
        self.search_edit.setClearButtonEnabled(True)

        filters = QHBoxLayout()
        filters.setSpacing(12)
        filters.addWidget(self.category_filter)
        filters.addWidget(self.type_filter)
        filters.addWidget(self.search_edit, stretch=1)

        # --- tablo
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Tür", "Kategori", "Soru", "Puan"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 190)
        self.table.setColumnWidth(3, 80)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.itemDoubleClicked.connect(lambda _item: self._edit_question())

        self.empty_label = QLabel()
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)

        # --- alt satır
        self.edit_btn = _button("Düzenle")
        self.edit_btn.clicked.connect(self._edit_question)
        self.copy_btn = _button("Kopyala")
        self.copy_btn.clicked.connect(self._copy_question)
        self.delete_btn = _button("Sil")
        self.delete_btn.clicked.connect(self._delete_question)
        self.count_label = QLabel()
        self.count_label.setObjectName("countLabel")

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addWidget(self.edit_btn)
        footer.addWidget(self.copy_btn)
        footer.addWidget(self.delete_btn)
        footer.addStretch()
        footer.addWidget(self.count_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.setSpacing(16)
        layout.addLayout(head)
        layout.addLayout(filters)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self.empty_label, stretch=1)
        layout.addLayout(footer)

        self._reload_categories()
        self.category_filter.currentIndexChanged.connect(self.reload)
        self.type_filter.currentIndexChanged.connect(self.reload)
        self.search_edit.textChanged.connect(self.reload)
        self.reload()

    # ------------------------------------------------------------------

    def _reload_categories(self):
        current = self.category_filter.currentData() if self.category_filter.count() else None
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("Tüm kategoriler", None)
        self.category_filter.addItem("Kategorisiz", qb.UNCATEGORIZED)
        for c in qb.list_categories():
            self.category_filter.addItem(f"{c['name']} ({c['question_count']})", c["id"])
        for i in range(self.category_filter.count()):
            if self.category_filter.itemData(i) == current:
                self.category_filter.setCurrentIndex(i)
                break
        self.category_filter.blockSignals(False)

    def reload(self):
        questions = qb.list_questions(
            self.category_filter.currentData(),
            self.type_filter.currentData(),
            self.search_edit.text(),
        )
        self.table.setRowCount(len(questions))
        for row, q in enumerate(questions):
            cells = (
                qb.TYPE_LABELS[q["type"]],
                q["category_name"] or "Kategorisiz",
                " ".join(q["text"].split()),   # çok satırlı metni tek satıra indir
                f"{q['default_points']:g}",
            )
            for col, value in enumerate(cells):
                item = QTableWidgetItem(value)
                item.setToolTip(q["text"])
                if col == 0:
                    item.setData(Qt.UserRole, q["id"])
                self.table.setItem(row, col, item)

        has_rows = bool(questions)
        self.table.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)
        filtered = (self.category_filter.currentData() is not None
                    or self.type_filter.currentData() is not None
                    or self.search_edit.text().strip())
        self.empty_label.setText(
            "Bu filtrelere uyan soru yok." if filtered
            else "Henüz soru yok. Sağ üstteki \"Yeni soru\" düğmesiyle ilk soruyu ekle."
        )
        self.count_label.setText(f"{len(questions)} soru")
        self._update_buttons()

    def _selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.table.item(rows[0].row(), 0).data(Qt.UserRole)

    def _update_buttons(self):
        has = self._selected_id() is not None
        for btn in (self.edit_btn, self.copy_btn, self.delete_btn):
            btn.setEnabled(has)

    # ------------------------------------------------------------------

    def _new_question(self):
        if QuestionDialog(self.user_id, parent=self).exec():
            self._reload_categories()
            self.reload()

    def _load_selected(self):
        question_id = self._selected_id()
        if question_id is None:
            return None
        question = qb.get_question(question_id)
        if question is None:
            show_error(self, "Soru bulunamadı", "Bu soru artık yok. Liste yenileniyor.")
            self.reload()
        return question

    def _edit_question(self):
        question = self._load_selected()
        if question and QuestionDialog(self.user_id, question, parent=self).exec():
            self._reload_categories()
            self.reload()

    def _copy_question(self):
        question = self._load_selected()
        if question and QuestionDialog(self.user_id, question, as_copy=True, parent=self).exec():
            self._reload_categories()
            self.reload()

    def _delete_question(self):
        question = self._load_selected()
        if question is None:
            return
        preview = " ".join(question["text"].split())
        if len(preview) > 90:
            preview = preview[:90] + "..."
        if not ask_confirm(self, "Soruyu sil", f"“{preview}” sorusu kalıcı olarak silinecek.",
                           "Sil", danger=True):
            return
        try:
            qb.delete_question(question["id"])
        except ValueError as e:
            show_error(self, "Soru silinemedi", str(e))
            return
        self._reload_categories()
        self.reload()

    def _manage_categories(self):
        dialog = CategoryDialog(self)
        dialog.exec()
        if dialog.changed:
            self._reload_categories()
            self.reload()
