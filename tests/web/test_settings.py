import unittest
from pathlib import Path

from services.simulator_api.settings import Settings, SettingsError


ROOT = Path(__file__).resolve().parents[2]


class SettingsTests(unittest.TestCase):
    def env(self, **overrides):
        values = {
            "APP_ENV": "development",
            "AUTH_MODE": "local",
            "APP_ORIGIN": "http://127.0.0.1:3000",
            "SIMULATOR_API_URL": "http://127.0.0.1:8000",
            "DATA_DIR": str(ROOT / ".local" / "dicer-web"),
            "PORT": "8000",
            "API_HOST": "127.0.0.1",
            "WEB_RELEASE": "local",
            "LOG_LEVEL": "INFO",
        }
        values.update(overrides)
        return values

    def test_local_settings_are_explicit_and_loopback_only(self):
        settings = Settings.from_env(self.env())
        self.assertEqual(settings.auth_mode, "local")
        self.assertEqual(settings.api_host, "127.0.0.1")
        self.assertEqual(settings.port, 8000)
        self.assertFalse(settings.allowed_user_ids)

    def test_local_auth_is_rejected_in_production_or_on_hosted_platform(self):
        for changes in (
            {"APP_ENV": "production"},
            {"RENDER": "true"},
            {"VERCEL": "1"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SettingsError):
                Settings.from_env(self.env(**changes))

    def test_local_mode_refuses_public_bind_and_non_loopback_origin(self):
        for changes in (
            {"API_HOST": "0.0.0.0"},
            {"APP_ORIGIN": "http://192.168.1.10:3000"},
            {"SIMULATOR_API_URL": "https://api.example.org"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SettingsError):
                Settings.from_env(self.env(**changes))

    def test_port_and_data_directory_are_validated(self):
        for changes in (
            {"PORT": "0"},
            {"PORT": "not-a-port"},
            {"DATA_DIR": ""},
            {"DATA_DIR": "relative/path"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SettingsError):
                Settings.from_env(self.env(**changes))

    def test_production_requires_supabase_and_authorized_user_ids(self):
        production = self.env(
            APP_ENV="production",
            AUTH_MODE="supabase",
            APP_ORIGIN="https://lab.example.org",
            SIMULATOR_API_URL="https://api.example.org",
            API_HOST="0.0.0.0",
            SUPABASE_URL="https://example.supabase.co",
            ALLOWED_USER_IDS="b8a92c84-fbd6-4f76-b2f4-0a6f58948799",
            SUPABASE_JWT_ALGORITHMS="ES256",
        )
        settings = Settings.from_env(production)
        self.assertEqual(len(settings.allowed_user_ids), 1)
        for changes in (
            {"SUPABASE_URL": ""},
            {"ALLOWED_USER_IDS": ""},
            {"ALLOWED_USER_IDS": "not-a-uuid"},
            {"SUPABASE_JWT_ALGORITHMS": "none"},
        ):
            invalid = dict(production)
            invalid.update(changes)
            with self.subTest(changes=changes), self.assertRaises(SettingsError):
                Settings.from_env(invalid)

    def test_settings_do_not_parse_users_from_request_headers(self):
        settings = Settings.from_env(self.env())
        self.assertFalse(hasattr(settings, "user_id"))


if __name__ == "__main__":
    unittest.main()
