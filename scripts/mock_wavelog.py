"""Mini-Wavelog (API v2) zum Ausprobieren ohne echte Instanz.

Start: python scripts/mock_wavelog.py 8099 -> im Programm Adresse
http://127.0.0.1:8099, API-Key wl2_demo. Speichert nichts.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

TOKEN = "wl2_demo"
STATIONS = [
    {
        "id": 1,
        "name": "Heimstation",
        "callsign": "DL0QSL",
        "gridsquare": "JO62QM",
        "cq": 14,
        "itu": 28,
        "active": True,
    },
    {
        "id": 2,
        "name": "Portabel Harz",
        "callsign": "DL0QSL/P",
        "gridsquare": "JO51HS",
        "cq": 14,
        "itu": 28,
        "active": False,
    },
]
CALLS = [
    "EA8ABC",
    "JA1XYZ",
    "VK2DEF",
    "W1AW",
    "OH2GHI",
    "ZS6JKL",
    "PY2MNO",
    "VE3PQR",
    "G4STU",
    "I2VWX",
    "SP5ABC",
    "OK1DEF",
]
MODES = [
    ("SSB", None, 14230000, "59"),
    ("CW", None, 7025000, "599"),
    ("MFSK", "FT8", 14074000, "-12"),
    ("SSB", None, 21300000, "57"),
]
QSOS = []
for i, call in enumerate(CALLS * 2):
    m = MODES[i % 4]
    QSOS.append(
        {
            "id": 4000 + i,
            "station_id": 1 if i % 5 else 2,
            "call": call,
            "band": ["20m", "40m", "20m", "15m"][i % 4],
            "mode": m[0],
            "submode": m[1],
            "freq": m[2],
            "qso_date": f"2026-10-{1+i%28:02d} {8+i%12:02d}:{(i*7)%60:02d}:00",
            "rst_sent": m[3],
            "rst_rcvd": m[3],
            "qsl_sent": "Y" if i % 7 == 0 else "N",
        }
    )
PATCHES = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=None):
        data = b"" if body is None else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._send(401, {"error": {"code": "unauthorized", "message": "invalid token"}})
            return False
        return True

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._auth():
            return
        if u.path == "/index.php/api/v2/station":
            return self._send(200, {"data": STATIONS, "meta": {}})
        if u.path == "/index.php/api/v2/qso":
            sid = int(q.get("station_id", ["0"])[0])
            per = int(q.get("per_page", ["50"])[0])
            page = int(q.get("page", ["1"])[0])
            rows = [r for r in QSOS if r["station_id"] == sid]
            chunk = rows[(page - 1) * per : page * per]
            return self._send(
                200,
                {
                    "data": chunk,
                    "meta": {
                        "page": page,
                        "per_page": per,
                        "count": len(chunk),
                        "total": len(rows),
                        "has_more": page * per < len(rows),
                    },
                },
            )
        self._send(404, {"error": {"code": "not_found"}})

    def do_PATCH(self):
        if not self._auth():
            return
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        qid = int(u.path.rsplit("/", 1)[-1])
        for r in QSOS:
            if r["id"] == qid:
                r.update(body)
                PATCHES.append((qid, body))
                return self._send(200, {"data": r})
        self._send(404, {"error": {"code": "not_found"}})


def start(port=0):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    start(int(sys.argv[1]))
    threading.Event().wait()
