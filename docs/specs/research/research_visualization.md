# Research: Visual representations of repos & processes (2025-2026)

Scope: tools and patterns for agent-generated visuals that serve both humans (README, docs) and agents (compressed context).

---

## 1. Repo-level visuals

| Tool | Type | Agent-generatable | Stays fresh | Best for |
|------|------|-------------------|-------------|----------|
| **Mermaid C4/component in README** | Diagram-as-code, in-repo | Yes (Claude writes mermaid directly) | Only with discipline / CI regen | Curated, small-to-medium repos. Renders natively on GitHub. |
| **GitDiagram** (`gitdiagram.com`, [ahmedkhaleel2004/gitdiagram](https://github.com/ahmedkhaleel2004/gitdiagram)) | Hosted SaaS, two-pass LLM | No (external service) | Re-run on demand; not committed | Quick external comprehension. Replace `hub` with `diagram` in any GitHub URL. Components are clickable to source. |
| **Repomix** ([yamadashy/repomix](https://github.com/yamadashy/repomix)) | Flat dump w/ TOC | Yes (CLI) | Regenerate per use | Feeding repo to LLMs. ~56M tokens vs GitIngest's 69M on same repo (Tree-sitter compression). |
| **GitIngest** ([coderamp-labs/gitingest](https://github.com/coderamp-labs/gitingest)) | Hosted + CLI | Yes | Zero-setup, URL trick | Fastest path to a single-text digest. |
| **madge / dependency-cruiser** | AST-based dep graph -> SVG/mermaid | Yes (deterministic) | Trivial to regen in CI | Auto JS/TS module graphs. Outputs mermaid that drops straight into README. |
| **Diagrams (Python)**, **D2**, **Structurizr DSL** | DSL-based | Partially | Best paired with CI | Cloud architectures, C4. One enterprise cited cut documentation lag from 3 weeks to 2 days after moving Visio -> Structurizr DSL + Git. |
| **C4-Agent MCP** ([jonverrier/C4Diagrammer](https://github.com/jonverrier/C4-Agent)) | MCP server, AI-generated C4 | Yes (Claude via MCP) | Re-run | Legacy codebase comprehension. |

**Verdict for this repo**: hand-curated mermaid in README + a small `scripts/gen-dep-graph` walker (madge or custom) for the few graphs that should auto-regen. GitDiagram is a one-shot external view, not part of an in-repo workflow.

---

## 2. Process / workflow visuals

GitHub natively renders Mermaid in markdown without plugins; PlantUML requires committing rendered images (which drift); Excalidraw has no code integration but wins on collaborative whiteboarding. For Claude Code's UI: mermaid in markdown is what's understood and rendered well, and it's what the existing `mermaid-skill`, `claude-mermaid` MCP, and `awesome-skills/mermaid-syntax-skill` projects all target.

For "what happens when user runs `/commit-smart`" use **`sequenceDiagram`** (participants = User, MainSession, Subagent, Git). For "how a hook intercepts a Bash call" use **`flowchart LR`** with decision diamonds. Don't reach for PlantUML/Excalidraw unless you specifically need UML class/state machines or freeform sketches.

Token cost note: a mermaid diagram for a 10-15 step workflow costs ~150-350 tokens vs 800-1,500 for prose — a 3-6x context win that matters for skill files.

---

## 3. AI-generated mermaid (Claude Opus 4.7)

Practitioner reports ([Korny's blog Oct 2025](https://blog.korny.info/2025/10/10/agent-mermaid-reporting-for-duty), [Zolkos Nov 2025](https://www.zolkos.com/2025/11/26/mermaid-validation-skill-for-claude-code)) converge on:

- **What Claude gets wrong**: special-char escaping in node labels (parens, colons, slashes), reserved words (`end`, `class`, `subgraph` IDs collide), inconsistent arrow syntax across diagram types, stale syntax (it skews to older mermaid), and over-busy diagrams when given vague prompts.
- **What works**:
  1. **Validation loop**: pipe output through `mmdc` (mermaid-cli) and feed errors back. The `awesome-skills/mermaid-syntax-skill` and `veelenga/claude-mermaid` MCP do exactly this with live-reload.
  2. **Focused prompts**: state diagram type, max node count, and "no labels containing parens/colons — wrap in quotes."
  3. **Multimodal feedback**: render to PNG, let Claude view it, ask "is this readable?" — catches layout issues.
  4. **Subagent for batch generation**: one diagram per task works fine inline; many diagrams should be delegated.

---

## 4. Pencil MCP

Pencil (`docs.pencil.dev`) is a **UI/UX design tool for web and mobile**, not architecture diagrams. `.pen` files are encrypted JSON; the MCP server (`mcp__pencil__*` tools installed in this environment) ships guideline topics like `landing-page`, `mobile-app`, `web-app`, `slides`, `design-system`, `tailwind` — every one is UI surface design. The "Pencil to Code" skill outputs React + Tailwind from a pen file. **Not useful for repo/process diagrams.** Use it only if claude-leverage ever grows a marketing site or dashboard UI.

---

## 5. Freshness — what well-maintained OSS projects actually do in 2026

Two patterns dominate, and they're not mutually exclusive:

1. **Regenerate-from-truth in CI** for things that have a single source of truth: dependency graphs (madge), cloud topology (Diagrams Python / Structurizr from IaC), API sequence diagrams (from OpenAPI). PR check fails if committed diagram differs from regenerated.
2. **Hand-curated but tiny** for conceptual architecture: 1-2 mermaid blocks max in top-level README, treated as canonical and reviewed on every architecturally relevant PR. The IcePanel blog and Zus Health write-ups both land here: small + reviewed beats large + auto-generated for conceptual diagrams, because auto-generated component diagrams from code tend to be too noisy to be useful.

**Recommendation for claude-leverage**: hand-curated mermaid in README (already present), plus optionally a `docs-sync`-style check that flags PRs touching `hooks/`, `commands/`, or `agents/` if the diagram block wasn't updated. The existing `claude-leverage:docs-sync` skill is the natural home.

Sources:
- [GitDiagram](https://github.com/ahmedkhaleel2004/gitdiagram), [gitdiagram.com](https://gitdiagram.com/)
- [Repomix](https://github.com/yamadashy/repomix), [GitIngest](https://github.com/coderamp-labs/gitingest)
- [Mermaid C4 syntax](https://mermaid.js.org/syntax/c4.html), [C4-Agent MCP](https://github.com/jonverrier/C4-Agent)
- [Korny: Agent Mermaid reporting for duty](https://blog.korny.info/2025/10/10/agent-mermaid-reporting-for-duty)
- [Zolkos: A Mermaid Validation Skill for Claude Code](https://www.zolkos.com/2025/11/26/mermaid-validation-skill-for-claude-code)
- [awesome-skills/mermaid-syntax-skill](https://github.com/awesome-skills/mermaid-syntax-skill), [veelenga/claude-mermaid](https://github.com/veelenga/claude-mermaid)
- [Mermaid vs PlantUML vs Draw.io (mermaideditor)](https://mermaideditor.com/blog/mermaid-vs-plantuml-vs-drawio)
- [Diagrams As Code In Your Repo's README (Zus Health)](https://zushealth.com/diagrams-as-code-in-your-repos-readme/)
- [IcePanel: pros and cons of diagram-as-code](https://icepanel.io/blog/2025-02-05-the-pros-and-cons-of-diagram-as-code-for-software-architecture)
- [Pencil.dev docs](https://docs.pencil.dev/getting-started/ai-integration)
- [MindStudio: Mermaid in Claude Code Skills for context compression](https://www.mindstudio.ai/blog/mermaid-diagrams-claude-code-skills-context-compression)
