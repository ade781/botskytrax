# Skytrax & SkyVote Automation

Kumpulan skrip CLI Python untuk automasi pengujian dan pengiriman data survei secara terstruktur.

## Struktur Project
- `trax/`: Modul utama pengiriman survei (`submit_survey.py`, `email_generator.py`, `email.json`, `survey_options.json`, serta koleksi referensi).
- `vote/`: Modul pengiriman bukti survei (`submit_vote.py` beserta folder `screenshot/`).

## Cara Menjalankan
- **Mode Trax:**
  ```bash
  python trax/submit_survey.py
  ```
- **Mode Vote:**
  ```bash
  python vote/submit_vote.py
  ```
