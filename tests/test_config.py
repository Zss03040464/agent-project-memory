from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import PurePosixPath, PureWindowsPath
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

    def test_sync_and_volume_broad_roots_are_rejected_but_projects_are_allowed(
        self,
    ) -> None:
        config_mod = import_api("agent_project_memory.config")
        fake_home = self.root / "home"
        dropbox = fake_home / "Dropbox"
        mobile_documents = fake_home / "Library" / "Mobile Documents"
        cloud_drive = mobile_documents / "com~apple~CloudDocs"
        dropbox_project = dropbox / "work" / "project"
        cloud_project = cloud_drive / "work" / "project"
        alias = self.root / "dropbox-alias"
        for path in (dropbox_project, cloud_project):
            path.mkdir(parents=True)
            (path / ".git").mkdir()
        alias.symlink_to(dropbox, target_is_directory=True)
        volume_root = Path("/Volumes/ExternalDisk")
        volume_project = volume_root / "work" / "project"
        config_path = self.root / "config.toml"
        config_path.write_text(
            "\n".join(
                [
                    "trusted_roots = [",
                    f'  "{dropbox}",',
                    f'  "{alias}",',
                    f'  "{mobile_documents}",',
                    f'  "{cloud_drive}",',
                    '  "/Volumes",',
                    f'  "{volume_root}",',
                    f'  "{dropbox_project}",',
                    f'  "{cloud_project}",',
                    f'  "{volume_project}"',
                    "]",
                ]
            ),
            encoding="utf-8",
        )

        with mock.patch.object(Path, "home", return_value=fake_home):
            result = config_mod.load_config(config_path)

        self.assertEqual(
            result.config.trusted_roots,
            (
                dropbox_project.resolve(),
                cloud_project.resolve(),
            ),
        )
        self.assertEqual(
            result.diagnostics, ("unsafe or denied trusted roots ignored",)
        )

    def test_sync_root_families_require_marked_project_candidates(self) -> None:
        config_mod = import_api("agent_project_memory.config")
        fake_home = self.root / "home"
        cloud_storage = fake_home / "Library" / "CloudStorage"
        providers = (
            cloud_storage / "OneDrive-Personal",
            cloud_storage / "GoogleDrive-example",
            fake_home / "OneDrive",
            fake_home / "Dropbox",
        )
        broad_candidates = [cloud_storage]
        allowed_projects = []
        for provider in providers:
            provider.mkdir(parents=True)
            broad_candidates.extend((provider, provider / "project"))
            project = provider / "work" / "project"
            project.mkdir(parents=True)
            (project / ".git").mkdir()
            allowed_projects.append(project.resolve())
        volume = Path("/Volumes/ExternalDisk")
        broad_candidates.extend((Path("/Volumes"), volume, volume / "project"))
        alias = self.root / "cloud-provider-alias"
        alias.symlink_to(providers[0], target_is_directory=True)
        broad_candidates.append(alias)

        config_path = self.root / "config.toml"
        configured = broad_candidates + [
            provider / "work" / "project" for provider in providers
        ] + [volume / "work" / "project"]
        config_path.write_text(
            "trusted_roots = [\n"
            + ",\n".join(f'  "{path}"' for path in configured)
            + "\n]",
            encoding="utf-8",
        )

        with mock.patch.object(Path, "home", return_value=fake_home):
            result = config_mod.load_config(config_path)

        self.assertEqual(result.config.trusted_roots, tuple(allowed_projects))
        self.assertEqual(
            result.diagnostics, ("unsafe or denied trusted roots ignored",)
        )

    def test_strict_toml_subset_supports_literal_basic_integer_and_boolean(
        self,
    ) -> None:
        config_mod = import_api("agent_project_memory.config")

        parsed = config_mod.parse_toml_subset(
            "\n".join(
                [
                    r"literal = 'C:\Users\Example\Projects'",
                    r'basic = "line\nquote:\" unicode:\u4F60"',
                    "integer = 1_024",
                    "enabled = true",
                    r'''array = ['one', "two\tvalue"]''',
                ]
            ).encode("utf-8")
        )

        self.assertEqual(parsed["literal"], r"C:\Users\Example\Projects")
        self.assertEqual(parsed["basic"], 'line\nquote:" unicode:你')
        self.assertEqual(parsed["integer"], 1024)
        self.assertIs(parsed["enabled"], True)
        self.assertEqual(parsed["array"], ["one", "two\tvalue"])

    def test_invalid_toml_and_relative_roots_fail_open_independent_of_cwd(
        self,
    ) -> None:
        config_mod = import_api("agent_project_memory.config")
        cases = (
            r'project_markers = ["bad\qescape"]',
            'trusted_roots = ["relative/project"]',
            'denied_roots = ["../relative"]',
        )
        other_cwd = self.root / "other-cwd"
        other_cwd.mkdir()
        for text in cases:
            with self.subTest(text=text):
                config_path = self.root / "config.toml"
                config_path.write_text(text, encoding="utf-8")
                with mock.patch.object(Path, "cwd", return_value=other_cwd):
                    result = config_mod.load_config(config_path)
                self.assertEqual(result.config, config_mod.Config.defaults())
                self.assertEqual(
                    result.diagnostics,
                    ("invalid configuration; using safe defaults",),
                )

    def test_symlink_loop_in_configured_root_fails_open_without_path_leak(
        self,
    ) -> None:
        config_mod = import_api("agent_project_memory.config")
        first = self.root / "PRIVATE-FIRST"
        second = self.root / "PRIVATE-SECOND"
        first.symlink_to(second)
        second.symlink_to(first)
        config_path = self.root / "config.toml"
        config_path.write_text(
            f'trusted_roots = ["{first}"]', encoding="utf-8"
        )

        result = config_mod.load_config(config_path)

        self.assertEqual(result.config, config_mod.Config.defaults())
        self.assertEqual(
            result.diagnostics, ("invalid configuration; using safe defaults",)
        )
        self.assertNotIn("PRIVATE", " ".join(result.diagnostics))

    def test_root_classification_is_cross_platform_and_marker_aware(self) -> None:
        config_mod = import_api("agent_project_memory.config")
        posix_home = PurePosixPath("/home/alice")
        windows_home = PureWindowsPath(r"C:\Users\Alice")
        dangerous = (
            (PurePosixPath("/"), posix_home),
            (PurePosixPath("/home"), posix_home),
            (PurePosixPath("/Users"), PurePosixPath("/Users/alice")),
            (posix_home, posix_home),
            (PureWindowsPath("C:\\"), windows_home),
            (PureWindowsPath(r"C:\Users"), windows_home),
            (windows_home, windows_home),
        )
        for candidate, home in dangerous:
            with self.subTest(candidate=str(candidate)):
                self.assertTrue(
                    config_mod.classify_root(candidate, home=home).is_dangerous
                )

        sync_project = PureWindowsPath(
            r"C:\Users\Alice\OneDrive\work\project"
        )
        without_marker = config_mod.classify_root(
            sync_project, home=windows_home, has_project_marker=False
        )
        with_marker = config_mod.classify_root(
            sync_project, home=windows_home, has_project_marker=True
        )
        self.assertTrue(without_marker.is_dangerous)
        self.assertTrue(without_marker.requires_project_marker)
        self.assertFalse(with_marker.is_dangerous)

    def test_sync_provider_deep_directory_requires_project_marker(self) -> None:
        config_mod = import_api("agent_project_memory.config")
        fake_home = self.root / "home"
        provider = fake_home / "Library" / "CloudStorage" / "Provider"
        unmarked = provider / "deep" / "unmarked"
        marked = provider / "deep" / "marked"
        unmarked.mkdir(parents=True)
        marked.mkdir(parents=True)
        (marked / ".git").mkdir()
        config_path = self.root / "config.toml"
        config_path.write_text(
            "\n".join(
                [
                    f'trusted_roots = ["{unmarked}", "{marked}"]',
                    'project_markers = [".git"]',
                ]
            ),
            encoding="utf-8",
        )

        with mock.patch.object(Path, "home", return_value=fake_home):
            result = config_mod.load_config(config_path)

        self.assertEqual(result.config.trusted_roots, (marked.resolve(),))


if __name__ == "__main__":
    unittest.main(verbosity=2)
