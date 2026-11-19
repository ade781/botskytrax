"""
Module Email Generator & Validator
Menyediakan fungsi pembentukan email dinamis dengan konfigurasi fleksibel,
validasi format email, dan penanganan data duplikat.
"""

import json
import os
import random
import re
from typing import List, Tuple, Set


# Regex standar untuk validasi format email dasar (RFC 5322 simplifikasi)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
)


def generate_dynamic_emails(
    count: int = 100,
    prefix: str = "ade",
    suffix: str = "asli",
    domain: str = "gmail.com",
    start_index: int = 1
) -> List[str]:
    """
    Menghasilkan daftar alamat email secara dinamis menggunakan pola:
    {prefix}{i}{suffix}@{domain}
    Contoh: ade1asli@gmail.com s/d ade100asli@gmail.com

    Args:
        count (int): Jumlah email yang ingin dibuat (default: 100).
        prefix (str): Prefix nama email (default: "ade").
        suffix (str): Suffix nama email sebelum @ (default: "asli").
        domain (str): Domain email (default: "gmail.com").
        start_index (int): Indeks awal iterasi (default: 1).

    Returns:
        List[str]: Daftar alamat email yang telah digenerate.
    """
    if count < 0:
        raise ValueError("Jumlah email (count) tidak boleh negatif.")

    emails = [
        f"{prefix}{i}{suffix}@{domain}"
        for i in range(start_index, start_index + count)
    ]
    return emails


def generate_random_numbered_emails(
    count: int = 10,
    prefix: str = "galangrakha",
    suffix: str = "",
    domain: str = "gmail.com",
    min_number: int = 1,
    max_number: int = 100
) -> List[str]:
    """
    Menghasilkan daftar email dengan angka acak unik dari rentang min_number s/d max_number.
    Contoh: galangrakha(angka)@gmail.com dengan angka 1-100 di-randomize sebanyak 10 kali.

    Args:
        count (int): Jumlah email yang ingin digenerate (default: 10).
        prefix (str): Prefix nama email (default: "galangrakha").
        suffix (str): Suffix opsional sebelum @ (default: "").
        domain (str): Domain email (default: "gmail.com").
        min_number (int): Batas bawah angka acak (default: 1).
        max_number (int): Batas atas angka acak (default: 100).

    Returns:
        List[str]: Daftar email dengan angka teracak tanpa duplikat.
    """
    pool_size = max_number - min_number + 1
    if count < 0 or count > pool_size:
        raise ValueError(f"count ({count}) harus berada di antara 0 dan {pool_size}.")

    random_numbers = random.sample(range(min_number, max_number + 1), count)
    return [f"{prefix}{num}{suffix}@{domain}" for num in random_numbers]


def randomize_from_base_email(
    base_email: str,
    count: int = 10,
    min_number: int = 1,
    max_number: int = 100
) -> List[str]:
    """
    Mengambil template email dasar (misal: 'galangrakha@gmail.com' dari email.json baris 1002)
    lalu menyisipkan angka acak (1-100) sebelum '@' sebanyak `count` kali secara dinamis oleh sistem.
    """
    if "@" not in base_email:
        raise ValueError(f"Format base_email tidak valid: {base_email}")

    local_part, domain = base_email.strip().split("@", 1)
    return generate_random_numbered_emails(
        count=count,
        prefix=local_part,
        suffix="",
        domain=domain,
        min_number=min_number,
        max_number=max_number
    )


def validate_email_format(email: str) -> bool:
    """
    Memvalidasi apakah string merupakan format email yang valid.

    Args:
        email (str): Alamat email yang akan diperiksa.

    Returns:
        bool: True jika format valid, False jika tidak valid.
    """
    if not isinstance(email, str) or not email.strip():
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def filter_and_deduplicate_emails(emails: List[str]) -> Tuple[List[str], List[str], List[str]]:
    """
    Memfilter daftar email: memisahkan email valid & unik, email duplikat, dan email tidak valid.

    Args:
        emails (List[str]): Daftar email mentah.

    Returns:
        Tuple[List[str], List[str], List[str]]:
            - valid_unique: Daftar email valid yang unik (mempertahankan urutan kemunculan pertama).
            - duplicates: Daftar email duplikat yang diabaikan.
            - invalid_format: Daftar email dengan format tidak valid.
    """
    seen: Set[str] = set()
    valid_unique: List[str] = []
    duplicates: List[str] = []
    invalid_format: List[str] = []

    for raw_email in emails:
        clean_email = raw_email.strip() if isinstance(raw_email, str) else ""

        if not validate_email_format(clean_email):
            invalid_format.append(clean_email or str(raw_email))
            continue

        normalized_email = clean_email.lower()
        if normalized_email in seen:
            duplicates.append(clean_email)
        else:
            seen.add(normalized_email)
            valid_unique.append(clean_email)

    return valid_unique, duplicates, invalid_format


def load_emails_from_file(filepath: str = "email.json") -> List[str]:
    """
    Membaca daftar email dari file JSON.

    Args:
        filepath (str): Path ke file JSON (default: 'email.json').

    Returns:
        List[str]: Daftar email dari file JSON.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File {filepath} tidak ditemukan.")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Isi file {filepath} harus berupa JSON array/list.")

    return [str(item) for item in data]

