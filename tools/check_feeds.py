"""Quick check of the alert feeds from this computer (run it from Israel).
Prints the raw answer of the primary OREF feed and of the backup feed, so the
guessed formats in red_alert.py (BACKUP_URL, BACKUP_THREAT_TO_CAT, NOTICE_CATS)
can be confirmed.   Usage:  python tools/check_feeds.py"""
import requests

HEADERS = {
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36",
}
URLS = [
    "https://www.oref.org.il/WarningMessages/alert/alerts.json",
    "https://api.tzevaadom.co.il/notifications",
    "https://www.oref.org.il/warningMessages/alert/History/AlertsHistory.json",
]
for url in URLS:
    print("=" * 70, "\n", url)
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        print("HTTP", r.status_code, "| bytes:", len(r.content))
        print(repr(r.text[:1500]))
    except Exception as e:
        print("FAILED:", type(e).__name__, e)
