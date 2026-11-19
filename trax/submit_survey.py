"""
Skytrax Airport Survey Automation System
Mendukung mode interaktif:
  1. Mode 10x Vote  : 1 email urut dari email.json -> 10 variasi angka acak (1-100)
  2. Mode 100x Vote : 10 email urut dari email.json -> 100 variasi vote diacak urutannya
Dilengkapi pelacakan progress baris pada email.json (progress.json),
pengacakan payload form (survey_options.json), validasi konfirmasi (gas/batal),
logging terstruktur, dan penanganan error per item.
"""

from datetime import datetime
import concurrent.futures
import json
import logging
import os
import random
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

try:
    import colorama
    colorama.init(autoreset=True)
except Exception:
    os.system("")

# Warna ANSI untuk tampilan terminal ala hacker
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"

from email_generator import (
    load_emails_from_file,
    randomize_from_base_email,
    validate_email_format,
    filter_and_deduplicate_emails,
)

# ==========================================================
# KONFIGURASI UTAMA
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMAIL_SOURCE_FILE = os.path.join(BASE_DIR, "email.json")
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")
SURVEY_OPTIONS_FILE = os.path.join(BASE_DIR, "survey_options.json")
DEFAULT_LOG_FILE = os.path.join(BASE_DIR, "survey_run.log")
VARIANTS_PER_EMAIL = 10        # Jumlah variasi angka acak per email dasar (10x)
RANDOM_NUM_MIN = 1
RANDOM_NUM_MAX = 100
MAX_WORKERS = 10               # Jumlah koneksi paralel (10 jalur)
DELAY_BETWEEN_REQUESTS = 0.0   # Jeda antar request dalam detik (opsional, misal 0.5)

DEFAULT_BASE_URL = "https://www.worldairportsurvey.com"
DEFAULT_CSRF_PATH = "/Surveys/Airport/admin.php?method=csrfToken"
DEFAULT_SUBMIT_PATH = "/Surveys/Airport/admin.php"

SERVER_VALIDATION_FIELDS = (
    "f5,f31,f32,f6,f15,f16,f18,f20,f21,f22,f23,f24,f25,f27,"
    "f34,f35,f36,f37,f38,f39,f40,f41,f42,f43,f45,f47,f48,f49,"
    "f50,f51,f52,f53,f33,f28,f2"
)

# Konfigurasi Logging
logger = logging.getLogger("SkytraxSurvey")


def setup_logger(log_to_file: bool = True, log_filename: str = DEFAULT_LOG_FILE, verbose: bool = True):
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
# MANAJEMEN PROGRESS (progress.json)
# ==========================================================
def load_progress(filepath: str = PROGRESS_FILE) -> Dict[str, Any]:
    """Membaca status progress terakhir dari progress.json."""
    default_state = {
        "next_index": 0,
        "last_email": None,
        "last_line_number": None,
        "total_emails_used": 0,
        "total_votes_sent": 0,
        "updated_at": None
    }
    if not os.path.exists(filepath):
        return default_state

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            default_state.update(data)
        return default_state
    except Exception:
        return default_state


def save_progress(state: Dict[str, Any], filepath: str = PROGRESS_FILE):
    """Menyimpan status progress terbaru ke progress.json."""
    state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ==========================================================
# MANAJEMEN PAYLOAD & REQUEST
# ==========================================================
_CACHED_SURVEY_OPTIONS: Optional[Dict[str, List[str]]] = None


def load_survey_options(filepath: str = SURVEY_OPTIONS_FILE) -> Dict[str, List[str]]:
    """Membaca opsi pilihan acak (f31, f32, f6) dari survey_options.json dengan in-memory cache."""
    global _CACHED_SURVEY_OPTIONS
    if _CACHED_SURVEY_OPTIONS is not None:
        return _CACHED_SURVEY_OPTIONS

    default_options = {
        "f31": ["Great hospitality, clean terminals, and smooth immigration process"],
        "f32": ["Depart", "Arrival", "Transfer", "Visiting"],
        "f6": ["1_2_month", "3_6_month", "12_month"]
    }
    if not os.path.exists(filepath):
        _CACHED_SURVEY_OPTIONS = default_options
        return _CACHED_SURVEY_OPTIONS

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        _CACHED_SURVEY_OPTIONS = {
            "f31": data.get("f31") or default_options["f31"],
            "f32": data.get("f32") or default_options["f32"],
            "f6": data.get("f6") or default_options["f6"],
        }
        return _CACHED_SURVEY_OPTIONS
    except Exception:
        _CACHED_SURVEY_OPTIONS = default_options
        return _CACHED_SURVEY_OPTIONS


def get_randomized_survey_answers(filepath: str = SURVEY_OPTIONS_FILE) -> Dict[str, str]:
    """Mengambil 1 kombinasi acak untuk field f31, f32, dan f6."""
    options = load_survey_options(filepath)
    return {
        "f31": random.choice(options["f31"]),
        "f32": random.choice(options["f32"]),
        "f6": random.choice(options["f6"]),
    }


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
    """Mengambil CSRF token dan cookie session (PHPSESSID) dari server."""
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
    custom_fields: Optional[Dict[str, str]] = None,
    randomize_options: bool = True
) -> Dict[str, str]:
    """Menyusun payload form data survei dengan email dinamis dan variasi acak."""
    randomized = get_randomized_survey_answers() if randomize_options else {
        "f31": "Great hospitality, clean terminals, and smooth immigration process",
        "f32": "Depart",
        "f6": "1_2_month",
    }

    payload = {
        "method": "validateForm",
        "serverValidationFields": SERVER_VALIDATION_FIELDS,
        "csrf_token": csrf_token,
        "f5": "Soekarno-Hatta International Airport",
        "f31": randomized["f31"],
        "f32": randomized["f32"],
        "f6": randomized["f6"],
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
    """Eksekusi 1 pengiriman survei (ambil CSRF token -> kirim payload -> validasi JSON)."""
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
                "f31": form_data.get("f31", "-"),
                "f32": form_data.get("f32", "-"),
                "f6": form_data.get("f6", "-"),
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
    delay_between_requests: float = DELAY_BETWEEN_REQUESTS,
    fresh_session_per_item: bool = True,
    log_to_file: bool = True,
    log_filename: str = DEFAULT_LOG_FILE,
    verbose_log: bool = False,
    max_workers: int = MAX_WORKERS
) -> Dict[str, Any]:
    """Memproses daftar email secara batch dengan pemrosesan paralel (multithreading)."""
    setup_logger(log_to_file=log_to_file, log_filename=log_filename, verbose=verbose_log)

    start_time = time.time()
    total_input = len(emails)

    logger.info("==================================================")
    logger.info("          STARTING BATCH SURVEY PROCESS           ")
    logger.info("==================================================")
    logger.info(f"Target Base URL         : {base_url}")
    logger.info(f"Total target vote       : {total_input}")
    logger.info(f"Max Workers (Paralel)   : {max_workers}")

    valid_unique, duplicates, invalid_format = filter_and_deduplicate_emails(emails)

    for inv in invalid_format:
        logger.warning(f"Format email diabaikan (invalid): {inv}")
    for dup in duplicates:
        logger.warning(f"Email duplikat diabaikan: {dup}")

    results: List[Dict[str, Any]] = []
    success_count = 0
    failed_count = 0
    failed_items: List[Dict[str, str]] = []
    shared_session = requests.Session() if not fresh_session_per_item else None
    print_lock = threading.Lock()
    completed_counter = 0

    print("\n" + "-" * 38)
    print(f" Mengirim {len(valid_unique)} vote ({max_workers} jalur paralel)...")
    print("-" * 38)

    def worker_submit(idx_original: int, email: str) -> Dict[str, Any]:
        nonlocal success_count, failed_count, completed_counter
        current_session = requests.Session() if fresh_session_per_item else shared_session
        result = submit_single_survey_request(
            email=email,
            base_url=base_url,
            session=current_session
        )
        result["index"] = idx_original

        with print_lock:
            completed_counter += 1
            current_num = completed_counter
            results.append(result)

            if result.get("success"):
                success_count += 1
                auto_id = result.get("auto_id", "-")
                f31_val = result.get("f31", "-")
                f32_val = result.get("f32", "-")
                f6_val = result.get("f6", "-")

                logger.info(
                    f"  -> [BERHASIL] | AutoID: {auto_id} | "
                    f"f32: {f32_val} | f6: {f6_val} | f31: \"{f31_val}\""
                )
                print(f"[{current_num}/{len(valid_unique)}] OK | ID: {auto_id}")
                print(f"       {email}")
                print(f"       f31: \"{f31_val}\"")
            else:
                failed_count += 1
                err_msg = result.get("error", "Unknown error")
                failed_items.append({"email": email, "error": err_msg})
                logger.error(f"  -> [GAGAL] [{result.get('status')}] | {err_msg}")
                print(f"[{current_num}/{len(valid_unique)}] GAGAL | {err_msg}")
                print(f"       {email}")

        return result

    # Eksekusi paralel jika max_workers > 1
    if max_workers > 1 and len(valid_unique) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(worker_submit, idx, email)
                for idx, email in enumerate(valid_unique, start=1)
            ]
            concurrent.futures.wait(futures)
    else:
        for idx, email in enumerate(valid_unique, start=1):
            worker_submit(idx, email)
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
        "failed_items": failed_items,
        "success_rate_percent": success_rate,
        "elapsed_seconds": elapsed_time,
        "results": results
    }

    return summary


# ==========================================================
# LOGIKA MENU INTERAKTIF
# ==========================================================
def prepare_vote_queue(
    base_emails: List[str],
    variants_per_email: int = VARIANTS_PER_EMAIL,
    shuffle_queue: bool = False
) -> List[str]:
    """
    Menghasilkan daftar email vote dari email dasar dengan variasi angka acak 1-100.
    Jika shuffle_queue=True (mode 100x), seluruh antrean vote akan diacak urutannya.
    """
    vote_queue: List[str] = []
    for base_email in base_emails:
        variants = randomize_from_base_email(
            base_email=base_email,
            count=variants_per_email,
            min_number=RANDOM_NUM_MIN,
            max_number=RANDOM_NUM_MAX
        )
        vote_queue.extend(variants)

    if shuffle_queue:
        random.shuffle(vote_queue)

    return vote_queue


def hacker_loading_sequence(workers: int, total_votes: int):
    """Animasi loading teknikal ala hacker sebelum eksekusi pengiriman."""
    steps = [
        ("0x00A1", "Hooked TLSv1.3 cipher suite"),
        ("0x01F4", "Seeding /dev/urandom entropy"),
        ("0x02C8", "Generating CSRF token matrix"),
        ("0x03B0", "Injecting f31 vector (600)"),
        ("0x04E2", f"Binding {workers} async worker threads"),
        ("0x05FF", f"Queueing {total_votes} encrypted payloads"),
    ]
    print(f"\n{DIM}{'-' * 38}{RESET}")
    for addr, msg in steps:
        print(f"{CYAN}[{addr}]{RESET} {msg} {GREEN}[OK]{RESET}")
        time.sleep(0.18)

    bar_width = 20
    for pct in range(0, 101, 10):
        filled = int(bar_width * pct / 100)
        bar = "#" * filled + "-" * (bar_width - filled)
        sys.stdout.write(f"\r{GREEN}[{bar}] {pct:3d}% // EXEC{RESET}")
        sys.stdout.flush()
        time.sleep(0.05)
    print(f"\n{DIM}{'-' * 38}{RESET}")


def verify_1000x_matrix() -> bool:
    """
    Panel verifikasi 2x2 (OFF -> READY) khusus mode 1000x.
    Mengharuskan 4 kode root yang berbeda untuk mengaktifkan seluruh modul.
    Perintah kembali tidak ditampilkan di UI (hidden command).
    """
    modules = {
        "CORE": False,
        "NET": False,
        "AUTH": False,
        "EXEC": False,
    }
    secret_commands = {
        "root init core": "CORE",
        "root sync net": "NET",
        "root auth ade7asli": "AUTH",
        "root exec 1000x": "EXEC",
    }
    hidden_abort_commands = {"root exit", "root abort", "batal"}

    def fmt_status(name: str, is_ready: bool) -> str:
        state = f"{GREEN}READY{RESET}" if is_ready else f"{RED}OFF  {RESET}"
        return f"{name:<4} : {state}"

    def verify_loading(mod_name: str):
        """Animasi loading 1.5 detik untuk setiap verifikasi modul."""
        tech_msg = {
            "CORE": "Verifying kernel & thread pool...",
            "NET": "Handshake TLS & socket sync...",
            "AUTH": "Decrypting Ade7asli root key...",
            "EXEC": "Arming 1000x launch vector...",
        }.get(mod_name, f"Validating {mod_name}...")
        print(f"{CYAN}[*] {tech_msg}{RESET}")
        bar_width = 20
        for step in range(1, 11):
            pct = step * 10
            filled = int(bar_width * pct / 100)
            bar = "#" * filled + "-" * (bar_width - filled)
            sys.stdout.write(f"\r{YELLOW}[{bar}] {pct:3d}% // {mod_name}{RESET}")
            sys.stdout.flush()
            time.sleep(0.15)  # 10 * 0.15s = 1.5 detik
        print()

    while not all(modules.values()):
        print(f"\n{YELLOW}{'-' * 38}{RESET}")
        print(f"{BOLD}{CYAN} [!] 1000X LAUNCH MATRIX (25 THREADS){RESET}")
        print(f"{YELLOW}{'-' * 38}{RESET}")
        print(f" {fmt_status('CORE', modules['CORE'])}   {fmt_status('NET', modules['NET'])}")
        print(f" {fmt_status('AUTH', modules['AUTH'])}   {fmt_status('EXEC', modules['EXEC'])}")
        print(f"{YELLOW}{'-' * 38}{RESET}")

        cmd = input(f"{GREEN} root@Ade7asli:~# {RESET}").strip().lower()

        if cmd in hidden_abort_commands:
            print(f"{RED}[!] ABORTED.{RESET}\n")
            return False
        elif cmd in secret_commands:
            mod_name = secret_commands[cmd]
            if not modules[mod_name]:
                verify_loading(mod_name)
                modules[mod_name] = True
                print(f"{GREEN}[+] {mod_name} -> SUCCESS{RESET}")
            else:
                print(f"{CYAN}[*] {mod_name} -> ALREADY READY{RESET}")
        else:
            print(f"{RED}[-] ACCESS DENIED{RESET}")

    print(f"\n{GREEN}{'-' * 38}{RESET}")
    print(f" {fmt_status('CORE', True)}   {fmt_status('NET', True)}")
    print(f" {fmt_status('AUTH', True)}   {fmt_status('EXEC', True)}")
    print(f"{GREEN}{'-' * 38}{RESET}")
    print(f"{BOLD}{GREEN}[+] ALL SYSTEMS READY // LAUNCHING!{RESET}")
    return True


def execute_menu_mode(
    all_emails: List[str],
    progress: Dict[str, Any],
    base_email_count: int,
    shuffle_queue: bool,
    mode_label: str,
    max_workers: int = MAX_WORKERS,
    require_matrix_auth: bool = False
) -> Dict[str, Any]:
    """Menjalankan mode 10x, 100x, atau 1000x dengan validasi & animasi hacker."""
    next_idx = progress.get("next_index", 0)
    total_available = len(all_emails)

    if next_idx >= total_available:
        print(f"\n{YELLOW}[INFO] Seluruh email di email.json sudah habis terpakai!{RESET}\n")
        return progress

    selected_bases = all_emails[next_idx: next_idx + base_email_count]
    if len(selected_bases) < base_email_count:
        print(
            f"\n{YELLOW}[PERINGATAN] Sisa email di {EMAIL_SOURCE_FILE} tinggal {len(selected_bases)} "
            f"(dibutuhkan {base_email_count}).{RESET}"
        )

    total_votes = len(selected_bases) * VARIANTS_PER_EMAIL
    start_line = next_idx + 2
    end_line = next_idx + len(selected_bases) + 1

    # Animasi loading teknikal ala hacker langsung saat menu dipilih
    hacker_loading_sequence(workers=max_workers, total_votes=total_votes)

    print(f"\n{CYAN}{'-' * 38}{RESET}")
    print(f"{BOLD} PREVIEW: {mode_label}{RESET}")
    print(f"{CYAN}{'-' * 38}{RESET}")
    if len(selected_bases) == 1:
        print(f" Baris {start_line} ({selected_bases[0]})")
    else:
        print(f" Baris {start_line} s/d {end_line} ({len(selected_bases)} email)")
        preview_list = selected_bases[:5]
        for i, em in enumerate(preview_list, start=start_line):
            print(f"  {i:4d}. {em}")
        if len(selected_bases) > 5:
            print(f"   ... (+{len(selected_bases) - 5} email lainnya)")
    print(f" Total : {total_votes} vote | {max_workers} threads")
    print(f"{CYAN}{'-' * 38}{RESET}")

    if require_matrix_auth:
        if not verify_1000x_matrix():
            return progress

    confirm = input(f"{GREEN} Lanjut? (gas/batal): {RESET}").strip().lower()
    if confirm != "gas":
        print(f"\n{YELLOW}[BATAL] Progress tidak berubah.{RESET}\n")
        return progress

    # Generate antrean vote sesuai mode
    vote_queue = prepare_vote_queue(
        base_emails=selected_bases,
        variants_per_email=VARIANTS_PER_EMAIL,
        shuffle_queue=shuffle_queue
    )

    summary = batch_process_surveys(
        emails=vote_queue,
        base_url=DEFAULT_BASE_URL,
        delay_between_requests=DELAY_BETWEEN_REQUESTS,
        max_workers=max_workers
    )

    # Update progress hanya setelah eksekusi selesai dijalankan
    new_next_idx = next_idx + len(selected_bases)
    progress["next_index"] = new_next_idx
    progress["last_email"] = selected_bases[-1]
    progress["last_line_number"] = end_line
    progress["total_emails_used"] = new_next_idx
    progress["total_votes_sent"] = progress.get("total_votes_sent", 0) + summary.get("success_count", 0)
    save_progress(progress)

    # Ringkasan akhir ringkas (38 karakter)
    print(f"\n{GREEN}{'=' * 38}{RESET}")
    print(f"{BOLD}{GREEN}         RINGKASAN PENGIRIMAN{RESET}")
    print(f"{GREEN}{'=' * 38}{RESET}")
    print(f" Berhasil : {summary['success_count']}/{summary['attempted']} ({summary['success_rate_percent']}%)")
    print(f" Gagal    : {summary['failed_count']}")
    print(f" Durasi   : {summary['elapsed_seconds']} detik")
    print(f" Posisi   : Baris {end_line}")
    print(f"            {selected_bases[-1]}")
    if summary.get("failed_items"):
        print(f"{RED}{'-' * 38}{RESET}")
        print(f"{RED} Daftar Gagal:{RESET}")
        for item in summary["failed_items"][:10]:
            print(f" - {item['email']}")
            print(f"   ({item['error']})")
        if len(summary["failed_items"]) > 10:
            print(f" ... (+{len(summary['failed_items']) - 10} lainnya di log)")
    print(f"{GREEN}{'=' * 38}{RESET}\n")

    return progress


def main():
    """Menampilkan menu utama interaktif ala hacker beserta status progress."""
    all_emails = load_emails_from_file(EMAIL_SOURCE_FILE)
    progress = load_progress()

    while True:
        next_idx = progress.get("next_index", 0)
        total_emails = len(all_emails)
        total_votes = progress.get("total_votes_sent", 0)

        print(f"{GREEN}{'-' * 38}{RESET}")
        print(f"{BOLD}{GREEN}=== WELCOME ADE7ASLI               ==={RESET}")
        print(f"{GREEN}{'-' * 38}{RESET}")
        print(f" USED : {CYAN}{next_idx}/{total_emails}{RESET} | SENT : {CYAN}{total_votes} votes{RESET}")
        if next_idx < total_emails:
            print(f" NEXT : Baris {next_idx + 2}")
            print(f"        {all_emails[next_idx]}")
        else:
            print(f" NEXT : {YELLOW}SELESAI (Habis){RESET}")
        print(f"{DIM}{'-' * 38}{RESET}")
        print(f" {GREEN}[1]{RESET} 10x   (10 threads)")
        print(f" {GREEN}[2]{RESET} 100x  (10 threads)")
        print(f" {RED}[3]{RESET} 1000x (25 threads) {YELLOW}[HEAVY]{RESET}")
        print(f" {DIM}[0]{RESET} EXIT")
        print(f"{GREEN}{'=' * 38}{RESET}")

        choice = input(f" {GREEN}root@Ade7asli:~#{RESET} pilih [1/2/3/0]: ").strip()

        if choice == "1":
            progress = execute_menu_mode(
                all_emails=all_emails,
                progress=progress,
                base_email_count=1,
                shuffle_queue=False,
                mode_label="10x Vote",
                max_workers=10,
                require_matrix_auth=False
            )
        elif choice == "2":
            progress = execute_menu_mode(
                all_emails=all_emails,
                progress=progress,
                base_email_count=10,
                shuffle_queue=True,
                mode_label="100x Vote",
                max_workers=10,
                require_matrix_auth=False
            )
        elif choice == "3":
            progress = execute_menu_mode(
                all_emails=all_emails,
                progress=progress,
                base_email_count=100,
                shuffle_queue=True,
                mode_label="1000x Vote [HEAVY]",
                max_workers=25,
                require_matrix_auth=True
            )
        elif choice == "0":
            print(f"\n{CYAN}[*] Session terminated. Goodbye Ade7asli.{RESET}\n")
            break
        else:
            print(f"\n{RED}[!] Pilih 1, 2, 3, atau 0.{RESET}\n")


if __name__ == "__main__":
    main()
