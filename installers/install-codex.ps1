$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ScriptDir "install-common.ps1") -Agent codex -DefaultTargetDir (Join-Path $HOME ".codex") @args
