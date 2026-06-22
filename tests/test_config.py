from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import ROOT, import_api


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="apm-config-")
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pyproject_declares_python_39_minimum(self) -> None:
        pyproject = ROOT / "pyproject.toml"
        self.assertTrue(pyproject.is_file(), "pyproject.toml must exist")
        text = pyproject.read_text(encoding="utf-8")
        self.assertIn('requires-python = ">=3.9"', text)

    def test_defaults_are_safe_and_typed(self) -> None:
        config_mod = import_api("agent_project_memory.config")
        result = config_mod.load_config(self.root / "missing.toml")

        self.assertEqual(result.diagnostics, ())
        self.assertEqual(result.config.trusted_roots, ())
        self.assertTrue(result.config.denied_roots)
        self.assertIn(".git", result.config.project_markers)
        self.assertGreater(result.config.max_total_bytes, result.config.max_file_bytes)
        self.assertGreaterEqual(result.config.feedback_promotion_threshold, 2)
        self.assertIsInstance(result.config.hard_fail_checks, tuple)
        self.assertIsInstance(result.config.warning_checks, tuple)

    def test_valid_configuration_loads_all_supported_fields(self) -> None:
        config_mod = import_api("agent_project_memory.config")
        trusted = self.root / "projects"
        denied = trusted / "blocked"
        config_path = self.root / "config.toml"
        config_path.write_text(
            "\n".join(
                [
                    f'trusted_roots = ["{trusted}"]',
                    f'denied_roots = ["{denied}"]',
                    'project_markers = [".git", "pyproject.toml"]',
                    "max_file_bytes = 2048",
                    "max_total_bytes = 8192",
                    "checkpoint_debounce_seconds = 9",
                    "checkpoint_retention = 7",
                    "prompt_excerpt_bytes = 128",
                    "feedback_promotion_threshold = 3",
                    "log_max_bytes = 4096",
                    'hard_fail_checks = ["privacy", "state"]',
                    'warning_checks = ["docs"]',
                ]
            ),
            encoding="utf-8",
        )

        result = config_mod.load_config(config_path)

        self.assertEqual(result.diagnostics, ())
        self.assertEqual(result.config.trusted_roots, (trusted.resolve(),))
        self.assertEqual(result.config.denied_roots[-1], denied.resolve())
        self.assertEqual(result.config.project_markers, (".git", "pyproject.toml"))
        self.assertEqual(result.config.max_file_bytes, 2048)
        self.assertEqual(result.config.max_total_bytes, 8192)
        self.assertEqual(result.config.checkpoint_debounce_seconds, 9)
        self.assertEqual(result.config.checkpoint_retention, 7)
        self.assertEqual(result.config.prompt_excerpt_bytes, 128)
        self.assertEqual(result.config.feedback_promotion_threshold, 3)
        self.assertEqual(result.config.log_max_bytes, 4096)
        self.assertEqual(result.config.hard_fail_checks, ("privacy", "state"))
        self.assertEqual(result.config.warning_checks, ("docs",))

    def test_damaged_configuration_fails_open_without_echoing_content(self) -> None:
        config_mod = import_api("agent_project_memory.config")
        config_path = self.root / "config.toml"
        marker = "DO_NOT_ECHO_THIS_VALUE"
        config_path.write_text(f'trusted_roots = ["{marker}"\n', encoding="utf-8")

        result = config_mod.load_config(config_path)

        self.assertEqual(result.config, config_mod.Config.defaults())
        self.assertEqual(len(result.diagnostics), 1)
        self.assertIn("invalid configuration", result.diagnostics[0])
        self.assertNotIn(marker, result.diagnostics[0])

    def test_unknown_field_and_wrong_type_fail_open(self) -> None:
        config_mod = import_api("agent_project_memory.config")
        for text in ("unknown_option = 1", 'max_file_bytes = "large"'):
            with self.subTest(text=text):
                config_path = self.root / "config.toml"
                config_path.write_text(text, encoding="utf-8")
                result = config_mod.load_config(config_path)
                self.assertEqual(result.config, config_mod.Config.defaults())
                self.assertEqual(result.diagnostics, ("invalid configuration; using safe defaults",))

    def test_unsafe_numeric_relationships_fail_open(self) -> None:
        config_mod = import_api("agent_project_memory.config")
        cases = (
            "feedback_promotion_threshold = 1",
            "max_file_bytes = 4096\nmax_total_bytes = 1024",
        )
        for text in cases:
            with self.subTest(text=text):
                config_path = self.root / "config.toml"
                config_path.write_text(text, encoding="utf-8")
                result = config_mod.load_config(config_path)
                self.assertEqual(result.config, config_mod.Config.defaults())
                self.assertEqual(
                    result.diagnostics,
                    ("invalid configuration; using safe defaults",),
                )

    def test_unreadable_configuration_fails_open(self) -> None:
        config_mod = import_api("agent_project_memory.config")
        config_path = self.root / "config.toml"
        config_path.write_text("max_file_bytes = 1", encoding="utf-8")
        with mock.patch.object(Path, "read_bytes", side_effect=PermissionError("private-value")):
            result = config_mod.load_config(config_path)

        self.assertEqual(result.config, config_mod.Config.defaults())
        self.assertEqual(result.diagnostics, ("configuration unreadable; using safe defaults",))
        self.assertNotIn("private-value", result.diagnostics[0])

    def test_dangerous_roots_are_filtered_and_denied_roots_win(self) -> None:
        config_mod = import_api("agent_project_memory.config")
        home = Path.home().resolve()
        safe = self.root / "safe"
        denied = safe / "private"
        config_path = self.root / "config.toml"
        config_path.write_text(
            "\n".join(
                [
                    "trusted_roots = [",
                    f'  "{Path(os.sep)}",',
                    f'  "{home}",',
                    '  "/Users",',
                    f'  "{home / ".codex"}",',
                    f'  "{safe}",',
                    f'  "{denied}"',
                    "]",
                    f'denied_roots = ["{denied}"]',
                ]
            ),
            encoding="utf-8",
        )

        result = config_mod.load_config(config_path)

        self.assertEqual(result.config.trusted_roots, (safe.resolve(),))
        self.assertIn(denied.resolve(), result.config.denied_roots)
        joined = " ".join(result.diagnostics)
        self.assertNotIn(str(home), joined)
        self.assertNotIn(str(safe), joined)
        self.assertIn("unsafe or denied trusted roots ignored", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
