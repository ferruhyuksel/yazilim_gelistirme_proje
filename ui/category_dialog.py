"""
ui/category_dialog.py
Kategori yönetimi: ekleme, yeniden adlandırma, silme.
Kategori silinirse içindeki sorular silinmez, 'kategorisiz' olur.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout,
)

from db import question_bank as qb
from ui.message_box import ask_confirm, show_error


class CategoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kategorileri yönet")
        self.resize(520, 560)
        self.changed = False  # çağıran taraf, değişiklik olduysa listeyi yeniler

        heading = QLabel("Kategoriler")
        heading.setObjectName("pageTitle")

        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_select)

        name_label = QLabel("Kategori adı")
        name_label.setObjectName("fieldLabel")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("örn. Diziler ve işaretçiler")

        self.add_btn = QPushButton("Ekle")
        self.add_btn.setProperty("variant", "primary")
        self.add_btn.clicked.connect(self._on_add)
        self.rename_btn = QPushButton("Seçiliyi yeniden adlandır")
        self.rename_btn.clicked.connect(self._on_rename)
        self.delete_btn = QPushButton("Seçiliyi sil")
        self.delete_btn.clicked.connect(self._on_delete)
        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.accept)

        actions = QHBoxLayout()
        actions.addWidget(self.add_btn)
        actions.addWidget(self.rename_btn)
        actions.addWidget(self.delete_btn)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(heading)
        layout.addWidget(self.list_widget, stretch=1)
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)
        layout.addLayout(actions)
        layout.addSpacing(6)
        layout.addLayout(footer)

        self._reload()

    def _selected(self):
        items = self.list_widget.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    def _reload(self, select_id=None):
        self.list_widget.clear()
        for c in qb.list_categories():
            item = QListWidgetItem(f"{c['name']}    ({c['question_count']} soru)")
            item.setData(Qt.UserRole, c)
            self.list_widget.addItem(item)
            if select_id == c["id"]:
                item.setSelected(True)
        self._on_select()

    def _on_select(self):
        cat = self._selected()
        self.rename_btn.setEnabled(cat is not None)
        self.delete_btn.setEnabled(cat is not None)
        if cat is not None:
            self.name_edit.setText(cat["name"])

    def _on_add(self):
        try:
            new_id = qb.add_category(self.name_edit.text())
        except ValueError as e:
            show_error(self, "Kategori eklenemedi", str(e))
            return
        self.changed = True
        self.name_edit.clear()
        self._reload(select_id=new_id)
        self.name_edit.clear()

    def _on_rename(self):
        cat = self._selected()
        if cat is None:
            return
        try:
            qb.rename_category(cat["id"], self.name_edit.text())
        except ValueError as e:
            show_error(self, "Kategori değiştirilemedi", str(e))
            return
        self.changed = True
        self._reload(select_id=cat["id"])

    def _on_delete(self):
        cat = self._selected()
        if cat is None:
            return
        n = cat["question_count"]
        text = f"“{cat['name']}” kategorisi silinecek."
        if n:
            text += f" İçindeki {n} soru silinmez, kategorisiz kalır."
        if not ask_confirm(self, "Kategoriyi sil", text, "Sil", danger=True):
            return
        try:
            qb.delete_category(cat["id"])
        except ValueError as e:
            show_error(self, "Kategori silinemedi", str(e))
            return
        self.changed = True
        self.name_edit.clear()
        self._reload()
