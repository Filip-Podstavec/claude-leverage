# install-codex.ps1 — PowerShell variant of scripts/install-codex.sh
#
# Installs the claude-leverage stack into Codex CLI on Windows:
#   1. Resolves __CLAUDE_LEVERAGE_DIR__ in .codex/hooks.json and writes to
#      $env:USERPROFILE\.codex\hooks.json
#   2. Appends @<absolute-path>/AGENTS.md to ~/.codex/AGENTS.md
#   3. Copies .codex/agents/*.toml to ~/.codex/agents/
#
# Idempotent: detects existing install via marker comment.

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = (Resolve-Path "$scriptDir\..").Path

$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$marker = '# claude-leverage: managed import — do not edit between markers'
$markerEnd = '# claude-leverage: end managed import'

function Say([string]$msg) { Write-Host "[install-codex] $msg" }
function Die([string]$msg) { Write-Error "[install-codex] ERROR: $msg"; exit 1 }

# Sanity
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    Say "WARNING: codex CLI not found on PATH. Install with: npm i -g @openai/codex"
}
if (-not (Test-Path "$repoDir\.codex\hooks.json")) { Die "expected $repoDir\.codex\hooks.json" }
if (-not (Test-Path "$repoDir\AGENTS.md")) { Die "expected $repoDir\AGENTS.md" }

New-Item -ItemType Directory -Force -Path $codexHome | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $codexHome 'agents') | Out-Null

# Resolve hooks.json
$targetHooks = Join-Path $codexHome 'hooks.json'
if ((Test-Path $targetHooks) -and -not (Select-String -Path $targetHooks -Pattern 'claude-leverage|__CLAUDE_LEVERAGE_DIR__' -Quiet)) {
    Copy-Item $targetHooks "$targetHooks.pre-claude-leverage.bak"
    Say "backed up existing hooks.json -> $targetHooks.pre-claude-leverage.bak"
}

$repoForJson = $repoDir -replace '\\', '/'   # JSON-friendly forward-slash path
(Get-Content -Raw -Encoding utf8 "$repoDir\.codex\hooks.json") `
    -replace '__CLAUDE_LEVERAGE_DIR__', $repoForJson |
    Out-File -Encoding utf8 -NoNewline:$false $targetHooks
Say "wrote $targetHooks (paths resolved to $repoForJson)"

# Wire AGENTS.md import
$targetAgents = Join-Path $codexHome 'AGENTS.md'
if (-not (Test-Path $targetAgents)) { New-Item -ItemType File -Force -Path $targetAgents | Out-Null }

$content = Get-Content -Raw -Encoding utf8 $targetAgents
if ($content -match [regex]::Escape($marker)) {
    # Strip existing marker block.
    $pattern = [regex]::Escape($marker) + '.*?' + [regex]::Escape($markerEnd) + '\r?\n?'
    $content = [regex]::Replace($content, $pattern, '', 'Singleline')
    Say "removed previous claude-leverage block from $targetAgents"
}

$block = @"

$marker
# Imports the canonical guidance from the claude-leverage stack at:
#   $repoDir
# Re-running scripts/install-codex.ps1 keeps this block fresh.
@$repoForJson/AGENTS.md
$markerEnd
"@

($content.TrimEnd() + $block) | Out-File -Encoding utf8 $targetAgents
Say "added @import to $targetAgents"

# Copy Codex agents
$agentsSrc = Join-Path $repoDir '.codex\agents'
$tomlFiles = Get-ChildItem -Path $agentsSrc -Filter *.toml -ErrorAction SilentlyContinue
if ($tomlFiles) {
    Copy-Item $tomlFiles.FullName -Destination (Join-Path $codexHome 'agents') -Force
    Say "copied $($tomlFiles.Count) agent definition(s) to $codexHome\agents\"
} else {
    Say "no agents in $agentsSrc yet — skipping"
}

Say "install complete."
Say "next: start a Codex session and verify with: codex --version"
Say "uninstall: delete the marker block from $targetAgents and remove $targetHooks"
