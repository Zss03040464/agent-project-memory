$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ScriptDir "install-common.ps1") -Agent gemini -DefaultTargetDir (Join-Path $HOME ".gemini") @args
