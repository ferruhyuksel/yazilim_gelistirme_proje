"""
ui/theme.py
Uygulamanın ortak görünümü (renkler, yazı boyutları, düğme/alan stilleri).
Tüm pencereler bu stil dosyasını main.py üzerinden otomatik alır.
Görünümü değiştirmek için sadece bu dosyadaki COLORS ve STYLESHEET düzenlenir.
"""

import base64
import tempfile
from pathlib import Path
from string import Template

COLORS = {
    "bg": "#F2F4F8",            # pencere arka planı
    "surface": "#FFFFFF",       # kart ve form yüzeyi
    "ink": "#1B2433",           # ana yazı rengi
    "muted": "#5B6677",         # ikincil yazı
    "border": "#D3D9E3",
    "hover": "#E8ECF4",
    "primary": "#1F5FBF",
    "primary_hover": "#1A4F9F",
    "primary_press": "#153F80",
    "brand": "#12304F",         # giriş ekranı sol panel
    "brand_text": "#B9C8DA",
    "danger": "#B3261E",
    "success": "#1E7A46",
}

# Açılır kutu oku (12x8 PNG). Qt stil dosyası ancak dosya yolu kabul ettiği için
# çalışma anında geçici klasöre yazılır.
_ARROW_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAICAYAAADN5B7xAAABCklEQVR4nGNgQAL19fVMDGgAmxhDTFplQERKaSQDAwNDWloaK0wcxg5LKHKPTCtLrK+vZ2Ksr69nuvP8x2ZePkGvDx9eh66Y07vGvr6eRf35c8ZZs2b9jkwssuHk5Tv84/u3a6y/OI0Z6+vrmZ4/Z+D4wfx7MzsHl9PXz59Sls3pmsvAwMAQllzsy8XJvYHh///rf/5+c1oyo/c1IwPDf0YGBsb/oaGFnOzCnEt4ePmDPn98l8rAwPCci5t3y8+f34++f/c5ePOKSS/h/kH2WGxG5bLk/Kb/SXmN/+Myqg7Yx8dzYPV8fX09E0wwJq1idUxGxZ7Q0EJOBgYGhtDQUGaMkIKA/4yEghUAFyZo2C3v180AAAAASUVORK5CYII="
)


def _arrow_path():
    path = Path(tempfile.gettempdir()) / "sinav_sistemi_arrow_down.png"
    try:
        path.write_bytes(base64.b64decode(_ARROW_PNG_B64))
    except OSError:
        pass  # yazılamazsa ok görünmez ama uygulama çalışır
    return path.as_posix()


_STYLESHEET = Template("""
QWidget {
    color: $ink;
    font-family: "Inter", "Noto Sans", "Ubuntu", "DejaVu Sans", sans-serif;
    font-size: 15px;
}
QMainWindow, QDialog { background: $bg; }
QLabel { background: transparent; }

QLineEdit, QPlainTextEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 10px 12px;
    min-height: 22px;
    selection-background-color: $primary;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QPlainTextEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid $primary; }

QPushButton {
    background: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 10px 20px;
    min-height: 22px;
    font-weight: 600;
}
QPushButton:hover { background: $hover; }
QPushButton:pressed { background: $border; }

QPushButton[variant="primary"] {
    background: $primary;
    border: 1px solid $primary;
    color: #FFFFFF;
}
QPushButton[variant="primary"]:hover { background: $primary_hover; border-color: $primary_hover; }
QPushButton[variant="primary"]:pressed { background: $primary_press; border-color: $primary_press; }

QPushButton[variant="link"] {
    background: transparent;
    border: none;
    color: $primary;
    padding: 8px;
}
QPushButton[variant="link"]:hover { background: transparent; color: $primary_press; }

QFrame#brandPanel { background: $brand; }
QLabel#brandTitle { color: #FFFFFF; font-size: 34px; font-weight: 700; }
QLabel#brandText { color: $brand_text; font-size: 16px; }
QLabel#brandFoot { color: $brand_text; font-size: 13px; }

QFrame#formArea { background: $surface; }
QLabel#formTitle { font-size: 28px; font-weight: 700; }
QLabel#formHint { color: $muted; font-size: 15px; }
QLabel#fieldLabel { font-size: 13px; font-weight: 600; }

QFrame#topBar { background: $surface; border-bottom: 1px solid $border; }
QLabel#appName { font-size: 19px; font-weight: 700; }
QLabel#userName { font-weight: 600; }
QLabel#userRole { color: $muted; font-size: 13px; }

QFrame#card { background: $surface; border: 1px solid $border; border-radius: 10px; }
QLabel#welcome { font-size: 30px; font-weight: 700; }
QLabel#hint { color: $muted; font-size: 16px; }

QLabel#msgTitle { font-size: 20px; font-weight: 700; }
QLabel#msgTitle[kind="error"] { color: $danger; }
QLabel#msgTitle[kind="info"] { color: $success; }
QLabel#msgText { font-size: 15px; color: $ink; }

QLabel#sectionTitle { font-size: 18px; font-weight: 700; }
QLabel#statusOk { color: $success; font-weight: 600; }
QLabel#serverAddress { font-size: 30px; font-weight: 700; color: $primary; }

QTableWidget {
    background: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    gridline-color: transparent;
    selection-background-color: #DCE7F7;
    selection-color: $ink;
}
QTableWidget::item { padding: 6px 10px; }
QHeaderView::section {
    background: $bg;
    border: none;
    border-bottom: 1px solid $border;
    padding: 8px 10px;
    font-weight: 600;
}

QPushButton[variant="danger"] { background: $danger; border: 1px solid $danger; color: #FFFFFF; }
QPushButton[variant="danger"]:hover { background: #8F1F19; border-color: #8F1F19; }
QPushButton[variant="icon"] {
    border: none; background: transparent; color: $muted; padding: 6px 10px; font-size: 18px;
}
QPushButton[variant="icon"]:hover { color: $danger; background: transparent; }

QLabel#pageTitle { font-size: 24px; font-weight: 700; }
QLabel#optionLetter { font-weight: 700; color: $muted; min-width: 18px; }
QLabel#countLabel { color: $muted; }
QLabel#errorText { color: $danger; font-weight: 600; }
QLabel#emptyState { color: $muted; font-size: 16px; }
QRadioButton { spacing: 8px; }

QListWidget {
    background: $surface; border: 1px solid $border; border-radius: 6px; padding: 4px; outline: none;
}
QListWidget::item { padding: 10px 12px; border-radius: 4px; }
QListWidget::item:selected { background: #DCE7F7; color: $ink; }
QComboBox QAbstractItemView {
    background: $surface; border: 1px solid $border;
    selection-background-color: #DCE7F7; selection-color: $ink; outline: none;
}

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }

QTabWidget::pane { border: none; border-top: 1px solid $border; }
QTabWidget::tab-bar { left: 28px; }
QTabBar::tab {
    padding: 14px 22px; margin-right: 4px; font-weight: 600; color: $muted;
    background: transparent; border: none; border-bottom: 3px solid transparent;
}
QTabBar::tab:selected { color: $primary; border-bottom: 3px solid $primary; }
QTabBar::tab:hover:!selected { color: $ink; }

QComboBox { padding-right: 36px; }
QComboBox::drop-down { border: none; background: transparent; width: 34px; }
QComboBox::down-arrow { image: url($arrow); width: 12px; height: 8px; margin-right: 14px; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button { width: 0px; border: none; }

QLabel#examTimer { font-size: 30px; font-weight: 700; }
QLabel#examTimer[urgent="true"] { color: $danger; }

QPushButton[nav] { padding: 0px; min-height: 42px; min-width: 42px; border-radius: 8px; }
QPushButton[nav="answered"] { background: #DCE7F7; border: 1px solid #9DB8E3; }
QPushButton[nav="empty"] { background: $surface; }
QPushButton[current="true"] { border: 2px solid $primary; color: $primary; }

QFrame#choiceCard { background: $surface; border: 2px solid $border; border-radius: 10px; }
QFrame#choiceCard:hover { border-color: #9DB8E3; }
QFrame#choiceCard[selected="true"] { background: #EEF4FD; border-color: $primary; }

QLabel#statusPending { color: #B45309; font-weight: 600; }
QFrame#answerBox { background: #F7F9FC; border: 1px solid $border; border-radius: 8px; }
QCheckBox { spacing: 8px; }

QPushButton:disabled { color: #9AA3B2; background: $bg; border-color: $border; }
QPushButton[variant="primary"]:disabled { background: #9DB8E3; border-color: #9DB8E3; color: #FFFFFF; }
QPushButton[variant="link"]:disabled { background: transparent; border: none; }
""")

STYLESHEET = _STYLESHEET.substitute(COLORS, arrow=_arrow_path())
