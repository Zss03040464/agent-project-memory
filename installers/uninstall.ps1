param(
  [ValidateSet("codex", "claude", "gemini", "generic")]
  [string]$Agent = "codex",
  [string]$TargetDir = (Join-Path $HOME ".codex"),
  [string]$RulesFile,
  [switch]$RemoveMemory,
  [switch]$DryRun,
  [switch]$Yes
)

$ErrorActionPreference = "Stop"
$BeginMarker = "<!-- BEGIN AGENT_PROJECT_MEMORY_RULES -->"
$EndMarker = "<!-- END AGENT_PROJECT_MEMORY_RULES -->"

function Write-PlannedAction {
  param([string]$Message)
  if ($DryRun) { Write-Host "[dry-run] $Message" } else { Write-Host $Message }
}

function Get-TimeStamp { return (Get-Date -Format "yyyyMMddHHmmss") }

function Backup-ItemIfExists {
  param([string]$Path)
  if (Test-Path -LiteralPath $Path) {
    $BackupPath = "$Path.backup.$(Get-TimeStamp)"
    Write-PlannedAction "backup $Path -> $BackupPath"
    if (-not $DryRun) { Copy-Item -LiteralPath $Path -Destination $BackupPath -Recurse -Force }
  }
}

function Detect-RulesFile {
  param([string]$Target, [string]$AgentName, [string]$ExplicitRulesFile)
  if ($ExplicitRulesFile) { return $ExplicitRulesFile }
  $Candidates = @()
  switch ($AgentName) {
    "codex" { $Candidates = @("AGENTS.md", "CODEX.md", "instructions.md") }
    "claude" { $Candidates = @("CLAUDE.md", "instructions.md", "AGENTS.md") }
    "gemini" { $Candidates = @("GEMINI.md", "AGENTS.md", "instructions.md") }
    default { $Candidates = @("AGENTS.md", "instructions.md") }
  }
  foreach ($Name in $Candidates) {
    $Candidate = Join-Path $Target $Name
    if (Test-Path -LiteralPath $Candidate -PathType Leaf) { return $Candidate }
  }
  return $null
}

function Remove-ManagedBlock {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    Write-PlannedAction "rules file not found: $Path"
    return
  }
  $Text = Get-Content -LiteralPath $Path -Raw
  if (-not $Text.Contains($BeginMarker)) {
    Write-PlannedAction "managed block not present in $Path"
    return
  }
  Backup-ItemIfExists $Path
  Write-PlannedAction "remove managed rule block from $Path"
  if ($DryRun) { return }
  $Pattern = "(?s)" + [regex]::Escape($BeginMarker) + ".*?" + [regex]::Escape($EndMarker) + "\s*"
  $Updated = [regex]::Replace($Text, $Pattern, "", 1)
  Set-Content -LiteralPath $Path -Value $Updated -Encoding UTF8
}

Write-Host "Agent Project Memory uninstall"
Write-Host "Agent: $Agent"
Write-Host "Target: $TargetDir"
if ($DryRun) { Write-Host "Mode: dry-run" }

if (-not $DryRun -and -not $Yes) {
  $Reply = Read-Host "Uninstall managed Agent Project Memory rules from $TargetDir? [y/N]"
  if ($Reply -notin @("y", "Y", "yes", "YES")) {
    Write-Host "Cancelled."
    exit 1
  }
}

$DetectedRules = Detect-RulesFile $TargetDir $Agent $RulesFile
if ($DetectedRules) {
  Remove-ManagedBlock $DetectedRules
} else {
  $Fallback = Join-Path $TargetDir "PROJECT_MEMORY_RULES_TO_ADD.md"
  if (Test-Path -LiteralPath $Fallback) {
    Backup-ItemIfExists $Fallback
    Write-PlannedAction "remove fallback rules file $Fallback"
    if (-not $DryRun) { Remove-Item -LiteralPath $Fallback -Force }
  } else {
    Write-Host "No rules file found; nothing to remove from rules."
  }
}

if ($RemoveMemory) {
  $MemoryDir = Join-Path $TargetDir "project_memory"
  if (Test-Path -LiteralPath $MemoryDir -PathType Container) {
    Backup-ItemIfExists $MemoryDir
    Write-PlannedAction "remove memory directory $MemoryDir"
    if (-not $DryRun) { Remove-Item -LiteralPath $MemoryDir -Recurse -Force }
  } else {
    Write-Host "Memory directory not found: $MemoryDir"
  }
} else {
  Write-Host "project_memory data was kept. Use -RemoveMemory to remove it explicitly."
}
