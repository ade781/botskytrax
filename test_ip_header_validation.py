"""
Skrip Pengujian & Simulasi Validasi Header IP (Localhost Security Audit)

Fitur:
1. Menjalankan server lokal sementara (Mock Backend) dalam 2 konfigurasi:
   - Konfigurasi RENTAN (mempercayai header HTTP secara langsung tanpa validasi proxy)
   - Konfigurasi AMAN (hanya mempercayai header proxy jika REMOTE_ADDR berasal dari Trusted Proxy)
2. Menjalankan 4 Skenario Pengujian (Skenario A, B, C, D) menggunakan IP Dokumentasi RFC 5737:
   - Skenario A: Default Request (Tanpa Header IP tambahan)
   - Skenario B: Header X-Forwarded-For (192.0.2.10)
   - Skenario C: Header X-Real-IP (198.51.100.10)
   - Skenario D: Header CF-Connecting-IP (203.0.113.10)
3. Mode Server Interaktif (--serve) di http://localhost:8000/api/ip-inspect untuk diuji via Postman.
"""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import requests

# Batasan keamanan: Hanya izinkan pengujian ke host lokal
ALLOWED_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Daftar IP Dokumentasi (RFC 5737) untuk pengujian
DOC_IP_XFF = "192.0.2.10"       # TEST-NET-1
DOC_IP_REAL = "198.51.100.10"   # TEST-NET-2
DOC_IP_CF = "203.0.113.10"      # TEST-NET-3


def is_valid_ip(ip_str: str) -> bool:
    """Memeriksa apakah string merupakan format alamat IPv4/IPv6 yang valid."""
    try:
        ipaddress.ip_address(ip_str.strip())
        return True
    except ValueError:
        return False


def resolve_client_ip(
    remote_addr: str,
    headers: Dict[str, str],
    trusted_proxies: List[str],
    enforce_proxy_trust: bool = True
) -> Tuple[str, str]:
    """
    Menentukan alamat IP klien berdasarkan konfigurasi kepercayaan proxy.
    Mengembalikan tuple: (resolved_ip, source_used)
    """
    # Normalisasi nama header ke huruf kecil
    norm_headers = {k.lower(): v for k, v in headers.items()}

    # Jika mode aman aktif, periksa apakah koneksi TCP langsung berasal dari Trusted Proxy
    if enforce_proxy_trust and remote_addr not in trusted_proxies:
        return remote_addr, "REMOTE_ADDR (Untrusted proxy headers ignored)"

    # Prioritas pembacaan header jika berasal dari Trusted Proxy (atau saat simulasi mode rentan)
    cf_ip = norm_headers.get("cf-connecting-ip")
    if cf_ip and is_valid_ip(cf_ip):
        return cf_ip.strip(), "Header: CF-Connecting-IP"

    x_real_ip = norm_headers.get("x-real-ip")
    if x_real_ip and is_valid_ip(x_real_ip):
        return x_real_ip.strip(), "Header: X-Real-IP"

    xff = norm_headers.get("x-forwarded-for")
    if xff:
        # Evaluasi dari kanan ke kiri untuk mengambil IP non-proxy terdekat
        ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
        for candidate in reversed(ips):
            if candidate not in trusted_proxies and is_valid_ip(candidate):
                return candidate, "Header: X-Forwarded-For"

    return remote_addr, "REMOTE_ADDR (Default)"


class IPInspectRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler lokal untuk menginspeksi cara backend membaca IP."""

    # Konfigurasi kelas yang dapat diubah saat pengujian
    enforce_proxy_trust: bool = True
    # Kosong secara default agar request langsung dari 127.0.0.1 dianggap klien langsung (bukan proxy)
    trusted_proxies: List[str] = []

    def log_message(self, format: str, *args: Any) -> None:
        """Menonaktifkan log standar per request agar tabel output tetap rapi."""
        pass

    def _send_json_Info(self) -> None:
        remote_addr = self.client_address[0]
        headers_dict = {k: v for k, v in self.headers.items()}

        content_length = int(self.headers.get("Content-Length", 0))
        body_raw = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body_json = json.loads(body_raw)
        except Exception:
            body_json = {}

        resolved_ip, resolution_source = resolve_client_ip(
            remote_addr=remote_addr,
            headers=headers_dict,
            trusted_proxies=self.trusted_proxies,
            enforce_proxy_trust=self.enforce_proxy_trust,
        )

        response_payload = {
            "scenario": body_json.get("scenario", "UNKNOWN"),
            "security_mode": "SECURE (Trusted Proxy Check)" if self.enforce_proxy_trust else "VULNERABLE (Blind Header Trust)",
            "socket_remote_addr": remote_addr,
            "resolved_client_ip": resolved_ip,
            "resolution_source": resolution_source,
            "received_ip_headers": {
                "X-Forwarded-For": self.headers.get("X-Forwarded-For"),
                "X-Real-IP": self.headers.get("X-Real-IP"),
                "CF-Connecting-IP": self.headers.get("CF-Connecting-IP"),
            },
        }

        body_bytes = json.dumps(response_payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self) -> None:
        self._send_json_Info()

    def do_POST(self) -> None:
        self._send_json_Info()


def validate_local_target(url: str) -> None:
    """Memastikan URL target hanya mengarah ke localhost / 127.0.0.1."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_LOCAL_HOSTS:
        raise ValueError(
            f"Pelanggaran Batasan Keamanan: Target '{hostname}' ditolak. "
            f"Skrip ini hanya mengizinkan pengujian ke {ALLOWED_LOCAL_HOSTS}."
        )


def run_test_scenarios(base_url: str) -> List[Dict[str, Any]]:
    """Menjalankan Skenario A, B, C, dan D terhadap endpoint lokal."""
    validate_local_target(base_url)
    endpoint = f"{base_url.rstrip('/')}/api/ip-inspect"

    scenarios = [
        {
            "id": "Skenario A",
            "name": "Default Request (Tanpa Header)",
            "headers": {},
            "expected_header_ip": "-",
        },
        {
            "id": "Skenario B",
            "name": "X-Forwarded-For",
            "headers": {"X-Forwarded-For": DOC_IP_XFF},
            "expected_header_ip": DOC_IP_XFF,
        },
        {
            "id": "Skenario C",
            "name": "X-Real-IP",
            "headers": {"X-Real-IP": DOC_IP_REAL},
            "expected_header_ip": DOC_IP_REAL,
        },
        {
            "id": "Skenario D",
            "name": "CF-Connecting-IP",
            "headers": {"CF-Connecting-IP": DOC_IP_CF},
            "expected_header_ip": DOC_IP_CF,
        },
    ]

    results = []
    for sc in scenarios:
        req_headers = {"Content-Type": "application/json"}
        req_headers.update(sc["headers"])
        res = requests.post(
            endpoint,
            headers=req_headers,
            json={"scenario": sc["id"]},
            timeout=5,
        )
        data = res.json()
        results.append({
            "id": sc["id"],
            "name": sc["name"],
            "header_sent": sc["expected_header_ip"],
            "socket_ip": data["socket_remote_addr"],
            "resolved_ip": data["resolved_client_ip"],
            "source": data["resolution_source"],
        })
    return results


def run_automated_comparison() -> None:
    """Menjalankan pengujian otomatis pada mode RENTAN vs mode AMAN di server lokal."""
    server = HTTPServer(("127.0.0.1", 0), IPInspectRequestHandler)
    port = server.server_port
    base_url = f"http://127.0.0.1:{port}"

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        # 1. Uji saat konfigurasi backend RENTAN (tidak memvalidasi asal proxy)
        IPInspectRequestHandler.enforce_proxy_trust = False
        IPInspectRequestHandler.trusted_proxies = []
        vuln_results = run_test_scenarios(base_url)

        # 2. Uji saat konfigurasi backend AMAN (hanya mempercayai daftar trusted_proxies)
        IPInspectRequestHandler.enforce_proxy_trust = True
        IPInspectRequestHandler.trusted_proxies = ["10.0.0.1"]  # 127.0.0.1 dianggap klien langsung
        secure_results = run_test_scenarios(base_url)

        print("=" * 96)
        print(" HASIL PENGUJIAN VALIDASI HEADER IP (LOCALHOST SIMULATION)")
        print("=" * 96)
        header_fmt = "{:<12} | {:<26} | {:<15} | {:<14} | {:<14} | {:<10}"
        print(header_fmt.format(
            "Skenario", "Header Dikirim", "IP Koneksi TCP", "Backend Rentan", "Backend Aman", "Status"
        ))
        print("-" * 96)

        for v_row, s_row in zip(vuln_results, secure_results):
            is_protected = s_row["resolved_ip"] == s_row["socket_ip"]
            status_str = "AMAN (PASS)" if is_protected else "RENTAN"
            header_desc = f"{v_row['name']}" if v_row["header_sent"] == "-" else f"{v_row['name']}: {v_row['header_sent']}"
            print(header_fmt.format(
                v_row["id"],
                header_desc[:26],
                s_row["socket_ip"],
                v_row["resolved_ip"],
                s_row["resolved_ip"],
                status_str,
            ))

        print("=" * 96)
        print("\nKesimpulan:")
        print("1. Pada Backend Rentan : Nilai header HTTP langsung menggantikan IP klien tanpa validasi.")
        print("2. Pada Backend Aman   : Header HTTP dari koneksi tak tepercaya diabaikan; tetap memakai IP TCP (127.0.0.1).")
        print("\nTip: Jalankan `python test_ip_header_validation.py --serve` untuk menguji endpoint ini langsung dari Postman.")

    finally:
        server.shutdown()
        server.server_close()


def run_interactive_server(port: int = 8000, vulnerable_mode: bool = False) -> None:
    """Menjalankan server lokal di port 8000 untuk pengujian manual menggunakan Postman."""
    IPInspectRequestHandler.enforce_proxy_trust = not vulnerable_mode
    IPInspectRequestHandler.trusted_proxies = ["10.0.0.1"]

    server = HTTPServer(("127.0.0.1", port), IPInspectRequestHandler)
    mode_str = "VULNERABLE (Menerima semua header)" if vulnerable_mode else "SECURE (Mengabaikan header tanpa trusted proxy)"
    print("=" * 65)
    print(f" LOCAL IP INSPECT SERVER AKTIF DI: http://localhost:{port}/api/ip-inspect")
    print(f" Mode Keamanan : {mode_str}")
    print(" Tekan Ctrl+C untuk menghentikan server.")
    print("=" * 65)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Menghentikan server lokal...")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Skrip Pengujian Validasi Header IP pada Localhost")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Jalankan server lokal di http://localhost:8000/api/ip-inspect untuk diuji dari Postman",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port untuk server lokal (default: 8000)",
    )
    parser.add_argument(
        "--vulnerable",
        action="store_true",
        help="Gunakan bersama --serve untuk mensimulasikan backend yang rentan terhadap manipulasi header",
    )
    args = parser.parse_args()

    if args.serve:
        run_interactive_server(port=args.port, vulnerable_mode=args.vulnerable)
    else:
        run_automated_comparison()
