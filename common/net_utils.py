"""
common/net_utils.py
Ağ yardımcıları.
"""

import socket


def get_local_ip():
    """Bu bilgisayarın yerel ağdaki IP adresini bulur (öğrencilerin gireceği adres).
    İnternet gerekmez: UDP soketi hiçbir paket göndermeden sadece rota seçtirir."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        pass
    finally:
        s.close()
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"
