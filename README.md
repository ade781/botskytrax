# Skytrax Survey Automation

Aplikasi CLI Python untuk automasi pengujian dan pengiriman data form survei secara interaktif.

## Gambaran Umum
- `submit_survey.py`: Modul utama dengan menu interaktif, manajemen sesi HTTP/CSRF, validasi konfirmasi, dan pencatatan log.
- `email_generator.py`: Modul pengelolaan, validasi format, dan variasi data email.
- `email.json` & `survey_options.json`: Sumber data daftar email dan variasi opsi isian form.
- `skytrax_postman_collection.json`: Koleksi Postman untuk pengujian API secara manual.

## Cara Menjalankan
```bash
python submit_survey.py
```
