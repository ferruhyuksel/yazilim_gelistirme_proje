"""
ui/formatting.py
Arayüzde ortak kullanılan küçük biçimlendirme yardımcıları.
"""


def format_remaining(seconds):
    """Kalan süreyi okunur biçime çevirir: 5400 -> '1 sa 30 dk', 754 -> '12:34'."""
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} sa {minutes:02d} dk"
    return f"{minutes:02d}:{secs:02d}"
