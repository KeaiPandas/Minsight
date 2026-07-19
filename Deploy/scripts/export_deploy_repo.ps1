param(
    [string]$Target = "..\Minsight-Deploy",
    [switch]$Force,
    [switch]$InitGit
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptRoot "..\.."))
$TargetRoot = [System.IO.Path]::GetFullPath((Join-Path $SourceRoot $Target))

function Assert-SafeTarget {
    param([string]$Path)
    $source = [System.IO.Path]::GetFullPath($SourceRoot).TrimEnd("\")
    $target = [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
    if ($target -eq $source -or $source.StartsWith($target + "\")) {
        throw "Refusing unsafe target: $target"
    }
    if ([System.IO.Path]::GetPathRoot($target) -eq $target) {
        throw "Refusing to use drive root as target: $target"
    }
}

function Copy-Tree {
    param(
        [string]$Source,
        [string]$Destination
    )
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        if ($_.Name -in @(".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", "results")) {
            return
        }
        if (-not $_.PSIsContainer -and $_.Extension -in @(".pyc", ".sqlite", ".sqlite3", ".db", ".log")) {
            return
        }
        if ($_.Name -eq ".env") {
            return
        }
        $dest = Join-Path $Destination $_.Name
        if ($_.PSIsContainer) {
            Copy-Tree -Source $_.FullName -Destination $dest
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
        }
    }
}

Assert-SafeTarget -Path $TargetRoot

if (Test-Path -LiteralPath $TargetRoot) {
    if (-not $Force) {
        throw "Target already exists: $TargetRoot. Re-run with -Force to replace it."
    }
    Remove-Item -LiteralPath $TargetRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null

Copy-Tree -Source (Join-Path $SourceRoot "Deploy") -Destination (Join-Path $TargetRoot "Deploy")
Copy-Tree -Source (Join-Path $SourceRoot "Core\shared") -Destination (Join-Path $TargetRoot "Core\shared")
Copy-Tree -Source (Join-Path $SourceRoot "Core\v2") -Destination (Join-Path $TargetRoot "Core\v2")
Copy-Tree -Source (Join-Path $SourceRoot "Core\prompts\v2") -Destination (Join-Path $TargetRoot "Core\prompts\v2")
Copy-Tree -Source (Join-Path $SourceRoot "Core\data\scenarios") -Destination (Join-Path $TargetRoot "Core\data\scenarios")

@"
# Minsight Deploy

This is the deploy-only repository for Minsight.

Included:

- `Core/shared`, `Core/v2`, `Core/prompts/v2`, and demo scenarios needed by the formal Minsight Agent.
- `Deploy/` workbench HTTP server, frontend, persistence, Feishu adapters, and Aliyun ops templates.

Excluded:

- `Lab/` benchmark console, judge workflow, historical runs, and regression heatmaps.
- `docs/`, `PRD/`, local databases, local `.env` files, and generated artifacts.

Start from `Deploy/README.md`.
"@ | Set-Content -LiteralPath (Join-Path $TargetRoot "README.md") -Encoding utf8

@"
# Secrets and local configuration
.env
*.env
!Deploy/.env.production.example

# Runtime state
*.sqlite
*.sqlite3
*.db
*.log
logs/
tmp/
temp/

# Python caches and environments
__pycache__/
**/__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/

# Editor and OS files
.vscode/
.idea/
.DS_Store
Thumbs.db
desktop.ini
"@ | Set-Content -LiteralPath (Join-Path $TargetRoot ".gitignore") -Encoding utf8

@"
.git
.env
*.env
*.sqlite
*.sqlite3
*.db
Lab/results/
docs/
**/__pycache__/
**/*.py[cod]
.pytest_cache/
.venv/
venv/
node_modules/
"@ | Set-Content -LiteralPath (Join-Path $TargetRoot ".dockerignore") -Encoding utf8

if ($InitGit) {
    Push-Location $TargetRoot
    try {
        git init | Out-Null
        git add .
        git commit -m "Initial deploy-only export"
    } finally {
        Pop-Location
    }
}

Write-Host "Exported deploy-only repo to $TargetRoot"
