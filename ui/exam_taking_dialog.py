"""
ui/exam_taking_dialog.py
Öğrencinin sınavı çözdüğü ekran (öğrenci uygulaması).

- Soldan soru numaralarıyla gezinme, ortada tek soru, üstte geri sayım.
- Geri sayım, sunucunun verdiği kalan süreden yerel saatle akar. Süre bitince cevaplar
  otomatik gönderilir. Asıl süre kontrolü SUNUCUDADIR, buradaki sayaç yalnızca gösterge.
- Cevaplar, pencere kapansa bile (sınav açıkken) geri dönülebilsin diye çağıranın
  verdiği `answers` sözlüğünde tutulur.
- Cevap anahtarı bu pencereye hiç ulaşmaz (sunucu göndermez).
"""

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from client.network_exam_service import ServiceError
from ui.formatting import format_remaining
from ui.message_box import ask_confirm, show_error, show_info

# Soru türleri (sunucudaki db.question_bank değerleriyle aynı; öğrenci uygulaması
# veritabanı modüllerini yüklemesin diye burada ayrıca tanımlı)
TYPE_MULTIPLE_CHOICE = "multiple_choice"
TYPE_LABELS = {TYPE_MULTIPLE_CHOICE: "Çoktan seçmeli", "classic": "Klasik"}

URGENT_SECONDS = 60


def _repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _button(text, variant=None):
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


class ChoiceCard(QFrame):
    """Tıklanabilir şık kartı (harf + metin)."""

    clicked = Signal()

    def __init__(self, letter, text):
        super().__init__()
        self.setObjectName("choiceCard")
        self.setCursor(Qt.PointingHandCursor)
        letter_label = QLabel(letter)
        letter_label.setObjectName("optionLetter")
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)
        layout.addWidget(letter_label, alignment=Qt.AlignTop)
        layout.addWidget(text_label, stretch=1)

    def mousePressEvent(self, event):
        self.clicked.emit()

    def set_selected(self, selected):
        self.setProperty("selected", selected)
        _repolish(self)


class ExamTakingDialog(QDialog):
    def __init__(self, exam, exam_service, answers, parent=None):
        """exam: sunucudan gelen sınav paketi. answers: {soru_id: cevap}, çağıran tarafından
        saklanır (pencere kapanıp açılırsa cevaplar kaybolmasın)."""
        super().__init__(parent)
        self.exam = exam
        self.questions = exam["questions"]
        self.service = exam_service
        self.answers = answers
        self.index = 0
        self.submitted = False
        self._submitting = False
        self._force_close = False
        self._remaining0 = exam["remaining_seconds"]
        self._fetched_at = time.monotonic()
        self._cards = []

        self.setWindowTitle(exam["title"])
        self.resize(1200, 780)
        self.setMinimumSize(980, 640)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_top_bar())

        body = QHBoxLayout()
        body.setContentsMargins(28, 24, 28, 24)
        body.setSpacing(24)
        body.addWidget(self._build_navigator())
        body.addWidget(self._build_question_card(), stretch=1)
        root.addLayout(body, stretch=1)

        self._show_question(0)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(250)
        self._tick()

    # ------------------------------------------------------------------
    # Arayüz parçaları
    # ------------------------------------------------------------------

    def _build_top_bar(self):
        bar = QFrame()
        bar.setObjectName("topBar")
        title = QLabel(self.exam["title"])
        title.setObjectName("appName")
        self.progress_label = QLabel()
        self.progress_label.setObjectName("userRole")
        timer_caption = QLabel("Kalan süre")
        timer_caption.setObjectName("userRole")
        timer_caption.setAlignment(Qt.AlignRight)
        self.timer_label = QLabel()
        self.timer_label.setObjectName("examTimer")
        self.timer_label.setAlignment(Qt.AlignRight)
        timer_box = QVBoxLayout()
        timer_box.setSpacing(0)
        timer_box.addWidget(timer_caption)
        timer_box.addWidget(self.timer_label)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 12, 28, 12)
        layout.setSpacing(20)
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.progress_label)
        layout.addSpacing(16)
        layout.addLayout(timer_box)
        return bar

    def _build_navigator(self):
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(272)
        title = QLabel("Sorular")
        title.setObjectName("sectionTitle")

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        self._nav_buttons = []
        for i in range(len(self.questions)):
            btn = QPushButton(str(i + 1))
            btn.setProperty("nav", "empty")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, index=i: self._show_question(index))
            grid.addWidget(btn, i // 4, i % 4)
            self._nav_buttons.append(btn)
        grid.setRowStretch(grid.rowCount(), 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(grid_host)

        legend = QLabel("Dolu kutu: cevaplandı\nÇerçeveli kutu: şu anki soru")
        legend.setObjectName("countLabel")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(scroll, stretch=1)
        layout.addWidget(legend)
        return card

    def _build_question_card(self):
        card = QFrame()
        card.setObjectName("card")

        self.number_label = QLabel()
        self.number_label.setObjectName("sectionTitle")
        self.meta_label = QLabel()
        self.meta_label.setObjectName("countLabel")
        head = QHBoxLayout()
        head.addWidget(self.number_label)
        head.addStretch()
        head.addWidget(self.meta_label)

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text_label.setStyleSheet("font-size: 18px;")
        self.text_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.answer_layout = QVBoxLayout()
        self.answer_layout.setSpacing(10)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(18)
        content_layout.addWidget(self.text_label)
        content_layout.addLayout(self.answer_layout)
        content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)

        self.prev_btn = _button("←  Önceki")
        self.prev_btn.clicked.connect(lambda: self._show_question(self.index - 1))
        self.next_btn = _button("Sonraki  →")
        self.next_btn.clicked.connect(lambda: self._show_question(self.index + 1))
        self.submit_btn = _button("Sınavı gönder", "primary")
        self.submit_btn.clicked.connect(self._on_submit_clicked)
        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addWidget(self.prev_btn)
        footer.addWidget(self.next_btn)
        footer.addStretch()
        footer.addWidget(self.submit_btn)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(16)
        layout.addLayout(head)
        layout.addWidget(scroll, stretch=1)
        layout.addLayout(footer)
        return card

    # ------------------------------------------------------------------
    # Soru gösterme ve cevap tutma
    # ------------------------------------------------------------------

    def _clear_answer_area(self):
        while self.answer_layout.count():
            item = self.answer_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Hemen gizle ve ayır: deleteLater tek başına bir sonraki olay döngüsüne
                # kadar eski bileşeni ekranda bırakır (titreme / hayalet düğme).
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._cards = []

    def _show_question(self, index):
        if not 0 <= index < len(self.questions):
            return
        self.index = index
        q = self.questions[index]
        self.number_label.setText(f"Soru {index + 1} / {len(self.questions)}")
        self.meta_label.setText(f"{TYPE_LABELS.get(q['type'], q['type'])}     {q['points']:g} puan")
        self.text_label.setText(q["text"])

        self._clear_answer_area()
        if q["type"] == TYPE_MULTIPLE_CHOICE:
            current = self.answers.get(q["id"])
            for i, option in enumerate(q["options"]):
                card = ChoiceCard(chr(ord("A") + i), option)
                card.set_selected(current == i)
                card.clicked.connect(lambda i=i: self._choose(i))
                self._cards.append(card)
                self.answer_layout.addWidget(card)
            clear_btn = _button("Seçimi temizle", "link")
            clear_btn.clicked.connect(lambda: self._choose(None))
            self.answer_layout.addWidget(clear_btn, alignment=Qt.AlignLeft)
        else:
            edit = QPlainTextEdit()
            edit.setPlaceholderText("Cevabını buraya yaz")
            edit.setMinimumHeight(260)
            edit.setPlainText(self.answers.get(q["id"], ""))
            edit.textChanged.connect(lambda: self._on_text(q["id"], edit.toPlainText()))
            self.answer_layout.addWidget(edit)

        self.prev_btn.setEnabled(index > 0)
        self.next_btn.setEnabled(index < len(self.questions) - 1)
        self._refresh_nav()

    def _choose(self, option_index):
        q = self.questions[self.index]
        if option_index is None:
            self.answers.pop(q["id"], None)
        else:
            self.answers[q["id"]] = option_index
        for i, card in enumerate(self._cards):
            card.set_selected(option_index == i)
        self._refresh_nav()

    def _on_text(self, question_id, text):
        if text.strip():
            self.answers[question_id] = text
        else:
            self.answers.pop(question_id, None)
        self._refresh_nav()

    def _is_answered(self, question):
        value = self.answers.get(question["id"])
        if value is None:
            return False
        return bool(value.strip()) if isinstance(value, str) else True

    def _answered_count(self):
        return sum(1 for q in self.questions if self._is_answered(q))

    def _refresh_nav(self):
        for i, (q, btn) in enumerate(zip(self.questions, self._nav_buttons)):
            btn.setProperty("nav", "answered" if self._is_answered(q) else "empty")
            btn.setProperty("current", i == self.index)
            _repolish(btn)
        self.progress_label.setText(
            f"Cevaplanan: {self._answered_count()} / {len(self.questions)}")

    # ------------------------------------------------------------------
    # Süre
    # ------------------------------------------------------------------

    def _remaining(self):
        return self._remaining0 - (time.monotonic() - self._fetched_at)

    def _tick(self):
        left = self._remaining()
        self.timer_label.setText(format_remaining(left if left > 0 else 0))
        urgent = left <= URGENT_SECONDS
        if self.timer_label.property("urgent") != urgent:
            self.timer_label.setProperty("urgent", urgent)
            _repolish(self.timer_label)
        if left <= 0 and not self._submitting and not self.submitted:
            self._submit(auto=True)

    # ------------------------------------------------------------------
    # Gönderme
    # ------------------------------------------------------------------

    def _on_submit_clicked(self):
        total = len(self.questions)
        answered = self._answered_count()
        text = f"{total} sorudan {answered} tanesini cevapladın."
        if answered < total:
            text += f" {total - answered} soru boş kalacak."
        text += "\n\nGönderdikten sonra cevaplarını değiştiremezsin."
        if ask_confirm(self, "Sınavı gönder", text, "Gönder"):
            self._submit(auto=False)

    def _submit(self, auto):
        if self._submitting or self.submitted:
            return
        self._submitting = True
        self.submit_btn.setEnabled(False)
        if auto:
            self.submit_btn.setText("Gönderiliyor...")
        payload = {q["id"]: self.answers.get(q["id"]) for q in self.questions}
        try:
            self.service.submit_exam(self.exam["id"], payload)
        except ServiceError as e:
            self._submitting = False
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Sınavı gönder")
            if e.connection_lost:
                show_error(self, "Bağlantı koptu",
                           f"Cevapların gönderilemedi: {e}\n\nEğitmene haber ver. "
                           "Bu pencere açık kaldığı sürece cevapların burada duruyor.")
            else:
                show_error(self, "Cevaplar kabul edilmedi", str(e))
                self._close_now()
            return
        self.submitted = True
        self._timer.stop()
        show_info(
            self,
            "Süre doldu, cevapların gönderildi" if auto else "Cevapların gönderildi",
            "Cevapların eğitmene iletildi. Sonuçları eğitmen açıklayacak.",
        )
        self._close_now()

    def _close_now(self):
        self._force_close = True
        self.accept() if self.submitted else self.reject()

    def reject(self):
        """Esc veya pencereyi kapatma: gönderilmemiş cevaplar için onay iste."""
        if self._force_close or self.submitted or self._submitting:
            self._timer.stop()
            super().reject()
            return
        text = ("Cevapların henüz gönderilmedi. Çıkarsan sınav açık olduğu sürece geri dönüp "
                "kaldığın yerden devam edebilirsin, ama süre işlemeye devam eder.")
        if ask_confirm(self, "Sınavdan çık", text, "Çık", danger=True):
            self._timer.stop()
            super().reject()
