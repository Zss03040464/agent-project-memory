$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ScriptDir "install-common.ps1") -TargetDir (Join-Path $HOME ".claude")
