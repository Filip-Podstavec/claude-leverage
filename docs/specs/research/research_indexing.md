# Codebase "map" approaches for AI coding agents — 2025-2026 state of the art

Scope: comparing four strategies for orienting an agent (Claude Code primary, Codex secondary) in a real repo, for a *single* developer on Windows who values low maintenance.

## 1. Pre-built semantic index / RAG over embeddings

This is the Cursor and (formerly) Cody approach: chunk the repo (Cursor uses AST-aware ~500-token chunks), embed via OpenAI or a custom model, store in a vector DB (Cursor uses Turbopuffer), and do nearest-neighbour lookup at query time. Cursor adds a Merkle-tree sync so only changed files re-embed.

**Pays off when:** the repo is huge (>500k LOC), code is stable, and you want sub-second semantic recall ("find anything that conceptually does X") across files the agent would never grep for. Useful in monorepos.

**Over-engineered when:** the repo is <50k LOC, churns daily, or the developer already knows roughly where things live.

**Maintenance burden:** real. You either run a background indexer (Cursor does this for you, hidden), or you stand up a Chroma/LlamaIndex pipeline yourself. Staleness is the killer — between commits the index lies, and on a fast-moving branch the lies compound. Sourcegraph publicly **deprecated embeddings for Cody Enterprise** in 2024-2025, replacing them with their classic keyword/structural search precisely because "embeddings require all of your code to be represented in vector space… stored, maintained, and updated" with no quality win.

**Consensus:** the industry quietly walked away from pure-embedding RAG for code in 2024-2025. Cursor still uses it but heavily wrapped with grep/AST passes; Cody dropped it; Aider never adopted it; Claude Code rejected it.

## 2. Symbol index (ctags / tree-sitter / LSP / aider-style repo-map)

Aider's repo-map is the canonical implementation: tree-sitter parses every file, extracts defs and references, builds a directed symbol graph, and runs personalized PageRank against the files currently in chat. The top-ranked symbols get rendered as elided code skeletons fitting a token budget (default 1k, configurable via `--map-tokens`). It is stuffed into the prompt every turn.

**Pays off when:** the model needs a *structural* picture ("what calls this function, what types exist") that grep can't cheaply assemble, especially in statically-typed languages where tree-sitter is accurate.

**Over-engineered when:** you're on Windows with a polyglot repo (tree-sitter language pack installs are notoriously fiddly on Windows — see aider issue #4433 about PowerShell repo-map support), or when your agent already has a strong Explore loop.

**Maintenance burden:** low *if* the tool maintains it for you (aider rebuilds on the fly). Standalone ctags is essentially free but produces dumber output. The PageRank rebuild is fast but not instant on big repos.

**Consensus:** still respected. Aider users swear by it. But it's mostly invisible plumbing — nobody recommends running ctags by hand in 2025. The interesting derivative is that **Claude Code intentionally did not adopt this**; Boris Cherny (Anthropic, Claude Code lead) said on X and on Latent Space that they tried "recursive model-based indexing" and it lost to plain agentic grep.

## 3. On-demand grep/glob (Claude Code's native Explore)

Three tools: Glob (path patterns), Grep (ripgrep under the hood), Read (full file). Claude Code spawns an Explore sub-agent on Haiku with its own context window, so heavy exploration doesn't burn the main Opus/Sonnet budget. This is the path Anthropic publicly endorses.

**Pays off when:** the repo changes daily, the developer is solo, the agent is good at iterative search (Claude Code is, demonstrably). An Amazon Science paper (Feb 2026, widely cited in the Claude-Code-vs-RAG discussions) reported keyword/agentic search hitting >90% of RAG quality with zero index.

**Over-engineered when:** never — it's literally zero-config.

**Maintenance burden:** zero. No staleness because nothing is cached.

**Consensus:** this is the dominant 2025-2026 default for new agentic coding tools. Cherny's quote — "agentic search outperformed everything. By a lot. And this was surprising" — is the most-cited line in the space. The cost is tokens and latency per query, which is exactly what Explore-on-Haiku is designed to amortize.

## 4. Hybrid: static manifest (CLAUDE.md / module summaries) + on-demand grep

A short, hand-curated map: tech stack, top-level module purpose, "do not touch" zones, common commands. Anthropic's own guidance and the community analyses (Emergent Mind's CLAUDE.md corpus study: ~77% of files contain build commands, ~72% style notes, ~65% architecture overview) converge on a 100-200 line sweet spot, with per-folder CLAUDE.md for deeper modules.

**Pays off when:** you want to skip the first 5-10 grep round-trips by giving the agent the *shape* of the repo upfront. Especially valuable for things grep can't tell you: which module is legacy, why two implementations exist, what the test command actually is.

**Over-engineered when:** you try to keep symbol-level detail in it (the index will rot). Keep it conceptual, let grep handle the literal.

**Maintenance burden:** moderate-but-honest. Architecture changes monthly, not daily, so a human can keep up. The `/init` command bootstraps it.

**Consensus:** this is the practitioner default in 2025-2026. Every "Claude Code best practices" post (Anthropic's own, the dev.to and skywork.ai writeups) leads with CLAUDE.md. It composes cleanly with Explore: the manifest gives the strategic map, grep does the tactical lookup.

## Recommendation for your stack

For a solo dev on Windows with Claude Code primary + Codex secondary, the value/pain ranking is unambiguous:

1. **Hybrid #4 + native Explore #3** — best ratio by a wide margin. Maintain a tight root CLAUDE.md (≤200 lines) per repo, optionally per-folder CLAUDE.md for the 2-3 hairy modules, and let Explore-on-Haiku do the rest. Zero indexing infra, no Windows tree-sitter pain, no staleness. Codex secondary still benefits because CLAUDE.md is just markdown — Codex can be pointed at it or you can mirror it as `AGENTS.md` (which you already have in this repo).
2. **#2 aider repo-map** — only worth installing if you also use aider as a second agent. As a standalone "map provider" for Claude Code, it duplicates what Explore already does well.
3. **#1 embedding RAG** — skip. The cost/staleness/Windows-infra triad is brutal for one person, and the industry's most credible builders (Cherny, Sourcegraph) have publicly walked away from it for code.

## Sources

- [Boris Cherny on X: early Claude Code used RAG + vector DB, agentic search won](https://x.com/bcherny/status/2017824286489383315)
- [Building Claude Code with Boris Cherny — Pragmatic Engineer](https://newsletter.pragmaticengineer.com/p/building-claude-code-with-boris-cherny)
- [Claude Code: Anthropic's Agent in Your Terminal — Latent Space](https://www.latent.space/p/claude-code)
- [Claude Code Doesn't Index Your Codebase — Vadim's blog](https://vadim.blog/claude-code-no-indexing)
- [Why Claude Code Abandoned RAG for Agentic Search — zenn.dev](https://zenn.dev/karamage/articles/2514cf04e0d1ac?locale=en)
- [Settling the RAG Debate — SmartScope](https://smartscope.blog/en/ai-development/practices/rag-debate-agentic-search-code-exploration/)
- [Building a better repository map with tree sitter — aider](https://aider.chat/2023/10/22/repomap.html)
- [Repository map docs — aider](https://aider.chat/docs/repomap.html)
- [Improving GPT-4's codebase understanding with ctags — aider](https://aider.chat/docs/ctags.html)
- [PowerShell RepoMap support issue #4433 — aider](https://github.com/Aider-AI/aider/issues/4433)
- [How Cursor Indexes Codebases Fast — Engineer's Codex](https://read.engineerscodex.com/p/how-cursor-indexes-codebases-fast)
- [Securely indexing large codebases — Cursor blog](https://cursor.com/blog/secure-codebase-indexing)
- [How Cody understands your codebase — Sourcegraph](https://sourcegraph.com/blog/how-cody-understands-your-codebase)
- [The anatomy of an AI coding assistant — Sourcegraph](https://sourcegraph.com/blog/anatomy-of-a-coding-assistant)
- [Cody FAQs (embeddings replaced by Sourcegraph Search) — Sourcegraph docs](https://sourcegraph.com/docs/cody/faq)
- [Using CLAUDE.MD files — Anthropic](https://claude.com/blog/using-claude-md-files)
- [Best practices for Claude Code — Anthropic](https://code.claude.com/docs/en/best-practices)
- [CLAUDE.md manifest analysis — Emergent Mind](https://www.emergentmind.com/topics/claude-md-files)
