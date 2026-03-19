#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Red Alert Monitor v5.0  -  התרעות צבע אדום
Real-time IDF Home Front Command alerts
+ Google location sharing  + multi-sound  + crash fix
+ Telegram bot auto-setup  + map auto-close  + green all-clear fix
"""
import sys, os, json, time, math, threading, subprocess, ctypes, winreg, hashlib, sqlite3
from datetime import datetime
from collections import deque

# ── Elevation ────────────────────────────────────────────────────
def _ensure_admin():
    try:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                f'"{os.path.abspath(__file__)}"', None, 1)
            sys.exit(0)
    except Exception:
        pass
_ensure_admin()

# ── auto-install ─────────────────────────────────────────────────
for _pkg in ["requests", "PyQt5"]:
    try:
        __import__(_pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", _pkg, "--quiet"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

import requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame, QSystemTrayIcon, QMenu, QAction, QDialog,
    QListWidget, QListWidgetItem, QLineEdit, QAbstractItemView,
    QDesktopWidget, QSizeGrip, QCheckBox, QMessageBox,
    QRadioButton, QButtonGroup, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QRectF, QUrl
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen, QLinearGradient,
    QIcon, QPixmap, QPainterPath
)

# ── WebEngine flags — must be set BEFORE QApplication is created ──────────
# Chromium crashes when running as Administrator (UAC elevated) with GPU on.
# Disable GPU and software rasterizer to prevent silent C++ crashes.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                      "--disable-gpu --disable-software-rasterizer "
                      "--no-sandbox --disable-dev-shm-usage")
# Also suppress Chromium log spam
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

_HAS_WEB = False
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage
    _HAS_WEB = True
except ImportError:
    pass

APP_VERSION  = "5.0.0"
APP_NAME     = "התרעות צבע אדום"
INSTALL_DIR  = r"C:\RedAlertIDF"          # תיקיית התקנה קבועה
INSTALL_EXE  = os.path.join(INSTALL_DIR, "RedAlertMonitor.exe")
INSTALL_VBS  = os.path.join(INSTALL_DIR, "launch.vbs")
INSTALL_PY   = os.path.join(INSTALL_DIR, "red_alert.py")
POLL_MS     = 2000
OREF_URL    = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
API_HEADERS = {
    "Referer":          "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36",
    "Accept":           "application/json, text/javascript, */*; q=0.01",
    "Accept-Language":  "he-IL,he;q=0.9",
}
CFG_PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                        "RedAlert", "config.json")

GPROFILE_PATH  = os.path.join(os.path.dirname(CFG_PATH), "google_profile")
GMAP_SHARE_URL = "https://www.google.com/maps"

# Google Maps internal location-sharing endpoint (cookie-based auth)
GMAP_LOC_URL = (
    "https://maps.google.com/maps/rpc/locationsharing/read"
    "?authuser=2&hl=he&gl=il"
    "&pb=!1m7!8m6!1m3!1i14!2f31.5!3f35.0!2i15!3x4!2m2!1e1!3m3!1m2!1i400!2i280"
)

# ════════════════════════════════════════════════════════════════
#  SOUND PROFILES  (freq_hz, duration_ms, pause_after_ms)
# ════════════════════════════════════════════════════════════════
SOUND_PROFILES = {
    "standard": {
        "name":  "סטנדרטי – 3 צפירות עולות",
        "beeps": [(800,160,40),(1100,160,40),(1400,160,70),(800,500,0)],
    },
    "urgent": {
        "name":  "דחוף – ריפוד מהיר",
        "beeps": [(1400,60,0),(800,60,0)]*4 + [(1400,400,0)],
    },
    "siren": {
        "name":  "אזעקה – טון עולה ויורד",
        "beeps": [(500,200,0),(650,200,0),(800,200,0),(950,200,0),(1100,300,100),
                  (950,200,0),(800,200,0),(650,200,0),(500,400,0)],
    },
    "soft": {
        "name":  "עדין – טון נמוך",
        "beeps": [(650,400,100),(800,300,100),(650,500,0)],
    },
}
FRIEND_SOUND_BEEPS = [(1200,100,0),(1500,100,0),(1800,250,80),(1500,100,0),(1800,400,0)]

# ════════════════════════════════════════════════════════════════
#  CITY COORDINATES
# ════════════════════════════════════════════════════════════════
CITY_COORDS = {
    "תל אביב - מרכז העיר":(32.080,34.781),"תל אביב - דרום העיר":(32.053,34.761),
    "תל אביב - צפון העיר":(32.100,34.792),"ירושלים":(31.768,35.214),
    "חיפה":(32.794,34.990),"באר שבע":(31.252,34.791),"אשדוד":(31.804,34.655),
    "אשקלון":(31.669,34.574),"נתניה":(32.329,34.856),"רחובות":(31.894,34.811),
    "בת ים":(32.017,34.750),"חולון":(32.011,34.774),"רמת גן":(32.068,34.824),
    "בני ברק":(32.084,34.834),"פתח תקווה":(32.094,34.888),"ראשון לציון":(31.973,34.801),
    "הרצליה":(32.166,34.844),"כפר סבא":(32.176,34.908),"רעננה":(32.185,34.871),
    "הוד השרון":(32.150,34.894),"נס ציונה":(31.930,34.799),"לוד":(31.952,34.895),
    "רמלה":(31.930,34.868),"מודיעין-מכבים-רעות":(31.893,35.010),
    "קריית שמונה":(33.207,35.571),"נהריה":(33.004,35.095),"עכו":(32.921,35.068),
    "חדרה":(32.434,34.918),"נתיבות":(31.418,34.590),"שדרות":(31.526,34.597),
    "אופקים":(31.315,34.622),"דימונה":(31.068,35.033),"ירוחם":(30.989,34.931),
    "ערד":(31.259,35.213),"מצפה רמון":(30.610,34.801),"אילת":(29.558,34.948),
    "טבריה":(32.792,35.531),"צפת":(32.965,35.496),"עפולה":(32.607,35.290),
    "בית שאן":(32.499,35.500),"נצרת":(32.700,35.304),"קריית אתא":(32.813,35.110),
    "קריית ביאליק":(32.835,35.078),"קריית מוצקין":(32.839,35.076),
    "קריית ים":(32.853,35.067),"טירת כרמל":(32.761,34.973),"נשר":(32.775,35.033),
    "גדרה":(31.812,34.773),"יבנה":(31.877,34.744),"ראש העין":(32.095,34.958),
    "פרדס חנה-כרכור":(32.476,34.974),"זכרון יעקב":(32.571,34.953),
    "מגדל העמק":(32.676,35.238),"יקנעם עילית":(32.659,35.106),
    "קריית מלאכי":(31.729,34.743),"גן יבנה":(31.790,34.707),
    "כרמיאל":(32.914,35.294),"שפרעם":(32.806,35.167),"יסוד המעלה":(33.051,35.594),
    "קצרין":(32.994,35.691),"בית שמש":(31.755,34.992),"קריית גת":(31.610,34.770),
    "נוף הגליל":(32.708,35.325),"רמת השרון":(32.147,34.839),"גבעתיים":(32.071,34.810),
    "אור יהודה":(32.029,34.853),"יהוד-מונוסון":(32.034,34.889),
    "קריית אונו":(32.063,34.869),"גבעת שמואל":(32.080,34.850),
    "תל מונד":(32.261,34.924),"בנימינה-גבעת עדה":(32.524,34.945),
    "כפר קרע":(32.507,35.106),"אום אל-פחם":(32.516,35.154),
    "באקה אל-גרבייה":(32.416,35.040),"טייבה":(32.308,34.996),
    "קלנסווה":(32.282,34.986),"רהט":(31.394,34.754),"תל שבע":(31.250,34.730),
    "עומר":(31.270,34.853),"להבים":(31.370,34.819),"ניצן":(31.720,34.629),
    "נחל עוז":(31.476,34.487),"כפר עזה":(31.490,34.530),"בארי":(31.460,34.490),
    "רעים":(31.515,34.513),"מפלסים":(31.600,34.570),"יד מרדכי":(31.630,34.551),
    "זיקים":(31.648,34.535),"שרשרת":(31.598,34.543),"מגן":(31.280,34.470),
    "נבטים":(31.170,34.650),"חצרים":(31.268,34.786),"מיתר":(31.220,34.940),
    "ביתר עילית":(31.696,35.123),"מודיעין עילית":(31.931,35.043),
    "אריאל":(32.106,35.167),"מעלה אדומים":(31.777,35.299),
    "גוש עציון":(31.650,35.110),"בית אל":(31.940,35.220),
    "אפרת":(31.651,35.154),"דולב":(31.956,35.143),"קדומים":(32.156,35.159),
    "אלקנה":(32.108,35.029),"כוכב יאיר":(32.210,34.967),"שוהם":(31.999,34.957),
    "אור עקיבא":(32.504,34.920),"קיסריה":(32.497,34.893),"כפר יונה":(32.315,34.937),
    "חצור הגלילית":(32.979,35.399),"ראש פינה":(32.972,35.545),
    "מגדל":(32.832,35.508),"עין גב":(32.783,35.628),
    "מרום גולן":(33.121,35.767),"מג'דל שמס":(33.272,35.771),
    "אשקלון - מרכז":(31.668,34.574),"אשקלון - צפון":(31.693,34.573),
    "חוף אשקלון":(31.710,34.553),"לכיש":(31.550,34.850),
    "שפיר":(31.620,34.760),"יואב":(31.680,34.730),
    "קריית עקרון":(31.870,34.820),"מזכרת בתיה":(31.855,34.837),
    "ניר עם":(31.510,34.528),"גבעת ברנר":(31.840,34.820),
    # מושבים ויישובים נוספים
    "ברקת":(32.080,34.940),"כפר מל":(32.270,34.858),
    "נורדיה":(32.305,34.876),"בית חנינא":(31.832,35.229),"מעלה מכמש":(31.857,35.280),
    "גבעת זאב":(31.870,35.165),
    "אלעזר":(31.648,35.121),"כפר עציון":(31.658,35.114),
    "עלי":(32.054,35.282),"שילה":(32.052,35.299),"עפרה":(31.975,35.233),
    "קרני שומרון":(32.167,35.067),
    "מעלה שומרון":(32.117,35.074),
    "מכמורת":(32.360,34.858),"גן השרון":(32.206,34.903),
    "אבן יהודה":(32.279,34.888),"צור יצחק":(32.237,34.912),
    "כפר ויתקין":(32.380,34.893),"חרוצים":(32.355,34.902),
    "שפיים":(32.230,34.836),"הרצליה פיתוח":(32.170,34.817),
    "קדימה-צורן":(32.274,34.916),"טירה":(32.232,34.951),
    "ג'לג'וליה":(32.153,34.957),"כפר קאסם":(32.114,34.977),
    "ראשון לציון - מזרח":(31.985,34.832),"נס ציונה - מזרח":(31.921,34.819),
    "חולון - מזרח":(32.008,34.784),"בת ים - מזרח":(32.015,34.762),
    "מבשרת ציון":(31.801,35.154),"מעלה אדומים - מזרח":(31.775,35.317),
    "אבו גוש":(31.808,35.111),"ביר נבאלה":(31.847,35.224),
    "בית שמש - ב":(31.745,34.989),"צור הדסה":(31.726,35.064),
    "בית זית":(31.806,35.132),"ירושלים - קטמון":(31.754,35.200),
    "ירושלים - גילה":(31.736,35.175),"ירושלים - הר חומה":(31.726,35.218),
    "תלפיות מזרח":(31.748,35.237),"ירושלים - ארנונה":(31.751,35.221),
    "כפר סבא - מזרח":(32.178,34.929),"אלפי מנשה":(32.157,35.046),
    "פדואל":(32.140,35.003),"עמנואל":(32.147,35.138),
    "חלמיש":(31.956,35.124),"בית חורון":(31.889,35.072),
    "כפר נפאח":(32.993,35.655),"אל רום":(33.096,35.755),
    "נווה אטיב":(33.152,35.634),
    "מסעדה":(33.240,35.768),"בוקעתא":(33.238,35.755),
    "קצרין - מזרח":(33.010,35.710),"אלי עד":(32.982,35.649),
    "נוב":(32.965,35.618),"אניעם":(32.975,35.694),
    "שדה אליהו":(32.550,35.527),"מולדת":(32.615,35.412),
    "כפר יחזקאל":(32.578,35.397),"גבע":(32.553,35.335),
    "יזרעאל":(32.567,35.300),"דבוריה":(32.685,35.372),
    "נצרת עילית":(32.708,35.325),"יובלים":(32.756,35.186),
    "שפרעם - מזרח":(32.800,35.180),"כאבול":(32.855,35.215),
    "חורפיש":(33.003,35.310),"מע'אר":(32.875,35.260),
    "שגב-שלום":(31.440,34.683),"לקיה":(31.367,34.736),
}
ALL_CITIES = sorted(CITY_COORDS.keys())

# ── OREF full city list ────────────────────────────────────────
OREF_CITIES_URL = "https://www.oref.org.il/Shared/Ajax/GetDistricts.aspx?lang=he"

def _fetch_oref_cities():
    """Fetches the full locality list from the OREF API and updates ALL_CITIES."""
    global ALL_CITIES
    try:
        r = requests.get(OREF_CITIES_URL, headers=API_HEADERS, timeout=8)
        data = r.json()
        api_cities = set()
        for item in data:
            city = (item.get("label") or item.get("value") or "").strip()
            if city:
                api_cities.add(city)
        if api_cities:
            ALL_CITIES = sorted(set(CITY_COORDS.keys()) | api_cities)
    except Exception:
        pass  # keep the static list on failure

# ════════════════════════════════════════════════════════════════
#  CATEGORIES
# ════════════════════════════════════════════════════════════════
CATEGORIES = {
    "1":  {"name":"ירי רקטות וטילים","icon":"🚀","color":"#FF2020","dark":"#3D0000","shelter":10,"anim":"bounce","origin":"south"},
    "2":  {"name":"חדירת כלי טייס עוין","icon":"✈","color":"#FF6600","dark":"#3D1500","shelter":60,"anim":"fly","origin":"north"},
    "3":  {"name":"רעידת אדמה","icon":"🌍","color":"#FF8800","dark":"#2a1a00","shelter":None,"anim":"shake","origin":None},
    "4":  {"name":"חומרים מסוכנים","icon":"☢","color":"#FFAA00","dark":"#2a2000","shelter":None,"anim":"pulse","origin":None},
    "5":  {"name":"חדירת מחבלים","icon":"⚠","color":"#FF0044","dark":"#3D0011","shelter":None,"anim":"bounce","origin":None},
    "6":  {"name":"צונאמי","icon":"🌊","color":"#0088FF","dark":"#001133","shelter":None,"anim":"wave","origin":None},
    "7":  {"name":"חשד לרעידת אדמה","icon":"🌍","color":"#FF8800","dark":"#2a1a00","shelter":None,"anim":"shake","origin":None},
    "13": {"name":"ירי רקטות וטילים","icon":"🚀","color":"#FF2020","dark":"#3D0000","shelter":10,"anim":"bounce","origin":"south"},
    "101":{"name":"בדיקה","icon":"🔔","color":"#888888","dark":"#222222","shelter":None,"anim":"pulse","origin":None},
}
DEFAULT_CAT = {"name":"התרעה","icon":"🔴","color":"#FF0000","dark":"#3D0000","shelter":None,"anim":"bounce","origin":None}

# ════════════════════════════════════════════════════════════════
#  HISTORY DB  — שמירת היסטוריית התרעות ב-SQLite
# ════════════════════════════════════════════════════════════════
class HistoryDB:
    """Persists alerts to SQLite so history survives restarts."""

    _DB_PATH = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "RedAlert", "history.db"
    )

    def __init__(self):
        os.makedirs(os.path.dirname(self._DB_PATH), exist_ok=True)
        self._con  = sqlite3.connect(self._DB_PATH, check_same_thread=False)
        self._lock = threading.Lock()
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS alerts("
            "  id    TEXT PRIMARY KEY,"
            "  cat   TEXT,"
            "  title TEXT,"
            "  cities TEXT,"   # JSON array
            "  ts    TEXT"     # ISO-format datetime
            ")"
        )
        self._con.commit()

    # ── write ────────────────────────────────────────────────────
    def save(self, alert):
        try:
            with self._lock:
                self._con.execute(
                    "INSERT OR IGNORE INTO alerts(id,cat,title,cities,ts) VALUES(?,?,?,?,?)",
                    (alert.id, alert.cat, alert.title,
                     json.dumps(alert.cities, ensure_ascii=False),
                     alert.ts.isoformat())
                )
                self._con.commit()
        except Exception:
            pass

    # ── read ─────────────────────────────────────────────────────
    def load_recent(self, limit=200):
        """Returns raw dicts for Alert() reconstruction (newest first)."""
        try:
            with self._lock:
                cur = self._con.execute(
                    "SELECT id,cat,title,cities,ts FROM alerts ORDER BY ts DESC LIMIT ?",
                    (limit,)
                )
                return [
                    {"id": r[0], "cat": r[1], "title": r[2],
                     "data": json.loads(r[3]), "_ts_override": r[4]}
                    for r in cur.fetchall()
                ]
        except Exception:
            return []

    def stats(self):
        """Returns {total, today, top_city}."""
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            with self._lock:
                total = self._con.execute(
                    "SELECT COUNT(*) FROM alerts"
                ).fetchone()[0]
                today = self._con.execute(
                    "SELECT COUNT(*) FROM alerts WHERE ts >= ?", (today_str,)
                ).fetchone()[0]
                rows = self._con.execute(
                    "SELECT cities FROM alerts ORDER BY ts DESC LIMIT 500"
                ).fetchall()
            city_count = {}
            for (cj,) in rows:
                for c in json.loads(cj):
                    city_count[c] = city_count.get(c, 0) + 1
            top_city = max(city_count, key=city_count.get) if city_count else None
            return {"total": total, "today": today, "top_city": top_city}
        except Exception:
            return {"total": 0, "today": 0, "top_city": None}

    def search(self, city_filter="", limit=300):
        """Search alerts by city substring. Returns list of raw dicts."""
        try:
            with self._lock:
                if city_filter:
                    cur = self._con.execute(
                        "SELECT id,cat,title,cities,ts FROM alerts "
                        "WHERE cities LIKE ? ORDER BY ts DESC LIMIT ?",
                        (f"%{city_filter}%", limit)
                    )
                else:
                    cur = self._con.execute(
                        "SELECT id,cat,title,cities,ts FROM alerts ORDER BY ts DESC LIMIT ?",
                        (limit,)
                    )
                return [
                    {"id": r[0], "cat": r[1], "title": r[2],
                     "data": json.loads(r[3]), "_ts": r[4]}
                    for r in cur.fetchall()
                ]
        except Exception:
            return []

    def close(self):
        try:
            self._con.close()
        except Exception:
            pass


ORIGINS = {
    "gaza":     ("🇵🇸","עזה",             "רצועת עזה — חמאס / ג'יהאד אסלאמי","#FF3030"),
    "lebanon":  ("🇱🇧","לבנון",           "לבנון — חיזבאללה",                  "#FF6600"),
    "houthis":  ("🇾🇪","חות'ים / תימן",  "תימן — חות'ים",                      "#FFAA00"),
    "iran":     ("🇮🇷","איראן",           "איראן — כוח קודס",                   "#FF8000"),
    "westbank": ("🏴","גדה המערבית",      "גדה המערבית — טרור מקומי",           "#FF2266"),
    "syria":    ("🇸🇾","סוריה",           "סוריה",                              "#DD6600"),
    "unknown":  ("❓","מקור לא ידוע",     "מקור לא ידוע",                       "#888888"),
}

_CITY_ORIGIN_RULES = [
    (["נחל עוז","כפר עזה","בארי","רעים","ניר עם","שדרות","נתיבות","אופקים","מגן",
      "יד מרדכי","זיקים","ניצן","אשקלון","אשדוד","קריית מלאכי","גדרה","יבנה",
      "נס ציונה","ראשון לציון","באר שבע","להבים","עומר","מיתר","ירוחם","דימונה","ערד"], "gaza"),
    (["קריית שמונה","מטולה","שלומי","נהריה","מעלות","כרמיאל","עכו","חצור הגלילית",
      "ראש פינה","צפת","טבריה","יסוד המעלה","חיפה","קריית אתא","קריית ביאליק",
      "קריית מוצקין","קריית ים","טירת כרמל","נשר","נוף הגליל","נצרת","עפולה",
      "מגדל העמק","בית שאן","קצרין","מרום גולן","מג'דל שמס"], "lebanon"),
    (["תל אביב","רמת גן","בני ברק","פתח תקווה","הרצליה","נתניה","רעננה","כפר סבא",
      "הוד השרון","ראש העין","רמת השרון","גבעתיים","בת ים","חולון","אור יהודה",
      "יהוד","לוד","רמלה","ירושלים","בית שמש","מודיעין","קריית אונו","שוהם",
      "גבעת שמואל","אילת","מצפה רמון"], "houthis"),
    (["מעלה אדומים","גוש עציון","אפרת","ביתר עילית","בית אל","אריאל","קדומים",
      "דולב","מודיעין עילית"], "westbank"),
    (["קצרין","מג'דל שמס","מרום גולן","עין זיוון"], "syria"),
]

def _detect_origin_key(cities, default_hint):
    s = " ".join(cities)
    for kws, key in _CITY_ORIGIN_RULES:
        if any(k in s for k in kws): return key
    if default_hint == "south": return "gaza"
    if default_hint == "north": return "lebanon"
    if default_hint == "east":  return "iran"
    return "unknown"

# ════════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════════
class Config:
    DEF = {
        "locations":[],"sound":True,"sound_type":"standard",
        "auto_fullscreen":True,"show_map":True,"autostart":False,"poll_interval":2,
        "telegram_token":"","telegram_chat_id":"","telegram_enabled":False,
        "webhook_url":"","webhook_enabled":False,
        "widget_x":None,"widget_y":None,"widget_w":262,"widget_h":130,
        "minimized":False,"google_user":None,"google_cookies":None,
        "fullscreen_timeout":15,
        "overlay_timeout":30,
        "friend_sound_type":"soft",   # same / silent / soft / standard / urgent / siren / friend
        "friend_alert_banner":True,   # הצג באנר כתום כשחבר באזור התרעה
    }
    def __init__(self): self.data=dict(self.DEF); self._load()
    def _load(self):
        try:
            if os.path.exists(CFG_PATH):
                with open(CFG_PATH,"r",encoding="utf-8") as f: self.data.update(json.load(f))
        except Exception: pass
    def save(self):
        try:
            os.makedirs(os.path.dirname(CFG_PATH),exist_ok=True)
            with open(CFG_PATH,"w",encoding="utf-8") as f: json.dump(self.data,f,ensure_ascii=False,indent=2)
        except Exception: pass
    def get(self,k,d=None): return self.data.get(k,self.DEF.get(k,d))
    def set(self,k,v): self.data[k]=v; self.save()
    def set_autostart(self, enable, exe_path=""):
        """מגדיר הפעלה עם Windows.
        תמיד מתקין ל-C:\\RedAlertIDF (נתיב קבוע) ומצביע משם ב-Task Scheduler.
        גיבוי ב-Registry."""
        import shutil as _shutil
        try:
            # ── שלב 0: הכן את תיקיית ההתקנה הקבועה ──────────────────────
            os.makedirs(INSTALL_DIR, exist_ok=True)

            if enable:
                # ── שלב 1: קבע מה להריץ מ-C:\RedAlertIDF ─────────────────
                if getattr(sys, "frozen", False):
                    # רץ כ-EXE — העתק ל-INSTALL_DIR אם שם אחר
                    src = os.path.abspath(sys.executable)
                    if src.lower() != INSTALL_EXE.lower():
                        _shutil.copy2(src, INSTALL_EXE)
                    cmd, args, wd = INSTALL_EXE, "", INSTALL_DIR

                else:
                    # רץ כ-.py — העתק VBS ו-py ל-INSTALL_DIR
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    src_vbs = os.path.join(script_dir, "launch.vbs")
                    src_py  = os.path.abspath(__file__)
                    _shutil.copy2(src_py, INSTALL_PY)
                    if os.path.exists(src_vbs):
                        _shutil.copy2(src_vbs, INSTALL_VBS)
                        cmd, args = "wscript.exe", f'"{INSTALL_VBS}"'
                    else:
                        cmd, args = sys.executable, f'"{INSTALL_PY}"'
                    wd = INSTALL_DIR

                # ── שלב 2: Scheduled Task (עם הרשאות מנהל) ───────────────
                try:
                    xp = os.path.join(os.path.dirname(CFG_PATH), "task.xml")
                    args_xml = f"<Arguments>{args}</Arguments>" if args else ""
                    xml = (
                        '<?xml version="1.0" encoding="UTF-16"?>'
                        '<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
                        '<Triggers><LogonTrigger><Enabled>true</Enabled>'
                        '<Delay>PT5S</Delay></LogonTrigger></Triggers>'
                        '<Principals><Principal id="Author">'
                        '<LogonType>InteractiveToken</LogonType>'
                        '<RunLevel>HighestAvailable</RunLevel>'
                        '</Principal></Principals>'
                        '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>'
                        '<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>'
                        '<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'
                        '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>'
                        '</Settings>'
                        f'<Actions><Exec>'
                        f'<Command>{cmd}</Command>'
                        f'{args_xml}'
                        f'<WorkingDirectory>{wd}</WorkingDirectory>'
                        f'</Exec></Actions></Task>'
                    )
                    with open(xp, "w", encoding="utf-16") as f:
                        f.write(xml)
                    subprocess.run(
                        f'schtasks /create /f /tn "RedAlertMonitor" /xml "{xp}"',
                        shell=True, capture_output=True, text=True, timeout=15)
                except Exception:
                    pass

                # ── שלב 3: Registry (גיבוי) ───────────────────────────────
                try:
                    reg_val = f'"{cmd}" {args}'.strip() if args else f'"{cmd}"'
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                        r"Software\Microsoft\Windows\CurrentVersion\Run",
                                        0, winreg.KEY_SET_VALUE)
                    winreg.SetValueEx(key, "RedAlertMonitor", 0, winreg.REG_SZ, reg_val)
                    winreg.CloseKey(key)
                except Exception:
                    pass

            else:
                # ── ביטול: מחיקה מ-Task Scheduler ומ-Registry ────────────
                subprocess.run('schtasks /delete /f /tn "RedAlertMonitor"',
                               shell=True, capture_output=True, timeout=10)
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                        r"Software\Microsoft\Windows\CurrentVersion\Run",
                                        0, winreg.KEY_SET_VALUE)
                    try:
                        winreg.DeleteValue(key, "RedAlertMonitor")
                    except FileNotFoundError:
                        pass
                    winreg.CloseKey(key)
                except Exception:
                    pass

            self.set("autostart", enable)
        except Exception:
            pass

# ════════════════════════════════════════════════════════════════
#  ALERT
# ════════════════════════════════════════════════════════════════
class Alert:
    def __init__(self,raw):
        self.id=str(raw.get("id",time.time())); self.cat=str(raw.get("cat","1"))
        self.title=raw.get("title","התרעה"); self.cities=raw.get("data",[])
        _ts = raw.get("_ts_override")
        try: self.ts = datetime.fromisoformat(_ts) if _ts else datetime.now()
        except Exception: self.ts = datetime.now()
        self.info=CATEGORIES.get(self.cat,DEFAULT_CAT)
    @property
    def icon(self):     return self.info["icon"]
    @property
    def color(self):    return self.info["color"]
    @property
    def dark(self):     return self.info["dark"]
    @property
    def time_str(self): return self.ts.strftime("%H:%M:%S")
    @property
    def shelter_text(self):
        t=self.info.get("shelter"); return f"היכנסו למרחב המוגן ושהו {t} דקות" if t else ""
    @property
    def origin(self):
        hint=self.info.get("origin")
        if hint is None: return None
        return ORIGINS.get(_detect_origin_key(self.cities,hint),ORIGINS["unknown"])
    def map_markers(self):
        o=self.origin; origin_str=f"{o[0]} {o[1]}" if o else ""
        out=[]
        for city in self.cities:
            if city in CITY_COORDS:
                lat,lng=CITY_COORDS[city]
                out.append({"city":city,"lat":lat,"lng":lng,
                            "icon":self.icon,"color":self.color,"type":self.title,
                            "time":self.time_str,"origin":origin_str,
                            "origin_full":o[2] if o else ""})
        return out

# ════════════════════════════════════════════════════════════════
#  ALERT WORKER  (now supports dynamic friend-city filter)
# ════════════════════════════════════════════════════════════════
class AlertWorker(QThread):
    new_alert=pyqtSignal(dict); alert_cleared=pyqtSignal()
    conn_error=pyqtSignal(str); conn_ok=pyqtSignal()
    def __init__(self,config):
        super().__init__(); self.config=config; self._running=True
        self._last_id=None; self._had_err=False; self._clear_count=0
        self._friend_cities=set(); self._temp_cities=set(); self._lock=threading.Lock()
    def update_friend_cities(self,cities):
        with self._lock: self._friend_cities=set(c for c in cities if c)
    def update_temp_cities(self,cities):
        with self._lock: self._temp_cities=set(c for c in cities if c)
    def run(self):
        sess=requests.Session(); sess.headers.update(API_HEADERS)
        while self._running:
            try:
                r=sess.get(OREF_URL,timeout=4); text=r.text.strip().lstrip("\ufeff")
                if self._had_err: self._had_err=False; self.conn_ok.emit()
                if not text or len(text)<5 or text in ("{}","null",""):
                    self._clear_count += 1
                    if self._clear_count >= 2 and self._last_id is not None:
                        self._last_id=None; self._clear_count=0; self.alert_cleared.emit()
                else:
                    self._clear_count = 0
                    try: data=json.loads(text)
                    except Exception: data={}
                    if data and "id" in data:
                        aid=str(data["id"])
                        # Filter out cat=101 "בדיקה" — OREF system test alerts
                        if str(data.get("cat","")) == "101":
                            self._clear_count += 1
                            if self._clear_count >= 2 and self._last_id is not None:
                                self._last_id=None; self._clear_count=0; self.alert_cleared.emit()
                        elif aid!=self._last_id:
                            self._clear_count=0; self._last_id=aid
                            locs=self.config.get("locations",[])
                            with self._lock: friend_locs=self._friend_cities; temp_locs=self._temp_cities
                            all_locs=list(set(locs)|friend_locs|temp_locs)
                            cities=data.get("data",[])
                            if not all_locs:
                                self.new_alert.emit(data)
                            else:
                                matched=[c for c in cities if c in all_locs]
                                if matched:
                                    fd=dict(data); fd["data"]=matched; self.new_alert.emit(fd)
                    else:
                        self._clear_count += 1
                        if self._clear_count >= 2 and self._last_id is not None:
                            self._last_id=None; self._clear_count=0; self.alert_cleared.emit()
            except requests.exceptions.ConnectionError:
                if not self._had_err: self._had_err=True; self.conn_error.emit("אין חיבור לאינטרנט")
            except Exception: pass
            time.sleep(self.config.get("poll_interval", 2))
    def stop(self): self._running=False; self.quit(); self.wait(2000)

# ════════════════════════════════════════════════════════════════
#  SOUND PLAYER  (multi-profile + friend sound)
# ════════════════════════════════════════════════════════════════
class SoundPlayer:
    def __init__(self): self._busy=False; self._type="standard"
    def set_type(self,t):
        if t in SOUND_PROFILES: self._type=t
    def play(self,friend_in_area=False,friend_sound_type="friend"):
        if self._busy: return
        if friend_in_area:
            fst = friend_sound_type or "friend"
            if fst == "silent":
                return                                      # שקט לחלוטין
            elif fst == "same":
                beeps = SOUND_PROFILES[self._type]["beeps"]  # כמו ההתרעה הרגילה
            elif fst == "friend":
                beeps = FRIEND_SOUND_BEEPS                   # צפצוף ייחודי לחברים
            elif fst in SOUND_PROFILES:
                beeps = SOUND_PROFILES[fst]["beeps"]         # פרופיל שנבחר
            else:
                beeps = SOUND_PROFILES["soft"]["beeps"]      # fallback — עדין
        else:
            beeps = SOUND_PROFILES[self._type]["beeps"]
        self._busy=True
        threading.Thread(target=self._run,args=(beeps,),daemon=True).start()
    def preview(self,stype):
        beeps=FRIEND_SOUND_BEEPS if stype=="friend" else SOUND_PROFILES.get(stype,SOUND_PROFILES["standard"])["beeps"]
        threading.Thread(target=self._run,args=(beeps,),daemon=True).start()
    def _run(self,beeps):
        try:
            import winsound
            for freq,dur,pause in beeps:
                winsound.Beep(freq,dur)
                if pause: time.sleep(pause/1000)
        except Exception:
            try: sys.stdout.write("\a\a\a"); sys.stdout.flush()
            except Exception: pass
        finally: self._busy=False

# ════════════════════════════════════════════════════════════════
#  GOOGLE SAPISID HASH  (needed for Maps API auth header)
# ════════════════════════════════════════════════════════════════
def _sapisidhash(sapisid,origin="https://maps.google.com"):
    ts=str(int(time.time()))
    h=hashlib.sha1(f"{ts} {sapisid} {origin}".encode()).hexdigest()
    return f"SAPISIDHASH {ts}_{h}"

# ════════════════════════════════════════════════════════════════
#  LOCATION SHARING WORKER
# ════════════════════════════════════════════════════════════════
class LocationSharingWorker(QThread):
    locations_updated=pyqtSignal(list)
    auth_failed=pyqtSignal()
    INTERVAL=30

    def __init__(self,cookies):
        super().__init__(); self._cookies=cookies; self._running=True

    def run(self):
        while self._running:
            result=self._fetch()
            if result is None: self.auth_failed.emit(); break
            self.locations_updated.emit(result)
            for _ in range(self.INTERVAL*10):
                if not self._running: break
                time.sleep(0.1)

    def _fetch(self):
        try:
            sapisid=self._cookies.get("SAPISID","")
            cookie_h="; ".join(f"{k}={v}" for k,v in self._cookies.items())
            headers={"Authorization":_sapisidhash(sapisid) if sapisid else "",
                     "Referer":"https://maps.google.com/","Cookie":cookie_h,
                     "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0",
                     "Accept":"application/json"}
            r=requests.get(GMAP_LOC_URL,headers=headers,timeout=10)
            if r.status_code==401: return None
            return self._parse(r.text)
        except Exception: return []

    def _parse(self,text):
        people=[]
        try:
            t=text[4:] if text.startswith(")]}'") else text
            data=json.loads(t.strip())
            persons=data[0] if (data and isinstance(data,list)) else []
            for p in (persons or []):
                if isinstance(p,list):
                    try: self._extract(p,people)
                    except Exception: pass
        except Exception: pass
        return people

    def _extract(self,p,out):
        uid,name,photo="","Unknown",""
        if p and isinstance(p[0],str): uid=p[0]
        if len(p)>1 and isinstance(p[1],str) and p[1].startswith("http"): photo=p[1]
        for item in p:
            if isinstance(item,str) and len(item)>1 and item!=uid and not item.startswith("http"):
                name=item; break
        lat,lng=self._find_coords(p)
        if lat is not None:
            city=self._nearest_city(lat,lng)
            out.append({"uid":uid,"name":name,"photo":photo,"lat":lat,"lng":lng,"city":city})

    def _find_coords(self,obj,depth=0):
        if depth>6: return None,None
        if isinstance(obj,list):
            if len(obj)>=2:
                try:
                    a,b=float(obj[0]),float(obj[1])
                    if -90<=a<=90 and -180<=b<=180 and (a!=0 or b!=0): return a,b
                except (TypeError,ValueError): pass
            for item in obj:
                la,ln=self._find_coords(item,depth+1)
                if la is not None: return la,ln
        return None,None

    def _nearest_city(self,lat,lng):
        best=None; best_d=float("inf")
        for city,(clat,clng) in CITY_COORDS.items():
            d=(lat-clat)**2+(lng-clng)**2
            if d<best_d: best_d=d; best=city
        return best if best_d<0.03 else None  # ~17 km

    def stop(self): self._running=False; self.quit(); self.wait(2000)

# ════════════════════════════════════════════════════════════════
#  LOCATION TRACK WORKER  — מעקב מיקום כל 5 דקות לפי IP
# ════════════════════════════════════════════════════════════════
class LocationTrackWorker(QThread):
    """Periodically checks the user's location via IP.
    Emits location_detected(city) whenever the detected city changes."""
    location_detected = pyqtSignal(str)
    INTERVAL = 300   # seconds between checks

    def __init__(self):
        super().__init__()
        self._running = True
        self._last_city = None

    def run(self):
        while self._running:
            result = _detect_city_from_ip()
            city = result[0] if result else None
            if city and city != self._last_city:
                self._last_city = city
                self.location_detected.emit(city)
            for _ in range(self.INTERVAL * 10):
                if not self._running:
                    break
                time.sleep(0.1)

    def stop(self):
        self._running = False
        self.quit()
        self.wait(2000)

# ════════════════════════════════════════════════════════════════
#  MAP HTML  (3 marker types: alert/user/friend)
# ════════════════════════════════════════════════════════════════
MAP_HTML = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
html,body,#map{width:100%;height:100%;background:#120000;}
.am{font-size:24px;filter:drop-shadow(0 0 7px #FF2020);
    animation:pulse 0.9s ease-in-out infinite alternate;}
@keyframes pulse{from{transform:scale(1) rotate(-5deg);}to{transform:scale(1.4) rotate(5deg);}}
.leaflet-popup-content-wrapper{background:rgba(20,0,0,0.95);color:#fff;
  border:1px solid #FF4040;border-radius:8px;backdrop-filter:blur(4px);}
.leaflet-popup-tip{background:rgba(20,0,0,0.95);}
.leaflet-popup-content{font-family:Arial,sans-serif;font-size:13px;
  direction:rtl;text-align:right;min-width:130px;}
.leaflet-control-attribution{background:rgba(0,0,0,0.55)!important;color:#666!important;}
#status{position:fixed;top:10px;right:10px;background:rgba(0,0,0,0.80);
  color:#888;padding:8px 14px;border-radius:8px;font-family:Arial;
  font-size:12px;direction:rtl;z-index:999;line-height:1.8;}
.fr{background:#00AA44;color:white;border-radius:50%;width:34px;height:34px;
    display:flex;align-items:center;justify-content:center;font-size:18px;
    border:2px solid #00FF66;box-shadow:0 0 10px rgba(0,200,80,.7);}
</style>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head><body>
<div id="status">אין התרעות פעילות</div>
<div id="map"></div>
<script>
var map=L.map('map',{center:[31.5,34.9],zoom:8});
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{
  attribution:'&copy; OpenStreetMap &copy; CARTO',maxZoom:19}).addTo(map);
var layer=L.layerGroup().addTo(map);

function updateAlerts(aj,uj,fj){
  layer.clearLayers();
  var alerts=[],userCities=[],friends=[];
  try{alerts=JSON.parse(aj||'[]');}catch(e){}
  try{userCities=JSON.parse(uj||'[]');}catch(e){}
  try{friends=JSON.parse(fj||'[]');}catch(e){}

  var st=document.getElementById('status');
  var bounds=[];

  // ── 1. User's own cities — always visible as blue house pins ──
  var alertCitySet={};
  alerts.forEach(function(a){alertCitySet[a.city]=true;});

  userCities.forEach(function(uc){
    if(!uc.lat||!uc.lng) return;
    var inAlert=!!alertCitySet[uc.name];
    var ring=inAlert?'3px solid #FF4444':'2px solid #4499FF';
    var bg  =inAlert?'#2a0066':'#002255';
    var ico=L.divIcon({
      html:'<div style="background:'+bg+';border:'+ring+';border-radius:50%;'
          +'width:32px;height:32px;display:flex;align-items:center;justify-content:center;'
          +'font-size:17px;box-shadow:0 0 8px rgba(100,180,255,.8);">🏠</div>',
      iconSize:[32,32],iconAnchor:[16,16],className:''});
    var mk=L.marker([uc.lat,uc.lng],{icon:ico,zIndexOffset:500}).addTo(layer);
    mk.bindPopup(
      '<b style="color:#88CCFF">🏠 '+uc.name+'</b>'+
      (inAlert?'<br/><span style="color:#FF6666;font-weight:bold;">⚠ בהתרעה פעילה!</span>':
               '<br/><span style="color:#88CCFF;font-size:11px;">הישוב שלי</span>'));
    if(!inAlert) bounds.push([uc.lat,uc.lng]);
  });

  // ── 2. Alert markers ────────────────────────────────────────
  alerts.forEach(function(m){
    var isMe=userCities.some(function(uc){return uc.name===m.city;});
    var col=isMe?'#4499FF':m.color;
    var sz=isMe?28:24;
    var ico=L.divIcon({
      html:'<div class="am" style="color:'+(isMe?'#88CCFF':'#fff')+
           ';font-size:'+sz+'px;text-shadow:0 0 10px '+col+'">'+m.icon+'</div>',
      iconSize:[38,38],iconAnchor:[19,19],className:''});
    var mk=L.marker([m.lat,m.lng],{icon:ico}).addTo(layer);
    mk.bindPopup(
      '<b style="color:'+col+'">'+m.icon+' '+m.type+'</b><br/>'+
      '<span>'+m.city+'</span>'+
      (isMe?'<br/><span style="color:#88CCFF;font-size:11px;">📍 הישוב שלי</span>':'')+
      (m.origin?'<br/><span style="color:#ffcc66;font-size:12px;">🎯 '+m.origin+'</span>':'')+
      '<br/><small style="color:#aaa;">'+m.time+'</small>');
    L.circle([m.lat,m.lng],{radius:isMe?5500:4000,color:col,fillColor:col,
      fillOpacity:isMe?.18:.10,weight:isMe?2:1.5,opacity:.7}).addTo(layer);
    bounds.push([m.lat,m.lng]);
  });

  // ── 3. Friend / location-sharing markers ───────────────────
  friends.forEach(function(f){
    if(!f.lat||!f.lng) return;
    var inAlert=alerts.some(function(a){return a.city===f.city;});
    var bgC=inAlert?'#AA2200':'#00AA44', bdC=inAlert?'#FF4444':'#00FF66';
    var ico=L.divIcon({
      html:'<div class="fr" style="background:'+bgC+';border-color:'+bdC+'">'+
           (f.photo?'<img src="'+f.photo+'" style="width:30px;height:30px;border-radius:50%"'
                   +' onerror="this.outerHTML=\'👤\'">':'👤')+'</div>',
      iconSize:[34,34],iconAnchor:[17,17],className:''});
    var mk=L.marker([f.lat,f.lng],{icon:ico,zIndexOffset:1000}).addTo(layer);
    mk.bindPopup(
      '<b style="color:#00FF88">👤 '+f.name+'</b><br/>'+
      (f.city?'<span style="color:'+(inAlert?'#FF8888':'#88FFAA')+'">📍 '+f.city+'</span>':
              '<span style="color:#aaa">מיקום לא ידוע</span>')+
      (inAlert?'<br/><span style="color:#FF4444;font-size:11px;">⚠ באזור ההתרעה!</span>':''));
    bounds.push([f.lat,f.lng]);
  });

  // ── 4. Status bar ───────────────────────────────────────────
  if(!alerts.length&&!friends.length&&!userCities.length){
    st.innerHTML='אין התרעות פעילות'; st.style.color='#888';
  } else {
    var parts=[];
    if(userCities.length) parts.push('📍 '+userCities.length+' ישובים שלי');
    if(alerts.length)     parts.push('⚠ '+alerts.length+' בהתרעה');
    if(friends.length)    parts.push('🟢 '+friends.length+' במעקב');
    var fi=friends.filter(function(f){return alerts.some(function(a){return a.city===f.city;});});
    if(fi.length) parts.push('<span style="color:#FF8888">⚠ '+fi.length+' באזור ההתרעה!</span>');
    st.innerHTML=parts.join('  |  ');
    st.style.color=alerts.length?'#FF5555':'#88CCFF';
  }

  if(bounds.length===1)    map.setView(bounds[0],13,{animate:true});
  else if(bounds.length>1) map.fitBounds(bounds,{padding:[50,50],maxZoom:12,animate:true});
}
window.updateAlerts=updateAlerts;
</script></body></html>"""

# ════════════════════════════════════════════════════════════════
#  MAP WINDOW
# ════════════════════════════════════════════════════════════════
class MapWindow(QWidget):
    sig_google_sharing = pyqtSignal()   # ← פותח גוגל מפות שיתוף מיקום

    def __init__(self):
        super().__init__()
        self.setWindowTitle("מפת התרעות  —  Red Alert")
        self.setWindowFlags(Qt.Window|Qt.WindowStaysOnTopHint)
        self.resize(920,680); self.setStyleSheet("background:#120000;")
        v=QVBoxLayout(self); v.setContentsMargins(0,0,0,0); v.setSpacing(0)
        # header
        hdr=QWidget(); hdr.setFixedHeight(44)
        hdr.setStyleSheet("background:#1a0000;border-bottom:1px solid #440000;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0); hl.setSpacing(8)
        lbl=QLabel("🗺  מפת התרעות בזמן אמת")
        lbl.setFont(QFont("Arial",12,QFont.Bold)); lbl.setStyleSheet("color:white;")
        lbl.setLayoutDirection(Qt.RightToLeft)
        cb=QPushButton("✕"); cb.setFixedSize(30,30)
        cb.setStyleSheet("QPushButton{background:rgba(255,255,255,0.1);color:white;border:none;"
                         "border-radius:15px;font-size:13px;}QPushButton:hover{background:#FF2020;}")
        cb.clicked.connect(self.hide)
        # כפתור "שיתוף מיקום Google"
        gbtn=QPushButton("🌍  שיתוף מיקום Google")
        gbtn.setFixedHeight(28)
        gbtn.setStyleSheet(
            "QPushButton{background:#004422;color:#88FFBB;border:1px solid #006633;"
            "border-radius:6px;padding:0 10px;font-size:11px;}"
            "QPushButton:hover{background:#006633;}")
        gbtn.clicked.connect(self.sig_google_sharing)
        hl.addWidget(cb); hl.addWidget(gbtn); hl.addStretch(); hl.addWidget(lbl)
        v.addWidget(hdr)
        # legend
        leg=QWidget(); leg.setFixedHeight(26)
        leg.setStyleSheet("background:#110000;border-bottom:1px solid #330000;")
        ll=QHBoxLayout(leg); ll.setContentsMargins(16,0,16,0); ll.setSpacing(18)
        for dot,txt in [("#FF3030","התרעה"),("#4499FF","הישוב שלי"),("#00AA44","שיתוף מיקום")]:
            lw=QLabel(f'<span style="color:{dot}">●</span> {txt}')
            lw.setFont(QFont("Arial",9)); lw.setStyleSheet("color:rgba(255,255,255,0.7);")
            ll.addWidget(lw)
        ll.addStretch(); v.addWidget(leg)
        if _HAS_WEB:
            self._web=QWebEngineView()
            self._web.loadFinished.connect(self._on_page_ready)
            self._web.setHtml(MAP_HTML)
            v.addWidget(self._web,1)
        else:
            info=QLabel("להתקנת המפה:\n\npy -m pip install PyQtWebEngine\n\nלאחר מכן הפעל מחדש.")
            info.setAlignment(Qt.AlignCenter); info.setFont(QFont("Arial",13))
            info.setStyleSheet("color:#FF8888;padding:40px;"); info.setLayoutDirection(Qt.RightToLeft)
            v.addWidget(info,1); self._web=None
        self._user_cities=[]
        self._friends=[]
        self._last_markers=[]
        self._page_ready=False      # True לאחר שהדף + Leaflet סיימו לטעון
        self._pending_js=None       # עדכון שממתין עד שהדף מוכן
        self._auto_close_timer=QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.hide)

    def _on_page_ready(self, ok):
        self._page_ready = True
        if self._pending_js:
            js = self._pending_js
            self._pending_js = None
            self._web.page().runJavaScript(js)

    def _run_js(self, js):
        """מריץ JS — אם הדף מוכן מיד, אחרת שומר לביצוע עם loadFinished."""
        if not self._web or not _HAS_WEB:
            return
        if self._page_ready:
            self._web.page().runJavaScript(js)
        else:
            self._pending_js = js  # הדף עוד לא מוכן — נשמור

    def _cities_with_coords(self):
        result=[]
        for name in self._user_cities:
            if name in CITY_COORDS:
                lat,lng=CITY_COORDS[name]
                result.append({"name":name,"lat":lat,"lng":lng})
        return result

    def update_alerts(self,markers,user_cities=None,friends=None):
        if user_cities is not None: self._user_cities=user_cities
        if friends     is not None: self._friends=friends
        if markers     is not None: self._last_markers=markers
        if self._web and _HAS_WEB:
            aj=json.dumps(self._last_markers,       ensure_ascii=False)
            uj=json.dumps(self._cities_with_coords(),ensure_ascii=False)
            fj=json.dumps(self._friends,             ensure_ascii=False)
            self._run_js(f"updateAlerts({repr(aj)},{repr(uj)},{repr(fj)})")
        # סגירה אוטומטית 10 שניות אחרי קבלת התרעה
        if markers:
            self._auto_close_timer.start(10_000)
        else:
            self._auto_close_timer.stop()

    def update_friends(self,friends):
        """Update friend markers while keeping current alert markers."""
        self._friends=friends
        # Pass None for markers so _last_markers is reused
        self.update_alerts(None,None,friends)

    def refresh(self):
        """Re-draw everything (user cities, last alerts, friends)."""
        self.update_alerts(None,None,None)

    def clear(self):
        self.update_alerts([],self._user_cities,self._friends)

# ════════════════════════════════════════════════════════════════
#  HISTORY WINDOW  — חלון היסטוריה עם פילטר וסטטיסטיקות
# ════════════════════════════════════════════════════════════════
class HistoryWindow(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("📋  היסטוריית התרעות — Red Alert")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.resize(800, 620)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("QWidget{background:#0e0000; color:white;}")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # ── Title ──────────────────────────────────────────────
        title = QLabel("📋  היסטוריית התרעות")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:white;")
        root.addWidget(title)

        sep0 = QFrame(); sep0.setFixedHeight(1)
        sep0.setStyleSheet("background:rgba(255,100,100,.25);")
        root.addWidget(sep0)

        # ── Stats row ──────────────────────────────────────────
        self._stats_container = QWidget()
        self._stats_container.setStyleSheet("background:transparent;")
        self._stats_layout = QHBoxLayout(self._stats_container)
        self._stats_layout.setContentsMargins(0, 0, 0, 0)
        self._stats_layout.setSpacing(10)
        root.addWidget(self._stats_container)

        # ── Search + export row ────────────────────────────────
        sr = QHBoxLayout(); sr.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  חיפוש לפי ישוב...")
        self._search.setLayoutDirection(Qt.RightToLeft)
        self._search.setStyleSheet(
            "QLineEdit{background:#200000;color:white;border:1px solid #550000;"
            "border-radius:6px;padding:7px 10px;font-size:12px;}"
            "QLineEdit:focus{border-color:#FF4040;}")
        self._search.textChanged.connect(lambda: self._load(self._search.text().strip()))
        clr = QPushButton("✕"); clr.setFixedSize(30, 30)
        clr.setToolTip("נקה חיפוש")
        clr.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,.08);color:rgba(255,255,255,.5);"
            "border:none;border-radius:5px;font-size:11px;}"
            "QPushButton:hover{background:rgba(255,80,80,.35);color:white;}")
        clr.clicked.connect(lambda: self._search.clear())
        sr.addWidget(self._search, 1); sr.addWidget(clr)
        root.addLayout(sr)

        # ── Scrollable list ────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            "QScrollBar:vertical{background:rgba(255,255,255,.05);width:5px;border-radius:3px;}"
            "QScrollBar::handle:vertical{background:rgba(255,255,255,.22);border-radius:3px;}")
        self._inner = QWidget(); self._inner.setStyleSheet("background:transparent;")
        self._list = QVBoxLayout(self._inner)
        self._list.setContentsMargins(0, 0, 4, 0)
        self._list.setSpacing(4)
        self._list.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._inner)
        root.addWidget(self._scroll, 1)

        # ── Footer ─────────────────────────────────────────────
        footer = QLabel("נבנה על ידי הראלי דודאי  |  מרץ 2026")
        footer.setFont(QFont("Arial", 8)); footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color:rgba(255,200,100,.28);")
        root.addWidget(footer)

    # ── stats ───────────────────────────────────────────────────
    def _update_stats(self):
        for i in reversed(range(self._stats_layout.count())):
            item = self._stats_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        stats = self._db.stats()
        for label, val, color in [
            ("סה\"כ התרעות", str(stats["total"]),   "#FF6060"),
            ("היום",         str(stats["today"]),   "#FFAA40"),
            ("ישוב שכיח",   stats["top_city"] or "—", "#88CCFF"),
        ]:
            box = QFrame()
            box.setStyleSheet(
                "QFrame{background:#1a0000;border:1px solid #440000;border-radius:8px;}")
            bl = QVBoxLayout(box); bl.setContentsMargins(14, 8, 14, 8); bl.setSpacing(2)
            vl = QLabel(val); vl.setFont(QFont("Arial", 20, QFont.Bold))
            vl.setStyleSheet(f"color:{color};"); vl.setAlignment(Qt.AlignCenter)
            ll = QLabel(label); ll.setFont(QFont("Arial", 9))
            ll.setStyleSheet("color:rgba(255,255,255,.50);"); ll.setAlignment(Qt.AlignCenter)
            bl.addWidget(vl); bl.addWidget(ll)
            self._stats_layout.addWidget(box)

    # ── list ────────────────────────────────────────────────────
    def _load(self, city_filter=""):
        for i in reversed(range(self._list.count())):
            w = self._list.itemAt(i).widget()
            if w: w.setParent(None)

        records = self._db.search(city_filter=city_filter, limit=300)

        if not records:
            msg = ("אין התרעות שמורות עדיין" if not city_filter
                   else f"לא נמצאו התרעות עבור  \"{city_filter}\"")
            empty = QLabel(msg)
            empty.setFont(QFont("Arial", 12)); empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:rgba(255,255,255,.35);padding:50px;")
            empty.setLayoutDirection(Qt.RightToLeft)
            self._list.addWidget(empty)
            return

        # חישוב רוחב עמודת זמן פעם אחת לפי DPI אמיתי
        from PyQt5.QtGui import QFontMetrics as _FM
        _time_font = QFont("Consolas", 9)
        _time_col_w = _FM(_time_font).horizontalAdvance("23:59:59") + 16

        current_date = None
        for rec in records:
            ts_str = rec["_ts"]
            try:
                ts = datetime.fromisoformat(ts_str)
                date_label = ts.strftime("%d/%m/%Y")
                time_label = ts.strftime("%H:%M:%S")
            except Exception:
                date_label = ts_str[:10]
                time_label = ts_str[11:19] if len(ts_str) > 10 else ""

            # ── date separator ────────────────────────────────
            if date_label != current_date:
                current_date = date_label
                date_sep = QWidget(); date_sep.setFixedHeight(24)
                date_sep.setStyleSheet("background:rgba(255,255,255,.04);border-radius:4px;")
                dl = QHBoxLayout(date_sep); dl.setContentsMargins(10, 0, 10, 0)
                dlbl = QLabel(f"📅  {date_label}")
                dlbl.setFont(QFont("Arial", 9))
                dlbl.setStyleSheet("color:rgba(255,200,100,.70);")
                dlbl.setLayoutDirection(Qt.RightToLeft)
                dl.addWidget(dlbl); dl.addStretch()
                self._list.addWidget(date_sep)

            cat_info = CATEGORIES.get(rec["cat"], DEFAULT_CAT)
            cities   = rec["data"]
            color    = cat_info["color"]

            row = QFrame()
            # border-right כי ב-RTL האייקון נמצא בצד ימין הפיזי
            row.setStyleSheet(
                f"QFrame{{background:rgba(25,4,4,.85);border-right:3px solid {color};"
                f"border-radius:6px;}}"
                f"QFrame:hover{{background:rgba(45,8,8,.95);}}")
            # הגדר LTR כדי שהפריסה תהיה: [זמן | טקסט | אייקון] משמאל לימין
            row.setLayoutDirection(Qt.LeftToRight)
            rl = QHBoxLayout(row); rl.setContentsMargins(10, 8, 12, 8); rl.setSpacing(10)

            # עמודת זמן — רוחב שחושב לפי DPI אמיתי (מחוץ ללולאה)
            tl = QLabel(time_label); tl.setFont(_time_font)
            tl.setStyleSheet("color:rgba(255,220,100,.65);")
            tl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            tl.setFixedWidth(_time_col_w)

            # עמודת תוכן — מרכז, RTL
            col = QVBoxLayout(); col.setSpacing(2)
            ttl = QLabel(rec["title"])
            ttl.setFont(QFont("Arial", 9, QFont.Bold))
            ttl.setStyleSheet("color:white;"); ttl.setLayoutDirection(Qt.RightToLeft)
            cs = "  |  ".join(cities[:5])
            if len(cities) > 5: cs += f"  +{len(cities)-5}"
            cl = QLabel(cs); cl.setFont(QFont("Arial", 8))
            cl.setStyleSheet("color:rgba(255,255,255,.72);")
            cl.setLayoutDirection(Qt.RightToLeft); cl.setWordWrap(True)
            col.addWidget(ttl); col.addWidget(cl)

            # אייקון — ימין
            ico = QLabel(cat_info["icon"])
            ico.setFont(QFont("Segoe UI Emoji", 14))
            ico.setFixedWidth(28); ico.setAlignment(Qt.AlignCenter)

            rl.addWidget(tl, 0, Qt.AlignTop)
            rl.addLayout(col, 1)
            rl.addWidget(ico, 0, Qt.AlignVCenter)
            self._list.addWidget(row)

    def showEvent(self, e):
        super().showEvent(e)
        self._update_stats()
        self._load(self._search.text().strip())


# ════════════════════════════════════════════════════════════════
#  FLOATING WIDGET
# ════════════════════════════════════════════════════════════════
class FloatingWidget(QWidget):
    sig_fullscreen=pyqtSignal(); sig_settings=pyqtSignal(); sig_map=pyqtSignal()
    sig_google=pyqtSignal(); sig_history=pyqtSignal()   # ← history window
    sig_snooze=pyqtSignal(int)   # minutes (0=cancel)
    MIN_W,MIN_H=340,160
    def __init__(self,config):
        super().__init__(); self.config=config
        self._alerts=deque(maxlen=60); self._active=None
        self._pulse=False; self._step=0; self._drag_pos=None
        self._minimized=config.get("minimized",False)
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMinimumSize(self.MIN_W,self.MIN_H)
        # תמיד מינימום MIN_H — גם אם config שמר ערך קטן יותר
        saved_h = config.get("widget_h", 160)
        w=max(self.MIN_W,config.get("widget_w",340)); h=max(self.MIN_H, saved_h)
        self.resize(w,h); self._build(); self._position()
        self._timer=QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(450)
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(10,10,10,8); root.setSpacing(5)
        hdr=QWidget(); hdr.setFixedHeight(32)
        hl=QHBoxLayout(hdr); hl.setContentsMargins(4,0,4,0); hl.setSpacing(5)
        def sb(t,tip):
            b=QPushButton(t); b.setFixedSize(26,26); b.setToolTip(tip)
            b.setStyleSheet("QPushButton{background:rgba(255,255,255,0.15);color:white;border:none;"
                            "border-radius:13px;font-size:13px;}"
                            "QPushButton:hover{background:rgba(255,255,255,0.32);}"); return b
        self._bc=sb("⚙","הגדרות"); self._bm=sb("🗺","מפה")
        self._bg=sb("🌍","שיתוף מיקום Google"); self._bh=sb("📋","היסטוריה")
        self._bmute=sb("🔔","השתק התרעות"); self._bx=sb("−","מזעור")
        self._bc.clicked.connect(self.sig_settings); self._bm.clicked.connect(self.sig_map)
        self._bg.clicked.connect(self.sig_google); self._bh.clicked.connect(self.sig_history)
        self._bmute.clicked.connect(self._open_snooze_menu)
        self._bx.clicked.connect(self._toggle_min)
        hl.addWidget(self._bc); hl.addWidget(self._bm); hl.addWidget(self._bg)
        hl.addWidget(self._bh); hl.addWidget(self._bmute); hl.addStretch(1)
        hl.addWidget(self._bx)
        self._idle=QLabel("אין התרעות פעילות"); self._idle.setAlignment(Qt.AlignCenter)
        self._idle.setFont(QFont("Arial",10))
        self._idle.setStyleSheet("color:rgba(255,255,255,0.45);padding:12px 0;")
        self._idle.setLayoutDirection(Qt.RightToLeft)
        self._scroll=QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            "QScrollBar:vertical{background:rgba(255,255,255,0.07);width:4px;border-radius:2px;}"
            "QScrollBar::handle:vertical{background:rgba(255,255,255,0.26);border-radius:2px;}")
        self._scroll.hide()
        self._iw=QWidget(); self._iw.setStyleSheet("background:transparent;")
        self._il=QVBoxLayout(self._iw); self._il.setContentsMargins(0,0,0,0)
        self._il.setSpacing(3); self._il.setAlignment(Qt.AlignTop); self._scroll.setWidget(self._iw)
        self._lconn=QLabel(""); self._lconn.setAlignment(Qt.AlignCenter)
        self._lconn.setFont(QFont("Arial",7)); self._lconn.setFixedHeight(13)
        self._lconn.setStyleSheet("color:rgba(255,220,0,0.75);")
        # ── קרדיט ────────────────────────────────────────────────
        self._lcredit=QLabel("נבנה על ידי הראלי דודאי  |  מרץ 2026")
        self._lcredit.setAlignment(Qt.AlignCenter)
        self._lcredit.setFont(QFont("Arial",7)); self._lcredit.setFixedHeight(15)
        self._lcredit.setStyleSheet("color:rgba(255,210,120,0.72);background:transparent;")
        self._grip=QSizeGrip(self); self._grip.setStyleSheet("background:transparent;")
        root.addWidget(hdr); root.addWidget(self._idle)
        root.addWidget(self._scroll,1); root.addWidget(self._lconn); root.addWidget(self._lcredit)
    def _position(self):
        sc=QApplication.desktop().availableGeometry()
        x=self.config.get("widget_x"); y=self.config.get("widget_y")
        if x is None: x=sc.right()-self.width()-12
        if y is None: y=sc.top()+60
        self.move(x,y)
    def resizeEvent(self,e):
        super().resizeEvent(e); gw=16
        self._grip.move(self.width()-gw,self.height()-gw); self._grip.resize(gw,gw)
        if not self._minimized:
            self.config.set("widget_w",self.width()); self.config.set("widget_h",self.height())
    def _open_snooze_menu(self):
        from PyQt5.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:#1a0000;color:white;border:1px solid #550000;}"
                           "QMenu::item:selected{background:#FF2020;}")
        menu.addAction("🔇  השתק 30 דקות", lambda: self.sig_snooze.emit(30))
        menu.addAction("🔇  השתק שעה",     lambda: self.sig_snooze.emit(60))
        menu.addAction("🔇  השתק 2 שעות",  lambda: self.sig_snooze.emit(120))
        menu.addSeparator()
        menu.addAction("🔔  בטל השתקה",    lambda: self.sig_snooze.emit(0))
        menu.exec_(self._bmute.mapToGlobal(self._bmute.rect().bottomLeft()))

    def update_mute_icon(self, muted: bool):
        self._bmute.setText("🔇" if muted else "🔔")
        self._bmute.setToolTip("מושתק — לחץ לביטול" if muted else "השתק התרעות")
        style_extra = ("QPushButton{background:rgba(255,100,100,0.35);color:white;border:none;"
                       "border-radius:12px;font-size:12px;}"
                       "QPushButton:hover{background:rgba(255,100,100,0.55);}") if muted else (
                       "QPushButton{background:rgba(255,255,255,0.14);color:white;border:none;"
                       "border-radius:12px;font-size:12px;}"
                       "QPushButton:hover{background:rgba(255,255,255,0.30);}")
        self._bmute.setStyleSheet(style_extra)

    def _toggle_min(self):
        self._minimized=not self._minimized; self.config.set("minimized",self._minimized)
        if self._minimized:
            self.setFixedHeight(50); self._idle.hide(); self._scroll.hide()
            self._lcredit.hide(); self._bx.setText("+")
        else:
            self.setMinimumHeight(self.MIN_H); self.setMaximumHeight(16777215)
            self.resize(self.width(),max(self.MIN_H,self.config.get("widget_h",130)))
            self._lcredit.show(); self._bx.setText("−"); self._refresh_content()
    def _refresh_content(self):
        if self._minimized: return
        if not self._alerts: self._idle.show(); self._scroll.hide()
        else: self._idle.hide(); self._scroll.show()
    def add_alert(self,a):
        # מנע כפילויות — אותו ID לא יתווסף פעמיים
        if any(a2.id == a.id for a2 in self._alerts):
            return
        # פתח ממוזעור אוטומטית כשמגיעה התרעה — כדי שהישוב וההתרעה יהיו גלויים
        if self._minimized:
            self._toggle_min()
        self._active=a; self._alerts.appendleft(a); self._rebuild(); self._refresh_content()
    def clear_alerts(self): self._active=None; self._rebuild()
    def _rebuild(self):
        for i in reversed(range(self._il.count())):
            w=self._il.itemAt(i).widget()
            if w: w.setParent(None)
        for a in list(self._alerts)[:12]: self._il.addWidget(self._make_row(a))
    def _make_row(self,a):
        act=(self._active and self._active.id==a.id)
        f=QFrame(); f.setMinimumHeight(74); f.setCursor(Qt.PointingHandCursor)
        bg=(f"qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {a.color},stop:1 rgba(60,0,0,0.92))"
            if act else "rgba(48,4,4,0.88)")
        brd="rgba(255,255,255,0.38)" if act else "rgba(255,255,255,0.09)"
        f.setStyleSheet(f"QFrame{{background:{bg};border-radius:8px;border:1px solid {brd};}}")
        lay=QHBoxLayout(f); lay.setContentsMargins(8,7,8,7); lay.setSpacing(8)
        li=QLabel(a.icon); li.setFont(QFont("Segoe UI Emoji",20)); li.setFixedWidth(32); li.setAlignment(Qt.AlignCenter)
        col=QVBoxLayout(); col.setSpacing(3)
        t1=QLabel(a.title); t1.setFont(QFont("Arial",10,QFont.Bold)); t1.setStyleSheet("color:white;"); t1.setLayoutDirection(Qt.RightToLeft); t1.setWordWrap(True)
        cs="  |  ".join(a.cities[:3])+(f"  +{len(a.cities)-3}" if len(a.cities)>3 else "")
        t2=QLabel(cs); t2.setFont(QFont("Arial",9)); t2.setStyleSheet("color:rgba(255,255,255,0.80);"); t2.setLayoutDirection(Qt.RightToLeft); t2.setWordWrap(True)
        col.addWidget(t1); col.addWidget(t2)
        if act and a.origin:
            flag,short,full,ocol=a.origin
            t3=QLabel(f"{flag} {short}"); t3.setFont(QFont("Segoe UI Emoji",8))
            t3.setStyleSheet(f"color:{ocol};background:rgba(0,0,0,0.3);border-radius:3px;padding:1px 4px;")
            t3.setLayoutDirection(Qt.RightToLeft); col.addWidget(t3)
        col.addStretch()
        tt=QLabel(a.time_str); tt.setFont(QFont("Arial",8)); tt.setStyleSheet("color:rgba(255,255,255,0.45);"); tt.setAlignment(Qt.AlignTop|Qt.AlignLeft)
        lay.addWidget(li); lay.addLayout(col,1); lay.addWidget(tt,0,Qt.AlignTop)
        f.mouseDoubleClickEvent=lambda e: self.sig_fullscreen.emit()
        return f
    def set_conn_error(self,m): self._lconn.setText(f"⚠ {m}")
    def set_conn_ok(self):       self._lconn.setText("")
    def _tick(self): self._pulse=not self._pulse; self._step=(self._step+1)%360; self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r=self.rect().adjusted(2,2,-2,-2)
        path=QPainterPath(); path.addRoundedRect(QRectF(r),16,16)

        if self._active and self._pulse:
            # ── פעיל / פולס — גלאס אדום עם זוהר ──────────────────
            c=QColor(self._active.color); c.setAlpha(145)
            dk=QColor(self._active.dark);  dk.setAlpha(190)
            g=QLinearGradient(0,0,0,r.height()); g.setColorAt(0,c); g.setColorAt(1,dk)
            p.fillPath(path,g)
            # shimmer — פס אור עדין בחלק עליון (אפקט זכוכית)
            sh=QLinearGradient(0,0,0,r.height()*0.28)
            sh.setColorAt(0,QColor(255,255,255,52)); sh.setColorAt(1,QColor(255,255,255,0))
            p.fillPath(path,sh)
            # border זוהר בצבע ההתרעה
            p.setPen(QPen(QColor(self._active.color),2.0))
        elif self._active:
            # ── פעיל / שקט — גלאס עמום יותר ────────────────────
            c2=QColor(self._active.color); c2.setAlpha(75)
            dk2=QColor(self._active.dark); dk2.setAlpha(175)
            g2=QLinearGradient(0,0,0,r.height()); g2.setColorAt(0,c2); g2.setColorAt(1,dk2)
            p.fillPath(path,g2)
            sh2=QLinearGradient(0,0,0,r.height()*0.22)
            sh2.setColorAt(0,QColor(255,255,255,38)); sh2.setColorAt(1,QColor(255,255,255,0))
            p.fillPath(path,sh2)
            p.setPen(QPen(QColor(self._active.color),1.2))
        else:
            # ── סרק — גלאס כהה שקוף ────────────────────────────
            g3=QLinearGradient(0,0,0,r.height())
            g3.setColorAt(0,QColor(22,6,6,168)); g3.setColorAt(1,QColor(10,2,2,152))
            p.fillPath(path,g3)
            sh3=QLinearGradient(0,0,0,r.height()*0.18)
            sh3.setColorAt(0,QColor(255,255,255,30)); sh3.setColorAt(1,QColor(255,255,255,0))
            p.fillPath(path,sh3)
            p.setPen(QPen(QColor(255,255,255,38),1.0))
        p.drawPath(path)
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton: self._drag_pos=e.globalPos()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self,e):
        if e.buttons()==Qt.LeftButton and self._drag_pos: self.move(e.globalPos()-self._drag_pos)
    def mouseReleaseEvent(self,e):
        if e.button()==Qt.LeftButton and self._drag_pos:
            self.config.set("widget_x",self.x()); self.config.set("widget_y",self.y()); self._drag_pos=None
    def mouseDoubleClickEvent(self,e): self.sig_fullscreen.emit()

# ════════════════════════════════════════════════════════════════
#  FULL SCREEN  — תוקן: ללא WA_DeleteOnClose + try/except בסגירה
# ════════════════════════════════════════════════════════════════
class FullScreen(QWidget):
    sig_shelter_confirmed = pyqtSignal()   # נפלט כשמשתמש לוחץ "אני במרחב המוגן"
    sig_dismissed         = pyqtSignal()   # נפלט כשהמשתמש סוגר ידנית (✕)

    def __init__(self,history,active=None,timeout=0,screen=None):
        super().__init__()
        self.history=list(history)
        self.active=active or (self.history[0] if self.history else None)
        self._step=0
        self._auto_secs=int(timeout)
        self._auto_left=int(timeout)
        self._screen=screen  # QScreen or None → primary
        self._setup()
        self._tmr=QTimer(self); self._tmr.timeout.connect(self._tick); self._tmr.start(40)
        if self._auto_secs > 0:
            self._atimer=QTimer(self); self._atimer.timeout.connect(self._auto_tick); self._atimer.start(1000)
    def _setup(self):
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        sc = self._screen.geometry() if self._screen else QApplication.desktop().screenGeometry()
        self.setGeometry(sc)
        self.setStyleSheet("background:#080000;"); self.setLayoutDirection(Qt.RightToLeft)
        SW=sc.width(); SH=sc.height()
        ban_h=max(120,int(SH*.16)); city_h=max(150,int(SH*.20))
        hist_h=max(90,int(SH*.12)); font_big=max(18,int(SW*.016))
        font_sub=max(11,int(SW*.009)); font_ico=max(32,int(SH*.048))
        cols=max(3,SW//220); mx=max(28,int(SW*.030))
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        a=self.active
        if a:
            # ── Banner ────────────────────────────────────────────────
            ban=QWidget()
            # setMinimumHeight (לא Fixed) — כך הבאנר מתרחב לפי כמות התוכן
            ban.setMinimumHeight(ban_h)
            ban.setStyleSheet(f"background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                              f"stop:0 {a.color},stop:1 rgba(80,0,0,.97));")
            bl=QHBoxLayout(ban); bl.setContentsMargins(mx,10,mx,10); bl.setSpacing(16)
            self._ico=QLabel(a.icon); self._ico.setFont(QFont("Segoe UI Emoji",font_ico))
            self._ico.setAlignment(Qt.AlignCenter); self._ico.setFixedWidth(int(font_ico*2.0))
            tc=QVBoxLayout(); tc.setSpacing(5)
            t0=QLabel("🔴  התרעת צבע אדום!"); t0.setFont(QFont("Arial",font_big,QFont.Bold))
            t0.setStyleSheet("color:white;"); t0.setLayoutDirection(Qt.RightToLeft)
            t1=QLabel(a.title); t1.setFont(QFont("Arial",font_sub+2))
            t1.setStyleSheet("color:white;"); t1.setLayoutDirection(Qt.RightToLeft)
            # ── שעת ההתרעה — שורה נפרדת וברורה ────────────────────────
            t_time=QLabel(f"🕐  שעת התרעה:  {a.time_str}")
            t_time.setFont(QFont("Arial",font_sub+2,QFont.Bold))
            t_time.setStyleSheet("color:#FFE878;background:rgba(0,0,0,0.25);"
                                 "border-radius:5px;padding:2px 8px;")
            t_time.setLayoutDirection(Qt.RightToLeft)
            tc.addWidget(t0); tc.addWidget(t1); tc.addSpacing(4)
            tc.addWidget(t_time); tc.addStretch()
            cb=QPushButton("✕"); cb.setFixedSize(40,40)
            cb.setStyleSheet("QPushButton{background:rgba(0,0,0,.3);color:white;border:none;"
                             "border-radius:20px;font-size:16px;}QPushButton:hover{background:rgba(0,0,0,.6);}")
            cb.clicked.connect(self._dismiss)
            bl.addWidget(self._ico); bl.addLayout(tc,1); bl.addWidget(cb,0,Qt.AlignTop)
            root.addWidget(ban)
            # ── רצועת מרחב מוגן ───────────────────────────────────────
            sb=QWidget()
            # setMinimumHeight — מאפשר לרצועה להתרחב אם הטקסט ארוך
            sb.setMinimumHeight(max(48,int(SH*.055)))
            sb.setStyleSheet("background:#1b0000;")
            sl=QHBoxLayout(sb); sl.setContentsMargins(mx,8,mx,8)
            shelter_msg = "🏠  לא לצאת מהמרחב המוגן עד לשחרור ע\"י פיקוד העורף"
            if a.shelter_text:
                mins = a.info.get("shelter","?")
                shelter_msg = f"🏠  לא לצאת מהמרחב המוגן עד לשחרור ע\"י פיקוד העורף  ({mins} דק׳)"
            ls2=QLabel(shelter_msg)
            ls2.setFont(QFont("Arial",max(11,font_sub+1),QFont.Bold))
            ls2.setStyleSheet("color:#FFE040;"); ls2.setAlignment(Qt.AlignCenter)
            ls2.setWordWrap(True)           # ← מונע חיתוך טקסט
            ls2.setLayoutDirection(Qt.RightToLeft); sl.addWidget(ls2)
            root.addWidget(sb)
            # ── ישובים מוזהרים ─────────────────────────────────────────
            cw=QWidget(); cw.setStyleSheet("background:#110000;")
            cv=QVBoxLayout(cw); cv.setContentsMargins(mx,12,mx,12); cv.setSpacing(8)
            ch=QLabel(f"ישובים מוזהרים  ({len(a.cities)}):")
            ch.setFont(QFont("Arial",max(10,font_sub),QFont.Bold))
            ch.setStyleSheet("color:rgba(255,255,255,.68);"); cv.addWidget(ch)
            csc=QScrollArea(); csc.setWidgetResizable(True); csc.setFixedHeight(city_h)
            csc.setStyleSheet("QScrollArea{border:none;background:transparent;}"
                              "QScrollBar:vertical{background:rgba(255,255,255,.06);width:4px;}"
                              "QScrollBar::handle:vertical{background:rgba(255,255,255,.20);}")
            cc=QWidget(); cc.setStyleSheet("background:transparent;")
            fl2=QVBoxLayout(cc); fl2.setContentsMargins(0,0,0,0); fl2.setSpacing(5)
            rw=None; rl=None
            for i,city in enumerate(a.cities):
                if i%cols==0:
                    rw=QWidget(); rw.setStyleSheet("background:transparent;")
                    rl=QHBoxLayout(rw); rl.setContentsMargins(0,0,0,0); rl.setSpacing(5); fl2.addWidget(rw)
                lb=QLabel(f"  {city}  "); lb.setFont(QFont("Arial",max(10,font_sub+1),QFont.Bold))
                lb.setStyleSheet(f"color:white;background:{a.color};border-radius:5px;padding:4px 8px;")
                lb.setAlignment(Qt.AlignCenter); lb.setLayoutDirection(Qt.RightToLeft); rl.addWidget(lb)
            if rl and rl.count()%cols!=0: rl.addStretch()
            csc.setWidget(cc); cv.addWidget(csc); root.addWidget(cw)
        # ── היסטוריה ───────────────────────────────────────────────────
        if len(self.history)>1:
            hw=QWidget(); hw.setStyleSheet("background:#0c0000;")
            hv=QVBoxLayout(hw); hv.setContentsMargins(28,10,28,10); hv.setSpacing(3)
            ht=QLabel("היסטוריית התרעות אחרונות:")
            ht.setFont(QFont("Arial",11,QFont.Bold)); ht.setStyleSheet("color:rgba(255,255,255,.5);"); hv.addWidget(ht)
            hsc=QScrollArea(); hsc.setWidgetResizable(True); hsc.setFixedHeight(hist_h)
            hsc.setStyleSheet("QScrollArea{border:none;background:transparent;}")
            hco=QWidget(); hco.setStyleSheet("background:transparent;")
            hla=QVBoxLayout(hco); hla.setContentsMargins(0,0,0,0); hla.setSpacing(2)
            for alt in self.history[:13]:
                skip=a and alt.id==a.id
                rw2=QWidget(); rw2.setStyleSheet("background:transparent;")
                rl2=QHBoxLayout(rw2); rl2.setContentsMargins(0,1,0,1); rl2.setSpacing(8)
                op="0.30" if skip else "0.70"
                tl=QLabel(alt.time_str); tl.setFont(QFont("Arial",10,QFont.Bold))
                tl.setStyleSheet(f"color:rgba(255,220,100,{op});"); tl.setFixedWidth(90)
                tl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                il=QLabel(alt.icon); il.setFont(QFont("Segoe UI Emoji",11)); il.setFixedWidth(22)
                cl=QLabel(", ".join(alt.cities[:5])); cl.setFont(QFont("Arial",9))
                cl.setStyleSheet(f"color:rgba(255,255,255,{op});"); cl.setLayoutDirection(Qt.RightToLeft)
                rl2.addWidget(tl); rl2.addWidget(il); rl2.addWidget(cl,1); hla.addWidget(rw2)
            hsc.setWidget(hco); hv.addWidget(hsc); root.addWidget(hw)
        root.addStretch()
        # ── כפתורי פעולה ─────────────────────────────────────────────
        btn_row=QWidget(); btn_row.setFixedHeight(58)
        btn_row.setStyleSheet("background:#100000;border-top:1px solid rgba(255,255,255,.10);")
        brl=QHBoxLayout(btn_row); brl.setContentsMargins(40,8,40,8); brl.setSpacing(16)
        ok_btn=QPushButton("✓   הבנתי — סגור")
        ok_btn.setFixedHeight(38); ok_btn.setMinimumWidth(180)
        ok_btn.setFont(QFont("Arial",11))
        ok_btn.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,.10);color:white;"
            "border:1px solid rgba(255,255,255,.25);border-radius:8px;}"
            "QPushButton:hover{background:rgba(255,255,255,.20);}")
        ok_btn.clicked.connect(self.close)
        shelter_btn=QPushButton("🏠   אני במרחב המוגן")
        shelter_btn.setFixedHeight(38); shelter_btn.setMinimumWidth(200)
        shelter_btn.setFont(QFont("Arial",11,QFont.Bold))
        shelter_btn.setStyleSheet(
            "QPushButton{background:#8B0000;color:#FFE878;"
            "border:1px solid #CC2020;border-radius:8px;}"
            "QPushButton:hover{background:#CC0000;}")
        shelter_btn.clicked.connect(self._on_shelter_click)
        brl.addWidget(shelter_btn); brl.addStretch(); brl.addWidget(ok_btn)
        root.addWidget(btn_row)
        # ── שורת תחתית — שעון + ספירה ─────────────────────────────────
        bot=QWidget(); bot.setFixedHeight(32)
        bot.setStyleSheet("background:#050000;border-top:1px solid rgba(255,255,255,.06);")
        bl2=QHBoxLayout(bot); bl2.setContentsMargins(28,0,28,0)
        self._clk=QLabel(datetime.now().strftime("%H:%M:%S"))
        self._clk.setFont(QFont("Arial",11,QFont.Bold))
        self._clk.setStyleSheet("color:rgba(255,220,100,.90);")
        if self._auto_secs > 0:
            self._clbl=QLabel(self._fmt_auto())
            self._clbl.setFont(QFont("Arial",9)); self._clbl.setStyleSheet("color:rgba(255,200,100,.55);")
            el=self._clbl
        else:
            el=QLabel("ESC / לחיצה כפולה לסגירה")
            el.setFont(QFont("Arial",9)); el.setStyleSheet("color:rgba(255,255,255,.25);")
        cred_lbl=QLabel("נבנה על ידי הראלי דודאי  |  מרץ 2026")
        cred_lbl.setFont(QFont("Arial",8)); cred_lbl.setStyleSheet("color:rgba(255,200,100,.28);")
        bl2.addWidget(cred_lbl); bl2.addStretch(); bl2.addWidget(el); bl2.addStretch(); bl2.addWidget(self._clk)
        root.addWidget(bot)

    def _on_shelter_click(self):
        self.sig_shelter_confirmed.emit()
        self.close()
    def _fmt_auto(self):
        return f"נסגר אוטומטית בעוד  {self._auto_left}  שניות  |  ESC לסגירה"
    def go_green(self):
        """מעבר לצבע ירוק — האירוע הסתיים. מציג 'מותר לצאת' ונסגר לאחר 8 שניות."""
        try:
            if hasattr(self, '_tmr'):   self._tmr.stop()
            if hasattr(self, '_atimer'): self._atimer.stop()
            # הסתר את כל תוכן הווידג'ט הנוכחי
            for i in range(self.layout().count()):
                item = self.layout().itemAt(i)
                if item and item.widget():
                    item.widget().hide()
            # שכבה ירוקה מעל
            ov = QWidget(self); ov.setGeometry(self.rect())
            ov.setAttribute(Qt.WA_StyledBackground, True)   # חובה כדי ש-QWidget יצייר רקע stylesheet
            ov.setStyleSheet(
                "QWidget{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #002e18,stop:1 #001509);}")
            ol = QVBoxLayout(ov); ol.setAlignment(Qt.AlignCenter); ol.setSpacing(24)
            ol.setContentsMargins(60,60,60,60)

            ico = QLabel("✅"); ico.setFont(QFont("Arial", 90))
            ico.setAlignment(Qt.AlignCenter)
            t1 = QLabel("מותר לצאת מהמרחב המוגן")
            t1.setFont(QFont("Arial", 42, QFont.Bold))
            t1.setStyleSheet("color:#00FF88;"); t1.setAlignment(Qt.AlignCenter)
            t1.setLayoutDirection(Qt.RightToLeft)
            t2 = QLabel("פיקוד העורף אישר יציאה — בטוח לצאת")
            t2.setFont(QFont("Arial", 22)); t2.setStyleSheet("color:#AAFFCC;")
            t2.setAlignment(Qt.AlignCenter); t2.setLayoutDirection(Qt.RightToLeft)
            self._gc_lbl = QLabel("נסגר אוטומטית בעוד 8 שניות")
            self._gc_lbl.setFont(QFont("Arial", 13))
            self._gc_lbl.setStyleSheet("color:rgba(160,255,195,.50);")
            self._gc_lbl.setAlignment(Qt.AlignCenter)
            self._gc_lbl.setLayoutDirection(Qt.RightToLeft)

            ol.addWidget(ico); ol.addWidget(t1); ol.addWidget(t2); ol.addWidget(self._gc_lbl)
            ov.show(); ov.raise_(); self._green_overlay = ov

            self._gc_secs = 8
            self._gc_timer = QTimer(self)
            self._gc_timer.timeout.connect(self._gc_tick)
            self._gc_timer.start(1000)
        except Exception:
            self.close()

    def _gc_tick(self):
        self._gc_secs -= 1
        try:
            self._gc_lbl.setText(f"נסגר אוטומטית בעוד  {self._gc_secs}  שניות")
        except RuntimeError:
            pass
        if self._gc_secs <= 0:
            self._gc_timer.stop()
            self.close()

    def _dismiss(self):
        """סגירה ידנית — מעדכן RedAlertApp לא להציג שוב לאותה התרעה."""
        self.sig_dismissed.emit()
        self.close()

    def _auto_tick(self):
        self._auto_left -= 1
        try: self._clbl.setText(self._fmt_auto())
        except RuntimeError: pass
        if self._auto_left <= 0:
            try: self._atimer.stop()
            except RuntimeError: pass
            self.close()
    def _tick(self):
        self._step=(self._step+1)%360
        try:
            self._clk.setText(datetime.now().strftime("%H:%M:%S"))
            if hasattr(self,"_ico") and self.active:
                anim=self.active.info.get("anim","bounce")
                off=int(math.sin(math.radians(self._step*(12 if anim=="shake" else 6 if anim=="bounce" else 3)))*6)
                self._ico.setContentsMargins(0,off,0,-off)
        except RuntimeError: pass   # widget already deleted — safe to ignore
        self.update()
    def paintEvent(self,e):
        super().paintEvent(e); p=QPainter(self)
        p.setPen(QPen(QColor(255,0,0,8),1))
        p.drawLine(0,int((self._step/360)*self.height()),self.width(),int((self._step/360)*self.height()))
    def keyPressEvent(self,e):
        if e.key()==Qt.Key_Escape: self.close()
    def mouseDoubleClickEvent(self,e): self.close()
    def closeEvent(self,e):
        self._tmr.stop()
        if hasattr(self,'_atimer'):
            try: self._atimer.stop()
            except RuntimeError: pass
        super().closeEvent(e)

# ════════════════════════════════════════════════════════════════
#  LOCATIONS DIALOG
# ════════════════════════════════════════════════════════════════
class LocationsDialog(QDialog):
    def __init__(self,config,parent=None):
        super().__init__(parent); self.config=config; self._sel=set(config.get("locations",[]))
        self.setWindowTitle("בחירת ישובים"); self.setLayoutDirection(Qt.RightToLeft); self.resize(560,640)
        self.setStyleSheet("""
            QDialog{background:#160000;color:white;}
            QLabel{color:white;font-size:12px;}
            QLineEdit{background:#260000;color:white;border:1px solid #555;border-radius:5px;padding:7px;font-size:13px;}
            QListWidget{background:#1d0000;color:white;border:1px solid #444;border-radius:5px;font-size:12px;outline:0;}
            QListWidget::item{padding:6px 10px;border-radius:3px;}
            QListWidget::item:hover{background:rgba(255,50,50,0.12);}
            QPushButton{background:#FF2020;color:white;border:none;border-radius:6px;padding:8px 16px;font-size:12px;}
            QPushButton:hover{background:#FF4040;}
            QCheckBox{color:white;font-size:12px;spacing:8px;}
            QCheckBox::indicator{width:16px;height:16px;border-radius:3px;border:1px solid #777;background:#260000;}
            QCheckBox::indicator:checked{background:#FF2020;border-color:#FF4040;}
        """)
        v=QVBoxLayout(self); v.setContentsMargins(22,20,22,20); v.setSpacing(10)
        ti=QLabel("📍  בחירת ישובים להתרעה"); ti.setFont(QFont("Arial",14,QFont.Bold)); ti.setAlignment(Qt.AlignCenter); v.addWidget(ti)
        self._ca=QCheckBox("הצג התרעות עבור כל הישובים (ברירת מחדל)")
        self._ca.setChecked(not bool(self._sel)); self._ca.stateChanged.connect(self._on_all); v.addWidget(self._ca)
        self._se=QLineEdit(); self._se.setPlaceholderText("חיפוש ישוב..."); self._se.setEnabled(bool(self._sel)); self._se.textChanged.connect(self._filter); v.addWidget(self._se)
        self._cnt=QLabel(""); self._cnt.setFont(QFont("Arial",9)); self._cnt.setStyleSheet("color:rgba(255,180,180,.85);"); v.addWidget(self._cnt)
        self._lw=QListWidget(); self._lw.setEnabled(bool(self._sel)); v.addWidget(self._lw,1)
        self._pop(ALL_CITIES)
        rb=QHBoxLayout()
        stl="QPushButton{background:#333;color:white;border:none;border-radius:5px;padding:6px 12px;font-size:11px;}QPushButton:hover{background:#444;}"
        self._ba=QPushButton("בחר הכל"); self._ba.setEnabled(bool(self._sel)); self._ba.setStyleSheet(stl)
        self._bd=QPushButton("נקה הכל"); self._bd.setEnabled(bool(self._sel)); self._bd.setStyleSheet(stl)
        self._ba.clicked.connect(self._sel_all); self._bd.clicked.connect(self._desel_all)
        rb.addWidget(self._ba); rb.addWidget(self._bd); rb.addStretch(); v.addLayout(rb)
        sp=QFrame(); sp.setFixedHeight(1); sp.setStyleSheet("background:rgba(255,255,255,.1);"); v.addWidget(sp)
        bts=QHBoxLayout()
        cas="QPushButton{background:#333;color:white;border:none;border-radius:6px;padding:8px 16px;font-size:12px;}QPushButton:hover{background:#444;}"
        ca=QPushButton("ביטול"); ca.setStyleSheet(cas); sv=QPushButton("שמור")
        ca.clicked.connect(self.reject); sv.clicked.connect(self._save)
        bts.addWidget(ca); bts.addWidget(sv); v.addLayout(bts)
        self._lw.itemChanged.connect(self._on_item); self._upd_cnt()
    def _pop(self,cities):
        self._lw.blockSignals(True); self._lw.clear()
        for c in cities:
            it=QListWidgetItem(c); it.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if c in self._sel else Qt.Unchecked); self._lw.addItem(it)
        self._lw.blockSignals(False); self._upd_cnt()
    def _filter(self,txt): self._pop([c for c in ALL_CITIES if txt in c])
    def _on_all(self,st):
        en=not bool(st)
        for w in [self._lw,self._se,self._ba,self._bd]: w.setEnabled(en)
        self._upd_cnt()
    def _on_item(self,it):
        c=it.text()
        if it.checkState()==Qt.Checked: self._sel.add(c)
        else: self._sel.discard(c)
        self._upd_cnt()
    def _sel_all(self):
        self._lw.blockSignals(True)
        for i in range(self._lw.count()): it=self._lw.item(i); it.setCheckState(Qt.Checked); self._sel.add(it.text())
        self._lw.blockSignals(False); self._upd_cnt()
    def _desel_all(self):
        self._lw.blockSignals(True)
        for i in range(self._lw.count()): it=self._lw.item(i); it.setCheckState(Qt.Unchecked); self._sel.discard(it.text())
        self._lw.blockSignals(False); self._upd_cnt()
    def _upd_cnt(self):
        if self._ca.isChecked(): self._cnt.setText("כל הישובים")
        else: n=len(self._sel); self._cnt.setText(f"{n} ישובים נבחרו" if n else "לא נבחרו ישובים")
    def _save(self):
        if self._ca.isChecked(): self.config.set("locations",[])
        else: self.config.set("locations",list(self._sel))
        self.accept()

# ════════════════════════════════════════════════════════════════
#  SOUND DIALOG
# ════════════════════════════════════════════════════════════════
class SoundDialog(QDialog):
    def __init__(self,config,sound,parent=None):
        super().__init__(parent); self.config=config; self.sound=sound
        self._sel=config.get("sound_type","standard")
        self.setWindowTitle("בחירת צליל התרעה"); self.setLayoutDirection(Qt.RightToLeft); self.resize(400,340)
        self.setStyleSheet("""
            QDialog{background:#160000;color:white;}
            QLabel{color:white;}
            QPushButton{background:#FF2020;color:white;border:none;border-radius:6px;padding:8px 16px;font-size:12px;}
            QPushButton:hover{background:#FF4040;}
            QRadioButton{color:white;font-size:12px;spacing:8px;}
            QRadioButton::indicator{width:16px;height:16px;border-radius:8px;border:2px solid #777;background:#260000;}
            QRadioButton::indicator:checked{background:#FF2020;border-color:#FF4040;}
        """)
        v=QVBoxLayout(self); v.setContentsMargins(24,20,24,20); v.setSpacing(10)
        ti=QLabel("🔊  בחירת צליל התרעה"); ti.setFont(QFont("Arial",13,QFont.Bold)); ti.setAlignment(Qt.AlignCenter); v.addWidget(ti)
        def sep(): f=QFrame(); f.setFixedHeight(1); f.setStyleSheet("background:rgba(255,255,255,.1);"); return f
        v.addWidget(sep())
        self._radios={}; self._bg=QButtonGroup(self)
        prev_stl=("QPushButton{background:#2a0000;color:white;border:1px solid #550000;"
                  "border-radius:5px;font-size:11px;}QPushButton:hover{background:#440000;}")
        for key,profile in SOUND_PROFILES.items():
            row=QHBoxLayout(); rb=QRadioButton(profile["name"]); rb.setChecked(key==self._sel)
            self._bg.addButton(rb); self._radios[key]=rb
            prev=QPushButton("▶"); prev.setFixedSize(32,28); prev.setStyleSheet(prev_stl); prev.setToolTip("נגן")
            prev.clicked.connect(lambda ch=False,k=key: self.sound.preview(k))
            row.addWidget(rb,1); row.addWidget(prev); v.addLayout(row)
        v.addWidget(sep())
        frow=QHBoxLayout(); fl=QLabel("🟢  צליל לחבר באזור"); fl.setStyleSheet("color:#88FFAA;font-size:12px;")
        fp=QPushButton("▶"); fp.setFixedSize(32,28)
        fp.setStyleSheet("QPushButton{background:#004400;color:#88FF88;border:1px solid #006600;border-radius:5px;font-size:11px;}QPushButton:hover{background:#006600;}")
        fp.clicked.connect(lambda: self.sound.preview("friend"))
        frow.addWidget(fl,1); frow.addWidget(fp); v.addLayout(frow)
        v.addStretch(); v.addWidget(sep())
        bts=QHBoxLayout()
        cas="QPushButton{background:#333;color:white;border:none;border-radius:6px;padding:8px 16px;}QPushButton:hover{background:#444;}"
        ca=QPushButton("ביטול"); ca.setStyleSheet(cas); sv=QPushButton("שמור")
        ca.clicked.connect(self.reject); sv.clicked.connect(self._save)
        bts.addWidget(ca); bts.addWidget(sv); v.addLayout(bts)
    def _save(self):
        for key,rb in self._radios.items():
            if rb.isChecked(): self.config.set("sound_type",key); self.sound.set_type(key); break
        self.accept()

# ════════════════════════════════════════════════════════════════
#  LOCATION DETECT DIALOG  – זיהוי מיקום אוטומטי בהפעלה ראשונה
# ════════════════════════════════════════════════════════════════
def _detect_city_from_ip():
    """מנסה לזהות את העיר הקרובה ביותר לפי כתובת IP.
    מחזיר (city_name, lat, lon) או None אם נכשל."""
    try:
        r = requests.get("https://ip-api.com/json/?fields=city,lat,lon,status",
                         timeout=5)
        d = r.json()
        if d.get("status") != "success":
            return None
        lat, lon = float(d["lat"]), float(d["lon"])
        # מצא את הישוב הקרוב ביותר ב-CITY_COORDS
        best, best_dist = None, float("inf")
        for name, (clat, clon) in CITY_COORDS.items():
            dist = math.sqrt((clat - lat) ** 2 + (clon - lon) ** 2)
            if dist < best_dist:
                best_dist = dist
                best = name
        return (best, lat, lon) if best else None
    except Exception:
        return None


class LocationDetectDialog(QDialog):
    """דיאלוג שמוצג בהפעלה ראשונה / כשאין ישובים — מציג את המיקום שזוהה."""

    def __init__(self, detected_city, config, open_settings_cb, parent=None):
        super().__init__(parent)
        self._city   = detected_city
        self._config = config
        self._open_settings = open_settings_cb
        self.setWindowTitle("זיהוי מיקום"); self.setLayoutDirection(Qt.RightToLeft)
        self.resize(440, 260)
        self.setStyleSheet("QDialog{background:#120000;color:white;}"
                           "QLabel{color:white;} QPushButton{border-radius:6px;padding:8px 18px;font-size:12px;}")
        v = QVBoxLayout(self); v.setContentsMargins(30, 24, 30, 24); v.setSpacing(14)

        title = QLabel("📍  זוהה מיקומך")
        title.setFont(QFont("Arial", 14, QFont.Bold)); title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        sep = QFrame(); sep.setFixedHeight(1); sep.setStyleSheet("background:rgba(255,50,50,.3);")
        v.addWidget(sep)

        city_lbl = QLabel(detected_city or "לא זוהה")
        city_lbl.setFont(QFont("Arial", 18, QFont.Bold))
        city_lbl.setAlignment(Qt.AlignCenter)
        city_lbl.setStyleSheet(f"color:#FF8080;padding:8px;background:rgba(255,20,20,.12);"
                               f"border-radius:8px;border:1px solid rgba(255,50,50,.3);")
        v.addWidget(city_lbl)

        note = QLabel("האם להגדיר ישוב זה כמיקומך?\nלקבלת התרעות רק לאזור שלך.")
        note.setFont(QFont("Arial", 10)); note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet("color:rgba(255,255,255,.60);"); note.setLayoutDirection(Qt.RightToLeft)
        v.addWidget(note)

        bts = QHBoxLayout(); bts.setSpacing(10)
        ok_btn = QPushButton(f"✓  כן, הגדר {detected_city or ''}")
        ok_btn.setStyleSheet("QPushButton{background:#8B0000;color:white;border:1px solid #CC2020;}"
                             "QPushButton:hover{background:#CC0000;}")
        ok_btn.clicked.connect(self._confirm)

        more_btn = QPushButton("⚙  הגדרות נוספות")
        more_btn.setStyleSheet("QPushButton{background:rgba(255,255,255,.08);color:white;"
                               "border:1px solid rgba(255,255,255,.20);}"
                               "QPushButton:hover{background:rgba(255,255,255,.18);}")
        more_btn.clicked.connect(self._open_more)

        skip_btn = QPushButton("דלג")
        skip_btn.setStyleSheet("QPushButton{background:transparent;color:rgba(255,255,255,.35);"
                               "border:none;} QPushButton:hover{color:white;}")
        skip_btn.clicked.connect(self.reject)

        bts.addWidget(ok_btn, 2); bts.addWidget(more_btn, 1); bts.addWidget(skip_btn)
        v.addLayout(bts)

    def _confirm(self):
        if self._city:
            current = self._config.get("locations", [])
            if self._city not in current:
                current.append(self._city)
                self._config.set("locations", current)
        self.accept()

    def _open_more(self):
        self.accept()
        QTimer.singleShot(100, self._open_settings)


# ════════════════════════════════════════════════════════════════
#  TEMP LOCATION DIALOG  — "נמצאת ב[city], הוסף זמנית?"
# ════════════════════════════════════════════════════════════════
class TempLocationDialog(QDialog):
    """Shown when the user's IP location is not in their configured cities.
    Offers to add the detected city temporarily until they move away."""

    def __init__(self, city, parent=None):
        super().__init__(parent)
        self._city = city
        self._secs = 30
        self.setWindowTitle("מיקום חדש זוהה")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(420, 230)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(
            "QDialog{background:#120000;color:white;}"
            "QLabel{color:white;}"
            "QPushButton{border-radius:6px;padding:8px 18px;font-size:12px;}")
        v = QVBoxLayout(self); v.setContentsMargins(30, 22, 30, 22); v.setSpacing(12)

        title = QLabel("📍  זוהה מיקום חדש")
        title.setFont(QFont("Arial", 13, QFont.Bold)); title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet("background:rgba(255,50,50,.3);"); v.addWidget(sep)

        city_lbl = QLabel(city)
        city_lbl.setFont(QFont("Arial", 18, QFont.Bold))
        city_lbl.setAlignment(Qt.AlignCenter)
        city_lbl.setStyleSheet(
            "color:#FF8080;padding:8px;background:rgba(255,20,20,.12);"
            "border-radius:8px;border:1px solid rgba(255,50,50,.3);")
        v.addWidget(city_lbl)

        note = QLabel("הישוב אינו ברשימת ההתרעות שלך.\nהוסף אותו זמנית עד שתעבור מקום?")
        note.setFont(QFont("Arial", 10)); note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet("color:rgba(255,255,255,.62);")
        note.setWordWrap(True); note.setLayoutDirection(Qt.RightToLeft)
        v.addWidget(note)

        bts = QHBoxLayout(); bts.setSpacing(10)
        self._yes = QPushButton(f"✓  הוסף זמנית ({self._secs})")
        self._yes.setStyleSheet(
            "QPushButton{background:#8B0000;color:white;border:1px solid #CC2020;}"
            "QPushButton:hover{background:#CC0000;}")
        self._yes.clicked.connect(self.accept)
        no = QPushButton("לא תודה")
        no.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,.08);color:white;"
            "border:1px solid rgba(255,255,255,.20);}"
            "QPushButton:hover{background:rgba(255,255,255,.18);}")
        no.clicked.connect(self.reject)
        bts.addWidget(self._yes, 2); bts.addWidget(no, 1)
        v.addLayout(bts)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self):
        self._secs -= 1
        try:
            self._yes.setText(f"✓  הוסף זמנית ({self._secs})")
        except RuntimeError:
            pass
        if self._secs <= 0:
            self._timer.stop()
            self.reject()

    def closeEvent(self, e):
        try: self._timer.stop()
        except RuntimeError: pass
        super().closeEvent(e)


# ════════════════════════════════════════════════════════════════
#  GOOGLE AUTH DIALOG  – manual SAPISID paste (Chrome 127+ safe)
# ════════════════════════════════════════════════════════════════
class GoogleAuthDialog(QDialog):
    """
    Chrome 127+ uses App-Bound Encryption → no library can read cookies.
    Solution: user copies the SAPISID value from Chrome DevTools and pastes it here.
    Steps shown inside the dialog with a visual guide.
    """
    login_success = pyqtSignal(dict, str)

    _CSS = """
        QDialog{background:#0a1a0a;color:white;}
        QLabel{color:#CCFFCC;}
        QLineEdit{background:#0d2a0d;color:#AAFFAA;border:2px solid #226622;
                  border-radius:6px;padding:8px 12px;font-size:12px;font-family:Consolas;}
        QLineEdit:focus{border-color:#44CC44;}
        QPushButton{background:#1a3a1a;color:#88FF88;border:1px solid #336633;
                    border-radius:8px;padding:9px 18px;font-size:12px;}
        QPushButton:hover{background:#254a25;}
        QPushButton:disabled{background:#1a1a1a;color:#444;border-color:#333;}
    """

    # JS command — gets ALL Google cookies as a JSON string (needed for full API auth)
    _JS_CMD = ("JSON.stringify(Object.fromEntries("
               "document.cookie.split('; ').map(c=>{"
               "const[k,...v]=c.split('=');return[k,v.join('=')];})))")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Google Login – Location Sharing")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(560, 520)
        self.setStyleSheet(self._CSS)

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 18, 28, 18)
        v.setSpacing(12)

        # ── Title ────────────────────────────────────────────
        ti = QLabel("🌍  התחברות לגוגל – שיתוף מיקום")
        ti.setFont(QFont("Arial", 14, QFont.Bold))
        ti.setAlignment(Qt.AlignCenter)
        ti.setStyleSheet("color:#44FF88;")
        v.addWidget(ti)

        def sep():
            f = QFrame(); f.setFixedHeight(1)
            f.setStyleSheet("background:rgba(100,220,100,.2);")
            return f
        v.addWidget(sep())

        # ── Open Chrome ──────────────────────────────────────
        open_btn = QPushButton("🌐  פתח Google Maps ב-Chrome (וודא שמחובר)")
        open_btn.setFont(QFont("Arial", 11))
        open_btn.setStyleSheet(
            "QPushButton{background:#003a66;color:#88CCFF;border:1px solid #005599;"
            "border-radius:8px;padding:10px 18px;}"
            "QPushButton:hover{background:#004d88;}")
        open_btn.clicked.connect(self._open_maps)
        v.addWidget(open_btn)

        v.addWidget(sep())

        # ── Step 1 box ───────────────────────────────────────
        s1 = QFrame()
        s1.setStyleSheet("QFrame{background:#0d2a0d;border:1px solid #224422;border-radius:8px;}")
        s1v = QVBoxLayout(s1); s1v.setContentsMargins(14,10,14,10); s1v.setSpacing(8)

        h1 = QLabel("צעד 1 — הפעל Console ב-Chrome")
        h1.setFont(QFont("Arial", 11, QFont.Bold))
        h1.setStyleSheet("color:#44FF88;")
        s1v.addWidget(h1)

        t1 = QLabel("לחץ F12  →  לחץ על לשונית  Console  →  העתק את הפקודה הבאה והדבק (Ctrl+V)  →  Enter")
        t1.setFont(QFont("Arial", 10)); t1.setWordWrap(True)
        t1.setStyleSheet("color:#AAFFAA;")
        t1.setLayoutDirection(Qt.LeftToRight)
        s1v.addWidget(t1)

        # Code box + copy button
        code_row = QHBoxLayout(); code_row.setSpacing(8)
        code_box = QLineEdit(self._JS_CMD)
        code_box.setReadOnly(True)
        code_box.setLayoutDirection(Qt.LeftToRight)
        code_box.setStyleSheet(
            "QLineEdit{background:#061806;color:#88FF44;border:1px solid #336600;"
            "border-radius:5px;padding:6px 10px;font-size:11px;font-family:Consolas;}")
        copy_btn = QPushButton("📋 העתק")
        copy_btn.setFixedWidth(80)
        copy_btn.setStyleSheet(
            "QPushButton{background:#226622;color:white;border:none;border-radius:5px;"
            "padding:6px;font-size:11px;}QPushButton:hover{background:#338833;}")
        copy_btn.clicked.connect(lambda: (
            QApplication.clipboard().setText(self._JS_CMD),
            copy_btn.setText("✓ הועתק!")
        ))
        code_row.addWidget(code_box, 1); code_row.addWidget(copy_btn)
        s1v.addLayout(code_row)
        v.addWidget(s1)

        # ── Step 2 box ───────────────────────────────────────
        s2 = QFrame()
        s2.setStyleSheet("QFrame{background:#0d2a0d;border:1px solid #224422;border-radius:8px;}")
        s2v = QVBoxLayout(s2); s2v.setContentsMargins(14,10,14,10); s2v.setSpacing(8)

        h2 = QLabel("צעד 2 — הדבק את הערך שהופיע")
        h2.setFont(QFont("Arial", 11, QFont.Bold))
        h2.setStyleSheet("color:#44FF88;")
        s2v.addWidget(h2)

        t2 = QLabel("לאחר הלחיצה על Enter ב-Console יופיע ערך כזה:  \"ABCDEF12345_…\"   —  הדבק אותו כאן (בלי מרכאות):")
        t2.setFont(QFont("Arial", 10)); t2.setWordWrap(True)
        t2.setStyleSheet("color:#AAFFAA;")
        t2.setLayoutDirection(Qt.LeftToRight)
        s2v.addWidget(t2)

        self._inp = QLineEdit()
        self._inp.setPlaceholderText("ABCDEF_xxxx/…  (הדבק כאן)")
        self._inp.setLayoutDirection(Qt.LeftToRight)
        self._inp.setFixedHeight(40)
        self._inp.textChanged.connect(self._on_text)
        s2v.addWidget(self._inp)
        v.addWidget(s2)

        # ── Status ───────────────────────────────────────────
        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color:#FFAAAA;font-size:11px;min-height:20px;")
        v.addWidget(self._status)

        v.addStretch()
        v.addWidget(sep())

        # ── Buttons ──────────────────────────────────────────
        brow = QHBoxLayout(); brow.setSpacing(12)
        cancel = QPushButton("ביטול")
        cancel.setStyleSheet(
            "QPushButton{background:#2a0000;color:#FF8888;border:1px solid #550000;"
            "border-radius:8px;padding:9px 18px;}")
        cancel.clicked.connect(self.reject)

        self._save_btn = QPushButton("✅  שמור והתחבר")
        self._save_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self._save_btn.setEnabled(False)
        self._save_btn.setStyleSheet(
            "QPushButton{background:#1a4a1a;color:#88FF88;border:2px solid #338833;"
            "border-radius:8px;padding:9px 22px;font-size:13px;}"
            "QPushButton:hover{background:#286028;}"
            "QPushButton:disabled{background:#1a1a1a;color:#444;border-color:#333;}")
        self._save_btn.clicked.connect(self._save)

        brow.addWidget(cancel); brow.addStretch(); brow.addWidget(self._save_btn)
        v.addLayout(brow)

    @staticmethod
    def _open_maps():
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "https://maps.google.com"],
                shell=False, creationflags=0x08000000)
        except Exception:
            import webbrowser
            webbrowser.open("https://maps.google.com")

    def _on_text(self, txt: str):
        ok = len(txt.strip()) > 10
        self._save_btn.setEnabled(ok)
        if ok:
            self._status.setStyleSheet("color:#88FF88;font-size:11px;")
            self._status.setText("✓  נראה תקין – לחץ 'שמור והתחבר'")
        else:
            self._status.setStyleSheet("color:#FFAAAA;font-size:11px;")
            self._status.setText("")

    def _save(self):
        sapisid = self._inp.text().strip()
        if not sapisid:
            return
        cookies = {"SAPISID": sapisid}
        self._status.setStyleSheet("color:#44FF88;font-size:12px;")
        self._status.setText("✅  מחובר!")
        QApplication.processEvents()
        self.login_success.emit(cookies, "Google User")
        QTimer.singleShot(400, self.accept)

# ════════════════════════════════════════════════════════════════
#  GOOGLE BROWSER WINDOW  — חיבור אוטומטי עם פרופיל קוקיות מתמיד
# ════════════════════════════════════════════════════════════════
class GoogleBrowserWindow(QWidget):
    """
    חלון דפדפן מוטמע עם פרופיל קוקיות מתמיד.
    פעם ראשונה: המשתמש מתחבר רגיל לגוגל.
    בהמשך: קוקיות נשמרות → חיבור אוטומטי בכל הפעלה.
    פולט logged_in(cookies, name) כשמזוהה SAPISID.
    """
    logged_in = pyqtSignal(dict, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Google Maps – שיתוף מיקום")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.resize(980, 740)
        self._cookies = {}
        self._emitted = False
        self._profile = None
        self._view    = None
        self._status_lbl = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # ── Header bar ─────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(48)
        hdr.setStyleSheet("background:#0d3a0d;border-bottom:2px solid #1a6a1a;")
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(12, 0, 12, 0); hl.setSpacing(10)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet(
            "QPushButton{background:rgba(255,80,80,.25);color:white;border:none;border-radius:15px;font-size:13px;}"
            "QPushButton:hover{background:#CC2020;}")
        close_btn.clicked.connect(self.hide)

        self._status_lbl = QLabel("ממתין לכניסה לגוגל...")
        self._status_lbl.setFont(QFont("Arial", 10))
        self._status_lbl.setStyleSheet("color:#FFCC44;")

        title_lbl = QLabel("🌍  גוגל מפות — התחבר לחשבון Google שלך")
        title_lbl.setFont(QFont("Arial", 11, QFont.Bold))
        title_lbl.setStyleSheet("color:#88FF88;")
        title_lbl.setLayoutDirection(Qt.RightToLeft)

        hl.addWidget(close_btn)
        hl.addWidget(self._status_lbl)
        hl.addStretch()
        hl.addWidget(title_lbl)
        lay.addWidget(hdr)

        if not _HAS_WEB:
            info = QLabel("PyQtWebEngine לא מותקן.\n\npy -m pip install PyQtWebEngine")
            info.setAlignment(Qt.AlignCenter)
            info.setStyleSheet("color:#FFAAAA;font-size:14px;padding:40px;background:#120000;")
            info.setLayoutDirection(Qt.RightToLeft)
            lay.addWidget(info, 1)
            return

        os.makedirs(GPROFILE_PATH, exist_ok=True)

        # פרופיל מתמיד — שומר קוקיות בין הפעלות
        self._profile = QWebEngineProfile("gmap_auth", self)
        self._profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        self._profile.setPersistentStoragePath(GPROFILE_PATH)
        self._profile.setCachePath(os.path.join(GPROFILE_PATH, "cache"))

        store = self._profile.cookieStore()
        store.cookieAdded.connect(self._cookie_added)

        self._view = QWebEngineView()
        self._view.setPage(QWebEnginePage(self._profile, self._view))
        lay.addWidget(self._view, 1)

    def _cookie_added(self, cookie):
        name  = bytes(cookie.name()).decode("utf-8",  errors="ignore")
        value = bytes(cookie.value()).decode("utf-8", errors="ignore")
        dom   = cookie.domain()
        if "google" in dom:
            self._cookies[name] = value
            if name == "SAPISID" and not self._emitted:
                self._on_logged_in()

    def _on_logged_in(self):
        self._emitted = True
        if self._status_lbl:
            self._status_lbl.setText("✅  מחובר לגוגל!")
            self._status_lbl.setStyleSheet("color:#44FF88;font-weight:bold;")
        self.logged_in.emit(dict(self._cookies), "Google User")
        QTimer.singleShot(1200, self.hide)

    def load_saved_session(self):
        """טוען קוקיות שמורות מהדיסק — אם קיים SAPISID, פולט logged_in אוטומטית."""
        if self._profile:
            self._profile.cookieStore().loadAllCookies()

    def has_session(self):
        return bool(self._cookies.get("SAPISID"))

    def get_cookies(self):
        return dict(self._cookies)

    def open_for_login(self):
        """פותח את חלון הדפדפן לדף שיתוף המיקום של גוגל."""
        self._emitted = False  # allow re-emit if user re-logins
        if self._view:
            self._view.load(QUrl(GMAP_SHARE_URL))
        self.show()
        self.raise_()

    def clear_session(self):
        self._cookies.clear()
        self._emitted = False
        if self._profile:
            self._profile.cookieStore().deleteAllCookies()
        if self._status_lbl:
            self._status_lbl.setText("ממתין לכניסה לגוגל...")
            self._status_lbl.setStyleSheet("color:#FFCC44;")



# ════════════════════════════════════════════════════════════════
#  TELEGRAM DIALOG
# ════════════════════════════════════════════════════════════════
class TelegramDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent); self.config=config; self._setup()

    def _setup(self):
        self.setWindowTitle("הגדרות Telegram Bot")
        self.setLayoutDirection(Qt.RightToLeft); self.resize(420, 340)
        self.setStyleSheet("""
            QDialog{background:#001122;color:white;}
            QLabel{color:white;}
            QPushButton{background:#0088cc;color:white;border:none;border-radius:6px;padding:9px 20px;font-size:12px;}
            QPushButton:hover{background:#00aaff;}
            QCheckBox{color:white;font-size:12px;spacing:8px;}
            QCheckBox::indicator{width:17px;height:17px;border-radius:3px;border:1px solid #777;background:#001a33;}
            QCheckBox::indicator:checked{background:#0088cc;border-color:#00aaff;}
            QLineEdit{background:#001a33;color:white;border:1px solid #004466;border-radius:5px;padding:4px 8px;font-size:11px;}
            QLineEdit:hover{border-color:#00aaff;}
        """)
        v = QVBoxLayout(self); v.setContentsMargins(28,22,28,22); v.setSpacing(12)
        ti = QLabel("📱  הגדרות Telegram Bot")
        ti.setFont(QFont("Arial",13,QFont.Bold)); ti.setAlignment(Qt.AlignCenter); v.addWidget(ti)
        def sep(): f=QFrame(); f.setFixedHeight(1); f.setStyleSheet("background:rgba(255,255,255,.1);"); return f
        v.addWidget(sep())
        self._enabled = QCheckBox("✅  הפעל שליחת התרעות לטלגרם")
        self._enabled.setChecked(self.config.get("telegram_enabled", False)); v.addWidget(self._enabled)
        v.addWidget(sep())
        lbl_tok = QLabel("🤖  Bot Token:")
        lbl_tok.setFont(QFont("Arial",11)); v.addWidget(lbl_tok)
        self._token = QLineEdit(self.config.get("telegram_token",""))
        self._token.setPlaceholderText("123456789:ABCDefGhij...")
        self._token.setLayoutDirection(Qt.LeftToRight); v.addWidget(self._token)
        lbl_id = QLabel("💬  Chat ID (ערוץ / קבוצה / משתמש):")
        lbl_id.setFont(QFont("Arial",11)); v.addWidget(lbl_id)
        id_row = QHBoxLayout(); id_row.setSpacing(8)
        self._chat_id = QLineEdit(self.config.get("telegram_chat_id",""))
        self._chat_id.setPlaceholderText("-100123456789")
        self._chat_id.setLayoutDirection(Qt.LeftToRight)
        fetch_btn = QPushButton("🔍  זהה אוטומטית")
        fetch_btn.setFixedWidth(130)
        fetch_btn.setStyleSheet("QPushButton{background:#004466;color:#88CCFF;border:1px solid #006688;"
                                "border-radius:6px;padding:6px 12px;}QPushButton:hover{background:#005577;}")
        fetch_btn.clicked.connect(self._fetch_chat_id)
        id_row.addWidget(self._chat_id); id_row.addWidget(fetch_btn); v.addLayout(id_row)
        self._status = QLabel(""); self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet("color:#88CCFF;font-size:11px;"); v.addWidget(self._status)
        v.addWidget(sep())
        test_btn = QPushButton("📨  שלח הודעת בדיקה")
        test_btn.clicked.connect(self._send_test); v.addWidget(test_btn)
        setup_btn = QPushButton("🔧  הגדר בוט אוטומטית (שם / תיאור / פקודות)")
        setup_btn.setStyleSheet(
            "QPushButton{background:#005500;color:#88FF88;border:1px solid #008800;"
            "border-radius:6px;padding:9px 20px;font-size:12px;}"
            "QPushButton:hover{background:#007700;}")
        setup_btn.clicked.connect(self._auto_setup_bot); v.addWidget(setup_btn)
        self._setup_lbl = QLabel("")
        self._setup_lbl.setAlignment(Qt.AlignCenter)
        self._setup_lbl.setFont(QFont("Arial", 11, QFont.Bold))
        self._setup_lbl.setWordWrap(True)
        v.addWidget(self._setup_lbl)
        v.addStretch(); v.addWidget(sep())
        bts = QHBoxLayout()
        cas = "QPushButton{background:#333;color:white;border:none;border-radius:6px;padding:9px 20px;}"
        ca = QPushButton("ביטול"); ca.setStyleSheet(cas)
        sv = QPushButton("שמור"); sv.setStyleSheet(
            "QPushButton{background:#0088cc;color:white;border:none;border-radius:6px;padding:9px 20px;}")
        ca.clicked.connect(self.reject); sv.clicked.connect(self._save)
        bts.addWidget(ca); bts.addWidget(sv); v.addLayout(bts)

    def _fetch_chat_id(self):
        token = self._token.text().strip()
        if not token:
            self._status.setText("❌  הכנס Bot Token קודם"); self._status.setStyleSheet("color:#FF6666;font-size:11px;"); return
        self._status.setText("⏳  מחפש..."); self._status.setStyleSheet("color:#FFCC44;font-size:11px;")
        QApplication.processEvents()
        try:
            import urllib.request
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            with urllib.request.urlopen(url, timeout=6) as r:
                data = json.loads(r.read())
            results = data.get("result", [])
            if results:
                msg = results[-1].get("message") or results[-1].get("channel_post") or {}
                chat = msg.get("chat",{})
                cid = str(chat.get("id",""))
                if cid:
                    self._chat_id.setText(cid)
                    self._status.setText(f"✅  נמצא: {chat.get('title') or chat.get('first_name','')}")
                    self._status.setStyleSheet("color:#88FF88;font-size:11px;"); return
            self._status.setText("⚠  לא נמצאו הודעות — שלח הודעה לבוט קודם")
            self._status.setStyleSheet("color:#FFAA44;font-size:11px;")
        except Exception as e:
            self._status.setText(f"❌  שגיאה: {e}"); self._status.setStyleSheet("color:#FF6666;font-size:11px;")

    def _send_test(self):
        self._save_values()
        token = self.config.get("telegram_token","")
        chat_id = self.config.get("telegram_chat_id","")
        if not token or not chat_id:
            self._status.setText("❌  חסר Token או Chat ID"); self._status.setStyleSheet("color:#FF6666;font-size:11px;"); return
        self._status.setText("⏳  שולח..."); self._status.setStyleSheet("color:#FFCC44;font-size:11px;")
        QApplication.processEvents()
        try:
            import urllib.request, urllib.parse
            msg = "🔴 Red Alert Monitor — הודעת בדיקה ✅\nהחיבור לטלגרם תקין!"
            params = urllib.parse.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            url = f"https://api.telegram.org/bot{token}/sendMessage?{params}"
            with urllib.request.urlopen(url, timeout=6): pass
            self._status.setText("✅  נשלח בהצלחה!"); self._status.setStyleSheet("color:#88FF88;font-size:11px;")
        except Exception as e:
            self._status.setText(f"❌  {e}"); self._status.setStyleSheet("color:#FF6666;font-size:11px;")

    def _auto_setup_bot(self):
        """מגדיר שם, תיאור ופקודות של הבוט אוטומטית דרך ה-API."""
        from PyQt5.QtWidgets import QMessageBox
        token = self._token.text().strip()
        if not token:
            self._setup_lbl.setText("❌  יש להכניס Bot Token לפני ההגדרה")
            self._setup_lbl.setStyleSheet("color:#FF6666;")
            QMessageBox.warning(self, "חסר Token",
                                "יש להכניס את ה-Bot Token לפני ההגדרה האוטומטית.")
            return

        self._setup_lbl.setText("⏳  מתחבר לטלגרם ומגדיר בוט...")
        self._setup_lbl.setStyleSheet("color:#FFCC44;")
        QApplication.processEvents()

        errors = []
        try:
            import urllib.request
            base = f"https://api.telegram.org/bot{token}"

            def api(method, payload):
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                req  = urllib.request.Request(
                    f"{base}/{method}", data=data,
                    headers={"Content-Type": "application/json; charset=utf-8"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    res = json.loads(r.read())
                if not res.get("ok"):
                    raise ValueError(res.get("description", "שגיאה לא ידועה"))
                return res

            # ── שם הבוט ────────────────────────────────────
            try:
                api("setMyName", {"name": "Red Alert Monitor"})
            except Exception as e:
                errors.append(f"שם: {e}")

            # ── תיאור קצר ──────────────────────────────────
            try:
                api("setMyShortDescription",
                    {"short_description": "התרעות צבע אדום בזמן אמת"})
            except Exception as e:
                errors.append(f"תיאור קצר: {e}")

            # ── תיאור מלא ──────────────────────────────────
            try:
                api("setMyDescription", {
                    "description": (
                        "בוט התרעות צבע אדום בזמן אמת\n"
                        "מבוסס על נתוני פיקוד העורף - Red Alert Monitor v5\n"
                        "נבנה על ידי הראלי דודאי"
                    )
                })
            except Exception as e:
                errors.append(f"תיאור: {e}")

            # ── פקודות ─────────────────────────────────────
            try:
                api("setMyCommands", {
                    "commands": [
                        {"command": "start",   "description": "התחל / הצג מידע"},
                        {"command": "status",  "description": "סטטוס מערכת"},
                        {"command": "help",    "description": "עזרה ופקודות"},
                        {"command": "mute",    "description": "השתק התרעות ל-30 דקות"},
                        {"command": "unmute",  "description": "בטל השתקה"},
                        {"command": "test",    "description": "שלח הודעת בדיקה"},
                    ]
                })
            except Exception as e:
                errors.append(f"פקודות: {e}")

            if errors:
                msg = "הוגדר חלקית:\n" + "\n".join(f"  ⚠ {e}" for e in errors)
                self._setup_lbl.setText(f"⚠  {msg}")
                self._setup_lbl.setStyleSheet("color:#FFAA44;")
                QMessageBox.warning(self, "הגדרה חלקית", msg)
            else:
                self._setup_lbl.setText("✅  הבוט הוגדר בהצלחה!")
                self._setup_lbl.setStyleSheet("color:#88FF88;")
                QMessageBox.information(self, "הצלחה ✅",
                    "הבוט הוגדר בהצלחה!\n\n"
                    "✔ שם: Red Alert Monitor\n"
                    "✔ תיאור קצר ומלא עודכנו\n"
                    "✔ 6 פקודות הוגדרו\n\n"
                    "הפקודות יופיעו בטלגרם תוך מספר שניות.")

        except Exception as e:
            self._setup_lbl.setText(f"❌  שגיאה: {e}")
            self._setup_lbl.setStyleSheet("color:#FF6666;")
            QMessageBox.critical(self, "שגיאה", f"לא ניתן להתחבר לטלגרם:\n\n{e}")

    def _save_values(self):
        self.config.set("telegram_enabled", self._enabled.isChecked())
        self.config.set("telegram_token",   self._token.text().strip())
        self.config.set("telegram_chat_id", self._chat_id.text().strip())

    def _save(self):
        self._save_values(); self.accept()


# ════════════════════════════════════════════════════════════════
#  SETTINGS DIALOG
# ════════════════════════════════════════════════════════════════
class SettingsDialog(QDialog):
    request_test           =pyqtSignal()
    request_full_test      =pyqtSignal()
    request_google_login   =pyqtSignal()
    request_google_logout  =pyqtSignal()
    request_sound_dialog   =pyqtSignal()
    request_telegram_dialog=pyqtSignal()
    def __init__(self,config,parent=None):
        super().__init__(parent); self.config=config; self._setup()
    # ── poll interval options ──────────────────────────────────
    _POLL_OPTS = [
        (1,  "1 שנייה"),
        (2,  "2 שניות (ברירת מחדל)"),
        (3,  "3 שניות"),
        (5,  "5 שניות"),
        (10, "10 שניות"),
    ]
    # ── timeout options shared by both combos ─────────────────
    _TIMEOUT_OPTS = [
        (0,  "ללא (לא לסגור)"),
        (5,  "5 שניות"),
        (10, "10 שניות"),
        (15, "15 שניות"),
        (20, "20 שניות"),
        (30, "30 שניות"),
        (45, "45 שניות"),
        (60, "דקה"),
    ]

    def _setup(self):
        self.setWindowTitle(f"הגדרות  —  {APP_NAME}  v{APP_VERSION}")
        self.setLayoutDirection(Qt.RightToLeft); self.resize(440,560)
        self.setStyleSheet("""
            QDialog{background:#160000;color:white;}
            QLabel{color:white;}
            QPushButton{background:#FF2020;color:white;border:none;border-radius:6px;padding:9px 20px;font-size:12px;}
            QPushButton:hover{background:#FF4040;}
            QCheckBox{color:white;font-size:12px;spacing:8px;}
            QCheckBox::indicator{width:17px;height:17px;border-radius:3px;border:1px solid #777;background:#260000;}
            QCheckBox::indicator:checked{background:#FF2020;border-color:#FF4040;}
            QComboBox{background:#260000;color:white;border:1px solid #550000;border-radius:5px;
                      padding:4px 8px;font-size:11px;min-width:130px;}
            QComboBox:hover{border-color:#FF4040;}
            QComboBox QAbstractItemView{background:#1a0000;color:white;selection-background-color:#FF2020;}
            QLineEdit{background:#260000;color:white;border:1px solid #550000;border-radius:5px;
                      padding:4px 8px;font-size:11px;}
            QLineEdit:hover{border-color:#FF4040;}
        """)
        v=QVBoxLayout(self); v.setContentsMargins(28,22,28,22); v.setSpacing(12)
        ti=QLabel(f"⚙  הגדרות  —  גרסה {APP_VERSION}"); ti.setFont(QFont("Arial",13,QFont.Bold)); ti.setAlignment(Qt.AlignCenter); v.addWidget(ti)
        def sep(): f=QFrame(); f.setFixedHeight(1); f.setStyleSheet("background:rgba(255,255,255,.1);"); return f
        v.addWidget(sep())
        self._cs=QCheckBox("🔊  נגן צלילי התרעה"); self._cs.setChecked(self.config.get("sound",True)); v.addWidget(self._cs)
        self._cf=QCheckBox("🖥  פתח מסך מלא אוטומטית"); self._cf.setChecked(self.config.get("auto_fullscreen",True)); v.addWidget(self._cf)
        self._cm=QCheckBox("🗺  פתח מפה אוטומטית בהתרעה"); self._cm.setChecked(self.config.get("show_map",True)); v.addWidget(self._cm)
        self._ck=QCheckBox("🚀  הפעל עם Windows (כמנהל)"); self._ck.setChecked(self.config.get("autostart",False)); v.addWidget(self._ck)
        v.addWidget(sep())
        # ── ⏱ Timeout controls ───────────────────────────────────
        def mk_combo(cur_val):
            cb = QComboBox(); cb.setLayoutDirection(Qt.RightToLeft)
            for sec, lbl in self._TIMEOUT_OPTS:
                cb.addItem(lbl, sec)
            idx = next((i for i,(s,_) in enumerate(self._TIMEOUT_OPTS) if s==cur_val), 3)
            cb.setCurrentIndex(idx); return cb
        def row(lbl_txt, combo):
            r = QHBoxLayout(); r.setSpacing(10)
            l = QLabel(lbl_txt); l.setFont(QFont("Arial",11)); l.setLayoutDirection(Qt.RightToLeft)
            r.addWidget(combo); r.addStretch(); r.addWidget(l); return r
        self._cfs = mk_combo(self.config.get("fullscreen_timeout", 15))
        self._cov = mk_combo(self.config.get("overlay_timeout",    30))
        v.addLayout(row("🖥  סגור מסך מלא אוטומטית אחרי:", self._cfs))
        v.addLayout(row("📋  חלון מרחף — הצג במשך:", self._cov))
        # ── poll interval ─────────────────────────────────────
        def mk_poll_combo(cur_val):
            cb = QComboBox(); cb.setLayoutDirection(Qt.RightToLeft)
            for sec, lbl in self._POLL_OPTS:
                cb.addItem(lbl, sec)
            idx = next((i for i,(s,_) in enumerate(self._POLL_OPTS) if s==cur_val), 1)
            cb.setCurrentIndex(idx); return cb
        self._cpoll = mk_poll_combo(self.config.get("poll_interval", 2))
        v.addLayout(row("🔁  בדיקת התרעות כל:", self._cpoll))
        v.addWidget(sep())
        # ── Telegram ──────────────────────────────────────────
        tg = QPushButton("📱  הגדרות טלגרם / Telegram")
        tg.setStyleSheet("QPushButton{background:#00366e;color:#88CCFF;border:1px solid #005599;"
                         "border-radius:6px;padding:9px 20px;}QPushButton:hover{background:#004488;}")
        tg.clicked.connect(self.request_telegram_dialog); v.addWidget(tg)
        # ── Webhook ───────────────────────────────────────────
        wh_row = QHBoxLayout(); wh_row.setSpacing(10)
        self._cwh = QCheckBox("🌐  Webhook — שלח POST בהתרעה")
        self._cwh.setChecked(self.config.get("webhook_enabled", False))
        wh_row.addWidget(self._cwh); v.addLayout(wh_row)
        self._ewh = QLineEdit(self.config.get("webhook_url", ""))
        self._ewh.setPlaceholderText("https://example.com/webhook")
        self._ewh.setLayoutDirection(Qt.LeftToRight)
        v.addWidget(self._ewh)
        sb=QPushButton("🔊  בחר צליל התרעה ראשי")
        sb.setStyleSheet("QPushButton{background:#2a0000;color:#FFBBBB;border:1px solid #550000;border-radius:6px;padding:9px 20px;}QPushButton:hover{background:#440000;}")
        sb.clicked.connect(self.request_sound_dialog); v.addWidget(sb)
        # ── צליל עבור חברים בהתרעה ──────────────────────────────
        _FRIEND_SOUNDS = [
            ("friend",   "🔔  ייחודי לחברים (ברירת מחדל)"),
            ("same",     "🔊  כמו התרעה רגילה"),
            ("soft",     "🎵  עדין — טון נמוך"),
            ("silent",   "🔇  שקט — ללא צליל"),
            ("standard", "📯  סטנדרטי"),
            ("urgent",   "🚨  דחוף"),
        ]
        fs_row = QHBoxLayout(); fs_row.setSpacing(10)
        fs_lbl = QLabel("🟠  צליל חברים בהתרעה:")
        fs_lbl.setFont(QFont("Arial",11)); fs_lbl.setLayoutDirection(Qt.RightToLeft)
        self._cfs2 = QComboBox(); self._cfs2.setLayoutDirection(Qt.RightToLeft)
        cur_fst = self.config.get("friend_sound_type","friend")
        for key,lbl in _FRIEND_SOUNDS:
            self._cfs2.addItem(lbl, key)
            if key == cur_fst: self._cfs2.setCurrentIndex(self._cfs2.count()-1)
        fs_row.addWidget(self._cfs2); fs_row.addStretch(); fs_row.addWidget(fs_lbl)
        v.addLayout(fs_row)
        lb=QPushButton("📍  בחר ישובים להתרעה")
        lb.clicked.connect(lambda: LocationsDialog(self.config,self).exec_()); v.addWidget(lb)
        v.addWidget(sep())
        gu=self.config.get("google_user")
        if gu:
            gl=QLabel(f"✅  מחובר לגוגל:  {gu}"); gl.setStyleSheet("color:#88FF88;font-size:11px;"); gl.setAlignment(Qt.AlignCenter); v.addWidget(gl)
            gout=QPushButton("🔓  התנתק מגוגל")
            gout.setStyleSheet("QPushButton{background:#003300;color:#88FF88;border:1px solid #006600;border-radius:6px;padding:9px 20px;}QPushButton:hover{background:#005500;}")
            gout.clicked.connect(self.request_google_logout); v.addWidget(gout)
        else:
            gin=QPushButton("🌍  התחבר לגוגל – שיתוף מיקום")
            gin.setStyleSheet("QPushButton{background:#003366;color:#88CCFF;border:1px solid #006699;border-radius:6px;padding:9px 20px;}QPushButton:hover{background:#004488;}")
            gin.clicked.connect(self.request_google_login); v.addWidget(gin)
        v.addWidget(sep())
        tb=QPushButton("🔔  שלח התרעת בדיקה")
        tb.setStyleSheet("QPushButton{background:#333;color:white;border:none;border-radius:6px;padding:9px 20px;font-size:12px;}QPushButton:hover{background:#444;}")
        tb.clicked.connect(self._test); v.addWidget(tb)
        ftb=QPushButton("🧪  בדיקה מקיפה  (מסכים + טלגרם + דיווח)")
        ftb.setStyleSheet(
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #440044,stop:1 #004400);color:#EEFFEE;"
            "border:1px solid #AA44AA;border-radius:6px;"
            "padding:11px 20px;font-size:12px;font-weight:bold;}"
            "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #660066,stop:1 #006600);}")
        ftb.clicked.connect(self._full_test); v.addWidget(ftb)
        v.addStretch(); v.addWidget(sep())
        bts=QHBoxLayout()
        cas="QPushButton{background:#333;color:white;border:none;border-radius:6px;padding:9px 20px;font-size:12px;}QPushButton:hover{background:#444;}"
        ca=QPushButton("ביטול"); ca.setStyleSheet(cas); sv=QPushButton("שמור")
        ca.clicked.connect(self.reject); sv.clicked.connect(self._save)
        bts.addWidget(ca); bts.addWidget(sv); v.addLayout(bts)
    def _test(self): self._save(); self.accept(); self.request_test.emit()
    def _full_test(self): self._save(); self.accept(); self.request_full_test.emit()
    def _save(self):
        self.config.set("sound",              self._cs.isChecked())
        self.config.set("auto_fullscreen",    self._cf.isChecked())
        self.config.set("show_map",           self._cm.isChecked())
        self.config.set("fullscreen_timeout", self._cfs.currentData())
        self.config.set("overlay_timeout",    self._cov.currentData())
        self.config.set("friend_sound_type",  self._cfs2.currentData())
        self.config.set("poll_interval",      self._cpoll.currentData())
        self.config.set("webhook_enabled",    self._cwh.isChecked())
        self.config.set("webhook_url",        self._ewh.text().strip())
        ns=self._ck.isChecked()
        if ns!=self.config.get("autostart",False): self.config.set_autostart(ns,sys.executable)
        self.accept()

# ════════════════════════════════════════════════════════════════
#  SHELTER WAIT SCREEN  – "אל תצא מהמרחב המוגן"
# ════════════════════════════════════════════════════════════════
class ShelterWaitScreen(QWidget):
    """Full-screen red overlay shown after alert clears – user must wait
    until the IDF-mandated shelter period expires before leaving."""
    safe_to_leave = pyqtSignal()

    def __init__(self, seconds_remaining: int, parent=None):
        super().__init__(parent)
        self._secs = max(1, int(seconds_remaining))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # ── Layout ─────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(60, 20, 60, 30)
        layout.setSpacing(18)

        # Close button — top-right corner
        top_row = QHBoxLayout()
        top_row.addStretch()
        close_btn = QPushButton("✕  סגור מסך")
        close_btn.setFont(QFont("Arial", 11))
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.12);color:rgba(255,255,255,0.7);"
            "border:1px solid rgba(255,255,255,0.25);border-radius:8px;padding:0 14px;}"
            "QPushButton:hover{background:rgba(255,80,80,0.45);color:white;"
            "border-color:rgba(255,80,80,0.7);}")
        close_btn.clicked.connect(self.close)
        top_row.addWidget(close_btn)
        layout.addLayout(top_row)

        warn = QLabel("⛔")
        warn.setFont(QFont("Arial", 72))
        warn.setAlignment(Qt.AlignCenter)
        layout.addWidget(warn)

        title = QLabel("אל תצא מהמרחב המוגן!")
        title.setFont(QFont("Arial", 36, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:#FF2020;")
        title.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(title)

        sub = QLabel("ממתין לאישור פיקוד העורף לצאת")
        sub.setFont(QFont("Arial", 18))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#FFBBBB;")
        sub.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(sub)

        self._timer_lbl = QLabel(self._fmt(self._secs))
        self._timer_lbl.setFont(QFont("Courier New", 54, QFont.Bold))
        self._timer_lbl.setAlignment(Qt.AlignCenter)
        self._timer_lbl.setStyleSheet("color:#FFD700; letter-spacing:4px;")
        layout.addWidget(self._timer_lbl)

        note = QLabel("ההתרעה הסתיימה – ממתינים לאישור כניסה בטוחה")
        note.setFont(QFont("Arial", 13))
        note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet("color:rgba(255,200,200,0.75);")
        note.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(note)

        # ESC hint
        esc_lbl = QLabel("ESC  או  לחיצה כפולה  לסגירה")
        esc_lbl.setFont(QFont("Arial", 10))
        esc_lbl.setAlignment(Qt.AlignCenter)
        esc_lbl.setStyleSheet("color:rgba(255,255,255,0.28);")
        layout.addWidget(esc_lbl)

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start(1000)
        self.showFullScreen()

    @staticmethod
    def _fmt(s: int) -> str:
        m, ss = divmod(max(0, s), 60)
        return f"{m:02d}:{ss:02d}"

    def _on_tick(self):
        self._secs -= 1
        try:
            self._timer_lbl.setText(self._fmt(self._secs))
        except RuntimeError:
            pass
        if self._secs <= 0:
            self._tick.stop()
            self.safe_to_leave.emit()
            self.close()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 230))
        p.end()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.close()

    def closeEvent(self, e):
        try:
            self._tick.stop()
        except RuntimeError:
            pass
        super().closeEvent(e)


# ════════════════════════════════════════════════════════════════
#  SHELTER MINI BANNER  — רצועה צפה קטנה "יש להשאר במרחב מוגן"
# ════════════════════════════════════════════════════════════════
class ShelterMiniBanner(QWidget):
    """רצועה צפה קטנה אדומה — מוצגת אחרי שמשתמש לחץ 'אני במרחב המוגן'.
    כשפיקוד העורף משחרר (alert_cleared) → עובר לירוק ונסגר אחרי 8 שניות."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._released = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._lbl = QLabel("🏠  יש להשאר במרחב המוגן")
        self._lbl.setFont(QFont("Arial", 13, QFont.Bold))
        self._lbl.setStyleSheet("color:#FFE878;")
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setLayoutDirection(Qt.RightToLeft)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,.15);color:white;border:none;"
            "border-radius:12px;font-size:11px;}"
            "QPushButton:hover{background:rgba(255,80,80,.6);}")
        close_btn.clicked.connect(self.close)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 12, 0)
        lay.setSpacing(10)
        lay.addWidget(self._lbl, 1)
        lay.addWidget(close_btn)

        self.setFixedHeight(44)
        self._place()

    def _place(self):
        try:
            sc = QApplication.desktop().availableGeometry()
            self.setFixedWidth(min(500, sc.width() - 40))
            self.move(sc.center().x() - self.width() // 2, sc.top() + 4)
        except Exception:
            pass

    def release(self):
        """נקרא כש-alert_cleared מגיע — עובר להודעת שחרור ירוקה."""
        if self._released:
            return
        self._released = True
        self._lbl.setText("✅  פיקוד העורף שחרר — ניתן לצאת מהמרחב המוגן")
        self._lbl.setStyleSheet("color:#88FF88;")
        QTimer.singleShot(8_000, self.close)

    def paintEvent(self, e):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            color = QColor(0, 80, 0, 235) if self._released else QColor(130, 0, 0, 235)
            r = self.rect().adjusted(1, 1, -1, -1)
            path = QPainterPath()
            path.addRoundedRect(QRectF(r), 8, 8)
            p.fillPath(path, color)
            border = QColor(0, 200, 0, 160) if self._released else QColor(255, 80, 80, 160)
            p.setPen(QPen(border, 1.5))
            p.drawPath(path)
        except Exception:
            pass

    def closeEvent(self, e):
        super().closeEvent(e)


# ════════════════════════════════════════════════════════════════
#  ALL-CLEAR SCREEN  – "מותר לצאת"
# ════════════════════════════════════════════════════════════════
#  FRIEND ALERT BANNER  – באנר כתום צף כשחבר/ה באזור ההתרעה
# ════════════════════════════════════════════════════════════════
class FriendAlertBanner(QWidget):
    """רצועה כתומה-זהובה צפה המוצגת כשאדם ששיתף מיקומו נמצא באזור ההתרעה."""

    def __init__(self, names: list, cities: list, parent=None):
        super().__init__(parent)
        self._names  = names
        self._cities = cities
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        sc = QApplication.desktop().screenGeometry()
        W = min(520, sc.width() - 40)
        self.setFixedWidth(W)
        self.move((sc.width() - W) // 2, sc.top() + 60)

        root = QVBoxLayout(self); root.setContentsMargins(14, 10, 14, 10); root.setSpacing(6)

        # ── כותרת ──────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(8)
        ico = QLabel("🟠"); ico.setFont(QFont("Segoe UI Emoji", 16)); ico.setFixedWidth(26)
        title = QLabel("אדם קרוב אליך בהתרעה!")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title.setStyleSheet("color:#FFD050;"); title.setLayoutDirection(Qt.RightToLeft)
        xbtn = QPushButton("✕"); xbtn.setFixedSize(22, 22)
        xbtn.setStyleSheet("QPushButton{background:rgba(255,180,0,.20);color:white;border:none;"
                           "border-radius:11px;}QPushButton:hover{background:rgba(255,100,0,.55);}")
        xbtn.clicked.connect(self.close)
        hdr.addWidget(ico); hdr.addWidget(title, 1); hdr.addWidget(xbtn)
        root.addLayout(hdr)

        # ── שמות + ישובים ───────────────────────────────────────
        for name, city in zip(names, cities):
            row = QHBoxLayout(); row.setSpacing(8)
            nl = QLabel(f"👤  {name}")
            nl.setFont(QFont("Arial", 10, QFont.Bold))
            nl.setStyleSheet("color:white;"); nl.setLayoutDirection(Qt.RightToLeft)
            cl = QLabel(f"📍  {city}")
            cl.setFont(QFont("Arial", 10))
            cl.setStyleSheet("color:#FFCC80;"); cl.setLayoutDirection(Qt.RightToLeft)
            row.addWidget(nl); row.addStretch(); row.addWidget(cl)
            root.addLayout(row)

        # ── כיתוב תחתון ─────────────────────────────────────────
        note = QLabel("נבנה על ידי הראלי דודאי  |  מרץ 2026")
        note.setFont(QFont("Arial", 7)); note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet("color:rgba(255,210,100,.35);")
        root.addWidget(note)

        self.adjustSize()
        QTimer.singleShot(12_000, self.close)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        p.fillPath(path, QColor(110, 55, 0, 235))
        p.setPen(QPen(QColor(255, 165, 0, 160), 1.5))
        p.drawPath(path)
        p.end()


# ════════════════════════════════════════════════════════════════
#  FRIEND LOCATIONS DIALOG – הצע להוסיף ישובים של חברים
# ════════════════════════════════════════════════════════════════
class FriendLocationsDialog(QDialog):
    """מוצג פעם אחת בסשן כשנטענים מיקומי חברים עם ישובים ידועים.
    מאפשר להוסיף את ישוביהם לרשימת הישובים המנוטרים."""

    def __init__(self, friends: list, config, parent=None):
        super().__init__(parent)
        self._config  = config
        self._checks  = {}   # city → QCheckBox
        self.setWindowTitle("ישובים של אנשים ששיתפו מיקום")
        self.setLayoutDirection(Qt.RightToLeft); self.resize(460, 340)
        self.setStyleSheet("QDialog{background:#0e1a00;color:white;}"
                           "QLabel{color:white;}"
                           "QCheckBox{color:white;font-size:11px;spacing:8px;}"
                           "QCheckBox::indicator{width:16px;height:16px;border-radius:3px;"
                           "border:1px solid #558800;background:#1a2e00;}"
                           "QCheckBox::indicator:checked{background:#88CC00;border-color:#AAEE00;}"
                           "QPushButton{border-radius:6px;padding:8px 18px;font-size:12px;}")
        v = QVBoxLayout(self); v.setContentsMargins(28, 20, 28, 20); v.setSpacing(12)

        title = QLabel("📍  מיקום שותף זוהה")
        title.setFont(QFont("Arial", 13, QFont.Bold)); title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        sep = QFrame(); sep.setFixedHeight(1); sep.setStyleSheet("background:rgba(120,200,0,.30);")
        v.addWidget(sep)

        note = QLabel("הוסף את ישוביהם לרשימת ההתרעות שלך?")
        note.setFont(QFont("Arial", 10)); note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet("color:rgba(255,255,255,.60);"); v.addWidget(note)

        # ── שורה לכל חבר ─────────────────────────────────────
        existing = set(config.get("locations", []))
        sc_area = QScrollArea(); sc_area.setWidgetResizable(True); sc_area.setFixedHeight(160)
        sc_area.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        il = QVBoxLayout(inner); il.setContentsMargins(0, 0, 0, 0); il.setSpacing(6)
        for f in friends:
            city = f.get("city")
            if not city: continue
            row = QHBoxLayout(); row.setSpacing(10)
            avatar = QLabel("👤"); avatar.setFont(QFont("Segoe UI Emoji", 13)); avatar.setFixedWidth(24)
            name_lbl = QLabel(f["name"])
            name_lbl.setFont(QFont("Arial", 10, QFont.Bold))
            name_lbl.setStyleSheet("color:#BBFF88;"); name_lbl.setLayoutDirection(Qt.RightToLeft)
            city_lbl = QLabel(f"← {city}")
            city_lbl.setFont(QFont("Arial", 9))
            city_lbl.setStyleSheet("color:rgba(200,255,150,.75);"); city_lbl.setLayoutDirection(Qt.RightToLeft)
            cb = QCheckBox(); cb.setChecked(city not in existing)
            self._checks[city] = cb
            row.addWidget(avatar); row.addWidget(name_lbl); row.addWidget(city_lbl, 1); row.addWidget(cb)
            il.addLayout(row)
        sc_area.setWidget(inner); v.addWidget(sc_area)

        sep2 = QFrame(); sep2.setFixedHeight(1); sep2.setStyleSheet("background:rgba(120,200,0,.20);")
        v.addWidget(sep2)

        bts = QHBoxLayout(); bts.setSpacing(10)
        ok_btn = QPushButton("✓  הוסף ישובים מסומנים")
        ok_btn.setStyleSheet("QPushButton{background:#3a6600;color:white;border:1px solid #66AA00;}"
                             "QPushButton:hover{background:#559900;}")
        ok_btn.clicked.connect(self._save)
        skip_btn = QPushButton("דלג")
        skip_btn.setStyleSheet("QPushButton{background:transparent;color:rgba(255,255,255,.35);"
                               "border:none;}QPushButton:hover{color:white;}")
        skip_btn.clicked.connect(self.reject)
        bts.addWidget(ok_btn, 2); bts.addWidget(skip_btn)
        v.addLayout(bts)

        # ── קרדיט ─────────────────────────────────────────────
        credit = QLabel("נבנה על ידי הראלי דודאי  |  מרץ 2026")
        credit.setFont(QFont("Arial", 7)); credit.setAlignment(Qt.AlignCenter)
        credit.setStyleSheet("color:rgba(180,255,100,.28);")
        v.addWidget(credit)

    def _save(self):
        current = self._config.get("locations", [])
        for city, cb in self._checks.items():
            if cb.isChecked() and city not in current:
                current.append(city)
        self._config.set("locations", current)
        self.accept()


# ════════════════════════════════════════════════════════════════
class AllClearScreen(QWidget):
    """Brief green overlay confirming it is safe to leave the shelter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Build layout BEFORE showing
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(28)

        icon = QLabel("✅")
        icon.setFont(QFont("Arial", 80))
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("מותר לצאת מהמרחב המוגן")
        title.setFont(QFont("Arial", 38, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:#00FF88;")
        title.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(title)

        sub = QLabel("פיקוד העורף אישר יציאה – בטוח לצאת")
        sub.setFont(QFont("Arial", 18))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#AAFFCC;")
        sub.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(sub)

        hint = QLabel("חלון זה ייסגר אוטומטית בעוד 10 שניות")
        hint.setFont(QFont("Arial", 12))
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color:rgba(180,255,210,0.6);")
        hint.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(hint)

        credit = QLabel("נבנה על ידי הראלי דודאי  |  מרץ 2026")
        credit.setFont(QFont("Arial", 9)); credit.setAlignment(Qt.AlignCenter)
        credit.setStyleSheet("color:rgba(150,255,190,.30);")
        layout.addWidget(credit)

        QTimer.singleShot(10_000, self.close)
        # Show AFTER layout is fully built
        self.showFullScreen()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 30, 10, 220))
        p.end()

    def mouseReleaseEvent(self, e):
        self.close()


# ════════════════════════════════════════════════════════════════
#  ALERT OVERLAY  — חלון מרחף עם ספירה לאחור
# ════════════════════════════════════════════════════════════════
class AlertOverlay(QWidget):
    """
    חלון מרחף קומפקטי המוצג בכל התרעה.
    מציג את כל הישובים המוזהרים + ספירה לאחור.
    נסגר אוטומטית אחרי timeout שניות.
    הבר מצויר ב-paintEvent — בטוח לחלוטין, ללא ווידג'טים מקוננים.
    """
    sig_open_fullscreen = pyqtSignal()
    sig_dismissed       = pyqtSignal()   # נפלט כשהמשתמש סוגר את החלון ידנית

    def __init__(self, alert, my_cities=None, timeout=30, parent=None):
        super().__init__(parent)
        self._alert     = alert
        self._my_cities = set(my_cities or [])
        self._total     = max(1, int(timeout or 30))
        self._secs      = self._total
        self._drag      = None
        self._bar_ratio = 1.0   # 0.0–1.0, מעודכן ב-_on_tick

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._build()
        self._place()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(1000)

    def _build(self):
        a   = self._alert
        col = a.color
        hit = [c for c in a.cities if c in self._my_cities]

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 12)
        root.setSpacing(5)

        # ── Header ─────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(8)
        ico = QLabel(a.icon); ico.setFont(QFont("Segoe UI Emoji", 20))
        ico.setFixedWidth(34); ico.setAlignment(Qt.AlignCenter)
        ttl = QLabel(a.title); ttl.setFont(QFont("Arial", 12, QFont.Bold))
        ttl.setStyleSheet(f"color:{col};"); ttl.setLayoutDirection(Qt.RightToLeft)
        tim = QLabel(a.time_str); tim.setFont(QFont("Arial", 9))
        tim.setStyleSheet("color:rgba(255,255,255,.45);")
        xbtn = QPushButton("✕"); xbtn.setFixedSize(24, 24)
        xbtn.setStyleSheet(
            "QPushButton{background:rgba(255,80,80,.25);color:white;border:none;border-radius:12px;}"
            "QPushButton:hover{background:#AA2020;}")
        xbtn.clicked.connect(self._dismiss)
        hdr.addWidget(ico); hdr.addWidget(ttl, 1); hdr.addWidget(tim); hdr.addWidget(xbtn)
        root.addLayout(hdr)

        # ── My city alert ──────────────────────────────────────
        if hit:
            mc = QLabel(f"⚠  ישוב שלי מוזהר:  {'  |  '.join(hit)}")
            mc.setFont(QFont("Arial", 10, QFont.Bold))
            mc.setAlignment(Qt.AlignCenter); mc.setLayoutDirection(Qt.RightToLeft)
            mc.setStyleSheet(
                "color:white;background:rgba(255,30,30,.30);"
                "border-radius:5px;padding:3px 10px;")
            root.addWidget(mc)

        # ── Separator ──────────────────────────────────────────
        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet("background:rgba(255,255,255,.12);")
        root.addWidget(sep)

        # ── City count ─────────────────────────────────────────
        cnt = QLabel(f"ישובים מוזהרים  ({len(a.cities)}):")
        cnt.setFont(QFont("Arial", 9)); cnt.setLayoutDirection(Qt.RightToLeft)
        cnt.setStyleSheet("color:rgba(255,255,255,.55);")
        root.addWidget(cnt)

        # ── City tags (up to 18, 3 per row) ────────────────────
        max_show = 18; COLS = 3
        cw = QWidget(); cw.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(cw); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(3)
        row_l = None
        for i, city in enumerate(a.cities[:max_show]):
            if i % COLS == 0:
                rw = QWidget(); rw.setStyleSheet("background:transparent;")
                row_l = QHBoxLayout(rw)
                row_l.setContentsMargins(0, 0, 0, 0); row_l.setSpacing(3)
                cl.addWidget(rw)
            is_mine = city in self._my_cities
            bg = col if is_mine else "rgba(160,15,15,.75)"
            weight = QFont.Bold if is_mine else QFont.Normal
            lb = QLabel(city); lb.setFont(QFont("Arial", 9, weight))
            lb.setAlignment(Qt.AlignCenter); lb.setLayoutDirection(Qt.RightToLeft)
            lb.setStyleSheet(f"color:white;background:{bg};border-radius:4px;padding:2px 5px;")
            row_l.addWidget(lb)
        if row_l and row_l.count() % COLS != 0:
            row_l.addStretch()
        if len(a.cities) > max_show:
            more = QLabel(f"+{len(a.cities) - max_show} ישובים נוספים")
            more.setFont(QFont("Arial", 8))
            more.setStyleSheet("color:rgba(255,180,180,.55);")
            more.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            cl.addWidget(more)
        root.addWidget(cw)

        # ── Countdown label (בר מצויר ב-paintEvent) ───────────
        self._clbl = QLabel(self._fmt())
        self._clbl.setFont(QFont("Arial", 8)); self._clbl.setAlignment(Qt.AlignCenter)
        self._clbl.setStyleSheet("color:rgba(255,200,150,.60);")
        self._clbl.setLayoutDirection(Qt.RightToLeft)
        # placeholder QWidget בגובה 6px — הבר יצויר עליו ב-paintEvent
        self._bar_placeholder = QWidget()
        self._bar_placeholder.setFixedHeight(6)
        self._bar_placeholder.setStyleSheet("background:transparent;")
        self._bar_placeholder.setAttribute(Qt.WA_TransparentForMouseEvents)
        root.addWidget(self._bar_placeholder)
        root.addWidget(self._clbl)

        # ── Open fullscreen button ─────────────────────────────
        fsbtn = QPushButton("🖥  פתח מסך מלא")
        fsbtn.setFont(QFont("Arial", 10, QFont.Bold))
        fsbtn.setFixedHeight(32)
        fsbtn.setStyleSheet(
            f"QPushButton{{background:rgba(255,255,255,.08);color:white;"
            f"border:1px solid rgba(255,255,255,.18);border-radius:6px;}}"
            f"QPushButton:hover{{background:{col};border-color:{col};}}")
        fsbtn.clicked.connect(self._open_fs)
        root.addWidget(fsbtn)

        self.setFixedWidth(480)
        self.adjustSize()

    def _fmt(self):
        return f"נסגר בעוד  {max(0, self._secs)}  שניות"

    def _place(self):
        try:
            sc = QApplication.desktop().availableGeometry()
            self.move(sc.center().x() - self.width() // 2,
                      sc.top() + sc.height() // 5)
        except Exception:
            pass

    def _on_tick(self):
        self._secs -= 1
        self._bar_ratio = max(0.0, self._secs / self._total)
        try:
            self._clbl.setText(self._fmt())
            # עדכן רק את אזור הבר
            if self._bar_placeholder and self._bar_placeholder.isVisible():
                self._bar_placeholder.update()
            self.update()   # צייר מחדש את ה-paintEvent (רקע + בר)
        except RuntimeError:
            pass
        if self._secs <= 0:
            self._timer.stop()
            self.close()

    def _dismiss(self):
        """סגירה ידנית על ידי המשתמש — מעדכן את האפליקציה לא להציג שוב."""
        self.sig_dismissed.emit()
        self._timer.stop()
        self.close()

    def _open_fs(self):
        self.sig_open_fullscreen.emit()
        self._timer.stop()
        self.close()

    # ── ציור: רקע מעוגל + בר התקדמות ─────────────────────────
    def paintEvent(self, e):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)

            # ── רקע גלאס מעוגל ─────────────────────────────────
            r = self.rect().adjusted(2, 2, -2, -2)
            path = QPainterPath()
            path.addRoundedRect(QRectF(r), 16, 16)
            # שכבת בסיס כהה שקופה
            bg = QLinearGradient(0, 0, 0, r.height())
            bg.setColorAt(0, QColor(18, 2, 2, 225))
            bg.setColorAt(1, QColor(8,  1, 1, 215))
            p.fillPath(path, bg)
            # shimmer עליון — אפקט זכוכית
            sh = QLinearGradient(0, 0, 0, r.height() * 0.22)
            sh.setColorAt(0, QColor(255, 255, 255, 45))
            sh.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillPath(path, sh)
            # border בצבע ההתרעה
            border = QColor(self._alert.color); border.setAlpha(180)
            p.setPen(QPen(border, 2)); p.drawPath(path)

            # בר התקדמות — מצויר ישירות על ה-placeholder
            if self._bar_placeholder:
                br = self._bar_placeholder.geometry()
                mx = 14  # margin
                bx = br.x() + mx; by = br.y()
                bw = br.width() - mx * 2; bh = br.height()
                # רקע אפור
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 255, 255, 20))
                p.drawRoundedRect(bx, by, bw, bh, 3, 3)
                # בר צבעוני
                fill_w = max(4, int(bw * self._bar_ratio))
                p.setBrush(QColor(self._alert.color))
                p.drawRoundedRect(bx, by, fill_w, bh, 3, 3)
        except Exception:
            pass

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag:
            self.move(e.globalPos() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def closeEvent(self, e):
        try:
            self._timer.stop()
        except RuntimeError:
            pass
        super().closeEvent(e)


# ════════════════════════════════════════════════════════════════
#  FALL RESULTS  — תוצאות נפילה
# ════════════════════════════════════════════════════════════════
class FallResultsWorker(QThread):
    """מאחזר חדשות מ-RSS בצורת polling — מוסיף ידיעות חדשות ברגע שמופיעות."""
    results_ready = pyqtSignal(list)   # list of {"title","desc","link","ts"} — רק פריטים חדשים

    _INITIAL_WAIT = 60    # המתן דקה לפני הבדיקה הראשונה
    _POLL_INTERVAL = 30   # בדוק כל 30 שניות
    _MAX_DURATION  = 600  # עצור לאחר 10 דקות

    # מילות מפתח לתוצאות ירי/ירוט/נפילה — חייב להופיע יחד עם שם ישוב
    _KEYWORDS = ["נפילה","נפל","מכה","פגיעה","פגע","התפוצץ","נחת",
                 "ירוט","כיפת ברזל","חיסול","התרסק","שיגור","רקטה","טיל",
                 "כטב\"מ","מל\"ט","מחבל","פצצה","תקיפה","הפצצה"]
    # מקורות RSS ביטחוניים בלבד
    _RSS_FEEDS = [
        "https://www.ynet.co.il/Integration/StoryRss3.xml",   # ynet ביטחון
        "https://rss.walla.co.il/feed/22",                    # walla ביטחון
        "https://www.mako.co.il/AjaxPage?jspName=rssFeedGet.jsp&catId=1",  # mako חדשות
    ]

    def __init__(self, cities, alert_ts):
        super().__init__()
        self.cities    = [c.strip() for c in cities]
        self.alert_ts  = alert_ts
        self._stop     = False
        self.setObjectName("FallResultsWorker")

    def stop(self):
        self._stop = True

    @staticmethod
    def _norm(s):
        """נרמול טקסט להשוואה — מחליף מקף/גרש/רווח לצורך התאמה גמישה."""
        return s.replace("-", " ").replace("–", " ").replace("'", "'")

    def _city_in_text(self, text):
        """בודק אם אחד מהישובים מופיע בטקסט — עם נרמול מקף/רווח."""
        norm_text = self._norm(text)
        return any(self._norm(c) in norm_text for c in self.cities)

    def _log(self, msg):
        """כותב לוג לקובץ debug לצורך אבחון."""
        import os, datetime
        try:
            log_path = os.path.join(os.environ.get("APPDATA","~"), "RedAlert", "news_debug.log")
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
        except Exception:
            pass

    def run(self):
        import time as _t
        seen       = set()   # כותרות שכבר דיווחנו עליהן
        found_any  = False
        start      = _t.time()

        self._log(f"START — cities={self.cities}")

        # המתן ראשונית לפני בדיקה ראשונה
        _t.sleep(self._INITIAL_WAIT)

        while not self._stop and (_t.time() - start) < self._MAX_DURATION:
            raw = []
            for url in self._RSS_FEEDS:
                try:
                    items = self._fetch_rss(url)
                    raw.extend(items)
                    self._log(f"RSS OK {url} → {len(items)} items")
                except Exception as e:
                    self._log(f"RSS FAIL {url} → {e}")

            new_items = []
            for item in raw:
                key = item.get("title","")[:50]
                if key in seen: continue
                seen.add(key)

                # סינון לפי זמן פרסום
                pub_dt = item.get("_pub_dt")
                if pub_dt is not None:
                    delta = (pub_dt - self.alert_ts).total_seconds()
                    if delta < -600: continue   # פורסם יותר מ-10 דקות לפני ההתרעה
                    if delta > self._MAX_DURATION: continue  # עתידי מדי

                # סינון לפי הקשר: ישוב (עם נרמול מקף/רווח) + מילת מפתח
                text = item.get("title","") + " " + item.get("desc","")
                city_hit = self._city_in_text(text)
                kw_hit   = any(kw in text for kw in self._KEYWORDS)
                self._log(f"  item='{key[:40]}' city={city_hit} kw={kw_hit}")
                if city_hit and kw_hit:
                    new_items.append(item)

            if new_items:
                found_any = True
                self._log(f"EMIT {len(new_items)} new items")
                self.results_ready.emit(new_items[:5])

            # המתן עד לבדיקה הבאה
            elapsed   = _t.time() - start
            remaining = self._MAX_DURATION - elapsed
            if remaining <= 0: break
            _t.sleep(min(self._POLL_INTERVAL, remaining))

        self._log(f"END — found_any={found_any}")
        # בסיום — אם לא נמצא כלום, הודע פעם אחרונה
        if not found_any and not self._stop:
            self.results_ready.emit([])

    @staticmethod
    def _fetch_rss(url):
        import urllib.request
        import xml.etree.ElementTree as ET
        import re
        from email.utils import parsedate_to_datetime
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        root = ET.fromstring(data)
        out = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            raw_desc = (item.findtext("description") or "").strip()
            desc = re.sub(r"<[^>]+>","", raw_desc)[:200].strip()
            link  = (item.findtext("link") or "").strip()
            pub   = (item.findtext("pubDate") or "").strip()
            # פרסינג של זמן הפרסום
            pub_dt = None
            if pub:
                try:
                    pub_dt = parsedate_to_datetime(pub).replace(tzinfo=None)
                except Exception:
                    pass
            if title:
                out.append({"title":title,"desc":desc,"link":link,"ts":pub,"_pub_dt":pub_dt})
        return out


class FallResultsWindow(QWidget):
    """חלון קטן המציג עדכוני חדשות על נפילות לאחר ההתרעה."""
    def __init__(self, results, cities, alert_title="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("💥  תוצאות נפילה — עדכוני חדשות")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(500, 420)
        self.setStyleSheet("""
            QWidget{background:#0c0c1e;color:white;}
            QScrollArea{border:none;background:#0c0c1e;}
            QScrollBar:vertical{background:#1a1a2e;width:7px;border-radius:3px;}
            QScrollBar::handle:vertical{background:#555;border-radius:3px;}
        """)
        v = QVBoxLayout(self); v.setContentsMargins(20,16,20,16); v.setSpacing(10)

        ti = QLabel("💥  תוצאות נפילה — עדכוני חדשות שוטפים")
        ti.setFont(QFont("Arial",13,QFont.Bold)); ti.setAlignment(Qt.AlignCenter)
        ti.setStyleSheet("color:#FF8800;padding:4px 0;"); v.addWidget(ti)

        if alert_title:
            al = QLabel(f"🚨  {alert_title}"); al.setFont(QFont("Arial",10))
            al.setStyleSheet("color:#FFE878;"); v.addWidget(al)
        if cities:
            cl_txt = "  |  ".join(cities[:6]) + ("..." if len(cities)>6 else "")
            cl = QLabel(f"🏙  ישובים: {cl_txt}"); cl.setFont(QFont("Arial",10))
            cl.setStyleSheet("color:rgba(255,255,255,0.65);"); v.addWidget(cl)

        def sep(): f=QFrame(); f.setFixedHeight(1); f.setStyleSheet("background:rgba(255,255,255,.08);"); return f
        v.addWidget(sep())

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        cont = QWidget(); cl2 = QVBoxLayout(cont); cl2.setSpacing(10); cl2.setContentsMargins(0,4,0,4)
        self._scroll_layout = cl2
        self._no_results_lbl = None

        if not results:
            nl = QLabel("⏳  ממשיך לחפש חדשות רלוונטיות...")
            nl.setAlignment(Qt.AlignCenter)
            nl.setStyleSheet("color:rgba(255,255,255,0.45);font-size:12px;padding:24px;")
            cl2.addWidget(nl)
            self._no_results_lbl = nl
        else:
            self._add_cards(results)
        cl2.addStretch()
        scroll.setWidget(cont); v.addWidget(scroll, 1)
        v.addWidget(sep())
        src = QLabel("מקור: ynet · walla — בדיקה אוטומטית 2 דקות לאחר ההתרעה")
        src.setStyleSheet("color:rgba(255,255,255,0.28);font-size:10px;"); src.setAlignment(Qt.AlignCenter); v.addWidget(src)
        self._close_countdown = 10
        cb = QPushButton(f"סגור ({self._close_countdown})")
        cb.setStyleSheet("QPushButton{background:#333;color:white;border:none;border-radius:6px;padding:8px 22px;}")
        cb.clicked.connect(self.close); v.addWidget(cb, 0, Qt.AlignCenter)
        self._close_btn = cb
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setInterval(1000)
        self._auto_close_timer.timeout.connect(self._tick_close)
        self._auto_close_timer.start()

    def _add_cards(self, items):
        """מוסיף כרטיסיות ידיעות ל-layout הפנימי (ללא stretch)."""
        for item in items:
            card = QWidget()
            card.setStyleSheet("QWidget{background:#1a1a30;border-radius:9px;}")
            kl = QVBoxLayout(card); kl.setContentsMargins(14,10,14,10); kl.setSpacing(4)
            tl = QLabel(item.get("title",""))
            tl.setFont(QFont("Arial",11,QFont.Bold)); tl.setWordWrap(True)
            tl.setStyleSheet("color:white;"); tl.setLayoutDirection(Qt.RightToLeft)
            kl.addWidget(tl)
            if item.get("desc"):
                dl = QLabel(item["desc"][:180])
                dl.setFont(QFont("Arial",10)); dl.setWordWrap(True)
                dl.setStyleSheet("color:rgba(255,255,255,0.65);")
                dl.setLayoutDirection(Qt.RightToLeft); kl.addWidget(dl)
            if item.get("ts"):
                sl = QLabel(f"🕐  {item['ts']}")
                sl.setFont(QFont("Arial",9)); sl.setStyleSheet("color:rgba(255,255,255,0.38);")
                kl.addWidget(sl)
            if item.get("link"):
                ll = QLabel(f"🔗  <a href='{item['link']}' style='color:#58a6ff;'>{item['link'][:70]}</a>")
                ll.setOpenExternalLinks(True); ll.setWordWrap(True)
                ll.setFont(QFont("Arial",9)); kl.addWidget(ll)
            self._scroll_layout.addWidget(card)

    def add_items(self, items):
        """מוסיף ידיעות חדשות לחלון הפתוח ומאפס את הטיימר."""
        if self._no_results_lbl is not None:
            self._no_results_lbl.setParent(None)
            self._no_results_lbl = None
        # הסר stretch אחרון לפני הוספת פריטים
        n = self._scroll_layout.count()
        if n > 0:
            last = self._scroll_layout.itemAt(n - 1)
            if last and last.spacerItem():
                self._scroll_layout.removeItem(last)
        self._add_cards(items)
        self._scroll_layout.addStretch()
        # אפס את הטיימר סגירה אוטומטית
        self._close_countdown = 15
        self._auto_close_timer.start()

    def _tick_close(self):
        self._close_countdown -= 1
        if self._close_countdown <= 0:
            self._auto_close_timer.stop()
            self.close()
        else:
            self._close_btn.setText(f"סגור ({self._close_countdown})")


# ════════════════════════════════════════════════════════════════
#  MAIN APP
# ════════════════════════════════════════════════════════════════
class RedAlertApp(QApplication):
    def __init__(self):
        super().__init__(sys.argv)
        self.setApplicationName(APP_NAME); self.setQuitOnLastWindowClosed(False)
        self.config    =Config()
        self.history   =deque(maxlen=100)
        self.sound     =SoundPlayer(); self.sound.set_type(self.config.get("sound_type","standard"))
        # ── Persistent history DB ───────────────────────────────────
        self._history_db  = HistoryDB()
        self._history_win = None
        # Load previous sessions' alerts into the in-memory deque (oldest→appendleft→newest at [0])
        for rec in reversed(self._history_db.load_recent(100)):
            try: self.history.appendleft(Alert(rec))
            except Exception: pass
        self._fs            =None
        self._overlay       =None       # AlertOverlay instance
        self._friends       =[]
        self._loc_worker    =None
        self._google_browser=None
        # ── Shelter state ──────────────────────────────────────────
        self._shelter_end   =0.0
        self._shelter_scr   =None       # reserved (unused)
        self._allclear_scr  =None
        self._shelter_banner=None       # ShelterMiniBanner instance
        self._friend_banner =None       # FriendAlertBanner instance
        self._shown_friend_loc_dlg=False  # הצג דיאלוג ישובי חברים רק פעם אחת בסשן
        self._temp_locations=set()        # ישובים זמניים (לפי מיקום IP)
        self._mute_until    =0.0          # epoch — alerts muted until this time
        self._fall_workers  =[]           # FallResultsWorker instances (keep refs)
        self._active_alert_key = None     # (cat, frozenset(cities)) of currently-shown alert
        self._ack_key       =None         # (cat, frozenset(cities)) — dismissed by user
        self.widget=FloatingWidget(self.config)
        self.widget.sig_fullscreen.connect(self._fullscreen)
        self.widget.sig_settings.connect(self._settings)
        self.widget.sig_map.connect(self._show_map)
        self.widget.sig_google.connect(self._open_google_sharing)
        self.widget.sig_history.connect(self._show_history)
        self.widget.sig_snooze.connect(self._on_snooze)
        self.widget.show()
        self.map_win=MapWindow()
        self.map_win.sig_google_sharing.connect(self._open_google_sharing)
        self._tray_setup()
        self.worker=AlertWorker(self.config)
        self.worker.new_alert.connect(self._on_alert)
        self.worker.alert_cleared.connect(self._on_clear)
        self.worker.conn_error.connect(self.widget.set_conn_error)
        self.worker.conn_ok.connect(self.widget.set_conn_ok)
        self.worker.start()
        # ── Fetch full OREF city list in background ─────────────────
        threading.Thread(target=_fetch_oref_cities, daemon=True).start()
        # ── Location tracker — detect IP location changes ───────────
        self._loc_track=LocationTrackWorker()
        self._loc_track.location_detected.connect(self._on_ip_location_detected)
        self._loc_track.start()
        # ── Google — חיבור אוטומטי עם פרופיל קוקיות מתמיד ────────
        if _HAS_WEB:
            self._google_browser = GoogleBrowserWindow()
            self._google_browser.logged_in.connect(self._on_google_login_browser)
            # טוען קוקיות שמורות → אם קיים SAPISID, logged_in יופעל אוטומטית
            self._google_browser.load_saved_session()
        else:
            # Fallback: קוקיות שמורות בקונפיג
            saved = self.config.get("google_cookies")
            if saved:
                self._start_loc_worker(saved)
        # Show user's own cities on the map from the start
        QTimer.singleShot(1500, self._init_map)
        # זיהוי מיקום תמיד בהפעלה — גם אם יש ישובים מוגדרים
        QTimer.singleShot(2200, self._check_startup_location)

    def _init_map(self):
        """Load user cities and friends onto the map immediately at startup."""
        uc = self.config.get("locations", [])
        self.map_win.update_alerts([], uc, self._friends)

    def _check_startup_location(self):
        """נקרא תמיד בהפעלה — מזהה מיקום IP בthread נפרד (לא חוסם את main thread)."""
        def _worker():
            result = _detect_city_from_ip()
            city = result[0] if result else None
            # חזרה ל-main thread דרך QTimer.singleShot
            QTimer.singleShot(0, lambda: self._apply_startup_location(city))
        threading.Thread(target=_worker, daemon=True).start()

    def _apply_startup_location(self, city):
        """מופעל ב-main thread אחרי זיהוי מיקום IP ב-background."""
        if not city:
            return
        permanent = self.config.get("locations", [])
        if not permanent:
            # הפעלה ראשונה / אין ישובים — הצג דיאלוג מלא
            self._auto_detect_location_with_city(city)
        elif city not in permanent and city not in self._temp_locations:
            # יש ישובים קבועים אבל נמצאים עכשיו במקום אחר — הוסף זמנית
            self._temp_locations.add(city)
            # עדכן את LocationTrackWorker שיידע את המיקום הנוכחי (מניעת כפילות)
            if self._loc_track and hasattr(self._loc_track, '_last_city'):
                self._loc_track._last_city = city
            self._update_temp_filter()
            self._init_map()
            self._tray.showMessage(
                f"📍  מיקום זוהה: {city}",
                f"נמצאת ב-{city} — הישוב נוסף זמנית לרשימת ההתרעות.\n"
                f"הישובים הקבועים שלך ({', '.join(permanent[:3])}"
                f"{'...' if len(permanent)>3 else ''}) פעילים תמיד.",
                QSystemTrayIcon.Information, 9000)
        # אם city כבר ב-permanent — אין צורך בפעולה, הכל תקין

    def _auto_detect_location(self):
        """מנסה לזהות מיקום לפי IP ומציג דיאלוג להגדרת ישוב (הפעלה ראשונה)."""
        result = _detect_city_from_ip()
        city = result[0] if result else None
        self._auto_detect_location_with_city(city)

    def _auto_detect_location_with_city(self, city):
        """מציג דיאלוג זיהוי מיקום עם ישוב נתון."""
        dlg = LocationDetectDialog(
            detected_city=city,
            config=self.config,
            open_settings_cb=self._settings,
            parent=self.widget
        )
        dlg.exec_()
        # אם המשתמש אישר → עדכן את המפה עם הישוב החדש
        if self.config.get("locations", []):
            self._init_map()

    # ── Tray ───────────────────────────────────────────────────
    def _tray_setup(self):
        px=QPixmap(22,22); px.fill(Qt.transparent)
        p=QPainter(px); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor("#FF2020"))); p.setPen(Qt.NoPen); p.drawEllipse(2,2,18,18); p.end()
        self._tray=QSystemTrayIcon(QIcon(px),self); self._tray.setToolTip(f"🔴  {APP_NAME}")
        menu=QMenu(); menu.setLayoutDirection(Qt.RightToLeft)
        menu.setStyleSheet("QMenu{background:#1a0000;color:white;border:1px solid #440000;border-radius:6px;padding:4px;}"
                           "QMenu::item{padding:7px 22px;border-radius:4px;}QMenu::item:selected{background:#FF2020;}"
                           "QMenu::separator{height:1px;background:rgba(255,255,255,.12);margin:3px 0;}")
        for lbl,cb in [("🖥  מסך מלא",self._fullscreen),("🗺  מפה",self._show_map),
                       ("📋  היסטוריה",self._show_history),(None,None),
                       ("⚙  הגדרות",self._settings),("🔔  בדיקה",self._test),(None,None),("❌  יציאה",self._exit)]:
            if lbl is None: menu.addSeparator()
            else: a=QAction(lbl,self); a.triggered.connect(cb); menu.addAction(a)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(
            lambda r:(self.widget.show() or self.widget.raise_())
            if r in(QSystemTrayIcon.DoubleClick,QSystemTrayIcon.Trigger) else None)
        self._tray.show()

    # ── IP Location tracking ────────────────────────────────────
    def _on_ip_location_detected(self, city):
        """Called when the IP-detected city changes."""
        permanent = set(self.config.get("locations", []))
        # If no permanent locations: first-run dialog handles it
        if not permanent:
            return
        # Remove all previous temp locations (we moved somewhere new)
        if self._temp_locations:
            removed = set(self._temp_locations)
            self._temp_locations.clear()
            self._update_temp_filter()
            self._tray.showMessage(
                "📍 ישוב זמני הוסר",
                f"עברת מקום — הוסרו: {', '.join(removed)}",
                QSystemTrayIcon.Information, 4000)
        # Ask to add new city temporarily if not already permanent
        if city not in permanent:
            QTimer.singleShot(800, lambda c=city: self._show_temp_loc_dialog(c))

    def _show_temp_loc_dialog(self, city):
        dlg = TempLocationDialog(city, self.widget)
        if dlg.exec_() == QDialog.Accepted:
            self._temp_locations.add(city)
            self._update_temp_filter()
            self._tray.showMessage(
                "📍 ישוב זמני נוסף",
                f"{city} נוסף זמנית לרשימת ההתרעות.",
                QSystemTrayIcon.Information, 5000)

    def _update_temp_filter(self):
        """Notify AlertWorker of current temporary locations."""
        self.worker.update_temp_cities(self._temp_locations)

    # ── Alert ──────────────────────────────────────────────────
    def _on_alert(self, data):
        def _log_step(step):
            try:
                with open(os.path.join(os.environ.get("APPDATA","~"),"RedAlert","crash.log"),
                          "a", encoding="utf-8") as f:
                    f.write(f"[ALERT] {step}\n")
            except Exception: pass

        try:
            _log_step("start")
            a = Alert(data)
            # מנע כפילויות בהיסטוריה לפי ID
            if not any(h.id == a.id for h in self.history):
                self.history.appendleft(a)
                self._history_db.save(a)
            self.widget.add_alert(a)
            _log_step("widget updated")
            # ── Deduplicate by (cat, cities) — OREF changes IDs for the same ongoing alert ──
            _ui_key = (a.cat, frozenset(a.cities))
            _is_same_alert = (_ui_key == self._active_alert_key)
            if not _is_same_alert:
                self._active_alert_key = _ui_key
            # ── Telegram / Webhook (fire unconditionally, mute only affects UI) ──
            if not _is_same_alert:
                threading.Thread(target=self._send_telegram, args=(a,), daemon=True).start()
                threading.Thread(target=self._fire_webhook,  args=(a,), daemon=True).start()
            # ── Fall results worker — rockets/aircraft only ────────────────────
            if not _is_same_alert and a.cat in ("1","2","13"):
                # עצור workers ישנים לפני הפעלת חדש
                for old_fw in list(self._fall_workers):
                    old_fw.stop()
                fw = FallResultsWorker(a.cities, a.ts)
                fw.results_ready.connect(
                    lambda res, _a=a: self._show_fall_results(res, _a))
                fw.finished.connect(lambda: self._fall_workers.remove(fw)
                                    if fw in self._fall_workers else None)
                self._fall_workers.append(fw)
                fw.start()
            # ── עדכון מפה תמיד (גם אם אותה התרעה) ─────────────────────────
            my_locs = self.config.get("locations", [])
            self.map_win.update_alerts(a.map_markers(), my_locs, self._friends)
            _log_step("map updated")
            # ── אם אותה התרעה כבר פעילה — דלג על כל ה-UI ────────────────────
            if _is_same_alert:
                _log_step("same alert key — skipping UI re-trigger")
                return
            # ── Mute check ────────────────────────────────────────────────────
            if time.time() < self._mute_until:
                _log_step("muted — skipping UI")
                return
            # ── Dismiss / ack check — user closed this exact alert before ─────
            _akey = (a.cat, frozenset(a.cities))
            if _akey == self._ack_key:
                _log_step("ack — already dismissed, skipping UI")
                return
            alerted = set(a.cities)
            my_hit  = bool(my_locs and alerted.intersection(my_locs))
            friend_hit = any(f.get("city") in alerted for f in self._friends)
            if self.config.get("sound", True):
                fst = self.config.get("friend_sound_type","friend")
                self.sound.play(friend_in_area=friend_hit, friend_sound_type=fst)
            _log_step("sound triggered")
            # ── חלון מרחף ────────────────────────────────────────────
            ov_secs = self.config.get("overlay_timeout", 30)
            if ov_secs > 0:
                self._close_overlay()
                self._overlay = AlertOverlay(a, my_cities=my_locs, timeout=ov_secs)
                self._overlay.sig_open_fullscreen.connect(self._fullscreen)
                self._overlay.sig_dismissed.connect(
                    lambda _k=(a.cat, frozenset(a.cities)): self._on_alert_dismissed(_k))
                self._overlay.show()
            _log_step("overlay shown")
            # ── מסך מלא ────────────────────────────────────────────
            if self.config.get("auto_fullscreen", True) or my_hit:
                self._fullscreen()
            _log_step("fullscreen shown")
            if self.config.get("show_map", True):
                self._show_map()
                # מפה נסגרת אוטומטית אחרי 10 שניות
                QTimer.singleShot(10_000, self.map_win.hide)
            _log_step("map shown")
            extra = ""
            if a.origin: extra = f"\n{a.origin[0]} מקור: {a.origin[1]}"
            if friend_hit:
                names = [f["name"] for f in self._friends if f.get("city") in alerted]
                extra += f"\n🟢 {', '.join(names)} באזור!"
            if my_hit: extra = f"\n⚠ ישוב שלי מוזהר!{extra}"
            self._tray.showMessage(f"{a.icon}  {a.title}",
                                   "  |  ".join(a.cities[:5]) + extra,
                                   QSystemTrayIcon.Critical, 6000)
            # ── באנר כתום לחברים בהתרעה ────────────────────────
            if friend_hit and self.config.get("friend_alert_banner", True):
                f_names=[f["name"] for f in self._friends if f.get("city") in alerted]
                f_cities=[f["city"] for f in self._friends if f.get("city") in alerted]
                self._close_friend_banner()
                self._friend_banner=FriendAlertBanner(f_names, f_cities)
                self._friend_banner.show()
            _log_step("tray shown")
            # ── Record shelter end time ───────────────────────────────
            shelter_mins = a.info.get("shelter") if (hasattr(a,"info") and a.info) else None
            if not isinstance(shelter_mins, (int, float)):
                shelter_mins = 10
            self._shelter_end = time.time() + int(shelter_mins) * 60
            _log_step("done")
        except Exception:
            import traceback
            try:
                with open(os.path.join(os.environ.get("APPDATA","~"),"RedAlert","crash.log"),
                          "a", encoding="utf-8") as f:
                    f.write(f"\n_on_alert ERR {datetime.now().isoformat()}\n")
                    f.write(traceback.format_exc())
            except Exception: pass

    def _close_overlay(self):
        if self._overlay is not None:
            try: self._overlay.close()
            except RuntimeError: pass
            self._overlay = None

    def _on_alert_dismissed(self, key):
        """מופעל כשהמשתמש סוגר FullScreen/Overlay — מונע הצגה חוזרת לאותה התרעה."""
        self._ack_key = key
        # סגור גם את ה-overlay אם פתוח
        self._close_overlay()

    def _on_clear(self):
        # איפוס ה-ack כשהתרעה נפסקת
        self._ack_key = None
        self._active_alert_key = None
        try:
            # אם המסך המלא פתוח — מעבר לצבע ירוק
            if self._fs is not None:
                fs_list = self._fs if isinstance(self._fs, list) else [self._fs]
                for fs in fs_list:
                    try:
                        if fs.isVisible(): fs.go_green()
                    except RuntimeError:
                        pass
                # לא מאפסים _fs — הם ייסגרו לאחר 8 שניות לבד
            self._close_overlay()
            self.widget.clear_alerts()
            uc=self.config.get("locations",[])
            self.map_win.update_alerts([],uc,self._friends)
            # אם המשתמש הצהיר שהוא במרחב מוגן → שחרר את הבאנר
            if self._shelter_banner is not None:
                try:
                    self._shelter_banner.release()
                    self._shelter_banner = None
                except RuntimeError:
                    self._shelter_banner = None
        except Exception:
            import traceback
            try:
                with open(os.path.join(os.environ.get("APPDATA","~"),"RedAlert","crash.log"),
                          "a", encoding="utf-8") as f:
                    f.write(f"\n_on_clear ERR {datetime.now().isoformat()}\n")
                    f.write(traceback.format_exc())
            except Exception: pass


    # ── FullScreen — crash-safe ────────────────────────────────
    def _fullscreen(self):
        # Close existing instances (list or single)
        if self._fs is not None:
            fs_list = self._fs if isinstance(self._fs, list) else [self._fs]
            for fs in fs_list:
                try:
                    if fs.isVisible(): fs.close()
                except RuntimeError: pass
            self._fs = None
        timeout  = self.config.get("fullscreen_timeout", 15)
        active   = self.history[0] if self.history else None
        screens  = QApplication.screens()
        instances = []
        ack_key = (active.cat, frozenset(active.cities)) if active else None
        for screen in screens:
            fs = FullScreen(self.history, active, timeout=timeout, screen=screen)
            fs.sig_shelter_confirmed.connect(self._on_shelter_button)
            fs.destroyed.connect(self._on_fs_destroyed)
            if ack_key:
                fs.sig_dismissed.connect(
                    lambda _k=ack_key: self._on_alert_dismissed(_k))
            fs.show()
            instances.append(fs)
        self._fs = instances if len(instances) > 1 else (instances[0] if instances else None)

    def _on_fs_destroyed(self):
        if isinstance(self._fs, list):
            self._fs = [fs for fs in self._fs if fs is not None]
            if not self._fs: self._fs = None
        else:
            self._fs = None

    def _on_shelter_button(self):
        """נקרא כשמשתמש לחץ 'אני במרחב המוגן' — מציג את ה-ShelterMiniBanner."""
        self._close_shelter_banner()
        self._shelter_banner = ShelterMiniBanner()
        self._shelter_banner.show()

    def _close_shelter_banner(self):
        if self._shelter_banner is not None:
            try: self._shelter_banner.close()
            except RuntimeError: pass
            self._shelter_banner = None

    def _close_friend_banner(self):
        if self._friend_banner is not None:
            try: self._friend_banner.close()
            except RuntimeError: pass
            self._friend_banner = None

    # ── Map / History / Settings ───────────────────────────────
    def _show_map(self): self.map_win.show(); self.map_win.raise_()

    def _show_history(self):
        if self._history_win is None:
            self._history_win = HistoryWindow(self._history_db)
        self._history_win.show()
        self._history_win.raise_()

    def _open_google_sharing(self):
        """פותח גוגל מפות שיתוף מיקום — בדפדפן המוטמע אם זמין, אחרת בדפדפן ברירת מחדל."""
        if _HAS_WEB and self._google_browser:
            self._google_browser.open_for_login()
        else:
            import webbrowser
            webbrowser.open(GMAP_SHARE_URL)

    def _show_fall_results(self, results, alert):
        """מופעל ב-main thread בכל פעם שה-FallResultsWorker מוצא ידיעות חדשות."""
        if results:
            # שלח לטלגרם מיד
            threading.Thread(target=self._send_telegram_fall_results,
                             args=(results, alert), daemon=True).start()
            # עדכן חלון קיים או פתח חדש
            win = getattr(self, "_fall_result_win", None)
            if win is not None and win.isVisible():
                win.add_items(results)
            else:
                self._tray.showMessage(
                    "📰  עדכון חדשות",
                    f"נמצאו {len(results)} ידיעות רלוונטיות",
                    QSystemTrayIcon.Warning, 8000)
                win = FallResultsWindow(results, alert.cities, alert.title)
                win.show()
                self._fall_result_win = win
        else:
            # timeout — לא נמצא כלום לאחר 10 דקות
            threading.Thread(target=self._send_telegram_fall_results,
                             args=([], alert), daemon=True).start()
            self._tray.showMessage(
                "💥  תוצאות נפילה",
                "לא נמצאו עדכוני חדשות — בדוק בערוצי החדשות",
                QSystemTrayIcon.Information, 8000)
            win = getattr(self, "_fall_result_win", None)
            if win is None or not win.isVisible():
                win = FallResultsWindow([], alert.cities, alert.title)
                win.show()
                self._fall_result_win = win

    def _on_snooze(self, minutes: int):
        if minutes == 0:
            self._mute_until = 0.0
            self.widget.update_mute_icon(False)
            self._tray.setToolTip(f"{APP_NAME} — פעיל")
        else:
            self._mute_until = time.time() + minutes * 60
            self.widget.update_mute_icon(True)
            self._tray.setToolTip(f"{APP_NAME} — מושתק {minutes} ד׳")

    def _settings(self):
        d=SettingsDialog(self.config,self.widget)
        d.request_test.connect(self._test)
        d.request_full_test.connect(self._full_test)
        d.request_google_login.connect(self._google_login)
        d.request_google_logout.connect(self._google_logout)
        d.request_sound_dialog.connect(self._sound_dialog)
        d.request_telegram_dialog.connect(self._telegram_dialog)
        d.exec_()

    def _send_telegram_test(self):
        """שולח הודעת בדיקה לטלגרם בנפרד — נקרא יחד עם _test()."""
        if not self.config.get("telegram_enabled", False): return
        token   = self.config.get("telegram_token", "")
        chat_id = self.config.get("telegram_chat_id", "")
        if not token or not chat_id: return
        def _do():
            try:
                import urllib.request, urllib.parse
                from datetime import datetime
                msg = (
                    "🔔  <b>הודעת בדיקה — Red Alert Monitor</b>\n\n"
                    "🚀  סוג: ירי רקטות וטילים\n"
                    "🏙  ישובים: תל אביב מרכז | רמת גן | בני ברק\n"
                    f"🕐  שעה: {datetime.now().strftime('%H:%M:%S')}\n\n"
                    "✅  החיבור לטלגרם תקין!"
                )
                params = urllib.parse.urlencode({
                    "chat_id": chat_id, "text": msg, "parse_mode": "HTML"
                })
                url = f"https://api.telegram.org/bot{token}/sendMessage?{params}"
                urllib.request.urlopen(url, timeout=6)
            except Exception: pass
        threading.Thread(target=_do, daemon=True).start()

    def _telegram_dialog(self):
        TelegramDialog(self.config, self.widget).exec_()

    # ── Telegram & Webhook ─────────────────────────────────────
    def _send_telegram(self, alert):
        if not self.config.get("telegram_enabled", False): return
        token   = self.config.get("telegram_token", "")
        chat_id = self.config.get("telegram_chat_id", "")
        if not token or not chat_id: return
        try:
            import urllib.request, urllib.parse
            cities_str = "  |  ".join(alert.cities[:8])
            msg = (f"{alert.icon}  <b>{alert.title}</b>\n"
                   f"🏙  {cities_str}\n"
                   f"🕐  {alert.ts.strftime('%H:%M:%S')}")
            params = urllib.parse.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            url = f"https://api.telegram.org/bot{token}/sendMessage?{params}"
            urllib.request.urlopen(url, timeout=6)
        except Exception: pass

    def _send_telegram_fall_results(self, results, alert):
        """שולח לטלגרם עדכון חדשות לאחר ההתרעה (מופעל מ-_show_fall_results)."""
        if not self.config.get("telegram_enabled", False): return
        token   = self.config.get("telegram_token", "")
        chat_id = self.config.get("telegram_chat_id", "")
        if not token or not chat_id: return
        try:
            import urllib.request, urllib.parse
            cities_str = "  |  ".join(alert.cities[:6])
            if results:
                lines = [f"📰  <b>עדכון חדשות — {alert.title}</b>",
                         f"🏙  {cities_str}",
                         f"🕐  {alert.ts.strftime('%H:%M:%S')}",
                         ""]
                for item in results[:5]:
                    title = item.get("title", "")
                    link  = item.get("link", "")
                    lines.append(f"• <b>{title}</b>")
                    if link:
                        lines.append(f"  🔗 {link}")
                msg = "\n".join(lines)
            else:
                msg = (f"📰  <b>עדכון חדשות — {alert.title}</b>\n"
                       f"🏙  {cities_str}\n"
                       f"🕐  {alert.ts.strftime('%H:%M:%S')}\n\n"
                       f"⏳  לא נמצאו עדכוני חדשות רלוונטיים")
            params = urllib.parse.urlencode({"chat_id": chat_id, "text": msg,
                                             "parse_mode": "HTML",
                                             "disable_web_page_preview": "true"})
            url = f"https://api.telegram.org/bot{token}/sendMessage?{params}"
            urllib.request.urlopen(url, timeout=6)
        except Exception: pass

    def _fire_webhook(self, alert):
        if not self.config.get("webhook_enabled", False): return
        url = self.config.get("webhook_url", "")
        if not url: return
        try:
            import urllib.request
            payload = json.dumps({
                "title":   alert.title,
                "cities":  alert.cities,
                "cat":     alert.cat,
                "ts":      alert.ts.isoformat(),
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type":"application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=6)
        except Exception: pass

    def _sound_dialog(self): SoundDialog(self.config,self.sound,self.widget).exec_()

    # ── Google ─────────────────────────────────────────────────
    def _google_login(self):
        if _HAS_WEB and self._google_browser:
            # פותח דפדפן מוטמע — המשתמש מתחבר רגיל, הכל אוטומטי
            self._google_browser.open_for_login()
        else:
            # Fallback: הדרך הישנה עם DevTools
            dlg = GoogleAuthDialog(self.widget)
            dlg.login_success.connect(self._on_google_login)
            dlg.exec_()

    def _on_google_login(self, cookies, name):
        """Fallback path (no WebEngine): manual SAPISID paste."""
        self.config.set("google_user", name or "Google User")
        self.config.set("google_cookies", cookies)
        self._start_loc_worker(cookies)
        QMessageBox.information(self.widget, "שיתוף מיקום גוגל",
            "✅ מחובר!\n\nהמערכת תעדכן את מיקום האנשים שחולקים איתך\nמיקום בגוגל כל 30 שניות.")

    def _on_google_login_browser(self, cookies, name):
        """נקרא אוטומטית כשנמצא SAPISID בדפדפן המוטמע."""
        if not cookies.get("SAPISID"):
            return
        self.config.set("google_user", name or "Google User")
        self.config.set("google_cookies", cookies)
        self._start_loc_worker(cookies)

    def _google_logout(self):
        self._stop_loc_worker()
        self.config.set("google_user", None)
        self.config.set("google_cookies", None)
        self._friends = []
        self.map_win.update_friends([])
        self.worker.update_friend_cities([])
        if self._google_browser:
            self._google_browser.clear_session()

    def _start_loc_worker(self,cookies):
        self._stop_loc_worker()
        self._loc_worker=LocationSharingWorker(cookies)
        self._loc_worker.locations_updated.connect(self._on_locs)
        self._loc_worker.auth_failed.connect(self._on_loc_fail)
        self._loc_worker.start()

    def _stop_loc_worker(self):
        if self._loc_worker: self._loc_worker.stop(); self._loc_worker=None

    def _on_locs(self,people):
        self._friends=people; self.map_win.update_friends(people)
        self.worker.update_friend_cities([p["city"] for p in people if p.get("city")])
        # ── פעם אחת בסשן: הצע להוסיף ישובי חברים לרשימת ההתרעות ──
        if not self._shown_friend_loc_dlg and people:
            friends_with_city=[p for p in people if p.get("city")]
            if friends_with_city:
                self._shown_friend_loc_dlg=True
                QTimer.singleShot(1200, lambda: self._show_friend_locs_dlg(friends_with_city))

    def _show_friend_locs_dlg(self, friends_with_city):
        """מציג דיאלוג להוספת ישובי חברים — נקרא מ-QTimer."""
        try:
            dlg=FriendLocationsDialog(friends_with_city, self.config, self.widget)
            dlg.exec_()
            # אם הוסיפו ישובים חדשים → עדכן מפה ו-worker
            if self.config.get("locations",[]):
                self._init_map()
                self.worker.update_friend_cities(
                    [p["city"] for p in self._friends if p.get("city")])
        except Exception:
            pass

    def _on_loc_fail(self):
        self._google_logout()
        self._tray.showMessage("שיתוף מיקום גוגל",
            "פג תוקף — יש להתחבר מחדש מההגדרות.",QSystemTrayIcon.Warning,5000)

    # ── Test / Exit ────────────────────────────────────────────
    def _test(self):
        self._on_alert({"id":f"T{int(time.time())}","cat":"1",
                        "title":"ירי רקטות וטילים",
                        "data":["תל אביב - מרכז העיר","רמת גן","בני ברק","חולון","גבעתיים"]})
        self._send_telegram_test()

    def _full_test(self):
        """בדיקה מקיפה: מסכים + טלגרם + דיווח תוצאות בחלון."""
        from PyQt5.QtWidgets import QMessageBox
        results = []

        # ── 1. אפס keys כדי לאלץ תצוגת מסכים מחדש ──────────────────
        self._active_alert_key = None
        self._ack_key          = None

        # ── 2. הפעל מסך מלא + overlay ────────────────────────────────
        try:
            self._on_alert({"id": f"FT{int(time.time())}", "cat": "1",
                            "title": "ירי רקטות וטילים",
                            "data": ["תל אביב - מרכז העיר", "רמת גן",
                                     "בני ברק", "חולון", "גבעתיים"]})
            results.append("✅  מסך מלא + Overlay הוקפצו")
        except Exception as e:
            results.append(f"❌  מסכים: {e}")

        # ── 3. שלח לטלגרם ישירות (ללא תלות ב-telegram_enabled) ───────
        token   = self.config.get("telegram_token",  "")
        chat_id = self.config.get("telegram_chat_id","")

        if not token:
            results.append("⚠️  טלגרם: חסר Bot Token — הגדר בהגדרות טלגרם")
        elif not chat_id:
            results.append("⚠️  טלגרם: חסר Chat ID — לחץ 'זהה אוטומטית' בהגדרות טלגרם")
        else:
            try:
                import urllib.request, urllib.parse
                from datetime import datetime
                msg = (
                    "🧪  <b>בדיקה מקיפה — Red Alert Monitor v5</b>\n\n"
                    "🚀  ירי רקטות וטילים\n"
                    "🏙  תל אביב | רמת גן | בני ברק | חולון | גבעתיים\n"
                    f"🕐  {datetime.now().strftime('%H:%M:%S')}\n\n"
                    "✅  כל המערכות תקינות!"
                )
                params = urllib.parse.urlencode({
                    "chat_id": chat_id, "text": msg, "parse_mode": "HTML"
                })
                url = f"https://api.telegram.org/bot{token}/sendMessage?{params}"
                with urllib.request.urlopen(url, timeout=8): pass
                results.append("✅  טלגרם: הודעה נשלחה בהצלחה!")
            except Exception as e:
                results.append(f"❌  טלגרם: {e}")

        # ── 4. הצג תוצאות ─────────────────────────────────────────────
        all_ok = all(r.startswith("✅") for r in results)
        icon   = QMessageBox.Information if all_ok else QMessageBox.Warning
        dlg    = QMessageBox(icon,
                             "תוצאות בדיקה מקיפה ✅" if all_ok else "תוצאות בדיקה מקיפה ⚠️",
                             "\n".join(results))
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.exec_()

    def _exit(self):
        self.worker.stop(); self._stop_loc_worker()
        if self._loc_track: self._loc_track.stop()
        self._close_overlay(); self._close_shelter_banner(); self._close_friend_banner()
        for fw in list(self._fall_workers):
            try: fw.quit(); fw.wait(500)
            except Exception: pass
        self._history_db.close()
        self.quit()


if __name__ == "__main__":
    # ── Auto-restart on crash ─────────────────────────────────────
    import traceback as _tb
    import faulthandler as _fh

    _CRASH_LOG = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "RedAlert", "crash.log"
    )

    # Enable faulthandler — writes C++ / segfault stack traces to crash.log
    os.makedirs(os.path.dirname(_CRASH_LOG), exist_ok=True)
    try:
        _fh_file = open(_CRASH_LOG + ".flt", "w", encoding="utf-8")
        _fh.enable(file=_fh_file)
    except Exception:
        pass

    # Catch unhandled Python exceptions in Qt slots (printed to stderr by PyQt5)
    def _excepthook(exc_type, exc_value, exc_tb):
        try:
            os.makedirs(os.path.dirname(_CRASH_LOG), exist_ok=True)
            with open(_CRASH_LOG, "a", encoding="utf-8") as fh:
                fh.write(f"\n{'='*60}\nUNHANDLED  {datetime.now().isoformat()}\n")
                fh.write("".join(_tb.format_exception(exc_type, exc_value, exc_tb)))
        except Exception:
            pass
    import sys as _sys
    _sys.excepthook = _excepthook

    def _run_once():
        """Launch the Qt app and return its exit code."""
        app = RedAlertApp()
        return app.exec_()

    def _relaunch():
        """Relaunch this process and exit the current one."""
        if getattr(sys, "frozen", False):
            # Running as a PyInstaller EXE
            exe = sys.executable
            subprocess.Popen([exe] + sys.argv[1:])
        else:
            # Running as a plain Python script
            subprocess.Popen([sys.executable, os.path.abspath(__file__)] + sys.argv[1:])
        sys.exit(0)

    def _log_crash(exc: Exception):
        os.makedirs(os.path.dirname(_CRASH_LOG), exist_ok=True)
        with open(_CRASH_LOG, "a", encoding="utf-8") as fh:
            fh.write(f"\n{'='*60}\n")
            fh.write(f"CRASH  {datetime.now().isoformat()}\n")
            fh.write(_tb.format_exc())
            fh.write("\n")

    _MAX_RESTARTS = 10          # safety cap – don't loop forever on fatal crashes
    _restart_count = 0

    while _restart_count < _MAX_RESTARTS:
        try:
            code = _run_once()
            if code == 0:
                # Clean exit (user chose "Exit" from tray)
                sys.exit(0)
            # Non-zero exit (e.g. Qt returned 1) – treat as crash, restart
            _log_crash(RuntimeError(f"Qt exited with code {code}"))
        except SystemExit as e:
            if e.code == 0:
                sys.exit(0)
            _log_crash(e)
        except Exception as e:
            _log_crash(e)

        _restart_count += 1
        # Brief pause before restarting so we don't spin on instant crashes
        time.sleep(2)
        _relaunch()   # relaunch as separate process; exits current process

    # If we exhausted retries, just exit
    sys.exit(1)
