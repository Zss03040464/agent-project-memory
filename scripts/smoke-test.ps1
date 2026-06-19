$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Scripts = @(
  "installers/install-common.ps1",
  "installers/install-codex.ps1",
  "installers/install-claude.ps1",
  "installers/install-gemini.ps1",
  "installers/uninstall.ps1"
)

foreach ($Script in $Scripts) {
  $Content = Get-Content -LiteralPath $Script -Raw
  [void][scriptblock]::Create($Content)
}

$Target = Join-Path ([System.IO.Path]::GetTempPath()) ("agent-project-memory-ps-" + [System.Guid]::NewGuid().ToString("N"))
try {
  & .\installers\install-codex.ps1 -TargetDir $Target -DryRun
  if (Test-Path -LiteralPath $Target) { throw "DryRun created target directory" }

  New-Item -ItemType Directory -Force -Path $Target | Out-Null
  Set-Content -LiteralPath (Join-Path $Target "AGENTS.md") -Value "# Existing rules`n" -Encoding UTF8

  & .\installers\install-codex.ps1 -TargetDir $Target -Yes
  & .\installers\install-codex.ps1 -TargetDir $Target -Yes

  $Index = Join-Path $Target "project_memory/INDEX.md"
  if (-not (Test-Path -LiteralPath $Index)) { throw "INDEX.md was not created" }

  $Rules = Get-Content -LiteralPath (Join-Path $Target "AGENTS.md") -Raw
  $Count = ([regex]::Matches($Rules, "BEGIN AGENT_PROJECT_MEMORY_RULES")).Count
  if ($Count -ne 1) { throw "Managed rule block count was $Count, expected 1" }

  & .\installers\uninstall.ps1 -TargetDir $Target -Yes
  $RulesAfter = Get-Content -LiteralPath (Join-Path $Target "AGENTS.md") -Raw
  if ($RulesAfter.Contains("BEGIN AGENT_PROJECT_MEMORY_RULES")) { throw "Uninstall did not remove managed block" }
  if (-not (Test-Path -LiteralPath $Index)) { throw "Uninstall removed memory data unexpectedly" }

  Write-Host "PowerShell smoke test passed."
} finally {
  if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }
}
