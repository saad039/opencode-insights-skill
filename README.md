# OpenCode Insights

Generate a comprehensive HTML usage report analyzing your OpenCode sessions — project areas, interaction patterns, friction points, actionable suggestions, cost breakdown, model/agent usage, and more.

Inspired by Claude Code's `/insights` command, rebuilt from scratch for the OpenCode ecosystem.

## Requirements

- [OpenCode](https://opencode.ai) installed and used (needs session history in `~/.local/share/opencode/opencode.db`)
- Python 3.8+ (stdlib only — zero pip dependencies)

## Installation

Clone the repo and copy the `insights/` folder to one of OpenCode's skill directories:

```bash
git clone https://github.com/saad039/opencode-insights-skill.git
cp -r opencode-insights-skill/insights/ ~/.config/opencode/skills/insights/
```

This installs it globally — available across all your projects. Alternatively, drop it into a specific project:

```bash
cp -r opencode-insights-skill/insights/ /path/to/project/.opencode/skills/insights/
```

OpenCode discovers skills automatically by walking up from your working directory. Any of these paths work:

| Path | Scope |
|------|-------|
| `~/.config/opencode/skills/insights/` | Global — all projects |
| `.opencode/skills/insights/` | Project-local |
| `.agents/skills/insights/` | Project-local (alt) |

### Verify

Open OpenCode and check that `insights` appears in `/skills`, or ask the agent to load it.

## Usage

Ask the agent to run the insights skill. The orchestrator will handle the full pipeline automatically. On completion you get a self-contained HTML report you can open in any browser:

```
file://~/.local/share/opencode/insights/report.html
```

## How It Works

The skill runs an 8-step pipeline orchestrated by the agent via `SKILL.md`:

```
┌──────────────────────────────────────────────────────────────┐
│  1. EXTRACT           Python queries SQLite DB               │
│     extract_sessions.py → meta.json + transcripts/           │
│     Rolls up child session stats (subagent tool counts,      │
│     tokens, costs, agent modes) into parent sessions.        │
│     Appends subagent result summaries to transcripts.        │
│     Discovers existing setup (agents, skills, commands,      │
│     tools, plugins, formatters, MCP, AGENTS.md, config).     │
├──────────────────────────────────────────────────────────────┤
│  2. FACET EXTRACTION    Parallel subagents (up to 50)        │
│     Each @facet-extractor reads one session transcript       │
│     (now enriched with subagent summaries), analyzes it,     │
│     and writes structured facets JSON.                       │
│     Cached in ~/.local/share/opencode/insights/facets/       │
├──────────────────────────────────────────────────────────────┤
│  3. AGGREGATE           Python merges all stats + facets     │
│     aggregate.py → aggregate.json + section prompts          │
├──────────────────────────────────────────────────────────────┤
│  4. SECTION GENERATION  6x @section-generator in parallel    │
│     + 1x @suggestions-generator (uses webfetch to verify     │
│     suggestions against live opencode.ai/docs)               │
├──────────────────────────────────────────────────────────────┤
│  5. SYNTHESIS           1 subagent produces at-a-glance      │
│     Reads all 7 sections → 4-part summary                    │
├──────────────────────────────────────────────────────────────┤
│  6. RENDER              Python generates self-contained HTML │
│     render_html.py → report.html (Neon Dossier design)       │
│     Auto-repairs malformed LLM JSON before rendering.        │
├──────────────────────────────────────────────────────────────┤
│  7. CONTEXT             Python builds follow-up context      │
│     So the agent can answer questions about the report       │
├──────────────────────────────────────────────────────────────┤
│  8. PRESENT             Agent shows you the report URL       │
└──────────────────────────────────────────────────────────────┘
```

## What the Report Covers

| Section | Description |
|---------|-------------|
| At a Glance | 4-part coaching summary: what's working, what's hindering, quick wins, ambitious workflows |
| What Keeps You Busy | Project areas with session counts and descriptions |
| Your Toolkit | Model distribution and full agent breakdown (build, plan, explore + custom agents like pr-review, code-reviewer, etc.) |
| Your Working Style | Interaction narrative, response times, parallel session detection, time-of-day activity |
| The Highlights Reel | Your best workflows and accomplishments |
| Room To Grow | Friction categories with specific examples (framed as assistant failures, not user blame) |
| The Bottom Line | Cost by model, token usage (input/output/reasoning) |
| Worth Exploring | AGENTS.md additions, custom commands/skills/agents to create, usage patterns — verified against live OC docs |
| What's Coming | Ambitious future workflows as models improve |


## Data Accuracy

- **Child session rollup**: Subagent work (functional-reviewer, code-reviewer, etc.) lives in child sessions. Stats are rolled up into parents so agent/tool/token counts reflect the full picture. Subagent summaries are appended to transcripts for richer facet extraction.
- **Grounded suggestions**: The `@suggestions-generator` uses `webfetch` to verify syntax against live opencode.ai/docs before recommending anything.
- **No duplicates**: The extraction step discovers your existing agents, skills, commands, tools, plugins, formatters, MCP servers, and AGENTS.md content — the LLM won't suggest what you already have.
- **Honest satisfaction**: Corrections count as dissatisfied, not "likely satisfied". Interruptions count as frustrated.
- **JSON repair**: LLM-generated section files with invalid escape sequences are auto-repaired before rendering.

## Caching

Facet extraction (the expensive LLM calls) is cached per-session in `~/.local/share/opencode/insights/facets/`. Subsequent runs only analyze new sessions. Stale facets with non-standard keys are auto-invalidated.

To force a full re-extraction:
```bash
rm -rf ~/.local/share/opencode/insights/facets/
```

## File Structure

```
insights/
├── SKILL.md                    # Orchestrator instructions for the agent
├── README.md                   # This file
├── agents/
│   ├── facet-extractor.md      # Subagent: analyze one session transcript
│   ├── section-generator.md    # Subagent: generate one report section
│   └── suggestions-generator.md # Subagent: generate verified suggestions (uses webfetch)
└── scripts/
    ├── extract_sessions.py     # Step 1: Query SQLite → metadata + transcripts + user setup
    ├── aggregate.py            # Step 3: Merge stats + facets → aggregate JSON
    ├── render_html.py          # Step 6: Aggregate + sections → HTML report
    ├── build_return_context.py # Step 7: Build follow-up Q&A context
    ├── extract_facets_single.py # Helper for facet subagents (read/write facets)
    └── lib/
        ├── db.py               # SQLite read-only connection + queries
        ├── stats.py            # Per-session metrics extraction (tools, tokens, errors, etc.)
        ├── transcript.py       # Serialize session messages → text transcript
        ├── prompts.py          # All 12 LLM prompt templates adapted for OpenCode
        ├── labels.py           # Display labels, chart colors, error patterns
        ├── schema.py           # Facet validation
        └── html_template.py    # Neon Dossier HTML report template + chart renderers
```

## Permissions

The skill needs `bash` permission to run Python scripts. The subagents are configured as:
- `bash`: allowed (for running Python scripts and reading files)
- `edit`: denied (subagents only write via Python scripts)

If OpenCode prompts for permission, allow bash access for the insights skill.

## Data Source

All data comes from OpenCode's SQLite database at `~/.local/share/opencode/opencode.db`. The skill reads it in **read-only** mode. Tables used:
- `session` — metadata (title, project, timestamps, lines added/removed)
- `message` — messages with role, model, agent, tokens, cost
- `part` — content parts (text, tool calls, reasoning, patches)

No data is sent anywhere. The report is generated locally.
