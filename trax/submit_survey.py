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
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
MAGENTA = "\033[95m"
BLUE = "\033[94m"
WHITE = "\033[97m"
DIM = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"

UI_WIDTH = 80
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Menghapus kode warna ANSI untuk menghitung panjang teks yang terlihat."""
    return _ANSI_RE.sub("", text)


def pad_right(text: str, width: int) -> str:
    """Menambahkan spasi di kanan berdasarkan panjang teks terlihat."""
    vis_len = len(strip_ansi(text))
    if vis_len >= width:
        return text
    return text + (" " * (width - vis_len))


def center_text(text: str, width: int) -> str:
    """Memusatkan teks berdasarkan panjang teks terlihat."""
    vis_len = len(strip_ansi(text))
    if vis_len >= width:
        return text
    left_pad = (width - vis_len) // 2
    right_pad = width - vis_len - left_pad
    return (" " * left_pad) + text + (" " * right_pad)


def box_top(width: int = UI_WIDTH, color: str = GREEN) -> str:
    return f"{color}╔{'═' * (width - 2)}╗{RESET}"


def box_sep(width: int = UI_WIDTH, color: str = GREEN) -> str:
    return f"{color}╠{'═' * (width - 2)}╣{RESET}"


def box_thin_sep(width: int = UI_WIDTH, color: str = DIM) -> str:
    return f"{color}╟{'─' * (width - 2)}╢{RESET}"


def box_bottom(width: int = UI_WIDTH, color: str = GREEN) -> str:
    return f"{color}╚{'═' * (width - 2)}╝{RESET}"


def box_line(text: str = "", width: int = UI_WIDTH, color: str = GREEN, align: str = "left") -> str:
    """Membungkus satu baris teks di dalam border ║ ... ║ selebar UI_WIDTH."""
    inner_width = width - 4
    vis_len = len(strip_ansi(text))
    if vis_len > inner_width:
        # Potong aman jika teks polos melebihi batas inner_width
        plain = strip_ansi(text)
        content = plain[: inner_width - 3] + "..."
    else:
        content = center_text(text, inner_width) if align == "center" else pad_right(text, inner_width)
    return f"{color}║{RESET} {content} {color}║{RESET}"


def render_progress_bar(current: int, total: int, bar_width: int = 32, fill_color: str = GREEN) -> str:
    """Membuat progress bar Unicode [████░░░░] beserta persentase."""
    pct = (current / total * 100.0) if total > 0 else 0.0
    filled = int(round(bar_width * current / total)) if total > 0 else 0
    filled = max(0, min(bar_width, filled))
    bar = f"{fill_color}{'█' * filled}{DIM}{'░' * (bar_width - filled)}{RESET}"
    return f"[{bar}] {BOLD}{pct:5.1f}%{RESET}"

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

    print()
    print(box_top(UI_WIDTH, CYAN))
    print(box_line(f"{BOLD}{CYAN}>> LIVE TRANSMISSION STREAM <<   TARGET: {len(valid_unique)} VOTES | THREADS: {max_workers}{RESET}", UI_WIDTH, CYAN, align="center"))
    print(box_bottom(UI_WIDTH, CYAN))

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
            total_valid = len(valid_unique)
            counter_tag = f"{DIM}[{current_num:3d}/{total_valid:3d}]{RESET}"

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
                f31_short = f31_val if len(f31_val) <= 46 else f31_val[:43] + "..."
                print(f" {counter_tag} {BOLD}{GREEN}[ OK ]{RESET} ID:{CYAN}{auto_id:<8}{RESET} | {WHITE}{email}{RESET}")
                print(f"           {DIM}├─ mode:{f32_val:<8} freq:{f6_val:<10} │ \"{f31_short}\"{RESET}")
            else:
                failed_count += 1
                err_msg = result.get("error", "Unknown error")
                failed_items.append({"email": email, "error": err_msg})
                logger.error(f"  -> [GAGAL] [{result.get('status')}] | {err_msg}")
                print(f" {counter_tag} {BOLD}{RED}[FAIL]{RESET} {WHITE}{email}{RESET} | {RED}{err_msg}{RESET}")

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
    """Animasi loading teknikal ala hacker tepat 1.5 detik sebelum eksekusi pengiriman."""
    steps = [
        ("0x00A1", "Hooked TLSv1.3 cipher suite (ECDHE-RSA-AES256-GCM)"),
        ("0x01F4", "Seeding /dev/urandom cryptographic entropy pool"),
        ("0x02C8", "Generating dynamic CSRF token matrix & session IDs"),
        ("0x03B0", "Injecting f31 vector payload (600 randomized entries)"),
        ("0x04E2", f"Binding {workers:02d} async worker threads to execution bus"),
        ("0x05FF", f"Queueing {total_votes:04d} encrypted survey payloads"),
    ]
    print()
    print(box_top(UI_WIDTH, CYAN))
    print(box_line(f"{BOLD}{CYAN}[*] INITIALIZING CYBERNETIC PAYLOAD ENGINE{RESET}", UI_WIDTH, CYAN, align="center"))
    print(box_thin_sep(UI_WIDTH, CYAN))
    # 6 steps * 0.15s = 0.90s
    for addr, msg in steps:
        line_str = f"{CYAN}[{addr}]{RESET} {WHITE}{msg:<58}{RESET} {BOLD}{GREEN}[ OK ]{RESET}"
        print(box_line(line_str, UI_WIDTH, CYAN))
        time.sleep(0.15)

    print(box_thin_sep(UI_WIDTH, CYAN))
    # 12 steps * 0.05s = 0.60s -> Total animasi = 0.90s + 0.60s = 1.50 detik
    bar_width = 44
    total_ticks = 12
    for step in range(1, total_ticks + 1):
        pct = int(step * 100 / total_ticks)
        filled = int(bar_width * step / total_ticks)
        bar = f"{GREEN}{'█' * filled}{DIM}{'░' * (bar_width - filled)}{RESET}"
        status_tag = "ARMED!" if step == total_ticks else "EXEC.."
        sys.stdout.write(f"\r {CYAN}║{RESET} [{bar}] {BOLD}{GREEN}{pct:3d}%{RESET} // {YELLOW}{status_tag}{RESET} ")
        sys.stdout.flush()
        time.sleep(0.05)
    print()
    print(box_bottom(UI_WIDTH, CYAN))


def verify_1000x_matrix() -> bool:
    """
    Panel verifikasi 2x2 (OFF -> READY) selebar 80 karakter khusus mode 1000x.
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

    def fmt_status(name: str, desc: str, is_ready: bool) -> str:
        state = f"{BOLD}{GREEN}[READY]{RESET}" if is_ready else f"{BOLD}{RED}[ OFF ]{RESET}"
        return f"{CYAN}{name:<4}{RESET} {DIM}({desc:<13}){RESET} : {state}"

    def verify_loading(mod_name: str):
        """Animasi loading 1.5 detik dengan efek decryption scramble."""
        tech_msg = {
            "CORE": "Verifying kernel & thread pool...",
            "NET": "Handshake TLS & socket sync...",
            "AUTH": "Decrypting Ade7asli root key...",
            "EXEC": "Arming 1000x launch vector...",
        }.get(mod_name, f"Validating {mod_name}...")
        print(f" {CYAN}[*]{RESET} {tech_msg}")
        bar_width = 38
        target_word = "READY"
        cipher_chars = "X#9$K@2!Q%7&Z*4"
        for step in range(1, 11):
            pct = step * 10
            filled = int(bar_width * pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            unlocked = step // 2
            scrambled = "".join(
                target_word[i] if i < unlocked else random.choice(cipher_chars)
                for i in range(len(target_word))
            )
            color = GREEN if step == 10 else YELLOW
            sys.stdout.write(f"\r {color}[{bar}] {pct:3d}% // DECRYPT: {scrambled}{RESET}")
            sys.stdout.flush()
            time.sleep(0.15)  # 10 * 0.15s = 1.5 detik
        print()

    while not all(modules.values()):
        print()
        print(box_top(UI_WIDTH, YELLOW))
        print(box_line(f"{BOLD}{RED}[!] 1000X HEAVY LAUNCH MATRIX :: ROOT AUTHORIZATION REQUIRED{RESET}", UI_WIDTH, YELLOW, align="center"))
        print(box_sep(UI_WIDTH, YELLOW))
        row1 = f" {fmt_status('CORE', 'Thread Pool', modules['CORE'])}   │   {fmt_status('NET', 'TLS Socket', modules['NET'])}"
        row2 = f" {fmt_status('AUTH', 'Root Key', modules['AUTH'])}   │   {fmt_status('EXEC', '1000x Bus', modules['EXEC'])}"
        print(box_line(row1, UI_WIDTH, YELLOW))
        print(box_line(row2, UI_WIDTH, YELLOW))
        print(box_bottom(UI_WIDTH, YELLOW))

        cmd = input(f" {BOLD}{GREEN}root@Ade7asli:~#{RESET} ").strip().lower()

        if cmd in hidden_abort_commands:
            print(f" {RED}[!] ABORTED BY OPERATOR.{RESET}\n")
            return False
        elif cmd in secret_commands:
            mod_name = secret_commands[cmd]
            if not modules[mod_name]:
                verify_loading(mod_name)
                modules[mod_name] = True
                print(f" {BOLD}{GREEN}[+] MODULE {mod_name} -> ONLINE / READY{RESET}")
            else:
                print(f" {CYAN}[*] MODULE {mod_name} -> ALREADY READY{RESET}")
        else:
            print(f" {RED}[-] ACCESS DENIED // INVALID ROOT COMMAND{RESET}")

    print()
    print(box_top(UI_WIDTH, GREEN))
    print(box_line(f"{BOLD}{GREEN}[+] ALL SYSTEMS ARMED & READY // LAUNCHING 1000X PAYLOAD{RESET}", UI_WIDTH, GREEN, align="center"))
    print(box_sep(UI_WIDTH, GREEN))
    print(box_line(f" {fmt_status('CORE', 'Thread Pool', True)}   │   {fmt_status('NET', 'TLS Socket', True)}", UI_WIDTH, GREEN))
    print(box_line(f" {fmt_status('AUTH', 'Root Key', True)}   │   {fmt_status('EXEC', '1000x Bus', True)}", UI_WIDTH, GREEN))
    print(box_bottom(UI_WIDTH, GREEN))
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
    """Menjalankan mode 10x, 100x, atau 1000x dengan validasi & UI widescreen 80 kolom."""
    next_idx = progress.get("next_index", 0)
    total_available = len(all_emails)

    if next_idx >= total_available:
        print(f"\n {YELLOW}[INFO] Seluruh email di email.json sudah habis terpakai!{RESET}\n")
        return progress

    selected_bases = all_emails[next_idx: next_idx + base_email_count]
    if len(selected_bases) < base_email_count:
        print(
            f"\n {YELLOW}[PERINGATAN] Sisa email di {EMAIL_SOURCE_FILE} tinggal {len(selected_bases)} "
            f"(dibutuhkan {base_email_count}).{RESET}"
        )

    total_votes = len(selected_bases) * VARIANTS_PER_EMAIL
    start_line = next_idx + 2
    end_line = next_idx + len(selected_bases) + 1

    # Animasi loading teknikal ala hacker (1.5 detik)
    hacker_loading_sequence(workers=max_workers, total_votes=total_votes)

    print()
    print(box_top(UI_WIDTH, CYAN))
    print(box_line(f"{BOLD}{CYAN}>> PRE-FLIGHT MISSION BRIEFING :: {mode_label.upper()} <<{RESET}", UI_WIDTH, CYAN, align="center"))
    print(box_sep(UI_WIDTH, CYAN))
    print(box_line(f" {DIM}TARGET VOTES :{RESET} {BOLD}{GREEN}{total_votes} votes{RESET}    {DIM}│  WORKERS :{RESET} {BOLD}{CYAN}{max_workers} parallel threads{RESET}", UI_WIDTH, CYAN))
    if len(selected_bases) == 1:
        print(box_line(f" {DIM}SOURCE NODE  :{RESET} Baris {start_line} -> {WHITE}{selected_bases[0]}{RESET}", UI_WIDTH, CYAN))
    else:
        print(box_line(f" {DIM}SOURCE RANGE :{RESET} Baris {start_line} s/d {end_line} ({len(selected_bases)} base emails)", UI_WIDTH, CYAN))
        print(box_thin_sep(UI_WIDTH, CYAN))
        preview_list = selected_bases[:5]
        for i, em in enumerate(preview_list, start=start_line):
            print(box_line(f"   {CYAN}[{i:4d}]{RESET} {WHITE}{em}{RESET}", UI_WIDTH, CYAN))
        if len(selected_bases) > 5:
            print(box_line(f"   {DIM}... (+{len(selected_bases) - 5} email lainnya dalam antrean){RESET}", UI_WIDTH, CYAN))
    print(box_bottom(UI_WIDTH, CYAN))

    if require_matrix_auth:
        if not verify_1000x_matrix():
            return progress

    confirm = input(f"\n {BOLD}{GREEN}root@Ade7asli:~#{RESET} Eksekusi misi sekarang? ({GREEN}gas{RESET}/{RED}batal{RESET}): ").strip().lower()
    if confirm != "gas":
        print(f"\n {YELLOW}[BATAL] Eksekusi dibatalkan. Progress tidak berubah.{RESET}\n")
        return progress

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

    # Ringkasan akhir widescreen (80 karakter) + Telemetry Kecepatan
    elapsed = summary["elapsed_seconds"]
    speed = round(summary["attempted"] / elapsed, 1) if elapsed > 0 else 0.0
    is_perfect = summary["failed_count"] == 0
    mission_status = "MISSION COMPLETE // 100% SUCCESS" if is_perfect else "PARTIAL COMPLETE // CHECK LOGS"
    status_color = GREEN if is_perfect else YELLOW

    print()
    print(box_top(UI_WIDTH, status_color))
    print(box_line(f"{BOLD}{status_color}★  {mission_status}  ★{RESET}", UI_WIDTH, status_color, align="center"))
    print(box_sep(UI_WIDTH, status_color))
    rate_bar = render_progress_bar(summary["success_count"], summary["attempted"], bar_width=32, fill_color=status_color)
    print(box_line(f" {DIM}SUCCESS RATE :{RESET} {rate_bar}", UI_WIDTH, status_color))
    print(box_line(f" {DIM}BERHASIL     :{RESET} {BOLD}{GREEN}{summary['success_count']}/{summary['attempted']}{RESET}   {DIM}│  GAGAL :{RESET} {BOLD}{RED}{summary['failed_count']}{RESET}", UI_WIDTH, status_color))
    print(box_line(f" {DIM}DURASI       :{RESET} {WHITE}{elapsed} detik{RESET}   {DIM}│  SPEED :{RESET} {BOLD}{CYAN}{speed} vote/s{RESET}", UI_WIDTH, status_color))
    print(box_line(f" {DIM}POSISI AKHIR :{RESET} Baris {end_line} -> {WHITE}{selected_bases[-1]}{RESET}", UI_WIDTH, status_color))

    if summary.get("failed_items"):
        print(box_sep(UI_WIDTH, RED))
        print(box_line(f"{BOLD}{RED}[!] DAFTAR GAGAL (TOP 10):{RESET}", UI_WIDTH, status_color))
        for item in summary["failed_items"][:10]:
            print(box_line(f" {RED}•{RESET} {WHITE}{item['email']}{RESET} {DIM}({item['error']}){RESET}", UI_WIDTH, status_color))
        if len(summary["failed_items"]) > 10:
            print(box_line(f" {DIM}... (+{len(summary['failed_items']) - 10} lainnya tercatat di survey_run.log){RESET}", UI_WIDTH, status_color))

    print(box_bottom(UI_WIDTH, status_color))
    print()

    return progress


def hacker_boot_sequence(total_emails: int):
    """Animasi boot widescreen 80 karakter (~1.5 detik) saat program pertama dibuka."""
    boot_lines = [
        (CYAN,  f"[BOOT 0x7FA2] 9C 11 E4 00 B8 4F 2A 88 -> KERNEL HANDSHAKE OK"),
        (DIM,   f"[KERN 0x801C] Mounting SKYTRAX-OPS v2.5 CYBERNETIC EDITION..."),
        (DIM,   f"[LOAD 0x8190] Indexing email.json ({total_emails} active target nodes)..."),
        (DIM,   f"[LOAD 0x82A4] Hydrating f31 matrix (600 randomized vectors)..."),
        (CYAN,  f"[SYNC 0x83F8] Synchronizing state from progress.json..."),
        (GREEN, f"[AUTH 0x84FF] SIGNATURE VERIFIED :: OPERATOR [ADE7ASLI]"),
    ]
    print()
    print(box_top(UI_WIDTH, CYAN))
    print(box_line(f"{BOLD}{CYAN}SKYTRAX-OPS :: SYSTEM BOOT & DIAGNOSTICS{RESET}", UI_WIDTH, CYAN, align="center"))
    print(box_thin_sep(UI_WIDTH, CYAN))
    for color, msg in boot_lines:
        print(box_line(f"{color}{msg}{RESET}", UI_WIDTH, CYAN))
        time.sleep(0.25)  # 6 * 0.25s = 1.50 detik
    print(box_bottom(UI_WIDTH, CYAN))


def print_welcome_banner():
    """Menampilkan ASCII Art besar WELCOME ADE7ASLI di dalam bingkai 80 karakter."""
    welcome_art = [
        " _    _ _____ _     _____ _____ __  __ _____ ",
        "| |  | |  ___| |   /  __ \\  _  |  \\/  |  ___|",
        "| |  | | |__ | |   | /  \\/ | | | .  . | |__  ",
        "| |/\\| |  __|| |   | |   | | | | |\\/| |  __| ",
        "\\  /\\  / |___| |___| \\__/\\ \\_/ / |  | | |___ ",
        " \\/  \\/\\____/\\_____/\\____/\\___/\\_|  |_/\\____/",
    ]
    ade_art = [
        "  ___  ______ _____ ______  ___   _____ _     _____ ",
        " / _ \\ |  _  \\  ___|___  / / _ \\ /  ___| |   |_   _|",
        "/ /_\\ \\| | | | |__    / / / /_\\ \\\\ `--.| |     | |  ",
        "|  _  || | | |  __|  / /  |  _  | `--. \\ |     | |  ",
        "| | | || |/ /| |___./ /   | | | |/\\__/ / |____ | |_ ",
        "\\_| |_/|___/ \\____/\\_/    \\_| |_/\\____/\\_____/\\___/ ",
    ]
    print(box_top(UI_WIDTH, GREEN))
    for line in welcome_art:
        print(box_line(f"{BOLD}{CYAN}{line}{RESET}", UI_WIDTH, GREEN, align="center"))
    for line in ade_art:
        print(box_line(f"{BOLD}{GREEN}{line}{RESET}", UI_WIDTH, GREEN, align="center"))
    print(box_line(f"{BOLD}{MAGENTA}<< SKYTRAX-OPS v2.5 :: HIGH-VELOCITY SURVEY COMMAND CENTER >>{RESET}", UI_WIDTH, GREEN, align="center"))


def main():
    """Menampilkan menu utama interaktif widescreen (80 kolom) ala hacker."""
    all_emails = load_emails_from_file(EMAIL_SOURCE_FILE)
    progress = load_progress()
    hacker_boot_sequence(len(all_emails))

    while True:
        next_idx = progress.get("next_index", 0)
        total_emails = len(all_emails)
        total_votes = progress.get("total_votes_sent", 0)
        remaining = max(0, total_emails - next_idx)

        print()
        print_welcome_banner()
        print(box_sep(UI_WIDTH, GREEN))
        prog_bar = render_progress_bar(next_idx, total_emails, bar_width=30, fill_color=CYAN)
        print(box_line(f" {DIM}QUEUE PROGRESS :{RESET} {prog_bar}  ({CYAN}{next_idx}/{total_emails}{RESET})", UI_WIDTH, GREEN))
        print(box_line(f" {DIM}TOTAL SENT     :{RESET} {BOLD}{GREEN}{total_votes} votes{RESET}   {DIM}│  REMAINING :{RESET} {BOLD}{YELLOW}{remaining} emails{RESET}", UI_WIDTH, GREEN))
        if next_idx < total_emails:
            print(box_line(f" {DIM}NEXT TARGET    :{RESET} {WHITE}Baris {next_idx + 2}{RESET} -> {CYAN}{all_emails[next_idx]}{RESET}", UI_WIDTH, GREEN))
        else:
            print(box_line(f" {DIM}NEXT TARGET    :{RESET} {BOLD}{YELLOW}ALL EMAILS EXHAUSTED (HABIS){RESET}", UI_WIDTH, GREEN))

        print(box_sep(UI_WIDTH, GREEN))
        print(box_line(f" {BOLD}{WHITE}SELECT EXECUTION VECTOR:{RESET}", UI_WIDTH, GREEN))
        print(box_line(f"  {BOLD}{GREEN}[1]{RESET} {WHITE}10x   SURVEY BURST{RESET}  {DIM}│{RESET} {CYAN}10 threads{RESET}  {DIM}│{RESET}  1 base email  (10 votes)", UI_WIDTH, GREEN))
        print(box_line(f"  {BOLD}{GREEN}[2]{RESET} {WHITE}100x  SURVEY STORM{RESET}  {DIM}│{RESET} {CYAN}10 threads{RESET}  {DIM}│{RESET} 10 base emails (100 votes)", UI_WIDTH, GREEN))
        print(box_line(f"  {BOLD}{RED}[3]{RESET} {YELLOW}1000x OVERDRIVE{RESET}     {DIM}│{RESET} {RED}25 threads{RESET}  {DIM}│{RESET} 100 base emails {RED}[MATRIX AUTH]{RESET}", UI_WIDTH, GREEN))
        print(box_line(f"  {DIM}[0] EXIT TERMINAL{RESET}", UI_WIDTH, GREEN))
        print(box_bottom(UI_WIDTH, GREEN))

        choice = input(f" {BOLD}{GREEN}root@Ade7asli:~#{RESET} pilih [1/2/3/0]: ").strip()

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
            print(f"\n {CYAN}[*] Session terminated. Goodbye Ade7asli.{RESET}\n")
            break
        else:
            print(f"\n {RED}[!] Pilihan tidak valid. Ketik 1, 2, 3, atau 0.{RESET}\n")


if __name__ == "__main__":
    main()
