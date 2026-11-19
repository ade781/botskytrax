"""
Unit & Integration Tests untuk Bot Skytrax Dynamic Email Generator & Batch Processing.
Menjalankan pengujian otomatis menggunakan unittest dan mock server lokal.
"""

import unittest
from email_generator import (
    generate_dynamic_emails,
    validate_email_format,
    filter_and_deduplicate_emails,
)
from mock_server import MockSurveyServer, MockSurveyHTTPHandler
from submit_survey import (
    submit_single_survey_request,
    batch_process_surveys,
    build_form_payload,
)


class TestDynamicEmailGenerator(unittest.TestCase):
    """Pengujian pembentukan email dinamis dan validasi pola."""

    def test_generator_exact_100_emails(self):
        """Memastikan generator menghasilkan tepat 100 email sesuai pola."""
        emails = generate_dynamic_emails(count=100)

        # 1. Jumlah tepat 100
        self.assertEqual(len(emails), 100, "Jumlah email harus tepat 100")

        # 2. Email pertama dan terakhir sesuai pola
        self.assertEqual(emails[0], "ade1asli@gmail.com")
        self.assertEqual(emails[1], "ade2asli@gmail.com")
        self.assertEqual(emails[2], "ade3asli@gmail.com")
        self.assertEqual(emails[99], "ade100asli@gmail.com")

        # 3. Semua email unik
        self.assertEqual(len(set(emails)), 100, "Semua email harus unik")

        # 4. Setiap elemen sesuai pola ade{i}asli@gmail.com
        for i, email in enumerate(emails, start=1):
            expected = f"ade{i}asli@gmail.com"
            self.assertEqual(email, expected)

    def test_generator_custom_configuration(self):
        """Memastikan generator dapat dikonfigurasi dengan fleksibel (prefix, suffix, domain, count)."""
        custom_emails = generate_dynamic_emails(
            count=5,
            prefix="tester",
            suffix="survey",
            domain="example.org",
            start_index=10
        )
        self.assertEqual(len(custom_emails), 5)
        self.assertEqual(custom_emails[0], "tester10survey@example.org")
        self.assertEqual(custom_emails[-1], "tester14survey@example.org")

    def test_validate_email_format(self):
        """Memastikan fungsi validasi format email bekerja dengan akurat."""
        valid_samples = [
            "ade1asli@gmail.com",
            "user.name+tag@sub.domain.co.id",
            "test_123@company.com"
        ]
        invalid_samples = [
            "ade1asli",
            "ade1asli@",
            "@gmail.com",
            "ade asli@gmail.com",
            "ade@gmail",
            "",
            None
        ]

        for email in valid_samples:
            self.assertTrue(validate_email_format(email), f"Harusnya valid: {email}")

        for email in invalid_samples:
            self.assertFalse(validate_email_format(email), f"Harusnya invalid: {email}")

    def test_filter_and_deduplicate(self):
        """Memastikan filter memisahkan email unik, duplikat, dan invalid."""
        raw_list = [
            "ade1asli@gmail.com",
            "ade2asli@gmail.com",
            "ade1asli@gmail.com",       # Duplikat
            "invalid-email-format",     # Invalid
            "ade3asli@gmail.com",
            "ADE2ASLI@GMAIL.COM",       # Duplikat case-insensitive
            "   "                       # Invalid
        ]

        valid_unique, duplicates, invalid = filter_and_deduplicate_emails(raw_list)

        self.assertEqual(valid_unique, ["ade1asli@gmail.com", "ade2asli@gmail.com", "ade3asli@gmail.com"])
        self.assertEqual(len(duplicates), 2)
        self.assertEqual(len(invalid), 2)


class TestBatchProcessingIntegration(unittest.TestCase):
    """Pengujian integrasi batch processing dengan Mock Server lokal."""

    @classmethod
    def setUpClass(cls):
        cls.mock_server = MockSurveyServer()
        cls.mock_server.start()

    @classmethod
    def tearDownClass(cls):
        cls.mock_server.stop()

    def setUp(self):
        MockSurveyHTTPHandler.received_submissions.clear()

    def test_single_survey_submission_mock(self):
        """Memastikan pengiriman survei tunggal berjalan lancar pada mock server."""
        email = "ade1asli@gmail.com"
        result = submit_single_survey_request(
            email=email,
            base_url=self.mock_server.base_url
        )

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("status"), "SUCCESS")
        self.assertEqual(result.get("email"), email)
        self.assertIn("MOCK-", result.get("auto_id"))

    def test_batch_process_100_emails(self):
        """Memastikan batch processing 100 email sukses diproses sepenuhnya."""
        emails = generate_dynamic_emails(count=100)

        summary = batch_process_surveys(
            emails=emails,
            base_url=self.mock_server.base_url,
            delay_between_requests=0.0,
            fresh_session_per_item=True,
            log_to_file=False,
            verbose_log=False
        )

        self.assertEqual(summary["total_input"], 100)
        self.assertEqual(summary["valid_unique"], 100)
        self.assertEqual(summary["attempted"], 100)
        self.assertEqual(summary["success_count"], 100)
        self.assertEqual(summary["failed_count"], 0)
        self.assertEqual(summary["duplicates_count"], 0)
        self.assertEqual(summary["invalid_format_count"], 0)
        self.assertEqual(summary["success_rate_percent"], 100.0)

        # Verifikasi data yang diterima mock server
        self.assertEqual(len(MockSurveyHTTPHandler.received_submissions), 100)
        first_sub = MockSurveyHTTPHandler.received_submissions[0]
        last_sub = MockSurveyHTTPHandler.received_submissions[-1]

        self.assertEqual(first_sub.get("f2"), "ade1asli@gmail.com")
        self.assertEqual(last_sub.get("f2"), "ade100asli@gmail.com")

    def test_individual_error_handling(self):
        """
        Memastikan error pada satu email tidak menghentikan pemrosesan email lainnya.
        Simulasi:
        - 1 email valid normal
        - 1 email memicu HTTP 500 error
        - 1 email format invalid
        - 1 email duplikat
        - 1 email memicu validasi server gagal
        - 1 email valid normal berikutnya
        """
        test_emails = [
            "ade1asli@gmail.com",
            "simulate_error_item@gmail.com",     # HTTP 500
            "email_rusak_tanpa_domain",          # Invalid format
            "ade1asli@gmail.com",                # Duplikat
            "simulate_validation_fail@gmail.com", # Validasi gagal
            "ade2asli@gmail.com"                 # Tetap diproses & berhasil
        ]

        summary = batch_process_surveys(
            emails=test_emails,
            base_url=self.mock_server.base_url,
            delay_between_requests=0.0,
            fresh_session_per_item=True,
            log_to_file=False,
            verbose_log=False
        )

        self.assertEqual(summary["total_input"], 6)
        self.assertEqual(summary["invalid_format_count"], 1)
        self.assertEqual(summary["duplicates_count"], 1)
        self.assertEqual(summary["attempted"], 4)
        # 2 berhasil: ade1asli@gmail.com dan ade2asli@gmail.com
        self.assertEqual(summary["success_count"], 2)
        # 2 gagal: simulate_error_item (500) dan simulate_validation_fail
        self.assertEqual(summary["failed_count"], 2)
        self.assertEqual(summary["success_rate_percent"], 50.0)


if __name__ == "__main__":
    unittest.main()
