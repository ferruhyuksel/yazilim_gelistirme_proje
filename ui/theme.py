"""
ui/theme.py
Uygulamanın ortak görünümü (renkler, yazı boyutları, düğme/alan stilleri).
Tüm pencereler bu stil dosyasını main.py üzerinden otomatik alır.
Görünümü değiştirmek için sadece bu dosyadaki COLORS ve STYLESHEET düzenlenir.
"""

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

_STYLESHEET = Template("""
QWidget {
    color: $ink;
    font-family: "Inter", "Noto Sans", "Ubuntu", "DejaVu Sans", sans-serif;
    font-size: 15px;
}
QMainWindow, QDialog { background: $bg; }
QLabel { background: transparent; }

QLineEdit {
    background: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 10px 12px;
    min-height: 22px;
    selection-background-color: $primary;
    selection-color: #FFFFFF;
}
QLineEdit:focus { border: 1px solid $primary; }

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
""")

STYLESHEET = _STYLESHEET.substitute(COLORS)
