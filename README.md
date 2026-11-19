# Bot Skytrax Survey Submitter

Automasi pengujian pengisian form survei Skytrax World Airport Survey via Python script dan Postman Collection.

## File dalam Repositori
- `submit_survey.py`: Script utama untuk automasi survei (mendukung single submit, batch processing, logging terstruktur, dan error handling).
- `email_generator.py`: Generator email dinamis (pola `ade{i}asli@gmail.com`), validasi format regex, dan filter duplikasi.
- `mock_server.py`: HTTP mock server lokal yang mensimulasikan endpoint Skytrax (`admin.php`) untuk pengujian batch 100 email yang aman.
- `test_batch_processing.py`: Rangkaian unit test dan integration test otomatis.
- `skytrax_postman_collection.json`: File koleksi Postman yang siap di-import untuk testing langsung di Postman.
- `skytrax.html`: File referensi struktur halaman wrapper survei.
- `form.html`: File referensi form survei iframe asli.

## Menjalankan Script

### 1. Langsung Menjalankan Batch 100 Email Dinamis (Default)
Cukup jalankan:
```bash
python submit_survey.py
```
Secara otomatis akan menghasilkan pola `ade1asli@gmail.com` s/d `ade100asli@gmail.com` dan memprosesnya secara batch.

> **Catatan Konfigurasi:** Anda dapat mengubah jumlah email (`BATCH_COUNT`) dan target pengujian (`USE_MOCK_SERVER = True/False`) langsung di bagian atas file `submit_survey.py`.

### 2. Pengiriman 1 Email Manual (Mode Single)
```bash
python submit_survey.py --mode single --email ade7@Gmail.com
```

### 3. Menjalankan Unit & Integration Test
```bash
python -m unittest -v test_batch_processing.py
```
