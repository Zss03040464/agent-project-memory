$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ScriptDir "install-common.ps1") -Agent claude -DefaultTargetDir (Join-Path $HOME ".claude") @args
