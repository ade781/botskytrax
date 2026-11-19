"""
Module Bot Skytrax Survey Submitter & Batch Processor
Mendukung pengiriman survei tunggal dan pemrosesan batch data email dinamis
dengan validasi, logging terstruktur, penanganan error per item, serta integrasi mock server.
"""

import argparse
import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

# Integrasi modular dengan generator email & mock server
from email_generator import (
    generate_dynamic_emails,
    validate_email_format,
    filter_and_deduplicate_emails,
    load_emails_from_file,
)
from mock_server import MockSurveyServer

# Konfigurasi Logging
logger = logging.getLogger("SkytraxSurvey")


def setup_logger(log_to_file: bool = True, log_filename: str = "batch_survey.log", verbose: bool = True):
    """Mengatur konfigurasi logger untuk konsol dan file."""
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if verbose:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_to_file:
        file_handler = logging.FileHandler(log_filename, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


# ==========================================================
# KONFIGURASI UTAMA (Dapat disesuaikan langsung di sini)
# ==========================================================
BATCH_COUNT = 100              # Jumlah email dinamis yang dibuat (ade1asli@ s/d ade100asli@)
USE_MOCK_SERVER = True         # True: Uji pada Mock Server lokal (aman & cepat)
                               # False: Kirim ke server publik Skytrax
DELAY_BETWEEN_REQUESTS = 0.0   # Jeda antar request dalam detik (misal: 0.2 atau 1.0)
DEFAULT_EMAIL_SINGLE = "ade7@Gmail.com"

# Nilai Default
DEFAULT_BASE_URL = "https://www.worldairportsurvey.com"
DEFAULT_CSRF_PATH = "/Surveys/Airport/admin.php?method=csrfToken"
DEFAULT_SUBMIT_PATH = "/Surveys/Airport/admin.php"

SERVER_VALIDATION_FIELDS = (
    "f5,f31,f32,f6,f15,f16,f18,f20,f21,f22,f23,f24,f25,f27,"
    "f34,f35,f36,f37,f38,f39,f40,f41,f42,f43,f45,f47,f48,f49,"
    "f50,f51,f52,f53,f33,f28,f2"
)


def get_default_headers(base_url: str = DEFAULT_BASE_URL) -> Dict[str, str]:
    """Membentuk header HTTP standar untuk request survei."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Origin": base_url,
        "Referer": f"{base_url}/Surveys/Airport/form.html",
        "X-Requested-With": "XMLHttpRequest",
    }


def fetch_csrf_token(
    session: requests.Session,
    csrf_url: str,
    headers: Dict[str, str],
    timeout: int = 15
) -> Tuple[str, str]:
    """
    Mengambil CSRF token dan cookie session dari server.

    Returns:
        Tuple[str, str]: (csrf_token, phpsessid)
    Raises:
        RuntimeError: Jika gagal mengambil token atau respons tidak valid.
    """
    res_csrf = session.get(csrf_url, headers=headers, timeout=timeout)
    if res_csrf.status_code != 200:
        raise RuntimeError(f"Gagal mengambil token. HTTP Status: {res_csrf.status_code}")

    try:
        csrf_data = res_csrf.json()
        csrf_token = csrf_data.get("csrf_token")
        if not csrf_token:
            raise ValueError("Kunci 'csrf_token' tidak ditemukan pada respons JSON.")
    except Exception as e:
        raise RuntimeError(f"Gagal membaca JSON token: {e}. Raw: {res_csrf.text[:100]}")

    phpsessid = session.cookies.get("PHPSESSID", "")
    return csrf_token, phpsessid


def build_form_payload(
    csrf_token: str,
    email: str,
    custom_fields: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """
    Menyusun payload form data survei secara dinamis dengan email yang ditentukan.
    """
    payload = {
        "method": "validateForm",
        "serverValidationFields": SERVER_VALIDATION_FIELDS,
        "csrf_token": csrf_token,
        "f5": "Soekarno-Hatta International Airport",
        "f31": "Great hospitality, clean terminals, and smooth immigration process",
        "f32": "Depart",
        "f6": "1_2_month",
        "f15": "5",
        "f16": "5",
        "f18": "5",
        "f20": "5",
        "f21": "5",
        "f22": "5",
        "f23": "5",
        "f24": "5",
        "f25": "5",
        "f27": "5",
        "f34": "5",
        "f35": "5",
        "f36": "5",
        "f37": "5",
        "f38": "5",
        "f39": "5",
        "f40": "5",
        "f41": "5",
        "f42": "5",
        "f43": "5",
        "f44": "5",
        "f45": "5",
        "f46": "5",
        "f47": "5",
        "f48": "5",
        "f49": "5",
        "f50": "5",
        "f51": "5",
        "f52": "5",
        "f53": "5",
        "f54": "5",
        "f33": "Indonesia",
        "f28": "I confirm that I agree to the Terms and Conditions",
        "f2": email
    }

    if custom_fields:
        payload.update(custom_fields)

    return payload


def submit_single_survey_request(
    email: str,
    base_url: str = DEFAULT_BASE_URL,
    session: Optional[requests.Session] = None,
    headers: Optional[Dict[str, str]] = None,
    custom_fields: Optional[Dict[str, str]] = None,
    timeout: int = 15
) -> Dict[str, Any]:
    """
    Eksekusi 1 pengiriman survei (ambil CSRF token -> kirim payload form -> tangani respons).

    Returns:
        Dict[str, Any]: Hasil pengiriman mencakup status, auto_id, date, time, dan data respons.
    """
    if not validate_email_format(email):
        return {
            "success": False,
            "status": "INVALID_FORMAT",
            "email": email,
            "error": "Format email tidak valid."
        }

    sess = session if session is not None else requests.Session()
    req_headers = headers if headers is not None else get_default_headers(base_url)

    csrf_url = f"{base_url.rstrip('/')}{DEFAULT_CSRF_PATH}"
    submit_url = f"{base_url.rstrip('/')}{DEFAULT_SUBMIT_PATH}"

    try:
        csrf_token, phpsessid = fetch_csrf_token(sess, csrf_url, req_headers, timeout=timeout)
        form_data = build_form_payload(csrf_token, email, custom_fields)

        res_submit = sess.post(submit_url, headers=req_headers, data=form_data, timeout=timeout)

        if res_submit.status_code != 200:
            return {
                "success": False,
                "status": "HTTP_ERROR",
                "email": email,
                "status_code": res_submit.status_code,
                "error": f"Server merespons HTTP {res_submit.status_code}"
            }

        try:
            result_json = res_submit.json()
        except Exception:
            return {
                "success": False,
                "status": "INVALID_JSON_RESPONSE",
                "email": email,
                "error": f"Respons bukan JSON valid: {res_submit.text[:100]}"
            }

        if result_json.get("validated") is True:
            field_values = result_json.get("fieldValues", {})
            return {
                "success": True,
                "status": "SUCCESS",
                "email": email,
                "auto_id": field_values.get("AutoID", "-"),
                "date": field_values.get("Date", "-"),
                "time": field_values.get("Time", "-"),
                "csrf_token": csrf_token,
                "phpsessid": phpsessid,
                "raw_response": result_json
            }
        else:
            return {
                "success": False,
                "status": "VALIDATION_FAILED",
                "email": email,
                "error": "Validasi form ditolak oleh server.",
                "raw_response": result_json
            }

    except Exception as exc:
        return {
            "success": False,
            "status": "EXCEPTION",
            "email": email,
            "error": str(exc)
        }


def batch_process_surveys(
    emails: List[str],
    base_url: str = DEFAULT_BASE_URL,
    delay_between_requests: float = 0.0,
    fresh_session_per_item: bool = True,
    log_to_file: bool = True,
    log_filename: str = "batch_survey.log",
    verbose_log: bool = True
) -> Dict[str, Any]:
    """
    Memproses daftar email secara batch dengan:
    1. Validasi format email.
    2. Deteksi & eliminasi data duplikat.
    3. Logging setiap proses ke konsol & file.
    4. Penanganan error secara individual per item.
    5. Ringkasan hasil pemrosesan.

    Args:
        emails: Daftar email yang akan diproses.
        base_url: Alamat target server (bisa mock server atau server asli).
        delay_between_requests: Jeda waktu antar request dalam detik.
        fresh_session_per_item: True jika tiap submission menggunakan session terpisah (direkomendasikan).

    Returns:
        Dict[str, Any]: Ringkasan lengkap hasil pemrosesan batch.
    """
    setup_logger(log_to_file=log_to_file, log_filename=log_filename, verbose=verbose_log)

    start_time = time.time()
    total_input = len(emails)

    logger.info("==================================================")
    logger.info("          STARTING BATCH SURVEY PROCESS           ")
    logger.info("==================================================")
    logger.info(f"Target Base URL         : {base_url}")
    logger.info(f"Total input email       : {total_input}")
    logger.info(f"Fresh Session per item  : {fresh_session_per_item}")

    # 1. Filter format email & eliminasi duplikat
    valid_unique, duplicates, invalid_format = filter_and_deduplicate_emails(emails)

    logger.info(f"Email valid & unik      : {len(valid_unique)}")
    logger.info(f"Email format tidak valid: {len(invalid_format)}")
    logger.info(f"Email duplikat          : {len(duplicates)}")

    for inv in invalid_format:
        logger.warning(f"Format email diabaikan (invalid): {inv}")
    for dup in duplicates:
        logger.warning(f"Email duplikat diabaikan: {dup}")

    results: List[Dict[str, Any]] = []
    success_count = 0
    failed_count = 0

    shared_session = requests.Session() if not fresh_session_per_item else None

    # 2. Proses pengiriman per item
    for idx, email in enumerate(valid_unique, start=1):
        logger.info(f"[{idx}/{len(valid_unique)}] Memproses survey untuk: {email}")

        # Penanganan error individual
        current_session = requests.Session() if fresh_session_per_item else shared_session
        result = submit_single_survey_request(
            email=email,
            base_url=base_url,
            session=current_session
        )

        result["index"] = idx
        results.append(result)

        if result.get("success"):
            success_count += 1
            logger.info(
                f"  -> [BERHASIL] | AutoID: {result.get('auto_id')} | "
                f"Waktu: {result.get('date')} {result.get('time')}"
            )
        else:
            failed_count += 1
            logger.error(
                f"  -> [GAGAL] [{result.get('status')}] | {result.get('error')}"
            )

        if delay_between_requests > 0 and idx < len(valid_unique):
            time.sleep(delay_between_requests)

    elapsed_time = round(time.time() - start_time, 2)
    success_rate = round((success_count / len(valid_unique) * 100), 2) if valid_unique else 0.0

    summary = {
        "total_input": total_input,
        "valid_unique": len(valid_unique),
        "invalid_format_count": len(invalid_format),
        "duplicates_count": len(duplicates),
        "attempted": len(valid_unique),
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate_percent": success_rate,
        "elapsed_seconds": elapsed_time,
        "invalid_emails": invalid_format,
        "duplicate_emails": duplicates,
        "results": results
    }

    # 3. Cetak Ringkasan Hasil Pemrosesan
    print("\n" + "=" * 55)
    print("           RINGKASAN BATCH PROCESSING SURVEY             ")
    print("=" * 55)
    print(f" Total Email Input      : {total_input}")
    print(f" Format Valid & Unik    : {len(valid_unique)}")
    print(f" Format Tidak Valid     : {len(invalid_format)}")
    print(f" Email Duplikat         : {len(duplicates)}")
    print(f" Total Diproses (Kirim) : {len(valid_unique)}")
    print(f" Berhasil (Success)     : {success_count}")
    print(f" Gagal (Failed)         : {failed_count}")
    print(f" Tingkat Keberhasilan   : {success_rate}%")
    print(f" Total Waktu Eksekusi   : {elapsed_time} detik")
    print("=" * 55)

    return summary


def submit_skytrax_survey(email: str = "ade7@Gmail.com", base_url: str = DEFAULT_BASE_URL):
    """
    Fungsi legacy yang dipertahankan untuk backward compatibility pengiriman tunggal.
    """
    session = requests.Session()
    headers = get_default_headers(base_url)
    csrf_url = f"{base_url.rstrip('/')}{DEFAULT_CSRF_PATH}"
    submit_url = f"{base_url.rstrip('/')}{DEFAULT_SUBMIT_PATH}"

    print("==================================================")
    print("      SKYTRAX AIRPORT SURVEY BOT SUBMITTER        ")
    print("==================================================")

    print("\n[1/2] Mengambil CSRF Token & Session Cookie dari server...")
    try:
        csrf_token, phpsessid = fetch_csrf_token(session, csrf_url, headers)
    except Exception as e:
        print(f"[-] GAGAL mengambil token: {e}")
        return

    print(f"[+] CSRF Token   : {csrf_token}")
    print(f"[+] PHPSESSID    : {phpsessid}")

    form_data = build_form_payload(csrf_token, email)

    print(f"\n[2/2] Mengirimkan data survey ke {submit_url} (Email: {email})...")
    res_submit = session.post(submit_url, headers=headers, data=form_data)
    print(f"[+] HTTP Status  : {res_submit.status_code}")

    try:
        result = res_submit.json()
        if result.get("validated") is True:
            autoid = result.get("fieldValues", {}).get("AutoID", "-")
            date = result.get("fieldValues", {}).get("Date", "-")
            time_val = result.get("fieldValues", {}).get("Time", "-")
            res_email = result.get("fieldValues", {}).get("f2", "-")

            print("\n==================================================")
            print("       [OK] SURVEY BERHASIL TERSUBMIT!            ")
            print("==================================================")
            print(f" No. AutoID : {autoid}")
            print(f" Waktu      : {date} {time_val}")
            print(f" Email      : {res_email}")
            print(f" Validated  : {result.get('validated')}")
            print("==================================================")
        else:
            print("\n[-] VALIDASI GAGAL:")
            print(json.dumps(result, indent=2))
    except Exception:
        print("\n[-] Respon Mentah dari Server:")
        print(res_submit.text)


def main():
    """CLI Entry point dengan dukungan argumen dan konfigurasi langsung."""
    parser = argparse.ArgumentParser(
        description="Skytrax Airport Survey Bot Submitter & Batch Processing"
    )
    parser.add_argument(
        "--mode",
        choices=["batch", "single"],
        default="batch",
        help="Mode eksekusi: 'batch' (default: proses 100 email dinamis) atau 'single' (1 email saja)."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=BATCH_COUNT,
        help=f"Jumlah email dinamis yang dibuat untuk batch (default: {BATCH_COUNT})."
    )
    parser.add_argument(
        "--email",
        type=str,
        default=DEFAULT_EMAIL_SINGLE,
        help=f"Email spesifik untuk mode 'single' (default: {DEFAULT_EMAIL_SINGLE})."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=None,
        help="Paksa gunakan mock server lokal (mengabaikan nilai USE_MOCK_SERVER)."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Paksa kirim ke server publik live (worldairportsurvey.com)."
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path ke file JSON berisi daftar email khusus (contoh: email.json)."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DELAY_BETWEEN_REQUESTS,
        help=f"Delay jeda antar request batch dalam detik (default: {DELAY_BETWEEN_REQUESTS})."
    )

    args = parser.parse_args()

    if args.mode == "single":
        submit_skytrax_survey(email=args.email)
        return

    # Mode Batch: Tentukan target mock atau live
    is_mock = USE_MOCK_SERVER
    if args.live:
        is_mock = False
    elif args.mock is not None:
        is_mock = args.mock

    # 1. Dapatkan daftar email (dari file JSON jika ditentukan, atau via generator dinamis)
    if args.file:
        emails = load_emails_from_file(args.file)
    else:
        emails = generate_dynamic_emails(count=args.count)

    print(f"\n[INFO] Menyiapkan pemrosesan batch {len(emails)} email dinamis...")
    print(f"       Email pertama : {emails[0]}")
    print(f"       Email terakhir: {emails[-1]}")
    print(f"       Target        : {'MOCK SERVER LOKAL (Aman)' if is_mock else 'SERVER PUBLIK SKYTRAX'}")

    if is_mock:
        with MockSurveyServer() as mock:
            batch_process_surveys(
                emails=emails,
                base_url=mock.base_url,
                delay_between_requests=args.delay
            )
    else:
        batch_process_surveys(
            emails=emails,
            base_url=DEFAULT_BASE_URL,
            delay_between_requests=args.delay
        )


if __name__ == "__main__":
    main()
