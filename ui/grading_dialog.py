"""
ui/grading_dialog.py
Eğitmenin bir öğrencinin cevaplarını incelediği ve klasik soruları elle puanladığı pencere.

- Çoktan seçmeli sorular otomatik puanlanmıştır: seçilen şık ve doğru şık gösterilir.
- Klasik sorularda öğrencinin cevabı ile beklenen cevap yan yana gösterilir, eğitmen puanı
  yazıp kaydeder. "Tam puan ver" ve "0 ver" kısayolları tek tıkla kaydeder.
- Daha önce puanlanmış cevap tekrar puanlanabilir. Toplam puan her kayıtta güncellenir.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from db import question_bank as qb
from db import submissions as sub_db
from ui.message_box import show_error


def _repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _button(text, variant=None):
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


def _caption(text):
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    return label


def _answer_box(text, muted=False):
    """Çerçeveli, seçilebilir, satır kaydıran metin kutusu."""
    box = QFrame()
    box.setObjectName("answerBox")
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if muted:
        label.setStyleSheet("color: #5B6677;")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.addWidget(label)
    return box


class AnswerCard(QFrame):
    """Tek bir sorunun kartı. Klasik soruda puanlama kontrollerini içerir."""

    saved = Signal()

    def __init__(self, answer):
        super().__init__()
        self.setObjectName("card")
        self.answer = answer
        self.max_points = answer["points"]

        title = QLabel(f"Soru {answer['position']}")
        title.setObjectName("sectionTitle")
        meta = QLabel(f"{qb.TYPE_LABELS[answer['type']]}     {self.max_points:g} puan")
        meta.setObjectName("countLabel")
        self.status = QLabel()
        head = QHBoxLayout()
        head.setSpacing(16)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(meta)
        head.addWidget(self.status)

        text = QLabel(answer["text"])
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text.setStyleSheet("font-size: 16px;")

        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(28, 22, 28, 22)
        self.layout_.setSpacing(10)
        self.layout_.addLayout(head)
        self.layout_.addWidget(text)

        if answer["type"] == qb.TYPE_MULTIPLE_CHOICE:
            self._build_choice()
        else:
            self._build_classic()
        self._refresh_status()

    # ------------------------------------------------------------------

    def _set_status(self, text, kind):
        self.status.setText(text)
        self.status.setObjectName(kind)   # statusOk | statusPending | errorText | countLabel
        _repolish(self.status)

    def _build_choice(self):
        a = self.answer
        options = a["options"]
        correct_index = int(a["answer_key"])
        correct_text = f"{chr(65 + correct_index)}) {options[correct_index]}"
        if a["given_answer"] is None:
            self.layout_.addWidget(_caption("Öğrencinin cevabı"))
            self.layout_.addWidget(_answer_box("Cevap verilmedi", muted=True))
        else:
            given = int(a["given_answer"])
            self.layout_.addWidget(_caption("Öğrencinin cevabı"))
            self.layout_.addWidget(_answer_box(f"{chr(65 + given)}) {options[given]}"))
        if not a["is_correct"]:
            self.layout_.addWidget(_caption("Doğru cevap"))
            self.layout_.addWidget(_answer_box(correct_text, muted=True))

    def _build_classic(self):
        a = self.answer
        if a["given_answer"] is None:
            self.layout_.addWidget(_caption("Öğrencinin cevabı"))
            self.layout_.addWidget(_answer_box("Cevap verilmedi", muted=True))
            self.spin = None
            return

        self.layout_.addWidget(_caption("Öğrencinin cevabı"))
        self.layout_.addWidget(_answer_box(a["given_answer"]))
        self.layout_.addWidget(_caption("Beklenen cevap"))
        self.layout_.addWidget(_answer_box(a["answer_key"], muted=True))
        if a["graded"] and a["graded_at"] is None and a["is_correct"]:
            # Gönderim anında sistem verdi (cevap beklenen cevapla birebir aynıydı)
            same = QLabel("Cevap beklenen cevapla birebir aynı olduğu için otomatik tam puan "
                          "verildi. İstersen puanı değiştirebilirsin.")
            same.setObjectName("statusOk")
            same.setWordWrap(True)
            self.layout_.addWidget(same)

        self.spin = QDoubleSpinBox()
        self.spin.setRange(0, self.max_points)
        self.spin.setDecimals(2)
        self.spin.setSingleStep(0.5)
        self.spin.setSuffix(f" / {self.max_points:g} puan")
        self.spin.setValue(a["score"] if a["graded"] else 0.0)
        self.spin.setMinimumWidth(190)
        self.spin.lineEdit().returnPressed.connect(self._save_spin)

        full_btn = _button("Tam puan ver")
        full_btn.clicked.connect(lambda: self._save(self.max_points))
        zero_btn = _button("0 ver")
        zero_btn.clicked.connect(lambda: self._save(0))
        save_btn = _button("Kaydet", "primary")
        save_btn.clicked.connect(self._save_spin)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self.spin)
        row.addWidget(save_btn)
        row.addSpacing(12)
        row.addWidget(full_btn)
        row.addWidget(zero_btn)
        row.addStretch()
        self.layout_.addSpacing(4)
        self.layout_.addLayout(row)

    def _refresh_status(self):
        a = self.answer
        if a["type"] == qb.TYPE_MULTIPLE_CHOICE:
            if a["is_correct"]:
                self._set_status(f"Doğru   {a['score']:g} puan", "statusOk")
            elif a["given_answer"] is None:
                self._set_status("Boş   0 puan", "countLabel")
            else:
                self._set_status("Yanlış   0 puan", "errorText")
        elif a["given_answer"] is None:
            self._set_status("Boş   0 puan", "countLabel")
        elif a["graded"] and a["graded_at"] is None:
            self._set_status(f"Otomatik puan   {a['score']:g} / {self.max_points:g}", "statusOk")
        elif a["graded"]:
            self._set_status(f"Elle puanlandı   {a['score']:g} / {self.max_points:g}", "statusOk")
        else:
            self._set_status("Puanlanmayı bekliyor", "statusPending")

    def _save_spin(self):
        self._save(self.spin.value())

    def _save(self, points):
        try:
            sub_db.grade_answer(self.answer["answer_id"], points)
        except ValueError as e:
            show_error(self, "Puan kaydedilemedi", str(e))
            return
        self.answer["score"] = round(float(points), 2)
        self.answer["graded"] = True
        self.answer["graded_at"] = "elle"   # yalnızca 'boş değil' bilgisi kullanılır
        self.answer["is_correct"] = self.answer["score"] >= self.max_points
        self.spin.setValue(self.answer["score"])
        self._refresh_status()
        self.saved.emit()


class GradingDialog(QDialog):
    def __init__(self, submission, exam_title, parent=None):
        """submission: db.submissions.list_submissions() satırı."""
        super().__init__(parent)
        self.submission_id = submission["id"]
        self.changed = False   # çağıran taraf, puan değiştiyse listeyi yeniler
        self.setWindowTitle(f"Cevaplar: {submission['full_name']}")
        self.resize(980, 780)
        self.setMinimumSize(800, 560)

        heading = QLabel(submission["full_name"])
        heading.setObjectName("pageTitle")
        info = QLabel(f"{exam_title}     Sınıf: {submission['class_name'] or '-'}     "
                      f"Gönderim: {submission['submitted_at']}")
        info.setObjectName("countLabel")
        self.total_label = QLabel()
        self.total_label.setObjectName("pageTitle")
        self.pending_label = QLabel()
        right = QVBoxLayout()
        right.setSpacing(2)
        right.addWidget(self.total_label, alignment=Qt.AlignRight)
        right.addWidget(self.pending_label, alignment=Qt.AlignRight)
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(heading)
        left.addWidget(info)
        top = QHBoxLayout()
        top.addLayout(left)
        top.addStretch()
        top.addLayout(right)

        content = QWidget()
        cards = QVBoxLayout(content)
        cards.setContentsMargins(0, 0, 10, 0)
        cards.setSpacing(16)
        for answer in sub_db.get_submission_answers(self.submission_id):
            card = AnswerCard(answer)
            card.saved.connect(self._on_saved)
            cards.addWidget(card)
        cards.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)

        close_btn = _button("Kapat", "primary")
        close_btn.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addLayout(top)
        layout.addWidget(scroll, stretch=1)
        layout.addLayout(footer)

        self._refresh_totals()

    def _on_saved(self):
        self.changed = True
        self._refresh_totals()

    def _refresh_totals(self):
        info = sub_db.get_submission(self.submission_id)
        self.total_label.setText(f"{info['total_score']:g} / {info['max_score']:g}")
        if info["pending_count"]:
            self.pending_label.setObjectName("statusPending")
            self.pending_label.setText(f"{info['pending_count']} cevap puanlanmayı bekliyor")
        else:
            self.pending_label.setObjectName("statusOk")
            self.pending_label.setText("Tüm cevaplar puanlandı")
        _repolish(self.pending_label)
