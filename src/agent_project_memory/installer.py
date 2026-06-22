"""Transactional, cross-platform installer used by thin shell wrappers."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PLUGIN_NAME = "agent-project-memory"
PLUGIN_ID = "agent-project-memory@personal"
BEGIN = "<!-- BEGIN AGENT_PROJECT_MEMORY_RULES -->"
END = "<!-- END AGENT_PROJECT_MEMORY_RULES -->"


@dataclass(frozen=True)
class Layout:
    repo_root: Path
    target: Path
    home: Path

    @property
    def plugin_source(self) -> Path:
        return self.home / "plugins" / PLUGIN_NAME

    @property
    def marketplace(self) -> Path:
        return self.home / ".agents" / "plugins" / "marketplace.json"

    @property
    def plugin_cache(self) -> Path:
        return self.target / "plugins" / "cache" / "personal" / PLUGIN_NAME

    @property
    def state_file(self) -> Path:
        return self.target / PLUGIN_NAME / "install-state.json"

    @property
    def backup_root(self) -> Path:
        return self.target / "backups" / PLUGIN_NAME


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def _atomic_text(path: Path, text: str, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old_mode = path.stat().st_mode & 0o777 if path.exists() else mode
    handle, raw = tempfile.mkstemp(prefix=".apm-", dir=str(path.parent))
    temporary = Path(raw)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, old_mode)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _json_write(path: Path, value: Any) -> None:
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _copy_item(source: Path, destination: Path) -> None:
    if source.is_dir() and not source.is_symlink():
        shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)


def _remove_item(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


class Snapshot:
    def __init__(self, paths: Iterable[Path]) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="apm-install-transaction-"))
        self.entries: List[Dict[str, Any]] = []
        unique = _without_overlaps(paths)
        for index, path in enumerate(unique):
            absolute = path.resolve(strict=False)
            entry: Dict[str, Any] = {
                "path": str(absolute),
                "existed": path.exists() or path.is_symlink(),
                "snapshot": None,
            }
            if entry["existed"]:
                snapshot_name = "item-{:03d}-{}".format(
                    index,
                    hashlib.sha256(str(absolute).encode("utf-8")).hexdigest()[:12],
                )
                destination = self.root / "payload" / snapshot_name
                _copy_item(path, destination)
                entry["snapshot"] = "payload/" + snapshot_name
            self.entries.append(entry)

    def restore(self, allowed_roots: Tuple[Path, ...]) -> None:
        _restore_entries(self.root, self.entries, allowed_roots)

    def persist(self, destination: Path, operation: str, full_backup: bool) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "operation": operation,
            "full_backup": full_backup,
            "entries": self.entries,
        }
        _json_write(self.root / "manifest.json", manifest)
        os.replace(self.root, destination)
        self.root = destination
        return destination

    def discard(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def _without_overlaps(paths: Iterable[Path]) -> Tuple[Path, ...]:
    result: List[Path] = []
    for path in sorted({item.resolve(strict=False) for item in paths}, key=lambda p: len(p.parts)):
        if any(path == parent or parent in path.parents for parent in result):
            continue
        result.append(path)
    return tuple(result)


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _restore_entries(
    snapshot_root: Path,
    entries: Iterable[Dict[str, Any]],
    allowed_roots: Tuple[Path, ...],
) -> None:
    for entry in entries:
        path = Path(str(entry["path"]))
        if not any(_under(path, root) for root in allowed_roots):
            raise RuntimeError("backup contains a path outside the installation roots")
        if path.exists() or path.is_symlink():
            _remove_item(path)
        if entry.get("existed"):
            source = snapshot_root / str(entry["snapshot"])
            _copy_item(source, path)


def _managed_paths(layout: Layout, full_backup: bool) -> Tuple[Path, ...]:
    paths = [
        layout.target / "AGENTS.md",
        layout.target / "PROJECT_MEMORY_RULES_TO_ADD.md",
        layout.target / "config.toml",
        layout.target / "hooks.json",
        layout.target / "bin" / "agent-project-memory",
        layout.target / "bin" / "agent-project-memory.cmd",
        layout.target / "continuity" / "config.toml",
        layout.state_file,
        layout.plugin_cache,
        layout.plugin_source,
        layout.marketplace,
    ]
    if full_backup:
        paths.extend((layout.target / "project_memory", layout.target / "continuity"))
    return _without_overlaps(paths)


def _confirm(args: argparse.Namespace, operation: str, target: Path) -> None:
    if args.yes or args.dry_run:
        return
    reply = input("{} Agent Project Memory in {}? [y/N] ".format(operation.title(), target))
    if reply not in ("y", "Y", "yes", "YES"):
        raise SystemExit("Cancelled.")


def _copy_templates(layout: Layout, force: bool) -> None:
    source = layout.repo_root / "skills" / "project-memory" / "templates"
    memory = layout.target / "project_memory"
    mapping = {
        source / "INDEX.template.md": memory / "INDEX.md",
        source / "CLOUD.template.md": memory / "CLOUD.md",
        source / "PROJECT_SUMMARY.template.md": memory / "templates" / "PROJECT_SUMMARY.template.md",
        source / "ISSUE_SUMMARY.template.md": memory / "templates" / "ISSUE_SUMMARY.template.md",
        source / "RECOVERY.template.md": memory / "templates" / "RECOVERY.template.md",
        layout.repo_root / ".agent-memory-ignore": memory / ".agent-memory-ignore",
    }
    for directory in (memory / "records", memory / "templates", memory / "archives"):
        directory.mkdir(parents=True, exist_ok=True)
    for source_path, destination in mapping.items():
        if destination.exists() and not force:
            continue
        if destination.exists():
            backup = destination.with_name(destination.name + ".backup." + _timestamp())
            shutil.copy2(destination, backup)
        _copy_item(source_path, destination)


def _managed_block(layout: Layout) -> str:
    body = (layout.repo_root / "snippets" / "AGENT_RULE_BLOCK.md").read_text(encoding="utf-8").rstrip()
    return BEGIN + "\n" + body + "\n" + END + "\n"


def _write_rules(layout: Layout, rules_file: Optional[str]) -> None:
    explicit = Path(rules_file).expanduser() if rules_file else None
    candidates = [
        explicit,
        layout.target / "AGENTS.md",
        layout.target / "CODEX.md",
        layout.target / "instructions.md",
    ]
    destination = next((path for path in candidates if path and path.is_file()), None)
    if destination is None:
        destination = layout.target / "PROJECT_MEMORY_RULES_TO_ADD.md"
    block = _managed_block(layout)
    if not destination.exists():
        _atomic_text(destination, block)
        return
    text = destination.read_text(encoding="utf-8")
    start = text.find(BEGIN)
    end = text.find(END, start + len(BEGIN)) if start >= 0 else -1
    if start >= 0 and end >= 0:
        updated = text[:start] + block + text[end + len(END) :].lstrip("\n")
    else:
        updated = text.rstrip() + "\n\n" + block
    if updated != text:
        _atomic_text(destination, updated)


def _install_plugin_source(layout: Layout) -> None:
    layout.plugin_source.mkdir(parents=True, exist_ok=True)
    distribution = (
        ".codex-plugin",
        "hooks",
        "skills",
        "src",
        "scripts/apm.py",
        "scripts/hook-entry.py",
        "README.md",
        "LICENSE",
        "pyproject.toml",
        ".agent-memory-ignore",
    )
    for relative in distribution:
        source = layout.repo_root / relative
        if source.exists():
            _copy_item(source, layout.plugin_source / relative)


def _update_marketplace(layout: Layout) -> str:
    if layout.marketplace.exists():
        try:
            catalog = json.loads(layout.marketplace.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError("personal marketplace is not valid JSON") from error
        if not isinstance(catalog, dict) or not isinstance(catalog.get("plugins", []), list):
            raise RuntimeError("personal marketplace has an unsupported shape")
        marketplace_name = str(catalog.get("name") or "personal")
    else:
        marketplace_name = "personal"
        catalog = {
            "name": marketplace_name,
            "interface": {"displayName": "Personal"},
            "plugins": [],
        }
    if marketplace_name != "personal":
        raise RuntimeError("the default marketplace path is not named personal")
    entry = {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": "./plugins/" + PLUGIN_NAME},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }
    catalog["plugins"] = [
        item
        for item in catalog.get("plugins", [])
        if not isinstance(item, dict) or item.get("name") != PLUGIN_NAME
    ] + [entry]
    _json_write(layout.marketplace, catalog)
    return marketplace_name


def _remove_marketplace_entry(layout: Layout) -> None:
    if not layout.marketplace.exists():
        return
    catalog = json.loads(layout.marketplace.read_text(encoding="utf-8"))
    original = list(catalog.get("plugins", []))
    catalog["plugins"] = [
        item
        for item in original
        if not isinstance(item, dict) or item.get("name") != PLUGIN_NAME
    ]
    if catalog["plugins"] != original:
        _json_write(layout.marketplace, catalog)


def _write_launchers(layout: Layout) -> None:
    script = layout.plugin_source / "scripts" / "apm.py"
    unix = "#!/usr/bin/env sh\nexec python3 {} \"$@\"\n".format(shlex.quote(str(script)))
    unix_path = layout.target / "bin" / "agent-project-memory"
    _atomic_text(unix_path, unix, mode=0o700)
    os.chmod(unix_path, 0o700)
    windows = '@py -3 "{}" %*\r\n'.format(str(script).replace('"', '""'))
    _atomic_text(layout.target / "bin" / "agent-project-memory.cmd", windows, mode=0o600)


def _write_continuity_config(layout: Layout) -> None:
    path = layout.target / "continuity" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    if path.exists():
        return
    content = (
        "# Agent Project Memory continuity configuration\n"
        "trusted_roots = []\n"
        "denied_roots = []\n"
        'project_markers = [".git", "AGENTS.md", "pyproject.toml", "package.json", "Cargo.toml", "go.mod", ".project-memory.toml"]\n'
        "feedback_promotion_threshold = 2\n"
    )
    _atomic_text(path, content)


def _codex_env(layout: Layout) -> Dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(layout.home)
    env["CODEX_HOME"] = str(layout.target)
    return env


def _plugin_installed(layout: Layout) -> bool:
    result = subprocess.run(
        ["codex", "plugin", "list", "--json"],
        env=_codex_env(layout),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode:
        return False
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return any(item.get("pluginId") == PLUGIN_ID for item in data.get("installed", []))


def _codex_plugin(layout: Layout, operation: str) -> None:
    installed = _plugin_installed(layout)
    if operation == "remove":
        if not installed:
            return
        command = ["codex", "plugin", "remove", PLUGIN_ID, "--json"]
    else:
        if installed and operation == "install":
            return
        if installed:
            removed = subprocess.run(
                ["codex", "plugin", "remove", PLUGIN_ID, "--json"],
                env=_codex_env(layout),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if removed.returncode:
                raise RuntimeError("Codex could not remove the previous plugin version")
        command = ["codex", "plugin", "add", PLUGIN_ID, "--json"]
    result = subprocess.run(
        command,
        env=_codex_env(layout),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("Codex plugin command failed")


def _migrate_v1_hook(layout: Layout) -> None:
    path = layout.target / "hooks.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for groups in data.get("hooks", {}).values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            handlers = group.get("hooks", []) if isinstance(group, dict) else []
            kept = []
            for handler in handlers:
                command = str(handler.get("command", "")) if isinstance(handler, dict) else ""
                if _is_v1_hook_command(command, layout):
                    changed = True
                else:
                    kept.append(handler)
            if isinstance(group, dict):
                group["hooks"] = kept
    if changed:
        _json_write(path, data)


def _is_v1_hook_command(command: str, layout: Layout) -> bool:
    if "git_checkpoint.py" not in command:
        return False
    expected = (layout.target / "hooks" / "git_checkpoint.py").resolve(strict=False)
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        candidate = Path(token.strip('"\''))
        if candidate.name != "git_checkpoint.py":
            continue
        if candidate.expanduser().resolve(strict=False) == expected:
            return True
    normalized = command.replace("\\", "/").casefold()
    return normalized.rstrip('"\' ').endswith("/.codex/hooks/git_checkpoint.py")


def _remove_managed_rules(layout: Layout, rules_file: Optional[str]) -> None:
    candidates = [
        Path(rules_file).expanduser() if rules_file else None,
        layout.target / "AGENTS.md",
        layout.target / "CODEX.md",
        layout.target / "instructions.md",
        layout.target / "PROJECT_MEMORY_RULES_TO_ADD.md",
    ]
    for path in candidates:
        if not path or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        start = text.find(BEGIN)
        end = text.find(END, start + len(BEGIN)) if start >= 0 else -1
        if start < 0 or end < 0:
            continue
        updated = (text[:start] + text[end + len(END) :]).strip()
        if path.name == "PROJECT_MEMORY_RULES_TO_ADD.md" and not updated:
            path.unlink()
        else:
            _atomic_text(path, updated + ("\n" if updated else ""))
        return


def _install(layout: Layout, args: argparse.Namespace, operation: str) -> None:
    layout.target.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(layout.target, 0o700)
    except OSError:
        pass
    _copy_templates(layout, args.force_template)
    if not args.no_rules:
        _write_rules(layout, args.rules_file)
    _install_plugin_source(layout)
    _update_marketplace(layout)
    if os.environ.get("APM_INSTALLER_TEST_FAIL") == "after-marketplace":
        raise RuntimeError("injected installer failure")
    _write_launchers(layout)
    _write_continuity_config(layout)
    if not args.no_activate:
        _codex_plugin(layout, operation)
    if args.migrate_v1_hook:
        _migrate_v1_hook(layout)
    state = {
        "schema_version": 1,
        "plugin_id": PLUGIN_ID,
        "version": "2.0.0",
        "plugin_source": str(layout.plugin_source),
        "marketplace": str(layout.marketplace),
        "installed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    _json_write(layout.state_file, state)


def _uninstall(layout: Layout, args: argparse.Namespace) -> None:
    if not args.no_activate:
        _codex_plugin(layout, "remove")
    _remove_marketplace_entry(layout)
    _remove_item(layout.plugin_source)
    _remove_item(layout.target / "bin" / "agent-project-memory")
    _remove_item(layout.target / "bin" / "agent-project-memory.cmd")
    _remove_managed_rules(layout, args.rules_file)
    _remove_item(layout.state_file)
    if args.remove_data:
        _remove_item(layout.target / "project_memory")
        _remove_item(layout.target / "continuity")


def _rollback(layout: Layout) -> None:
    manifests = sorted(layout.backup_root.glob("*/manifest.json"), reverse=True)
    if not manifests:
        raise RuntimeError("no installer backup is available")
    manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    allowed = (layout.target, layout.home / "plugins", layout.home / ".agents")
    _restore_entries(manifest_path.parent, manifest["entries"], allowed)
    _atomic_text(manifest_path.parent / "ROLLED_BACK", _timestamp() + "\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-project-memory-installer",
        description="Install, upgrade, uninstall, or roll back Agent Project Memory.",
    )
    parser.add_argument(
        "operation",
        nargs="?",
        default="install",
        choices=("install", "upgrade", "uninstall", "rollback"),
    )
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--default-target", type=Path)
    parser.add_argument("--home", type=Path)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--rules-file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--backup", action="store_true", help="Include project data in the restorable snapshot.")
    parser.add_argument("--force-template", action="store_true")
    parser.add_argument("--no-rules", action="store_true")
    parser.add_argument("--migrate-v1-hook", action="store_true")
    parser.add_argument("--remove-data", action="store_true")
    parser.add_argument("--no-activate", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    target = (args.target or args.default_target or (Path.home() / ".codex")).expanduser().resolve()
    home = (args.home or (target.parent if target.name == ".codex" else Path.home())).expanduser().resolve()
    repo_root = (args.repo_root or Path(__file__).resolve().parents[2]).expanduser().resolve()
    layout = Layout(repo_root=repo_root, target=target, home=home)
    _confirm(args, args.operation, target)
    if args.dry_run:
        print("[dry-run] {} Agent Project Memory in {}".format(args.operation, target))
        return 0
    if args.operation == "rollback":
        _rollback(layout)
        print("Rolled back Agent Project Memory from the latest local snapshot.")
        return 0
    snapshot = Snapshot(_managed_paths(layout, args.backup))
    allowed = (layout.target, layout.home / "plugins", layout.home / ".agents")
    try:
        if args.operation in ("install", "upgrade"):
            _install(layout, args, args.operation)
        else:
            _uninstall(layout, args)
        destination = layout.backup_root / (_timestamp() + "-" + args.operation)
        snapshot.persist(destination, args.operation, args.backup)
    except Exception as error:
        snapshot.restore(allowed)
        snapshot.discard()
        print("Installer failed and restored the previous state: {}".format(type(error).__name__))
        return 1
    print("{} completed. Restorable snapshot: {}".format(args.operation.title(), destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
