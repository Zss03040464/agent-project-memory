param(
  [Parameter(Mandatory=$true)]
  [string]$TargetDir
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

New-Item -ItemType Directory -Force -Path (Join-Path $TargetDir "project_memory\records") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $TargetDir "project_memory\templates") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $TargetDir "project_memory\archives") | Out-Null

Copy-Item (Join-Path $RepoRoot "skills\project-memory\templates\INDEX.template.md") (Join-Path $TargetDir "project_memory\INDEX.md") -Force
Copy-Item (Join-Path $RepoRoot "skills\project-memory\templates\CLOUD.template.md") (Join-Path $TargetDir "project_memory\CLOUD.md") -Force
Copy-Item (Join-Path $RepoRoot "skills\project-memory\templates\PROJECT_SUMMARY.template.md") (Join-Path $TargetDir "project_memory\templates\PROJECT_SUMMARY.template.md") -Force
Copy-Item (Join-Path $RepoRoot "skills\project-memory\templates\ISSUE_SUMMARY.template.md") (Join-Path $TargetDir "project_memory\templates\ISSUE_SUMMARY.template.md") -Force
Copy-Item (Join-Path $RepoRoot "skills\project-memory\templates\RECOVERY.template.md") (Join-Path $TargetDir "project_memory\templates\RECOVERY.template.md") -Force
Copy-Item (Join-Path $RepoRoot ".agent-memory-ignore") (Join-Path $TargetDir "project_memory\.agent-memory-ignore") -Force

Write-Host "Installed project_memory into: $(Join-Path $TargetDir 'project_memory')"
Write-Host ""
Write-Host "Add the following rule block to your agent global rules file:"
Write-Host ""
Get-Content (Join-Path $RepoRoot "snippets\AGENT_RULE_BLOCK.md")
