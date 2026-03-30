"""LLM prompt templates for OpenCode Insights, adapted for OpenCode ecosystem."""

import json
from pathlib import Path


FACET_EXTRACTION_PROMPT = """\
Analyze this OpenCode session and extract structured facets.

CRITICAL GUIDELINES:

1. **goal_categories**: Count ONLY what the USER explicitly asked for.
   - DO NOT count autonomous codebase exploration
   - DO NOT count work the assistant decided to do on its own
   - ONLY count when user says "can you...", "please...", "I need...", "let's..."

2. **user_satisfaction_counts**: Be HONEST. Do not sugarcoat. Base on ALL signals, not just explicit praise.
   - "Yay!", "great!", "perfect!", "exactly what I needed" → happy
   - "thanks", "looks good", "that works" (genuine, not dismissive) → satisfied
   - User continues without complaint AND the task was completed correctly → likely_satisfied
   - User had to repeat themselves, correct the assistant, or redirect approach → dissatisfied
   - User gave up, said "no", "wrong", "not what I asked", "try again", or had to explain the same thing 2+ times → frustrated
   - Cannot determine from transcript → unsure

   IMPORTANT: Do NOT default to likely_satisfied just because the user kept talking. If the user:
   - Had to correct the assistant → that's dissatisfied, not likely_satisfied
   - Had to repeat a request → that's dissatisfied
   - Said "ok" but then immediately changed approach → that's dissatisfied
   - Moved on after a failed attempt without acknowledgment → that's unsure, not satisfied
   - Interrupted the assistant → that's frustrated
   Count EACH distinct interaction/task separately. A session can have MULTIPLE satisfaction signals.

3. **friction_counts**: Be specific about what went wrong.
   - misunderstood_request: Interpreted user incorrectly
   - wrong_approach: Right goal, wrong solution method
   - buggy_code: Code didn't work correctly
   - user_rejected_action: User said no/stop to a tool call
   - excessive_changes: Over-engineered or changed too much

4. If very short or just warmup, use warmup_minimal for goal_category

5. **goal_categories keys** MUST be from this list ONLY:
   debug_investigate, implement_feature, fix_bug, write_script_tool, refactor_code,
   configure_system, create_pr_commit, analyze_data, understand_codebase, write_tests,
   write_docs, deploy_infra, code_review, warmup_minimal

6. **friction_counts keys** MUST be from this list ONLY:
   misunderstood_request, wrong_approach, buggy_code, user_rejected_action, got_blocked,
   user_stopped_early, wrong_file_or_location, excessive_changes, slow_or_verbose,
   tool_failed, user_unclear, external_issue

SESSION:
"""

FACET_RESPONSE_SCHEMA = """\

RESPOND WITH ONLY A VALID JSON OBJECT:
{
  "underlying_goal": "What the user fundamentally wanted to achieve",
  "goal_categories": {"category_name": count},
  "outcome": "fully_achieved|mostly_achieved|partially_achieved|not_achieved|unclear_from_transcript",
  "user_satisfaction_counts": {"level": count},
  "assistant_helpfulness": "unhelpful|slightly_helpful|moderately_helpful|very_helpful|essential",
  "session_type": "single_task|multi_task|iterative_refinement|exploration|quick_question",
  "friction_counts": {"friction_type": count},
  "friction_detail": "One sentence describing friction or empty",
  "primary_success": "none|fast_accurate_search|correct_code_edits|good_explanations|proactive_help|multi_file_changes|good_debugging",
  "brief_summary": "One sentence: what user wanted and whether they got it"
}"""

CHUNK_SUMMARY_PROMPT = """\
Summarize this portion of an OpenCode session transcript. Focus on:
1. What the user asked for
2. What the assistant did (tools used, files modified)
3. Any friction or issues
4. The outcome

Keep it concise - 3-5 sentences. Preserve specific details like file names, error messages, and user feedback.

TRANSCRIPT CHUNK:
"""

SECTION_PROMPTS = {
    "project_areas": """\
Analyze this OpenCode usage data and identify project areas.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "areas": [
    {{"name": "Area name", "session_count": N, "description": "2-3 sentences about what was worked on and how OpenCode was used."}}
  ]
}}

Include 4-5 areas. Skip internal operations.""",

    "interaction_style": """\
Analyze this OpenCode usage data and describe the user's interaction style.

Pay attention to:
- Which agent modes they prefer (plan, explore, build)
- Whether they switch models for different tasks
- How they delegate to subagents

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "narrative": "2-3 paragraphs analyzing HOW the user interacts with OpenCode. Use second person 'you'. Describe patterns: iterate quickly vs detailed upfront specs? Interrupt often or let the assistant run? Use different agent modes strategically? Include specific examples. Use **bold** for key insights.",
  "key_pattern": "One sentence summary of most distinctive interaction style"
}}""",

    "what_works": """\
Analyze this OpenCode usage data and identify what's working well for this user. Use second person ("you").

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "intro": "1 sentence of context",
  "impressive_workflows": [
    {{"title": "Short title (3-6 words)", "description": "2-3 sentences describing the impressive workflow or approach. Use 'you' not 'the user'."}}
  ]
}}

Include 3 impressive workflows.""",

    "friction_analysis": """\
Analyze this OpenCode usage data and identify friction points for this user. Use second person ("you").

IMPORTANT: When describing friction, frame it as what the ASSISTANT did wrong, not what the user did wrong.
Use language like "The assistant misunderstood..." or "OpenCode incorrectly..." rather than "You made errors..." or "You forgot...".
The friction section should help the user understand where their AI assistant fell short, not criticize the user.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "intro": "1 sentence summarizing friction patterns",
  "categories": [
    {{"category": "Concrete category name", "description": "1-2 sentences explaining this category and what could be done differently. Use 'you' not 'the user'.", "examples": ["Specific example with consequence", "Another example"]}}
  ]
}}

Include 3 friction categories with 2 examples each.""",

    "suggestions": """\
Analyze this OpenCode usage data and suggest concrete, actionable improvements.

## OPENCODE FEATURES REFERENCE

### 1. AGENTS.md — Project instructions file
The AGENTS.md file in your project root tells OpenCode how to behave. Add rules here to prevent repeated friction.
- Place at project root or `~/.config/opencode/AGENTS.md` for global rules
- Structure with `##` sections: Testing, Git, Communication Style, etc.
- Example: "Always run `npm test` after modifying files in src/auth/"

### 2. Custom Agents — Specialized agents with dedicated models/permissions
Create `.opencode/agents/<name>.md` with YAML frontmatter:
```
---
description: Reviews PRs for code quality
mode: subagent
model: moonshotai/kimi-k2.5
permission:
  bash:
    "gh *": "allow"
  edit: "deny"
---
You are a PR reviewer. For each PR:
1. Fetch the diff with `gh pr diff`
2. Check for: bugs, missing tests, security issues
3. Post review via `gh pr review --comment`
```
Good for: repetitive workflows you do 3+ times

### 3. Custom Commands — Slash commands that trigger specific prompts
Create `.opencode/commands/<name>.md` with frontmatter:
```
---
description: Review a PR
agent: build
---
Review PR $1 in this repo. Fetch the diff, analyze each changed file,
and post a review comment on GitHub with `gh pr review $1 --comment`.
Focus on: code quality, test coverage, breaking changes.
```
Then type `/review 87` to run it. Use `$1`, `$2` for arguments, `$ARGUMENTS` for all.

### 4. Agent Skills — Multi-step workflows as reusable recipes
Create `.opencode/skills/<name>/SKILL.md`:
```
---
name: pr-review
description: Comprehensive multi-agent PR review
---
## Steps
1. Fetch PR: `gh pr view $ARGUMENTS --json files,body`
2. For each changed file, analyze for issues
3. Check test coverage exists for new code
4. Post review: `gh pr review $ARGUMENTS --request-changes --body "..."`
```

### 5. MCP Servers — Connect to external APIs and databases
In opencode.json:
```json
{{
  "mcp": {{
    "sentry": {{
      "type": "remote",
      "url": "https://mcp.sentry.dev/mcp"
    }},
    "context7": {{
      "type": "remote",
      "url": "https://mcp.context7.com/mcp"
    }},
    "local-db": {{
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-sqlite", "path/to/db.sqlite"]
    }}
  }}
}}
```
Good for: database queries, error tracking, documentation lookup, GitHub integration.
Supports OAuth for remote servers. Use `opencode mcp auth <name>` to authenticate.
NOTE: MCP is being superseded by native skills and CLI integrations in the OpenCode ecosystem. Prefer suggesting custom commands, skills, and plugins over MCP servers.

### 6. Custom Tools — TypeScript functions the LLM can call
Create `.opencode/tools/<name>.ts`:
```typescript
import {{ tool }} from "@opencode-ai/plugin"
export default tool({{
  description: "Query project database",
  args: {{ query: tool.schema.string().describe("SQL query") }},
  async execute(args) {{
    const result = await Bun.$`sqlite3 db.sqlite ${{args.query}}`.text()
    return result.trim()
  }},
}})
```

### 6. Formatters — Auto-format code per language
In `opencode.json`:
```json
{{
  "formatter": {{
    "typescript": {{ "command": "npx prettier --write $FILE" }},
    "python": {{ "command": "ruff format $FILE" }},
    "rust": {{ "command": "rustfmt $FILE" }}
  }}
}}
```

### 7. Agent Modes — Right tool for the right job
- **plan**: Read-only, no file changes. Use for architecture/design.
- **explore**: Search-focused subagent. Use for codebase investigation.
- **build**: Full access. Use for implementation.
Press Tab to cycle. Configure default: `"default_agent": "build"` in opencode.json.

### 8. Custom Commands — Slash commands with arguments
Create `.opencode/commands/<name>.md`:
```
---
description: Review a PR by number
agent: build
---
Review PR $1 in this repo. Fetch the diff with `gh pr diff $1`, analyze
each changed file for bugs, missing tests, and security issues. Post a
review comment via `gh pr review $1 --comment --body "..."`.
```
Then type `/review 87`. Use `$1` for first arg, `$ARGUMENTS` for all.
Use `!`git branch --show-current`` to inject shell output into prompts.
Use `@filename` to attach file content.

### 9. GitHub Actions — Automated PR reviews and issue handling
Add OpenCode as a GitHub Action that triggers on PR/issue events:
- Mention `/opencode` in PR comments to trigger a task
- Auto-review PRs when opened/updated
- Cron-schedule recurring tasks (e.g., "review codebase for TODOs weekly")
- Create branches and open PRs to resolve issues automatically
Requires: model config, API key in GitHub Secrets, permissions for contents/PRs/issues.

### 10. CLI Headless Mode — Run OpenCode from scripts
```bash
opencode run "Fix the failing test in src/auth.ts"
```
- `opencode run "..."` for non-interactive execution
- `opencode serve` starts a persistent HTTP server; attach with `opencode run --attach http://localhost:4096 "..."`
- `--format json` for machine-readable output in CI/CD
- `--continue` to resume last session
- `--file path` to attach files to the prompt

### 11. Permissions — Granular tool access control
In opencode.json:
```json
{{
  "permission": {{
    "bash": {{
      "*": "ask",
      "git *": "allow",
      "npm test": "allow",
      "rm *": "deny"
    }},
    "edit": {{
      "*": "ask",
      "src/generated/*": "deny"
    }},
    "task": {{
      "*": "allow",
      "code-reviewer": "allow"
    }}
  }}
}}
```
Per-agent overrides in agent frontmatter: `permission: {{ edit: "deny" }}`.

### 12. Plugins — Hook into OpenCode events
Create `.opencode/plugins/my-plugin.ts`:
- `tool.execute.before` — intercept/block tool calls (e.g., block .env reads)
- `session.idle` — trigger notifications when work completes
- `shell.env` — inject environment variables into shell executions
- `experimental.session.compacting` — customize context preserved across compactions

### 13. Session Sharing — Share sessions for collaboration
- `/share` generates a public URL (`opncd.ai/s/<id>`)
- `"share": "auto"` in opencode.json auto-shares all sessions
- `/unshare` removes public access

### 14. opencode.json — Central configuration
```json
{{
  "model": "moonshotai/kimi-k2.5",
  "default_agent": "build",
  "permission": {{
    "bash": {{ "git *": "allow", "npm test": "allow" }},
    "edit": "ask"
  }},
  "compaction": "auto",
  "formatter": {{
    "typescript": {{ "command": "npx prettier --write $FILE" }}
  }}
}}
```

## OUTPUT REQUIREMENTS

Your suggestions MUST be concrete and copy-pasteable. Do NOT say "consider creating an agent" — instead write out the FULL agent file content. Do NOT say "add a rule to AGENTS.md" — write the EXACT text to add.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "opencode_config_additions": [
    {{
      "instruction": "The EXACT text to add. Must be a complete, copy-pasteable instruction. E.g., 'When reviewing PRs, always fetch the diff first with gh pr diff, then analyze each file for: bugs, missing tests, and security issues.'",
      "placement": "Exact location: 'Add to AGENTS.md under ## PR Reviews section' or 'Add to ~/.config/opencode/AGENTS.md under ## Git Workflow'",
      "why": "1 sentence citing specific session evidence"
    }}
  ],
  "features_to_try": [
    {{
      "feature": "Feature name (e.g., 'Custom Agent: PR Reviewer')",
      "one_liner": "What it does in one sentence",
      "why_for_you": "Why this helps YOU based on your actual session patterns",
      "example_code": "COMPLETE, COPY-PASTEABLE file content or config. Include the full frontmatter, the full prompt, the full command. The user should be able to copy this and paste it into a file and have it work."
    }}
  ],
  "usage_patterns": [
    {{
      "title": "Short actionable title",
      "suggestion": "1-2 sentence summary",
      "detail": "3-4 sentences with specific references to YOUR sessions and projects",
      "copyable_prompt": "A specific prompt the user can paste into OpenCode right now"
    }}
  ]
}}

CRITICAL RULES:
- For opencode_config_additions: PRIORITIZE instructions the user had to repeat in 2+ sessions. They should NOT have to repeat themselves.
- For features_to_try: Pick 2-3 features. Each example_code MUST be a COMPLETE file that works when copy-pasted. Include frontmatter, full prompt, everything. Do NOT use placeholders like <your-repo> — use actual project names from the session data.
- For usage_patterns: Each copyable_prompt must be a real prompt the user can paste.
- Include 3-5 items in each category.
- CHECK THE USER'S EXISTING SETUP section below. Do NOT suggest creating agents, skills, commands, or tools the user ALREADY HAS. Instead, suggest IMPROVEMENTS to existing ones, or suggest NEW ones for workflows not yet covered. If the user already has a pr-review agent, don't suggest creating one — suggest enhancing it or creating something they DON'T have yet.
- When suggesting AGENTS.md additions, check the existing AGENTS.md content first. Don't duplicate rules already there.
- DEPRIORITIZE MCP servers. The OpenCode ecosystem favors custom commands (.opencode/commands/), agent skills (.opencode/skills/), and plugins (.opencode/plugins/) over MCP. Only suggest MCP if there's a clear, specific use case that cannot be solved with skills or commands.""",

    "on_the_horizon": """\
Analyze this OpenCode usage data and identify future opportunities.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "intro": "1 sentence about evolving AI-assisted development",
  "opportunities": [
    {{"title": "Short title (4-8 words)", "whats_possible": "2-3 ambitious sentences about autonomous workflows", "how_to_try": "1-2 sentences mentioning relevant tooling", "copyable_prompt": "Detailed prompt to try"}}
  ]
}}

Include 3 opportunities. Think BIG — autonomous workflows, parallel agents, iterating against tests.""",

    "fun_ending": """\
Analyze this OpenCode usage data and find a memorable moment.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "headline": "A memorable QUALITATIVE moment from the transcripts — not a statistic. Something human, funny, or surprising.",
  "detail": "Brief context about when/where this happened"
}}

Find something genuinely interesting or amusing from the session summaries.""",
}

AT_A_GLANCE_PROMPT = """\
You're writing an "At a Glance" summary for an OpenCode usage insights report. The goal is to help the user understand their usage and improve how they use OpenCode, especially as models improve.

Use this 4-part structure:

1. **What's working** — What is the user's unique style of interacting with OpenCode and what are some impactful things they've done? You can include one or two details, but keep it high level since things might not be fresh in the user's memory. Don't be fluffy or overly complimentary. Also, don't focus on the tool calls they use.

2. **What's hindering you** — Split into (a) assistant's fault (misunderstandings, wrong approaches, bugs) and (b) user-side friction (not providing enough context, environment issues — ideally more general than just one project). Be honest but constructive.

3. **Quick wins to try** — Specific OpenCode features they could try from the examples below, or a workflow technique if you think it's really compelling. (Avoid stuff like "Ask the assistant to confirm before taking actions" or "Type out more context up front" which are less compelling.)

4. **Ambitious workflows for better models** — As we move to much more capable models over the next 3-6 months, what should they prepare for? What workflows that seem impossible now will become possible? Draw from the appropriate section below.

Keep each section to 2-3 not-too-long sentences. Don't overwhelm the user. Don't mention specific numerical stats or underlined_categories from the session data below. Use a coaching tone.

RESPOND WITH ONLY A VALID JSON OBJECT:
{{
  "whats_working": "(refer to instructions above)",
  "whats_hindering": "(refer to instructions above)",
  "quick_wins": "(refer to instructions above)",
  "ambitious_workflows": "(refer to instructions above)"
}}

SESSION DATA:
{context}

## Project Areas (what user works on)
{project_areas}

## Big Wins (impressive accomplishments)
{what_works}

## Friction Categories (where things go wrong)
{friction_analysis}

## Features to Try
{features_to_try}

## Usage Patterns to Adopt
{usage_patterns}

## On the Horizon (ambitious workflows for better models)
{on_the_horizon}"""


def build_section_context(aggregate: dict) -> str:
    """Build the context string passed to each section generator."""
    agg = aggregate
    top_tools = sorted(
        agg.get("tool_counts", {}).items(), key=lambda x: x[1], reverse=True
    )[:8]
    top_goals = sorted(
        agg.get("goal_categories", {}).items(), key=lambda x: x[1], reverse=True
    )[:8]

    lines = [
        f"Sessions: {agg.get('total_sessions', 0)} | "
        f"Analyzed: {agg.get('sessions_with_facets', 0)} | "
        f"Date range: {agg.get('date_range', {}).get('start', '?')[:10]} – "
        f"{agg.get('date_range', {}).get('end', '?')[:10]}",
        f"Messages: {agg.get('total_messages', 0)} | "
        f"Hours: {agg.get('total_duration_hours', 0)} | "
        f"Commits: {agg.get('git_commits', 0)}",
        f"Top tools: {', '.join(f'{k}({v})' for k, v in top_tools)}",
        f"Top goals: {', '.join(f'{k}({v})' for k, v in top_goals)}",
        f"Outcomes: {', '.join(f'{k}({v})' for k, v in agg.get('outcomes', {}).items())}",
        f"Satisfaction: {', '.join(f'{k}({v})' for k, v in agg.get('satisfaction', {}).items())}",
        f"Friction: {', '.join(f'{k}({v})' for k, v in agg.get('friction', {}).items())}",
        f"Languages: {', '.join(f'{k}({v})' for k, v in agg.get('languages', {}).items())}",
        f"Your models: {', '.join(f'{k}({v})' for k, v in agg.get('model_counts', {}).items())}",
        f"Your agents: {', '.join(f'{k}({v})' for k, v in agg.get('agent_counts', {}).items())}",
        f"Subagent models: {', '.join(f'{k}({v})' for k, v in agg.get('child_model_counts', {}).items())}",
        f"Subagent activity: {', '.join(f'{k}({v})' for k, v in agg.get('child_agent_counts', {}).items())}",
        f"Total cost: ${agg.get('total_cost', 0):.2f}",
    ]

    lines.append("")
    lines.append("SESSION SUMMARIES:")
    for s in agg.get("session_summaries", [])[:50]:
        date = s.get("date", "?")[:10]
        sid = s.get("id", "?")[:12]
        summary = s.get("summary", "")
        goal = s.get("goal", "")
        lines.append(f"- [{date}] {sid}... \"{summary}\" — Goal: {goal}")

    # Friction details
    friction_details = agg.get("friction_details", [])
    if friction_details:
        lines.append("")
        lines.append("FRICTION DETAILS:")
        for fd in friction_details[:30]:
            lines.append(f"- {fd}")

    return "\n".join(lines)


def build_user_setup_context(user_setup: dict) -> str:
    """Build a context string describing the user's existing agents, skills, etc."""
    lines = []
    has_anything = False

    def _section(title: str, data: dict, item_type: str = "items"):
        nonlocal has_anything
        if not data:
            return
        has_anything = True
        lines.append(f"\n{title} (do NOT suggest creating these — suggest improvements or NEW ones):")
        for project, items in data.items():
            if isinstance(items, list):
                lines.append(f"  Project '{project}': {', '.join(items)}")
            elif isinstance(items, dict):
                lines.append(f"  Project '{project}': {json.dumps(items)}")

    _section("EXISTING CUSTOM AGENTS", user_setup.get("agents", {}))
    _section("EXISTING CUSTOM SKILLS", user_setup.get("skills", {}))
    _section("EXISTING CUSTOM COMMANDS", user_setup.get("commands", {}))
    _section("EXISTING CUSTOM TOOLS", user_setup.get("tools", {}))
    _section("EXISTING MCP SERVERS", user_setup.get("mcp_servers", {}))
    _section("EXISTING PLUGINS", user_setup.get("plugins", {}))
    _section("EXISTING FORMATTERS", user_setup.get("formatters", {}))
    _section("EXISTING GITHUB ACTIONS WITH OPENCODE", user_setup.get("github_actions", {}))

    permissions = user_setup.get("permissions", {})
    if permissions:
        has_anything = True
        lines.append("\nEXISTING PERMISSIONS CONFIG:")
        for project, perm in permissions.items():
            lines.append(f"  Project '{project}': {json.dumps(perm, indent=2)}")

    opencode_config = user_setup.get("opencode_config", {})
    if opencode_config:
        has_anything = True
        lines.append("\nOPENCODE.JSON CONFIG:")
        for project, cfg in opencode_config.items():
            lines.append(f"  Project '{project}': {json.dumps(cfg)}")

    agents_md = user_setup.get("agents_md", {})
    if agents_md:
        has_anything = True
        lines.append("\nEXISTING AGENTS.MD CONTENT:")
        for project, content in agents_md.items():
            lines.append(f"--- {project} ---")
            lines.append(content[:1000])

    if not has_anything:
        lines.append("USER HAS NO CUSTOM CONFIGURATION. All features are available to suggest.")

    return "\n".join(lines)


def write_section_prompts(output_dir: str, aggregate: dict, user_setup: dict | None = None) -> None:
    """Write all 7 section prompt files to output_dir, filled with context."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    context = build_section_context(aggregate)

    # Build user setup context if available
    setup_context = ""
    if user_setup:
        setup_context = "\n\n## USER'S EXISTING SETUP\n" + build_user_setup_context(user_setup)

    for name, template in SECTION_PROMPTS.items():
        prompt = template + "\n\nSESSION DATA:\n" + context
        # Add user setup context to suggestions and at-a-glance prompts
        if name == "suggestions":
            prompt += setup_context
        (out / f"{name}.txt").write_text(prompt, encoding="utf-8")
