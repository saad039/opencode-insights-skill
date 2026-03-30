---
name: insights
description: Generate a comprehensive HTML usage report analyzing your OpenCode sessions — covers project areas, interaction style, friction points, feature suggestions, and more.
---

# OpenCode Insights

Generate a detailed HTML report analyzing your OpenCode session history.

## Prerequisites

- Python 3.8+ installed
- OpenCode database exists at `~/.local/share/opencode/opencode.db`

## Pipeline

Follow these steps in order. All Python scripts are in this skill's `scripts/` directory. Determine the absolute path to this skill directory first (the directory containing this SKILL.md file).

### Step 1: Extract Session Data

```bash
python3 <skill_dir>/scripts/extract_sessions.py --db ~/.local/share/opencode/opencode.db --out /tmp/opencode-insights-$(date +%s)/
```

This outputs the working directory path. Save it as `WORK_DIR`. It also prints how many qualifying sessions were found. If 0, inform the user and stop.

### Step 2: Facet Extraction

Check which sessions need facet extraction:

```bash
cat $WORK_DIR/uncached_sessions.json
```

For each uncached session ID (max 50), spawn a `@facet-extractor` subagent with this instruction:

> Read the transcript at `$WORK_DIR/transcripts/<session_id>.txt`, extract facets, and write the result to `$WORK_DIR/facets/<session_id>.json`. The skill directory is `<skill_dir>`.

You may spawn multiple facet-extractor subagents in parallel for faster processing.

If a subagent fails to produce valid JSON, retry once. If it fails again, skip that session.

### Step 3: Aggregate

After all facets are extracted:

```bash
python3 <skill_dir>/scripts/aggregate.py --work $WORK_DIR
```

This merges all session metadata + facets into `$WORK_DIR/aggregate.json` and writes section prompts to `$WORK_DIR/prompts/`.

### Step 4: Generate Report Sections

Spawn 6 `@section-generator` subagents in parallel AND 1 `@suggestions-generator` subagent:

**Using `@section-generator`** (6 sections):

| Section | Prompt File | Output File |
|---------|-------------|-------------|
| project_areas | `$WORK_DIR/prompts/project_areas.txt` | `$WORK_DIR/sections/project_areas.json` |
| interaction_style | `$WORK_DIR/prompts/interaction_style.txt` | `$WORK_DIR/sections/interaction_style.json` |
| what_works | `$WORK_DIR/prompts/what_works.txt` | `$WORK_DIR/sections/what_works.json` |
| friction_analysis | `$WORK_DIR/prompts/friction_analysis.txt` | `$WORK_DIR/sections/friction_analysis.json` |
| on_the_horizon | `$WORK_DIR/prompts/on_the_horizon.txt` | `$WORK_DIR/sections/on_the_horizon.json` |
| fun_ending | `$WORK_DIR/prompts/fun_ending.txt` | `$WORK_DIR/sections/fun_ending.json` |

**Using `@suggestions-generator`** (1 section — this agent verifies suggestions against live OpenCode docs):

| Section | Prompt File | Output File |
|---------|-------------|-------------|
| suggestions | `$WORK_DIR/prompts/suggestions.txt` | `$WORK_DIR/sections/suggestions.json` |

All 7 can be spawned in parallel. Each subagent should:
1. Read its prompt file and the aggregate data at `$WORK_DIR/aggregate.json`
2. Analyze and produce JSON output
3. Write the result to its output file

The `@suggestions-generator` will additionally use `webfetch` to verify syntax and best practices against https://opencode.ai/docs/ before finalizing suggestions.

### Step 5: At-a-Glance Synthesis

After all 7 sections are complete, spawn one more `@section-generator` subagent:

> Read all section results from `$WORK_DIR/sections/*.json` and the aggregate data from `$WORK_DIR/aggregate.json`. Produce a 4-part summary with keys: `whats_working`, `whats_hindering`, `quick_wins`, `ambitious_workflows`. Each should be 2-3 sentences with a coaching tone. Do NOT mention specific stats or underlined_categories. Write the result to `$WORK_DIR/sections/at_a_glance.json`.

### Step 6: Render HTML Report

```bash
python3 <skill_dir>/scripts/render_html.py --work $WORK_DIR --out ~/.local/share/opencode/insights/report.html
```

### Step 7: Build Follow-up Context

```bash
python3 <skill_dir>/scripts/build_return_context.py --work $WORK_DIR
```

Read the output file at `$WORK_DIR/return_context.txt` so you can answer follow-up questions about any section or data point.

### Step 8: Present to User

Tell the user:

> Your OpenCode Insights report is ready: `file:///home/$USER/.local/share/opencode/insights/report.html` (replace `$USER` with the current system username). 
>
> Want to dig into any section or try one of the suggestions?
