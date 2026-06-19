param(
  [ValidateSet("codex", "claude", "gemini", "generic")]
  [string]$Agent = "generic",
  [string]$DefaultTargetDir = "",
  [string]$TargetDir,
  [string]$RulesFile,
  [switch]$DryRun,
  [switch]$Yes,
  [switch]$NoRules,
  [switch]$Backup,
  [switch]$ForceTemplate
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$BeginMarker = "<!-- BEGIN AGENT_PROJECT_MEMORY_RULES -->"
$EndMarker = "<!-- END AGENT_PROJECT_MEMORY_RULES -->"

function Write-PlannedAction {
  param([string]$Message)
  if ($DryRun) { Write-Host "[dry-run] $Message" } else { Write-Host $Message }
}

function Get-TimeStamp {
  return (Get-Date -Format "yyyyMMddHHmmss")
}

function Backup-FileIfExists {
  param([string]$Path)
  if (Test-Path -LiteralPath $Path) {
    $BackupPath = "$Path.backup.$(Get-TimeStamp)"
    Write-PlannedAction "backup $Path -> $BackupPath"
    if (-not $DryRun) {
      Copy-Item -LiteralPath $Path -Destination $BackupPath -Force
    }
  }
}

function Ensure-Directory {
  param([string]$Path)
  Write-PlannedAction "mkdir -p $Path"
  if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Copy-TemplateFile {
  param(
    [string]$Source,
    [string]$Destination,
    [string]$Label
  )

  if (Test-Path -LiteralPath $Destination) {
    if ($ForceTemplate) {
      Backup-FileIfExists $Destination
      Write-PlannedAction "overwrite $Label $Destination"
      if (-not $DryRun) { Copy-Item -LiteralPath $Source -Destination $Destination -Force }
    } else {
      $same = $false
      try {
        $same = ((Get-FileHash -Algorithm SHA256 -LiteralPath $Source).Hash -eq (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash)
      } catch {
        $same = $false
      }
      if ($same) {
        Write-PlannedAction "keep unchanged $Label $Destination"
      } else {
        Write-PlannedAction "skip existing $Label $Destination (use -ForceTemplate to replace)"
      }
    }
  } else {
    Write-PlannedAction "copy $Label $Source -> $Destination"
    if (-not $DryRun) {
      New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
      Copy-Item -LiteralPath $Source -Destination $Destination
    }
  }
}

function Get-ManagedBlock {
  $RuleBody = Get-Content -LiteralPath (Join-Path $RepoRoot "snippets/AGENT_RULE_BLOCK.md") -Raw
  return "$BeginMarker`n$RuleBody`n$EndMarker`n"
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

function Write-ManagedBlock {
  param([string]$Path, [bool]$Fallback)

  Write-PlannedAction "prepare rules file $Path"
  if (-not $DryRun) { New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null }

  if ($DryRun) {
    if ($Fallback) { Write-PlannedAction "write manual rule block to $Path" }
    else { Write-PlannedAction "insert or replace managed rule block in $Path" }
    return
  }

  $Block = Get-ManagedBlock
  if (-not (Test-Path -LiteralPath $Path)) {
    Set-Content -LiteralPath $Path -Value $Block -Encoding UTF8
    return
  }

  $Text = Get-Content -LiteralPath $Path -Raw
  $Pattern = "(?s)" + [regex]::Escape($BeginMarker) + ".*?" + [regex]::Escape($EndMarker)
  if ([regex]::IsMatch($Text, $Pattern)) {
    $Updated = [regex]::Replace($Text, $Pattern, { param($m) $Block }, 1)
  } else {
    $Updated = $Text.TrimEnd() + "`n`n" + $Block
  }

  if ($Updated -eq $Text) {
    Write-PlannedAction "managed rule block already up to date in $Path"
    return
  }

  Backup-FileIfExists $Path
  Set-Content -LiteralPath $Path -Value $Updated -Encoding UTF8
}

if (-not $TargetDir) { $TargetDir = $DefaultTargetDir }
if (-not $TargetDir) { throw "No target directory provided. Use -TargetDir." }

$MemoryDir = Join-Path $TargetDir "project_memory"

Write-Host "Agent Project Memory installer"
Write-Host "Agent: $Agent"
Write-Host "Target: $TargetDir"
if ($DryRun) { Write-Host "Mode: dry-run" }

if (-not $DryRun -and -not $Yes) {
  $Reply = Read-Host "Install Agent Project Memory into $TargetDir? [y/N]"
  if ($Reply -notin @("y", "Y", "yes", "YES")) {
    Write-Host "Cancelled."
    exit 1
  }
}

Ensure-Directory (Join-Path $MemoryDir "records")
Ensure-Directory (Join-Path $MemoryDir "templates")
Ensure-Directory (Join-Path $MemoryDir "archives")

Copy-TemplateFile (Join-Path $RepoRoot "skills/project-memory/templates/INDEX.template.md") (Join-Path $MemoryDir "INDEX.md") "INDEX"
Copy-TemplateFile (Join-Path $RepoRoot "skills/project-memory/templates/CLOUD.template.md") (Join-Path $MemoryDir "CLOUD.md") "CLOUD"
Copy-TemplateFile (Join-Path $RepoRoot "skills/project-memory/templates/PROJECT_SUMMARY.template.md") (Join-Path $MemoryDir "templates/PROJECT_SUMMARY.template.md") "project template"
Copy-TemplateFile (Join-Path $RepoRoot "skills/project-memory/templates/ISSUE_SUMMARY.template.md") (Join-Path $MemoryDir "templates/ISSUE_SUMMARY.template.md") "issue template"
Copy-TemplateFile (Join-Path $RepoRoot "skills/project-memory/templates/RECOVERY.template.md") (Join-Path $MemoryDir "templates/RECOVERY.template.md") "recovery template"
Copy-TemplateFile (Join-Path $RepoRoot ".agent-memory-ignore") (Join-Path $MemoryDir ".agent-memory-ignore") "ignore file"

if ($NoRules) {
  Write-Host "Rules installation skipped because -NoRules was used."
  exit 0
}

$DetectedRules = Detect-RulesFile $TargetDir $Agent $RulesFile
if ($DetectedRules) {
  Write-ManagedBlock $DetectedRules $false
  Write-Host "Managed rule block installed into: $DetectedRules"
} else {
  $Fallback = Join-Path $TargetDir "PROJECT_MEMORY_RULES_TO_ADD.md"
  Write-ManagedBlock $Fallback $true
  Write-Host "No clear existing global rules file was found for $Agent."
  Write-Host "Manual rule block written to: $Fallback"
  Write-Host "Paste that managed block into your agent's global rules file."
}

Write-Host "Installed project_memory into: $MemoryDir"
