#!/usr/bin/env bash
# Claude Code status line – works on Windows (Git Bash) without jq
# Uses Python for JSON parsing instead

python -c "
import sys, json, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

data = json.load(sys.stdin)

parts = []

def make_bar(pct):
    pct = int(round(pct))
    filled = min(10, (pct * 10 + 50) // 100)
    bar = chr(9608) * filled + chr(9617) * (10 - filled)
    if pct >= 85:
        c = '\033[31m'
    elif pct >= 60:
        c = '\033[33m'
    else:
        c = '\033[32m'
    return c, bar, pct

import time

def time_until(epoch):
    if not epoch:
        return ''
    diff = int(epoch) - int(time.time())
    if diff <= 0:
        return ' (now)'
    h, m = divmod(diff // 60, 60)
    if h > 0:
        return f' ({h}h{m:02d}m)'
    return f' ({m}m)'

# Rate limit 5h
rl = data.get('rate_limits', {})
five_data = rl.get('five_hour', {})
five = five_data.get('used_percentage')
if five is not None:
    c, bar, pct = make_bar(five)
    reset = time_until(five_data.get('resets_at'))
    parts.append(f'{c}5h: {bar} {pct}%\033[2m{reset}\033[0m')

# Rate limit 7d
week_data = rl.get('seven_day', {})
week = week_data.get('used_percentage')
if week is not None:
    c, bar, pct = make_bar(week)
    reset = time_until(week_data.get('resets_at'))
    parts.append(f'{c}7d: {bar} {pct}%\033[2m{reset}\033[0m')

# Context window
ctx = data.get('context_window', {})
ctx_pct = ctx.get('used_percentage')
if ctx_pct is not None:
    c, bar, pct = make_bar(ctx_pct)
    parts.append(f'{c}Ctx: {bar} {pct}%\033[0m')

# Model
model = data.get('model', {}).get('display_name')
if model:
    parts.append(f'\033[36m{model}\033[0m')

# Git branch
import subprocess
cwd = data.get('workspace', {}).get('current_dir', '.')
try:
    branch = subprocess.check_output(['git', '-C', cwd, 'rev-parse', '--abbrev-ref', 'HEAD'], stderr=subprocess.DEVNULL, text=True).strip()
    if branch and branch != 'HEAD':
        parts.append(f'\033[34m# {branch}\033[0m')
except:
    pass

sep = '\033[2m | \033[0m'
print(sep.join(parts))
" <<< "$(cat)"
