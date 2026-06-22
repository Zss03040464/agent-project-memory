from __future__ import annotations

import unittest
from pathlib import Path

from tests.helpers import import_api


class PrivacyTests(unittest.TestCase):
    def test_sensitive_path_classification_covers_state_and_credentials(self) -> None:
        privacy = import_api("agent_project_memory.privacy")
        cases = {
            Path("/tmp/auth.json"): "auth_file",
            Path("/tmp/.env.production"): "environment_file",
            Path("/tmp/id_rsa"): "private_key_file",
            Path("/tmp/client-cert.pem"): "certificate_file",
            Path("/tmp/Chrome/Default/Cookies"): "browser_state",
        }

        for path, expected_category in cases.items():
            with self.subTest(path=path.name):
                result = privacy.classify_sensitive_path(path)
                self.assertTrue(result.is_sensitive)
                self.assertIn(expected_category, result.categories)
                self.assertNotIn(str(path), repr(result))

        self.assertFalse(
            privacy.classify_sensitive_path(Path("/tmp/project/README.md")).is_sensitive
        )

    def test_text_scan_returns_categories_without_matched_values(self) -> None:
        privacy = import_api("agent_project_memory.privacy")
        values = [
            "-----BEGIN " + "PRIVATE KEY-----",
            "-----BEGIN " + "CERTIFICATE-----",
            "sk-" + ("A" * 24),
            "ghp_" + ("B" * 24),
            "AKIA" + ("C" * 16),
            "Authorization: Bearer example-value",
            "Cookie: session=example-value",
            "password = example-value",
            "api_key: example-value",
        ]

        result = privacy.scan_sensitive_text("\n".join(values))

        self.assertTrue(result.is_sensitive)
        self.assertTrue(
            {
                "private_key",
                "certificate",
                "openai_token",
                "github_token",
                "aws_access_key",
                "authorization_header",
                "cookie_header",
                "secret_assignment",
            }.issubset(set(result.categories))
        )
        rendered = repr(result)
        for value in values:
            self.assertNotIn(value, rendered)

    def test_prompt_summary_is_redacted_digest_backed_and_byte_bounded(self) -> None:
        privacy = import_api("agent_project_memory.privacy")
        secret = "sk-" + ("Z" * 32)
        prompt = ("Summarize safely. " * 20) + f" token={secret}"

        result = privacy.summarize_prompt(prompt, max_bytes=96)

        self.assertLessEqual(len(result.excerpt.encode("utf-8")), 96)
        self.assertNotIn(secret, result.excerpt)
        self.assertNotIn(secret, repr(result))
        self.assertEqual(len(result.digest), 64)
        self.assertTrue(result.redacted)
        self.assertTrue(result.truncated)

    def test_environment_style_secret_assignments_are_detected(self) -> None:
        privacy = import_api("agent_project_memory.privacy")
        text = "\n".join(
            [
                "OPENAI_API_KEY=example-value",
                "AWS_SECRET_ACCESS_KEY=example-value",
                "GITHUB_TOKEN=example-value",
            ]
        )

        result = privacy.scan_sensitive_text(text)

        self.assertTrue(result.is_sensitive)
        self.assertIn("secret_assignment", result.categories)

    def test_reviewed_secret_formats_are_digest_only_and_fully_redacted(self) -> None:
        privacy = import_api("agent_project_memory.privacy")
        secrets = (
            "github_" + "pat_" + ("A" * 24),
            "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----",
            "COOKIE=private-session-value",
        )

        for secret in secrets:
            with self.subTest(kind=secret.split("=", 1)[0][:20]):
                scan = privacy.scan_sensitive_text(secret)
                summary = privacy.summarize_prompt(
                    "before " + secret + " after", max_bytes=256
                )

                self.assertTrue(scan.is_sensitive)
                self.assertTrue(privacy.is_digest_only(text=secret))
                self.assertTrue(summary.redacted)
                self.assertNotIn(secret, summary.excerpt)
                self.assertNotIn(secret, repr(scan))
                self.assertNotIn(secret, repr(summary))

    def test_encrypted_private_key_body_is_not_retained_in_excerpt(self) -> None:
        privacy = import_api("agent_project_memory.privacy")
        body = "PRIVATE-BODY-MARKER"
        pem = "\n".join(
            [
                "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----",
                body,
                "-----END " + "ENCRYPTED PRIVATE KEY-----",
            ]
        )

        summary = privacy.summarize_prompt(
            "before\n" + pem + "\nafter", max_bytes=512
        )

        self.assertTrue(summary.redacted)
        self.assertNotIn(body, summary.excerpt)
        self.assertNotIn(body, repr(summary))

    def test_digest_only_is_selected_for_sensitive_paths_or_content(self) -> None:
        privacy = import_api("agent_project_memory.privacy")
        secret_header = "-----BEGIN " + "PRIVATE KEY-----"

        self.assertTrue(privacy.is_digest_only(path=Path("/tmp/.env")))
        self.assertTrue(privacy.is_digest_only(text=secret_header))
        self.assertFalse(
            privacy.is_digest_only(
                path=Path("/tmp/project/notes.md"), text="ordinary project note"
            )
        )

    def test_unicode_prompt_truncation_never_splits_a_character(self) -> None:
        privacy = import_api("agent_project_memory.privacy")

        result = privacy.summarize_prompt("你好世界" * 20, max_bytes=17)

        self.assertLessEqual(len(result.excerpt.encode("utf-8")), 17)
        result.excerpt.encode("utf-8").decode("utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
