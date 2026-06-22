from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("apm_privacy_scan", ROOT / "scripts" / "privacy_scan.py")
assert SPEC and SPEC.loader
privacy_scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(privacy_scan)


class PrivacyScanScriptTests(unittest.TestCase):
    def test_scans_html_json_and_common_configuration_without_echoing_value(self) -> None:
        with tempfile.TemporaryDirectory(prefix="apm-secret-scan-") as raw:
            root = Path(raw)
            secret = "gh" + "p_" + "A" * 24
            (root / "page.html").write_text(f"<meta content='{secret}'>", encoding="utf-8")
            (root / "settings.json").write_text(json.dumps({"token": secret}), encoding="utf-8")
            (root / "tool.toml").write_text(f'token = "{secret}"\n', encoding="utf-8")
            findings = privacy_scan.scan_root(root)
            self.assertEqual({item.category for item in findings}, {"github_token"})
            output = io.StringIO()
            with redirect_stdout(output):
                privacy_scan.print_findings(findings)
            self.assertNotIn(secret, output.getvalue())

    def test_scans_archive_member_names_and_text_without_extracting(self) -> None:
        with tempfile.TemporaryDirectory(prefix="apm-archive-scan-") as raw:
            root = Path(raw)
            archive = root / "bundle.zip"
            secret = "sk-" + "B" * 24
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("nested/.env.production", "safe")
                handle.writestr("nested/readme.json", json.dumps({"key": secret}))
            findings = privacy_scan.scan_root(root)
            categories = {item.category for item in findings}
            self.assertIn("sensitive_archive_member", categories)
            self.assertIn("openai_key", categories)
            self.assertFalse((root / "nested").exists())

    def test_scans_binary_metadata_but_reports_only_category(self) -> None:
        with tempfile.TemporaryDirectory(prefix="apm-binary-scan-") as raw:
            root = Path(raw)
            secret = "AKIA" + "C" * 16
            (root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\nmetadata=" + secret.encode())
            findings = privacy_scan.scan_root(root)
            self.assertIn("aws_key", {item.category for item in findings})
            self.assertNotIn(secret, repr(findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
