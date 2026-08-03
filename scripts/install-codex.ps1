# install-codex.ps1 — PowerShell variant of scripts/install-codex.sh
#
# Installs the claude-leverage stack into Codex CLI on Windows:
#   1. Resolves __CLAUDE_LEVERAGE_DIR__ in .codex/hooks.json and writes to
#      $env:USERPROFILE\.codex\hooks.json
#   2. Appends @<absolute-path>/AGENTS.md to ~/.codex/AGENTS.md
#   3. Copies .codex/agents/*.toml to ~/.codex/agents/
#   4. Copies skills/* to ~/.agents/skills/claude-leverage/
#
# Idempotent: detects existing install via marker comment; overwrites
# skills directory in place.

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

# AIDEV-NOTE: PowerShell's -replace is regex on BOTH args; a literal '$' in
# $repoForJson (a project path like /home/user/my$project/...) would be
# interpreted as a regex backreference and silently mangle the JSON. Use
# Python's str.replace for the same delimiter-free substitution as the
# bash variant — Python is already required for install (sanity above).
$pythonBin = if (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' }
             elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' }
             else { Die 'python3 or python required for install-codex (path substitution)'; '' }

& $pythonBin -c @"
import sys
src_path, repo_dir, dst_path = sys.argv[1], sys.argv[2], sys.argv[3]
with open(src_path, encoding='utf-8') as f:
    body = f.read()
body = body.replace('__CLAUDE_LEVERAGE_DIR__', repo_dir)
with open(dst_path, 'w', encoding='utf-8') as f:
    f.write(body)
"@ "$repoDir\.codex\hooks.json" $repoForJson $targetHooks

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

# Copy skills
$skillsSrc = Join-Path $repoDir 'skills'
$skillsHome = if ($env:CLAUDE_LEVERAGE_AGENTS_HOME) { $env:CLAUDE_LEVERAGE_AGENTS_HOME } else { Join-Path $env:USERPROFILE '.agents' }
$skillsDest = Join-Path (Join-Path $skillsHome 'skills') 'claude-leverage'

if (Test-Path $skillsSrc) {
    New-Item -ItemType Directory -Force -Path (Join-Path $skillsHome 'skills') | Out-Null
    if (Test-Path $skillsDest) { Remove-Item -Recurse -Force $skillsDest }
    New-Item -ItemType Directory -Force -Path $skillsDest | Out-Null

    $installedCount = 0
    foreach ($skillDir in (Get-ChildItem -Path $skillsSrc -Directory)) {
        $skillMd = Join-Path $skillDir.FullName 'SKILL.md'
        if (Test-Path $skillMd) {
            Copy-Item -Recurse -Force $skillDir.FullName (Join-Path $skillsDest $skillDir.Name)
            $installedCount++
        }
    }

    if ($installedCount -gt 0) {
        Say "copied $installedCount skill(s) to $skillsDest\"
    } else {
        Remove-Item -Force $skillsDest -ErrorAction SilentlyContinue
        Say "no skills with SKILL.md found in $skillsSrc — skipping"
    }
} else {
    Say "no skills\ dir in $repoDir — skipping"
}

Say "install complete."
Say "next: start a Codex session and verify with: codex --version"
Say ""
Say "to uninstall, run:"
Say "  Remove-Item -Recurse -Force $skillsDest"
Say "  Remove-Item -Force $codexHome\agents\security-reviewer.toml,$codexHome\agents\flaky-test-isolator.toml,$codexHome\agents\readiness-reviewer.toml"
Say "  Remove-Item -Force $targetHooks  # or restore $targetHooks.pre-claude-leverage.bak"
Say "  # then edit $targetAgents and remove the block between the two '# claude-leverage:' markers"
