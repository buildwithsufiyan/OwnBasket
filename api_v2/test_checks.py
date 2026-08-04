from cryptography.fernet import Fernet
from django.test import SimpleTestCase, override_settings

from api_v2.checks import mobile_api_security_checks


VALID_KEY = Fernet.generate_key().decode()

BASE_SETTINGS = {
    "IS_PRODUCTION": False,
    "MOBILE_TOKEN_ENCRYPTION_KEY": VALID_KEY,
    "MOBILE_ACCESS_TOKEN_MINUTES": 15,
    "MOBILE_REFRESH_TOKEN_DAYS": 30,
    "MOBILE_SESSION_MAX_DAYS": 90,
}


def run_checks(**overrides):
    with override_settings(**{**BASE_SETTINGS, **overrides}):
        return [message.id for message in mobile_api_security_checks(None)]


class MobileApiSecurityChecksTests(SimpleTestCase):
    def test_valid_configuration_reports_nothing(self):
        self.assertEqual(run_checks(), [])

    def test_development_without_key_warns(self):
        self.assertEqual(run_checks(MOBILE_TOKEN_ENCRYPTION_KEY=""), ["api_v2.W001"])

    def test_production_requires_valid_fernet_key(self):
        self.assertEqual(
            run_checks(IS_PRODUCTION=True, MOBILE_TOKEN_ENCRYPTION_KEY="not-a-key"),
            ["api_v2.E001"],
        )

    def test_production_accepts_valid_fernet_key(self):
        self.assertEqual(run_checks(IS_PRODUCTION=True), [])

    def test_access_token_minutes_bounds(self):
        self.assertEqual(run_checks(MOBILE_ACCESS_TOKEN_MINUTES=4), ["api_v2.E002"])
        self.assertEqual(run_checks(MOBILE_ACCESS_TOKEN_MINUTES=61), ["api_v2.E002"])
        self.assertEqual(run_checks(MOBILE_ACCESS_TOKEN_MINUTES=5), [])
        self.assertEqual(run_checks(MOBILE_ACCESS_TOKEN_MINUTES=60), [])

    def test_refresh_token_days_bounds(self):
        self.assertEqual(
            run_checks(MOBILE_REFRESH_TOKEN_DAYS=0), ["api_v2.E003"]
        )
        self.assertEqual(
            run_checks(MOBILE_REFRESH_TOKEN_DAYS=91, MOBILE_SESSION_MAX_DAYS=91),
            ["api_v2.E003"],
        )

    def test_session_max_days_must_span_refresh_expiry(self):
        self.assertEqual(
            run_checks(MOBILE_REFRESH_TOKEN_DAYS=30, MOBILE_SESSION_MAX_DAYS=20),
            ["api_v2.E004"],
        )
        self.assertEqual(run_checks(MOBILE_SESSION_MAX_DAYS=366), ["api_v2.E004"])

    def test_multiple_problems_are_reported_together(self):
        self.assertEqual(
            run_checks(
                MOBILE_TOKEN_ENCRYPTION_KEY="",
                MOBILE_ACCESS_TOKEN_MINUTES=1,
                MOBILE_REFRESH_TOKEN_DAYS=0,
                MOBILE_SESSION_MAX_DAYS=0,
            ),
            ["api_v2.W001", "api_v2.E002", "api_v2.E003"],
        )
