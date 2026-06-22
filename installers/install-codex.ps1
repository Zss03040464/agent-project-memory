param(
  [ValidateSet("install", "upgrade", "uninstall", "rollback")]
  [string]$Operation = "install",
  [string]$TargetDir = (Join-Path $HOME ".codex"),
  [string]$HomeDir = $HOME,
  [string]$RulesFile,
  [switch]$DryRun,
  [switch]$Yes,
  [switch]$Backup,
  [switch]$ForceTemplate,
  [switch]$NoRules,
  [switch]$MigrateV1Hook,
  [switch]$RemoveData,
  [switch]$Help
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$Installer = Join-Path $RepoRoot "scripts/manage-install.py"
$CliArgs = @(
  $Installer,
  $Operation,
  "--agent", "codex",
  "--target", $TargetDir,
  "--home", $HomeDir,
  "--repo-root", $RepoRoot
)
if ($RulesFile) { $CliArgs += @("--rules-file", $RulesFile) }
if ($DryRun) { $CliArgs += "--dry-run" }
if ($Yes) { $CliArgs += "--yes" }
if ($Backup) { $CliArgs += "--backup" }
if ($ForceTemplate) { $CliArgs += "--force-template" }
if ($NoRules) { $CliArgs += "--no-rules" }
if ($MigrateV1Hook) { $CliArgs += "--migrate-v1-hook" }
if ($RemoveData) { $CliArgs += "--remove-data" }
if ($Help) { $CliArgs += "--help" }

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
$Python3 = Get-Command python3 -ErrorAction SilentlyContinue
$Python = Get-Command python -ErrorAction SilentlyContinue
if ($PyLauncher) {
  & $PyLauncher.Source -3 @CliArgs
} elseif ($Python3) {
  & $Python3.Source @CliArgs
} elseif ($Python) {
  & $Python.Source @CliArgs
} else {
  throw "Python 3 was not found on PATH."
}
exit $LASTEXITCODE
