# Migration, Uninstall, and Rollback

## v1 to v2

1. Run install in a temporary home and Codex home.
2. Install v2 without the migration flag so the plugin and legacy user Hook can be compared in parallel.
3. Confirm the plugin is listed, its Skill is discoverable, and its Hook is trusted through the normal Codex flow.
4. Back up real Codex configuration, Hooks, rules, project memory, continuity, plugin source/marketplace, and install records.
5. Install v2 into the real Codex home.
6. Run upgrade with `--migrate-v1-hook` or `-MigrateV1Hook` to remove only duplicate legacy Hook commands.
7. Keep `git_checkpoint.py` and all `refs/codex/checkpoints/*` in backup/read-only form.
8. Start a new thread and confirm there is one continuity Hook result per event.

The migration option does not delete old refs or blindly delete user Hook groups.

## Uninstall

Default uninstall removes plugin activation, plugin source, personal-marketplace entry, CLI launcher, and managed rule block. It keeps project memory and continuity data:

```bash
bash installers/uninstall.sh --yes
```

Remove data only after reviewing the automatic snapshot:

```bash
bash installers/uninstall.sh --yes --backup --remove-data
```

PowerShell uses `-Backup -RemoveData`.

## Rollback

Every mutating lifecycle operation creates a local transaction snapshot. Restore the latest snapshot with:

```bash
bash installers/install-codex.sh rollback --yes
```

```powershell
.\installers\install-codex.ps1 -Operation rollback -Yes
```

Rollback validates that every restored path remains under the selected Codex home, plugin home, or personal marketplace root. Installer backups do not remove hidden Git refs.
