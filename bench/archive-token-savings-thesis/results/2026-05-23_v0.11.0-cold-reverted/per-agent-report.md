# Per-agent verdicts - claude-leverage v0.11.0  (2026-05-23_v0.11.0-cold-reverted)

**Internal report - not part of README.** Use to decide which agents to improve, delete, or add.

![scatter](per-agent-scatter.png)

## Verdicts

| Verdict | Agent | Invocations | Tier(s) | Median tokens | Baseline est. | Savings | Quality |
|---|---|---:|---|---:|---:|---:|---:|
| GREAT | `claude-leverage:git-committer` | 3 | sonnet | 7.0k (6.8k-7.0k) | 51.2k | -86% | 100% |
| GREAT | `claude-leverage:context-gatherer` | 3 | haiku | 10.9k (10.6k-11.8k) | 35.4k | -69% | 100% |
| INSUFFICIENT DATA | `claude-leverage:code-reviewer` | 2 | sonnet | 6.7k (6.7k-6.8k) | 34.2k | -80% | 100% |

## Reading this report

**Important: this measures agent-execution efficiency, NOT system-level cost.**

An agent can show -78% savings here while the leveraged session as a whole costs MORE than baseline. Example: `code-reviewer` (Sonnet) uses 7k tokens to do the review; baseline Opus does the same review in 34k tokens. The agent itself is efficient. But the leveraged session also pays for Opus orchestration (~30k tokens to dispatch, read the report, and integrate). Net session cost can still be higher than baseline.

Use this report to ask: **is each agent doing its piece efficiently?** Use `report.md` (hero chart) to ask: **does the plugin net out cheaper overall?**

- **Baseline estimate** is the median total tokens the *baseline session* spent on the same task (the counterfactual: 'what would Opus alone have done if it did the whole task').
- **Savings** is `(baseline_estimate - median_agent_tokens) / baseline_estimate`. This is agent intrinsic efficiency, not net session savings. Negative = agent uses more tokens than baseline did total on the same task.
- **Quality** is the pass rate of the deterministic task-level check across all leveraged runs that engaged this agent. A low rate means the savings number is suspect.
- **Insufficient data** = n_invocations < 3. The mini-suite invokes each agent at most N times (one task per agent), so most rows will be INSUFFICIENT in v1. The realistic suite (v2) will fix this by spreading invocations across more tasks.

## Actions to consider

**Clear wins** (keep, possibly use as templates for future agents):
- `claude-leverage:git-committer` - savings 86%, quality 100%
- `claude-leverage:context-gatherer` - savings 69%, quality 100%
