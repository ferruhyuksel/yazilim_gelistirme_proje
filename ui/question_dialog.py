"""
ui/question_dialog.py
Soru ekleme / düzenleme / kopyalama penceresi.
Kaydetme işlemini pencerenin kendisi yapar: hata varsa uyarı gösterir ve açık kalır.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QRadioButton, QScrollArea, QVBoxLayout, QWidget,
)

from db import question_bank as qb
from ui.message_box import show_error


def _field(label_text, widget):
    box = QVBoxLayout()
    box.setSpacing(6)
    label = QLabel(label_text)
    label.setObjectName("fieldLabel")
    box.addWidget(label)
    box.addWidget(widget)
    return box


class OptionRow(QWidget):
    """Bir şık satırı: doğru şık seçici + harf + metin + kaldır düğmesi."""

    def __init__(self, group, on_remove):
        super().__init__()
        self.radio = QRadioButton()
        self.radio.setToolTip("Doğru şık")
        group.addButton(self.radio)
        self.letter = QLabel()
        self.letter.setObjectName("optionLetter")
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Şık metni")
        self.remove_btn = QPushButton("×")
        self.remove_btn.setProperty("variant", "icon")
        self.remove_btn.setToolTip("Şıkkı kaldır")
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.clicked.connect(lambda: on_remove(self))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.radio)
        layout.addWidget(self.letter)
        layout.addWidget(self.edit, stretch=1)
        layout.addWidget(self.remove_btn)


class QuestionDialog(QDialog):
    def __init__(self, user_id, question=None, as_copy=False, parent=None):
        """question verilmezse yeni soru. question + as_copy=True ise kopya olarak yeni soru."""
        super().__init__(parent)
        self.user_id = user_id
        self.question = None if as_copy else question
        if self.question:
            title = "Soruyu düzenle"
        elif as_copy:
            title = "Soruyu kopyala"
        else:
            title = "Yeni soru"
        self.setWindowTitle(title)
        self.resize(720, 780)
        self.setMinimumSize(640, 520)

        # --- üst satır: tür, kategori, puan
        self.type_combo = QComboBox()
        for t in qb.QUESTION_TYPES:
            self.type_combo.addItem(qb.TYPE_LABELS[t], t)
        self.type_combo.currentIndexChanged.connect(self._update_type_sections)

        self.category_combo = QComboBox()
        self.category_combo.addItem("Kategorisiz", None)
        for c in qb.list_categories():
            self.category_combo.addItem(c["name"], c["id"])

        self.points_spin = QDoubleSpinBox()
        self.points_spin.setRange(0.5, qb.MAX_POINTS)
        self.points_spin.setDecimals(1)
        self.points_spin.setSingleStep(1)
        self.points_spin.setValue(10)
        self.points_spin.setSuffix(" puan")

        top = QHBoxLayout()
        top.setSpacing(16)
        top.addLayout(_field("Soru türü", self.type_combo), stretch=2)
        top.addLayout(_field("Kategori", self.category_combo), stretch=2)
        top.addLayout(_field("Varsayılan puan", self.points_spin), stretch=1)

        # --- soru metni
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Soru metnini yaz")
        self.text_edit.setMinimumHeight(110)

        # --- çoktan seçmeli bölümü
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.rows = []
        self.options_layout = QVBoxLayout()
        self.options_layout.setSpacing(8)
        self.add_option_btn = QPushButton("+ Şık ekle")
        self.add_option_btn.setProperty("variant", "link")
        self.add_option_btn.setCursor(Qt.PointingHandCursor)
        self.add_option_btn.clicked.connect(lambda: self._add_option())

        self.mc_box = QWidget()
        mc_layout = QVBoxLayout(self.mc_box)
        mc_layout.setContentsMargins(0, 0, 0, 0)
        mc_layout.setSpacing(8)
        mc_label = QLabel("Şıklar (doğru şıkkı soldaki daireyle işaretle)")
        mc_label.setObjectName("fieldLabel")
        mc_layout.addWidget(mc_label)
        mc_layout.addLayout(self.options_layout)
        mc_layout.addWidget(self.add_option_btn, alignment=Qt.AlignLeft)

        # --- klasik bölümü
        self.answer_edit = QPlainTextEdit()
        self.answer_edit.setPlaceholderText("Beklenen cevabı yaz")
        self.answer_edit.setMinimumHeight(110)
        self.classic_box = QWidget()
        classic_layout = QVBoxLayout(self.classic_box)
        classic_layout.setContentsMargins(0, 0, 0, 0)
        classic_layout.addLayout(_field("Beklenen cevap", self.answer_edit))

        # --- kaydırılabilir form alanı
        content = QWidget()
        form = QVBoxLayout(content)
        form.setContentsMargins(4, 4, 12, 4)
        form.setSpacing(16)
        form.addLayout(top)
        form.addLayout(_field("Soru metni", self.text_edit))
        form.addWidget(self.mc_box)
        form.addWidget(self.classic_box)
        form.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)

        # --- alt düğmeler
        cancel_btn = QPushButton("Vazgeç")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Kaydet")
        save_btn.setProperty("variant", "primary")
        save_btn.setMinimumWidth(120)
        save_btn.clicked.connect(self._on_save)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        layout.addWidget(scroll, stretch=1)
        layout.addLayout(buttons)

        if question:
            self._fill(question)
        else:
            for _ in range(4):
                self._add_option()
        self._update_type_sections()

    # ------------------------------------------------------------------

    def _fill(self, q):
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(q["type"])))
        self.category_combo.setCurrentIndex(max(0, self.category_combo.findData(q["category_id"])))
        self.points_spin.setValue(q["default_points"])
        self.text_edit.setPlainText(q["text"])
        if q["type"] == qb.TYPE_MULTIPLE_CHOICE:
            for option in q["options"]:
                self._add_option(option)
            self.rows[int(q["answer_key"])].radio.setChecked(True)
        else:
            for _ in range(4):
                self._add_option()
            self.answer_edit.setPlainText(q["answer_key"])

    def _update_type_sections(self):
        is_mc = self.type_combo.currentData() == qb.TYPE_MULTIPLE_CHOICE
        self.mc_box.setVisible(is_mc)
        self.classic_box.setVisible(not is_mc)

    def _add_option(self, text=""):
        if len(self.rows) >= qb.MAX_OPTIONS:
            return
        row = OptionRow(self.group, self._remove_option)
        row.edit.setText(text)
        self.rows.append(row)
        self.options_layout.addWidget(row)
        self._refresh_rows()

    def _remove_option(self, row):
        if len(self.rows) <= qb.MIN_OPTIONS:
            return
        self.group.removeButton(row.radio)
        self.rows.remove(row)
        self.options_layout.removeWidget(row)
        row.deleteLater()
        self._refresh_rows()

    def _refresh_rows(self):
        for i, row in enumerate(self.rows):
            row.letter.setText(chr(ord("A") + i))
            row.remove_btn.setEnabled(len(self.rows) > qb.MIN_OPTIONS)
        self.add_option_btn.setEnabled(len(self.rows) < qb.MAX_OPTIONS)

    def _on_save(self):
        qtype = self.type_combo.currentData()
        category_id = self.category_combo.currentData()
        text = self.text_edit.toPlainText()
        points = self.points_spin.value()

        if qtype == qb.TYPE_MULTIPLE_CHOICE:
            options = [r.edit.text() for r in self.rows]
            checked = [i for i, r in enumerate(self.rows) if r.radio.isChecked()]
            answer_key = checked[0] if checked else None
        else:
            options = None
            answer_key = self.answer_edit.toPlainText()

        try:
            if self.question:
                qb.update_question(self.question["id"], qtype, text, category_id,
                                   options, answer_key, points)
            else:
                qb.add_question(qtype, text, category_id, options, answer_key,
                                points, self.user_id)
        except ValueError as e:
            show_error(self, "Soru kaydedilemedi", str(e))
            return
        self.accept()
