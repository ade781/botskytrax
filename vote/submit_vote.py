"""
Script Pengujian Upload Bukti ke SkyVote (https://vote.yia.co.id/)
Target pengujian default: 'Booster 1' menggunakan gambar dari folder vote/screenshoot/
"""

from datetime import datetime
import concurrent.futures
import io
import mimetypes
import os
import random
import threading
import time
import uuid
from typing import Any, Dict, List, Optional
import requests

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ==========================================================
# KONFIGURASI SKRIP PENGUJIAN SKYVOTE
# ==========================================================
SUPABASE_URL = "https://jslxlhxpwecrxjprhisx.supabase.co"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpzbHhsaHhwd2VjcnhqcHJoaXN4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY1ODY1MzIsImV4cCI6MjEwMjE2MjUzMn0."
    "UDL98uwq_ltqP2NaXqUYrjL16ZC60J5aZ9ko5t4pu1U"
)
STORAGE_BUCKET = "survey-bukti"

TARGET_NAMA = "Booster 3"
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot")
MAX_IMAGE_DIMENSION = 1280
JPEG_QUALITY = 65
MAX_WORKERS = 10               # Pengiriman paralel (10 jalur)


def get_supabase_headers(content_type: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def fetch_target_employee(nama: str = TARGET_NAMA) -> Dict[str, Any]:
    """Mengambil data pegawai target (misal: Booster 1) dari API SkyVote."""
    url = f"{SUPABASE_URL}/rest/v1/employees"
    params = {"select": "*", "nama": f"eq.{nama}", "is_active": "eq.true"}
    res = requests.get(url, headers=get_supabase_headers(), params=params, timeout=15)
    res.raise_for_status()
    data = res.json()
    if not data:
        raise ValueError(f"Pegawai '{nama}' tidak ditemukan atau tidak aktif.")
    return data[0]


def fetch_active_external_survey() -> Dict[str, Any]:
    """Mengambil survei eksternal aktif (default) dari API SkyVote."""
    url = f"{SUPABASE_URL}/rest/v1/surveys"
    params = {"select": "*", "status": "eq.Aktif", "tipe": "eq.Eksternal"}
    res = requests.get(url, headers=get_supabase_headers(), params=params, timeout=15)
    res.raise_for_status()
    data = res.json()
    if not data:
        raise ValueError("Tidak ada survei eksternal yang sedang aktif.")
    # Prioritaskan is_default=True jika ada
    for item in data:
        if item.get("is_default"):
            return item
    return data[0]


def list_screenshots(folder: str = SCREENSHOT_DIR) -> List[str]:
    """Mengambil daftar file gambar (.jpg, .jpeg, .png) dari folder screenshot secara urut."""
    if not os.path.exists(folder):
        return []
    valid_ext = (".jpg", ".jpeg", ".png")

    def sort_key(name: str):
        base = os.path.splitext(name)[0]
        return (0, int(base)) if base.isdigit() else (1, name.lower())

    files = [
        os.path.join(folder, f)
        for f in sorted(os.listdir(folder), key=sort_key)
        if f.lower().endswith(valid_ext)
    ]
    return files


_IMAGE_CACHE: Dict[str, tuple[bytes, str, str]] = {}
_CACHE_LOCK = threading.Lock()


def prepare_image_bytes(filepath: str) -> tuple[bytes, str, str]:
    """
    Membaca dan mengompres gambar sesuai aturan frontend SkyVote (max 1280px, quality 65%).
    Hasil kompresi disimpan di RAM cache agar tidak mengulang kompresi CPU saat 1000x upload.
    """
    with _CACHE_LOCK:
        if filepath in _IMAGE_CACHE:
            return _IMAGE_CACHE[filepath]

    filename = os.path.basename(filepath)
    mime_type, _ = mimetypes.guess_type(filepath)
    mime_type = mime_type or "image/jpeg"

    if HAS_PIL and mime_type in ("image/jpeg", "image/png"):
        with Image.open(filepath) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            base_name = os.path.splitext(filename)[0] + ".jpg"
            result = (buf.getvalue(), "image/jpeg", base_name)
    else:
        with open(filepath, "rb") as f:
            result = (f.read(), mime_type, filename)

    with _CACHE_LOCK:
        _IMAGE_CACHE[filepath] = result
    return result


def upload_bukti_to_storage(survey_id: int, filepath: str, suffix: str = "") -> str:
    """Mengunggah 1 file screenshot ke Supabase Storage bucket 'survey-bukti'."""
    img_bytes, content_type, clean_name = prepare_image_bytes(filepath)
    timestamp_ms = int(time.time() * 1000)
    unique_tag = uuid.uuid4().hex[:4]
    object_path = f"{survey_id}/{timestamp_ms}-{unique_tag}{suffix}-{clean_name}"

    upload_url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{object_path}"
    headers = get_supabase_headers(content_type=content_type)
    headers["x-upsert"] = "false"

    res = requests.post(upload_url, headers=headers, data=img_bytes, timeout=20)
    if res.status_code not in (200, 201):
        raise RuntimeError(f"Gagal upload storage ({res.status_code}): {res.text}")

    return object_path


def submit_vote_bukti(
    employee: Dict[str, Any],
    survey: Dict[str, Any],
    file1_path: str,
    file2_path: Optional[str] = None,
    tanggal: Optional[str] = None
) -> Dict[str, Any]:
    """Upload bukti screenshot lalu simpan record submission ke tabel 'submissions'."""
    survey_id = survey["id"]
    tgl = tanggal or datetime.now().strftime("%Y-%m-%d")

    uploaded_1 = upload_bukti_to_storage(survey_id, file1_path)
    uploaded_2 = ""
    if file2_path:
        try:
            uploaded_2 = upload_bukti_to_storage(survey_id, file2_path, suffix="-2")
        except Exception:
            # Rollback file 1 jika file 2 gagal
            del_url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{uploaded_1}"
            requests.delete(del_url, headers=get_supabase_headers(), timeout=10)
            raise

    payload = {
        "nama": employee["nama"],
        "tanggal": tgl,
        "survey_id": survey_id,
        "jenis_pegawai": employee.get("jenis_pegawai", ""),
        "departemen": employee.get("unit_kerja", ""),
        "file_bukti": uploaded_1,
        "file_bukti_2": uploaded_2,
    }

    insert_url = f"{SUPABASE_URL}/rest/v1/submissions"
    headers = get_supabase_headers(content_type="application/json")
    # Wajib return=minimal karena role anon hanya punya izin INSERT, bukan SELECT (RLS)
    headers["Prefer"] = "return=minimal"

    res = requests.post(insert_url, headers=headers, json=payload, timeout=15)
    if res.status_code not in (200, 201, 204):
        # Rollback file di storage jika insert gagal
        to_remove = [p for p in (uploaded_1, uploaded_2) if p]
        for p in to_remove:
            requests.delete(
                f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{p}",
                headers=get_supabase_headers(),
                timeout=10
            )
        raise RuntimeError(f"Gagal insert submission ({res.status_code}): {res.text}")

    return {
        "success": True,
        "nama": employee["nama"],
        "tanggal": tgl,
        "file_bukti": uploaded_1,
        "file_bukti_2": uploaded_2,
        "response": res.json() if res.text.strip() else {"status": "inserted"},
    }


def build_randomized_screenshot_queue(screenshots: List[str], count: int) -> List[str]:
    """
    Membuat antrean sebanyak `count` gambar secara acak dari daftar `screenshots`.
    Mengacak per siklus penuh agar distribusi penggunaan gambar merata dan tidak monoton.
    """
    queue: List[str] = []
    while len(queue) < count:
        pool = screenshots.copy()
        random.shuffle(pool)
        queue.extend(pool)
    return queue[:count]


def main():
    print("=" * 42)
    print("   SKYVOTE TEST SUBMITTER (BOOSTER 1)")
    print("=" * 42)

    screenshots = list_screenshots()
    if not screenshots:
        print(f"[!] Tidak ada gambar ditemukan di:\n    {SCREENSHOT_DIR}")
        return

    try:
        employee = fetch_target_employee(TARGET_NAMA)
        survey = fetch_active_external_survey()
    except Exception as e:
        print(f"[!] Gagal mengambil data awal: {e}")
        return

    while True:
        print(f" Target : {employee['nama']} ({employee.get('unit_kerja')})")
        print(f" Survei : {survey['nama']}")
        print("-" * 42)
        print(" [1] 10x Vote   (10 threads)")
        print(" [2] 100x Vote  (10 threads)")
        print(" [3] 1000x Vote (25 threads)")
        print(" [0] Keluar")
        print("=" * 42)

        choice = input(" Pilih [1/2/3/0]: ").strip()
        if choice == "0":
            print("Keluar.")
            break
        elif choice == "1":
            target_count = 10
            workers = MAX_WORKERS
        elif choice == "2":
            target_count = 100
            workers = MAX_WORKERS
        elif choice == "3":
            target_count = 1000
            workers = 25
        else:
            print("\n[!] Pilih 1, 2, 3, atau 0.\n")
            continue

        selected_files = build_randomized_screenshot_queue(screenshots, target_count)
        preview_names = ", ".join(os.path.basename(p) for p in selected_files[:5])

        print("-" * 42)
        print(f" Mode    : {target_count}x Vote (Randomize)")
        print(f" Target  : {employee['nama']}")
        print(f" Threads : {workers} jalur paralel")
        print(f" Sample  : {preview_names}, ...")
        confirm = input(" Lanjut? (gas/batal): ").strip().lower()
        if confirm != "gas":
            print("\n[BATAL] Pengiriman dibatalkan.\n")
            continue

        print("-" * 42)
        print(f" Mengirim {target_count} bukti ({workers} jalur)...")
        print("-" * 42)

        start_time = time.time()
        sukses = 0
        gagal = 0
        done_count = 0
        lock = threading.Lock()

        def worker(filepath: str):
            nonlocal sukses, gagal, done_count
            fname = os.path.basename(filepath)
            try:
                res = submit_vote_bukti(employee=employee, survey=survey, file1_path=filepath)
                with lock:
                    done_count += 1
                    sukses += 1
                    print(f"[{done_count}/{target_count}] OK | {fname}")
                    print(f"       -> {res['file_bukti']}")
            except Exception as e:
                with lock:
                    done_count += 1
                    gagal += 1
                    print(f"[{done_count}/{target_count}] GAGAL | {fname}")
                    print(f"       -> {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(worker, fp) for fp in selected_files]
            concurrent.futures.wait(futures)

        durasi = round(time.time() - start_time, 2)
        print("=" * 42)
        print(f" Selesai  : {durasi} detik")
        print(f" Berhasil : {sukses}/{target_count}")
        print(f" Gagal    : {gagal}")
        print("=" * 42 + "\n")


if __name__ == "__main__":
    main()
