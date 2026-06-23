param(
  [string]$TargetDir = (Join-Path $HOME ".codex"),
  [string]$HomeDir = $HOME,
  [string]$RulesFile,
  [switch]$DryRun,
  [switch]$Yes,
  [switch]$Backup,
  [switch]$RemoveData,
  [switch]$Help
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallScript = Join-Path $ScriptDir "install-codex.ps1"
$Forward = @{
  Operation = "uninstall"
  TargetDir = $TargetDir
  HomeDir = $HomeDir
}
if ($RulesFile) { $Forward.RulesFile = $RulesFile }
if ($DryRun) { $Forward.DryRun = $true }
if ($Yes) { $Forward.Yes = $true }
if ($Backup) { $Forward.Backup = $true }
if ($RemoveData) { $Forward.RemoveData = $true }
if ($Help) { $Forward.Help = $true }
& $InstallScript @Forward
exit $LASTEXITCODE
