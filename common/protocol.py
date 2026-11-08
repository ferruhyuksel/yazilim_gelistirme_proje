"""
common/protocol.py
Sunucu ile istemcinin ortak mesaj protokolü. Her iki taraf da bu dosyayı kullanır.

Mesaj biçimi (TCP üzerinde):
    [4 bayt: yük uzunluğu, big-endian] [UTF-8 JSON yük]

İstek :  {"type": "login", "data": {...}, "token": "..." veya null}
Yanıt :  {"ok": true,  "data": {...}}
         {"ok": false, "error": "Kullanıcıya gösterilebilir hata metni"}

Uzunluk başlığı sayesinde TCP'nin akış yapısında mesaj sınırları karışmaz.
"""

import json
import struct

DEFAULT_PORT = 5050
MAX_MESSAGE_SIZE = 5 * 1024 * 1024  # 5 MB, bundan büyük mesajlar reddedilir

# İstek türleri
PING = "ping"
LOGIN = "login"
REGISTER = "register"
CHANGE_PASSWORD = "change_password"
LOGOUT = "logout"
LIST_EXAMS = "list_exams"   # öğrenci: şu an açık sınavlar
GET_EXAM = "get_exam"       # öğrenci: bir sınavın soruları (cevap anahtarsız)

_HEADER = struct.Struct("!I")


class ProtocolError(Exception):
    """Bozuk veya aşırı büyük mesaj."""


def ok_response(data=None):
    return {"ok": True, "data": data or {}}


def error_response(message):
    return {"ok": False, "error": message}


def send_message(sock, obj):
    payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_MESSAGE_SIZE:
        raise ProtocolError("Mesaj çok büyük.")
    sock.sendall(_HEADER.pack(len(payload)) + payload)


def _recv_exact(sock, size):
    buf = bytearray()
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise ConnectionError("Bağlantı kapandı.")
        buf.extend(chunk)
    return bytes(buf)


def recv_message(sock):
    """Bir mesaj okuyup JSON nesnesi olarak döner.
    Bağlantı kapanırsa ConnectionError, mesaj bozuksa ProtocolError fırlatır."""
    (length,) = _HEADER.unpack(_recv_exact(sock, _HEADER.size))
    if length > MAX_MESSAGE_SIZE:
        raise ProtocolError("Mesaj çok büyük.")
    raw = _recv_exact(sock, length)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProtocolError("Geçersiz mesaj.")
