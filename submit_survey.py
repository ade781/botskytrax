import requests
import json

def submit_skytrax_survey():
    # Gunakan requests.Session agar cookie PHPSESSID otomatis tersimpan dan terkirim antar-request
    session = requests.Session()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.worldairportsurvey.com",
        "Referer": "https://www.worldairportsurvey.com/Surveys/Airport/form.html",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    csrf_url = "https://www.worldairportsurvey.com/Surveys/Airport/admin.php?method=csrfToken"
    submit_url = "https://www.worldairportsurvey.com/Surveys/Airport/admin.php"

    print("==================================================")
    print("      SKYTRAX AIRPORT SURVEY BOT SUBMITTER        ")
    print("==================================================")

    # 1. Ambil CSRF Token & Session Cookie
    print("\n[1/2] Mengambil CSRF Token & Session Cookie dari server...")
    res_csrf = session.get(csrf_url, headers=headers)
    
    if res_csrf.status_code != 200:
        print(f"[-] GAGAL mengambil token. HTTP Status: {res_csrf.status_code}")
        print(res_csrf.text)
        return

    try:
        csrf_data = res_csrf.json()
        csrf_token = csrf_data.get("csrf_token")
    except Exception as e:
        print(f"[-] Gagal membaca JSON token: {e}")
        print("Raw response:", res_csrf.text)
        return

    phpsessid = session.cookies.get("PHPSESSID")
    print(f"[+] CSRF Token   : {csrf_token}")
    print(f"[+] PHPSESSID    : {phpsessid}")

    # Daftar field wajib aktif (agar tidak menolak pertanyaan COVID-19 lama f17, f19, f26)
    server_validation_fields = (
        "f5,f31,f32,f6,f15,f16,f18,f20,f21,f22,f23,f24,f25,f27,"
        "f34,f35,f36,f37,f38,f39,f40,f41,f42,f43,f45,f47,f48,f49,"
        "f50,f51,f52,f53,f33,f28,f2"
    )

    # Data form survey
    form_data = {
        "method": "validateForm",
        "serverValidationFields": server_validation_fields,
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
        "f2": "ade7@Gmail.com"
    }

    # 2. Kirim data survey ke admin.php
    print("\n[2/2] Mengirimkan data survey ke admin.php...")
    res_submit = session.post(submit_url, headers=headers, data=form_data)

    print(f"[+] HTTP Status  : {res_submit.status_code}")
    
    try:
        result = res_submit.json()
        if result.get("validated") is True:
            autoid = result.get("fieldValues", {}).get("AutoID", "-")
            date = result.get("fieldValues", {}).get("Date", "-")
            time = result.get("fieldValues", {}).get("Time", "-")
            email = result.get("fieldValues", {}).get("f2", "-")
            
            print("\n==================================================")
            print("         ✓ SURVEY BERHASIL TERSUBMIT!             ")
            print("==================================================")
            print(f" No. AutoID : {autoid}")
            print(f" Waktu      : {date} {time}")
            print(f" Email      : {email}")
            print(f" Validated  : {result.get('validated')}")
            print("==================================================")
        else:
            print("\n[-] VALIDASI GAGAL:")
            print(json.dumps(result, indent=2))
    except Exception:
        print("\n[-] Respon Mentah dari Server:")
        print(res_submit.text)

if __name__ == "__main__":
    submit_skytrax_survey()
