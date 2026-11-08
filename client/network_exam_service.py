"""
client/network_exam_service.py
Öğrenci uygulamasının sınav servisi: aktif sınavları listeler, sınav paketini alır.
"""

from client.network_client import ServerError
from common import protocol


class ServiceError(Exception):
    """connection_lost=True ise sunucuyla bağlantı kopmuştur (tekrar denemek işe yaramaz)."""

    def __init__(self, message, connection_lost=False):
        super().__init__(message)
        self.connection_lost = connection_lost


class NetworkExamService:
    def __init__(self, client):
        self.client = client

    def _call(self, type_, data=None):
        try:
            return self.client.request(type_, data)
        except ConnectionError as e:
            raise ServiceError(str(e), connection_lost=True)
        except ServerError as e:
            raise ServiceError(str(e))

    def list_exams(self):
        """Şu an açık sınavlar: [{id, title, duration_minutes, question_count,
        total_points, remaining_seconds, submitted}, ...]"""
        return self._call(protocol.LIST_EXAMS)["exams"]

    def get_exam(self, exam_id):
        """Sınav paketi (cevap anahtarı içermez)."""
        return self._call(protocol.GET_EXAM, {"exam_id": exam_id})["exam"]
