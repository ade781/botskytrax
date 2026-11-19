"""
Mock Server untuk Pengujian Lokal Bot Skytrax Survey
Mensimulasikan endpoint Skytrax (admin.php) secara lokal tanpa mengirimkan
request otomatis ke server publik.
"""

import http.server
import json
import threading
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Set
import uuid


class MockSurveyHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Handler HTTP untuk mensimulasikan respons admin.php Skytrax."""

    # Rekaman request yang masuk untuk inspeksi/verifikasi pengujian
    received_submissions: List[Dict[str, str]] = []
    auto_id_counter: int = 1000
    lock = threading.Lock()

    # Flag pengujian untuk simulasi error jika diperlukan
    simulate_error_on_emails: Set[str] = set()

    def log_message(self, format, *args):
        # Mute logging default server agar tidak mengotori output CLI
        return

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        # Endpoint CSRF Token: /Surveys/Airport/admin.php?method=csrfToken
        if "method" in params and params["method"][0] == "csrfToken":
            token = f"mock_csrf_{uuid.uuid4().hex[:16]}"
            session_id = f"mock_phpsessid_{uuid.uuid4().hex[:24]}"

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Set-Cookie", f"PHPSESSID={session_id}; Path=/; HttpOnly")
            self.end_headers()

            response_data = {"csrf_token": token}
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Endpoint not found in mock server")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length).decode("utf-8")
        form_dict = {
            k: v[0] for k, v in urllib.parse.parse_qs(post_body, keep_blank_values=True).items()
        }

        # Cek simulasi error untuk testing kegagalan individual
        email = form_dict.get("f2", "")
        if "simulate_error" in email.lower() or email in MockSurveyHTTPHandler.simulate_error_on_emails:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Simulated Internal Server Error"}).encode("utf-8"))
            return

        if "simulate_invalid_json" in email.lower():
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>Fatal Error: DB connection failed</html>")
            return

        if "simulate_validation_fail" in email.lower():
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "validated": False,
                "error": "Simulated Form Validation Rejected"
            }).encode("utf-8"))
            return

        with MockSurveyHTTPHandler.lock:
            MockSurveyHTTPHandler.auto_id_counter += 1
            current_id = MockSurveyHTTPHandler.auto_id_counter
            MockSurveyHTTPHandler.received_submissions.append(form_dict)

        now = datetime.now()
        response_payload = {
            "validated": True,
            "fieldValues": {
                "AutoID": f"MOCK-{current_id}",
                "Date": now.strftime("%d/%m/%Y"),
                "Time": now.strftime("%H:%M:%S"),
                "f2": email
            }
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(response_payload).encode("utf-8"))


class MockSurveyServer:
    """Wrapper untuk menjalankan Mock Survey Server secara aman di thread latar belakang."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        # port=0 memilih port bebas otomatis yang dialokasikan oleh OS
        self.server = http.server.ThreadingHTTPServer((host, port), MockSurveyHTTPHandler)
        addr = self.server.server_address
        self.host: str = str(addr[0])
        self.port: int = int(addr[1])
        self.thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def csrf_url(self) -> str:
        return f"{self.base_url}/Surveys/Airport/admin.php?method=csrfToken"

    @property
    def submit_url(self) -> str:
        return f"{self.base_url}/Surveys/Airport/admin.php"

    def start(self):
        MockSurveyHTTPHandler.received_submissions.clear()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
