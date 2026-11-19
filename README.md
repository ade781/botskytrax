# Bot Skytrax Survey Submitter

Automasi pengujian pengisian form survei Skytrax World Airport Survey via Python script dan Postman Collection.

## File dalam Repositori
- `submit_survey.py`: Script Python untuk mengotomasi pengambilan CSRF token dan session PHP, lalu submit form survei.
- `skytrax_postman_collection.json`: File koleksi Postman yang siap di-import untuk testing langsung di Postman.
- `skytrax.html`: File referensi struktur halaman wrapper survei.
- `form.html`: File referensi form survei iframe asli.

## Menjalankan Script
```bash
python submit_survey.py
```
