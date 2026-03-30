"""HTML report template and chart renderers for OpenCode Insights."""

import html
import json
import re
from typing import Any

from .labels import (
    CHART_COLORS,
    SATISFACTION_ORDER,
    OUTCOME_ORDER,
    display_label,
    GOAL_CATEGORIES,
    SUCCESS_TYPES,
    FRICTION_TYPES,
    SATISFACTION_LEVELS,
    SESSION_TYPES,
    OUTCOMES,
    HELPFULNESS,
)

HELPFULNESS_ORDER = [
    "unhelpful", "slightly_helpful", "moderately_helpful",
    "very_helpful", "essential",
]


def escape(text: str) -> str:
    """HTML-escape text."""
    return html.escape(str(text), quote=True)


def md_bold_to_html(text: str) -> str:
    """Convert **bold** markdown to <strong> tags after HTML-escaping."""
    escaped = escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def render_bar_chart(
    data: dict[str, int | float],
    color: str,
    max_items: int = 6,
    ordered_keys: list[str] | None = None,
    label_map: dict | None = None,
    value_prefix: str = "",
) -> str:
    """Render a pure-CSS horizontal bar chart.

    Args:
        data: key->value mapping.
        color: CSS color for bars.
        max_items: max bars to show.
        ordered_keys: if set, display in this order instead of sort-by-value.
        label_map: optional key->display label mapping. None uses display_label
                   with smart title-casing. Pass {} to use raw keys.
        value_prefix: prefix for displayed values (e.g. "$").
    """
    if not data and not ordered_keys:
        return '<div class="chart-empty">No data</div>'

    if ordered_keys:
        items = [(k, data.get(k, 0)) for k in ordered_keys]  # include zeros
    else:
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:max_items]

    if not items:
        return '<div class="chart-empty">No data</div>'

    max_val = max((v for _, v in items), default=0)
    if max_val == 0:
        max_val = 1

    rows = []
    for key, val in items:
        if label_map is not None:
            # Explicit label_map: use it if key present, otherwise raw key
            label = label_map.get(key, key)
        else:
            label = display_label(key, {})
        pct = (val / max_val) * 100
        if isinstance(val, float):
            display_val = f"{value_prefix}{val:.2f}"
        else:
            display_val = f"{value_prefix}{val}"
        rows.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{escape(label)}</span>'
            f'<div class="bar-track">'
            f'<div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div>'
            f'</div>'
            f'<span class="bar-value">{display_val}</span>'
            f'</div>'
        )
    return "\n".join(rows)


def render_response_time_chart(response_times: list[float], color: str) -> str:
    """Render response time histogram."""
    buckets = {
        "2-10s": 0, "10-30s": 0, "30s-1m": 0,
        "1-2m": 0, "2-5m": 0, "5-15m": 0, ">15m": 0,
    }
    for t in response_times:
        if t <= 10:
            buckets["2-10s"] += 1
        elif t <= 30:
            buckets["10-30s"] += 1
        elif t <= 60:
            buckets["30s-1m"] += 1
        elif t <= 120:
            buckets["1-2m"] += 1
        elif t <= 300:
            buckets["2-5m"] += 1
        elif t <= 900:
            buckets["5-15m"] += 1
        else:
            buckets[">15m"] += 1

    return render_bar_chart(
        buckets, color, max_items=7,
        ordered_keys=list(buckets.keys()),
        label_map={},  # raw keys, no title-casing
    )


def render_time_of_day_chart(message_hours: list[int], color: str) -> str:
    """Render hour-of-day activity histogram (raw data, JS handles timezone)."""
    counts: dict[str, int] = {}
    for h in range(24):  # Initialize ALL hours
        counts[f"{h:02d}:00"] = 0
    for h in message_hours:
        label = f"{h:02d}:00"
        counts[label] = counts.get(label, 0) + 1
    ordered = [f"{h:02d}:00" for h in range(24)]
    return render_bar_chart(counts, color, max_items=24, ordered_keys=ordered)


def _render_section_cards(items: list[dict], color: str, fields: tuple) -> str:
    """Render a list of card items."""
    cards = []
    for item in items:
        title = escape(item.get(fields[0], ""))
        body = md_bold_to_html(item.get(fields[1], ""))
        extra = ""
        if len(fields) > 2:
            extra_content = item.get(fields[2])
            if extra_content:
                if isinstance(extra_content, list):
                    bullets = "".join(f"<li>{escape(e)}</li>" for e in extra_content)
                    extra = f'<ul class="card-examples">{bullets}</ul>'
                elif isinstance(extra_content, str):
                    extra = f'<p class="card-extra">{md_bold_to_html(extra_content)}</p>'
        cards.append(
            f'<div class="card">'
            f'<h4>{title}</h4>'
            f'<p>{body}</p>'
            f'{extra}'
            f'</div>'
        )
    return "\n".join(cards)


def _render_win_cards(items: list[dict]) -> str:
    """Render big win cards with green styling."""
    cards = []
    for item in items:
        title = escape(item.get("title", ""))
        body = md_bold_to_html(item.get("description", ""))
        cards.append(
            f'<div class="card win-card">'
            f'<h4>{title}</h4>'
            f'<p>{body}</p>'
            f'</div>'
        )
    return "\n".join(cards)


def _render_friction_cards(items: list[dict]) -> str:
    """Render friction cards with red styling."""
    cards = []
    for item in items:
        title = escape(item.get("category", ""))
        body = md_bold_to_html(item.get("description", ""))
        extra = ""
        extra_content = item.get("examples")
        if extra_content and isinstance(extra_content, list):
            bullets = "".join(f"<li>{escape(e)}</li>" for e in extra_content)
            extra = f'<ul class="card-examples">{bullets}</ul>'
        cards.append(
            f'<div class="card friction-card">'
            f'<h4>{title}</h4>'
            f'<p>{body}</p>'
            f'{extra}'
            f'</div>'
        )
    return "\n".join(cards)


def _render_suggestions_ui(suggestions: dict) -> str:
    """Render the suggestions section with checkboxes and copy buttons."""
    parts = []

    # Config additions
    additions = suggestions.get("opencode_config_additions", [])
    if additions:
        parts.append('<h4>Suggested Configuration Additions</h4>')
        parts.append(
            '<button class="copy-btn" onclick="copyAllChecked()">Copy All Checked</button>'
        )
        for i, item in enumerate(additions):
            instruction = escape(item.get("instruction", ""))
            placement = escape(item.get("placement", ""))
            why = escape(item.get("why", ""))
            data_text = escape(f"{placement}\n\n{item.get('instruction', '')}")
            parts.append(
                f'<div class="suggestion-item">'
                f'<label><input type="checkbox" checked data-idx="{i}" '
                f'data-text="{data_text}"> '
                f'<code>{instruction}</code></label>'
                f'<div class="suggestion-placement">{placement} <button class="copy-btn-sm" onclick="copyCmdItem({i})">Copy</button></div>'
                f'<div class="suggestion-why">{why}</div>'
                f'</div>'
            )

    # Features to try
    features = suggestions.get("features_to_try", [])
    if features:
        parts.append('<h4>Features to Try</h4>')
        for feat in features:
            name = escape(feat.get("feature", ""))
            one_liner = escape(feat.get("one_liner", ""))
            why_for_you = md_bold_to_html(feat.get("why_for_you", ""))
            example = escape(feat.get("example_code", ""))
            parts.append(
                f'<div class="card">'
                f'<h4>{name}</h4>'
                f'<p class="one-liner">{one_liner}</p>'
                f'<p>{why_for_you}</p>'
                f'<div class="code-block"><code>{example}</code></div>'
                f'<button class="copy-btn-sm" onclick="copyText(this)">Copy</button>'
                f'</div>'
            )

    return "\n".join(parts)


def _render_usage_patterns(patterns: list[dict]) -> str:
    """Render usage pattern cards with copyable prompts."""
    cards = []
    for pat in patterns:
        title = escape(pat.get("title", ""))
        suggestion = md_bold_to_html(pat.get("suggestion", ""))
        detail = md_bold_to_html(pat.get("detail", ""))
        prompt = escape(pat.get("copyable_prompt", ""))
        cards.append(
            f'<div class="card">'
            f'<h4>{title}</h4>'
            f'<p><strong>{suggestion}</strong></p>'
            f'<p>{detail}</p>'
            f'<div class="code-block"><code>{prompt}</code></div>'
            f'<button class="copy-btn-sm" onclick="copyText(this)">Copy</button>'
            f'</div>'
        )
    return "\n".join(cards)


def _render_horizon(opportunities: list[dict]) -> str:
    """Render on-the-horizon cards."""
    cards = []
    for opp in opportunities:
        title = escape(opp.get("title", ""))
        possible = md_bold_to_html(opp.get("whats_possible", ""))
        how = md_bold_to_html(opp.get("how_to_try", ""))
        prompt = escape(opp.get("copyable_prompt", ""))
        cards.append(
            f'<div class="card horizon-card">'
            f'<h4>{title}</h4>'
            f'<p>{possible}</p>'
            f'<p class="how-to">{how}</p>'
            f'<div class="code-block"><code>{prompt}</code></div>'
            f'<button class="copy-btn-sm" onclick="copyText(this)">Copy</button>'
            f'</div>'
        )
    return "\n".join(cards)


def render_html_report(aggregate: dict, sections: dict) -> str:
    """Generate the complete self-contained HTML report.

    Args:
        aggregate: The aggregate.json data.
        sections: Dict of section_name -> section JSON data.
    """
    agg = aggregate
    at_a_glance = sections.get("at_a_glance", {})
    project_areas = sections.get("project_areas", {})
    interaction = sections.get("interaction_style", {})
    what_works = sections.get("what_works", {})
    friction_analysis = sections.get("friction_analysis", {})
    suggestions = sections.get("suggestions", {})
    on_the_horizon = sections.get("on_the_horizon", {})
    fun_ending = sections.get("fun_ending", {})

    # Stats
    total_sessions = agg.get("total_sessions", 0)
    total_messages = agg.get("total_messages", 0)
    total_hours = agg.get("total_duration_hours", 0)
    date_start = agg.get("date_range", {}).get("start", "")[:10]
    date_end = agg.get("date_range", {}).get("end", "")[:10]

    raw_hour_counts = json.dumps({str(h): agg.get("message_hours", []).count(h) for h in range(24)})

    # Pre-render all charts outside the f-string to avoid {{}} issues
    _empty = {}
    chart_goals = render_bar_chart(agg.get('goal_categories', _empty), CHART_COLORS['goals'], label_map=GOAL_CATEGORIES)
    chart_tools = render_bar_chart(agg.get('tool_counts', _empty), CHART_COLORS['tools'])
    chart_langs = render_bar_chart(agg.get('languages', _empty), CHART_COLORS['languages'])
    chart_session_types = render_bar_chart(agg.get('session_types', _empty), CHART_COLORS['session_types'], label_map=SESSION_TYPES)
    chart_models = render_bar_chart(agg.get('model_counts', _empty), CHART_COLORS['models'])
    chart_agents = render_bar_chart(agg.get('agent_counts', _empty), CHART_COLORS['agents'])
    chart_child_agents = render_bar_chart(agg.get('child_agent_counts', _empty), CHART_COLORS['agents'])
    chart_child_models = render_bar_chart(agg.get('child_model_counts', _empty), CHART_COLORS['models'])
    chart_response = render_response_time_chart(agg.get('user_response_times', []), CHART_COLORS['response_times'])
    chart_tod = render_time_of_day_chart(agg.get('message_hours', []), CHART_COLORS['time_of_day'])
    chart_errors = render_bar_chart(agg.get('tool_error_categories', _empty), CHART_COLORS['tool_errors'])
    chart_success = render_bar_chart(agg.get('success', _empty), CHART_COLORS['what_helped'], label_map=SUCCESS_TYPES)
    chart_outcomes = render_bar_chart(agg.get('outcomes', _empty), CHART_COLORS['outcomes'], ordered_keys=OUTCOME_ORDER, label_map=OUTCOMES)
    chart_helpfulness = render_bar_chart(agg.get('helpfulness', _empty), 'rgb(185, 230, 0)', ordered_keys=HELPFULNESS_ORDER, label_map=HELPFULNESS)
    chart_friction = render_bar_chart(agg.get('friction', _empty), CHART_COLORS['friction'], label_map=FRICTION_TYPES)
    chart_satisfaction = render_bar_chart(agg.get('satisfaction', _empty), CHART_COLORS['satisfaction'], ordered_keys=SATISFACTION_ORDER, label_map=SATISFACTION_LEVELS)
    chart_cost_model = render_bar_chart(agg.get('cost_by_model', _empty), CHART_COLORS['cost'], value_prefix="$")

    lines_added = f"{agg.get('total_lines_added', 0):,}"
    lines_removed = f"{agg.get('total_lines_removed', 0):,}"

    total_messages_fmt = f"{total_messages:,}"
    total_files = f"{agg.get('total_files_modified', 0):,}"
    git_commits = agg.get('git_commits', 0)

    ps = agg.get('parallel_sessions', _empty)
    ps_overlap = ps.get('overlap_events', 0)
    ps_sessions = ps.get('sessions_involved', 0)
    ps_messages = ps.get('user_messages_during', 0)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenCode Insights</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Manrope:wght@400;500;600;700&family=Patrick+Hand&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --bone: #f8f8f6;
  --white: #ffffff;
  --ink: rgb(26, 38, 2);
  --sage: rgb(100, 116, 80);
  --lime: #ccff00;
  --sky: rgb(153, 238, 255);
  --amber: rgb(255, 209, 153);
  --border: rgba(26, 38, 2, 0.06);
  --shadow: rgba(26, 38, 2, 0.05);
  --track: rgba(26, 38, 2, 0.04);
}}

/* Animations */
@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(16px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes pulse {{
  0%, 100% {{ opacity: 1; transform: scale(1); }}
  50% {{ opacity: 0.6; transform: scale(1.8); }}
}}

/* Reset */
* {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  font-family: 'Manrope', -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bone);
  color: var(--ink);
  line-height: 1.6;
  padding: 48px;
  max-width: 860px;
  margin: 0 auto;
}}

/* Typography */
h1 {{
  font-family: 'Patrick Hand', cursive;
  font-size: 42px;
  font-weight: 400;
  color: var(--ink);
  margin-bottom: 6px;
  line-height: 1.15;
  transform: rotate(-0.5deg);
  transform-origin: left center;
}}
h2 {{
  font-family: 'Space Grotesk', sans-serif;
  font-size: 24px;
  font-weight: 700;
  color: var(--ink);
  margin: 64px 0 6px;
  padding: 0;
  border: none;
}}
.section-title {{
  font-family: 'Patrick Hand', cursive;
  font-size: 32px;
  color: var(--ink);
  margin: 64px 0 20px;
  font-weight: 400;
}}
h3 {{
  font-family: 'Manrope', sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 10px;
}}
h4 {{
  font-family: 'Manrope', sans-serif;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--ink);
}}
p {{
  font-family: 'Manrope', sans-serif;
  margin-bottom: 10px;
  color: var(--sage);
  font-size: 14px;
}}

/* Staggered reveal */
.section {{
  opacity: 0;
  animation: fadeUp 0.5s ease forwards;
}}
.section:nth-child(1) {{ animation-delay: 0.05s; }}
.section:nth-child(2) {{ animation-delay: 0.1s; }}
.section:nth-child(3) {{ animation-delay: 0.15s; }}
.section:nth-child(4) {{ animation-delay: 0.2s; }}
.section:nth-child(5) {{ animation-delay: 0.25s; }}
.section:nth-child(6) {{ animation-delay: 0.3s; }}
.section:nth-child(7) {{ animation-delay: 0.35s; }}
.section:nth-child(8) {{ animation-delay: 0.4s; }}
.section:nth-child(9) {{ animation-delay: 0.45s; }}
.section:nth-child(10) {{ animation-delay: 0.5s; }}
.section:nth-child(11) {{ animation-delay: 0.55s; }}
.section:nth-child(12) {{ animation-delay: 0.6s; }}
.section:nth-child(13) {{ animation-delay: 0.65s; }}
.section:nth-child(14) {{ animation-delay: 0.7s; }}

/* Header */
.header-stats {{
  font-family: 'Manrope', sans-serif;
  color: var(--sage);
  font-size: 14px;
  margin-bottom: 8px;
}}
.date-range {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--sage);
  margin-bottom: 8px;
}}
/* Marker highlight */
.marker {{
  background: linear-gradient(to top, rgba(204,255,0,0.35) 40%, transparent 40%);
  padding: 0 2px;
}}

/* Annotation */
.annotation {{
  font-family: 'Patrick Hand', cursive;
  font-size: 1.125rem;
  color: var(--sage);
  transform: rotate(-1.5deg);
  display: inline-block;
}}

/* Uppercase meta label */
.label-meta {{
  font-family: 'Manrope', sans-serif;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--sage);
}}

/* Sheet card */
.sheet {{
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 1px 4px var(--shadow);
  padding: 28px;
  margin-bottom: 20px;
}}
.sheet-lime {{ border-top: 4px solid var(--lime); }}
.sheet-sky {{ border-top: 4px solid var(--sky); }}
.sheet-amber {{ border-top: 4px solid var(--amber); }}

/* Pulse dot */
.pulse-dot {{
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--lime);
  position: relative;
}}
.pulse-dot::after {{
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  border: 1px solid var(--lime);
  animation: pulse 2s ease-in-out infinite;
}}

/* At a Glance */
.glance-card {{
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 1px 4px var(--shadow);
  border-top: 4px solid var(--lime);
  padding: 28px 28px 16px;
  margin: 24px 0 32px;
}}
.glance-card h2 {{
  margin: 0 0 20px;
  font-size: 22px;
}}
.glance-card h3 {{
  font-family: 'Manrope', sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  margin: 18px 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.glance-card h3::before {{
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--lime);
  flex-shrink: 0;
}}
.glance-card h3 .marker {{
  background: linear-gradient(to top, rgba(204,255,0,0.35) 40%, transparent 40%);
  padding: 0 2px;
}}
.glance-card p {{
  font-family: 'Manrope', sans-serif;
  font-size: 14px;
  color: var(--sage);
  line-height: 1.65;
  margin-bottom: 4px;
}}

/* Navigation TOC */
.nav-toc {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 40px;
}}
.nav-toc a {{
  font-family: 'Manrope', sans-serif;
  font-size: 12px;
  font-weight: 500;
  color: var(--ink);
  text-decoration: none;
  padding: 6px 14px;
  border-radius: 20px;
  border: 2px solid var(--ink);
  background: transparent;
  transition: background 0.15s, color 0.15s;
}}
.nav-toc a:hover {{
  background: var(--lime);
  color: var(--ink);
}}

/* Stats row */
.stats-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 0 0 48px;
}}
.stat-box {{
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 1px 4px var(--shadow);
  padding: 18px 20px;
  flex: 1;
  min-width: 110px;
  text-align: center;
}}
.stat-box:nth-child(1) {{ flex: 1.2; }}
.stat-box:nth-child(2) {{ flex: 1.5; }}
.stat-box:nth-child(4) {{ flex: 0.9; }}
.stat-box .value {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 32px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.2;
  display: inline-block;
  border-bottom: 2px solid rgba(204,255,0,0.6);
  padding-bottom: 2px;
}}
.stat-box .label {{
  font-family: 'Manrope', sans-serif;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--sage);
  margin-top: 8px;
}}

/* Cards */
.card {{
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 1px 4px var(--shadow);
  padding: 20px 24px;
  margin-bottom: 12px;
  border-top: 4px solid var(--lime);
}}
.card h4 {{
  font-family: 'Manrope', sans-serif;
  color: var(--ink);
  font-weight: 600;
}}
.card-examples {{
  margin: 8px 0 0 20px;
  list-style: disc;
}}
.card-examples li {{
  color: var(--sage);
  font-size: 13px;
  margin-bottom: 4px;
}}
.card-extra {{
  color: var(--sage);
  font-size: 13px;
}}

/* Win cards */
.win-card {{
  background: var(--white);
  border-top: 4px solid var(--lime);
  box-shadow: 0 1px 4px var(--shadow);
}}
.win-card h4 {{
  font-family: 'Manrope', sans-serif;
  color: var(--ink);
  font-weight: 600;
}}

/* Friction cards */
.friction-card {{
  background: var(--white);
  border-top: 4px solid var(--amber);
  box-shadow: 0 1px 4px var(--shadow);
}}
.friction-card h4 {{
  font-family: 'Manrope', sans-serif;
  color: var(--ink);
  font-weight: 600;
}}

/* Horizon cards */
.horizon-card {{
  background: linear-gradient(135deg, rgba(153,238,255,0.06), rgba(204,255,0,0.03));
  border-top: 4px solid var(--sky);
  box-shadow: 0 1px 4px var(--shadow);
}}
.horizon-card h4 {{
  font-family: 'Manrope', sans-serif;
  color: var(--ink);
  font-weight: 600;
}}

/* Chart sections */
.chart-section {{
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 1px 4px var(--shadow);
  padding: 20px 24px;
  margin-bottom: 12px;
}}
.chart-section h3 {{
  font-family: 'Manrope', sans-serif;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--sage);
  margin-bottom: 14px;
}}

/* Bar chart */
.bar-row {{
  display: flex;
  align-items: center;
  margin-bottom: 5px;
}}
.bar-label {{
  width: 140px;
  font-family: 'Manrope', sans-serif;
  font-size: 11px;
  color: var(--sage);
  text-align: right;
  padding-right: 12px;
  flex-shrink: 0;
}}
.bar-track {{
  flex: 1;
  height: 4px;
  background: var(--track);
  border-radius: 2px;
  overflow: hidden;
}}
.bar-fill {{
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}}
.bar-value {{
  width: 54px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--ink);
  text-align: right;
  padding-left: 10px;
}}
.chart-empty {{
  color: var(--sage);
  font-style: italic;
  font-size: 13px;
}}

/* Charts grid */
.charts-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}}
@media (max-width: 700px) {{ .charts-grid {{ grid-template-columns: 1fr; }} }}

/* Key pattern */
.key-pattern {{
  background: var(--white);
  padding: 20px 24px;
  border-radius: 12px;
  border-top: 4px solid var(--lime);
  box-shadow: 0 1px 4px var(--shadow);
  margin: 12px 0 16px;
  font-family: 'Manrope', sans-serif;
  font-style: italic;
  font-size: 14px;
  color: var(--sage);
}}

/* Parallel stats */
.parallel-stats {{
  padding: 8px 0;
}}
.parallel-stats p {{
  font-family: 'Manrope', sans-serif;
  color: var(--sage);
  font-size: 14px;
  margin-bottom: 6px;
}}
.parallel-stats strong {{
  font-family: 'JetBrains Mono', monospace;
  color: var(--ink);
}}

/* Fun card */
.fun-card {{
  background: var(--white);
  border-top: 4px solid var(--lime);
  border-radius: 12px;
  box-shadow: 0 1px 4px var(--shadow);
  padding: 36px 28px;
  margin: 48px 0 24px;
  text-align: center;
}}
.fun-card .headline {{
  font-family: 'Space Grotesk', sans-serif;
  font-size: 20px;
  font-style: italic;
  color: var(--ink);
  margin-bottom: 10px;
  line-height: 1.4;
}}
.fun-card .detail {{
  font-family: 'Manrope', sans-serif;
  color: var(--sage);
  font-size: 14px;
  margin-bottom: 12px;
}}
/* Code blocks */
.code-block {{
  background: var(--bone);
  border-radius: 8px;
  padding: 12px 14px;
  margin: 8px 0;
  position: relative;
  overflow-x: auto;
}}
.code-block code {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--ink);
}}

/* Buttons */
.copy-btn, .copy-btn-sm {{
  font-family: 'Manrope', sans-serif;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: opacity 0.15s;
}}
.copy-btn {{
  background: var(--lime);
  color: var(--ink);
  padding: 6px 14px;
  margin-bottom: 10px;
}}
.copy-btn-sm {{
  background: var(--lime);
  color: var(--ink);
  padding: 3px 10px;
  display: inline-block;
  margin-top: 6px;
  float: right;
}}
.copy-btn:hover, .copy-btn-sm:hover {{
  opacity: 0.8;
}}

/* Suggestions */
.suggestion-item {{
  background: var(--white);
  box-shadow: 0 1px 4px var(--shadow);
  padding: 14px 16px;
  border-radius: 12px;
  margin-bottom: 8px;
  position: relative;
}}
.suggestion-item label {{
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-family: 'Manrope', sans-serif;
  font-size: 14px;
}}
.suggestion-item input[type="checkbox"] {{
  accent-color: var(--lime);
  margin-top: 3px;
}}
.suggestion-item code {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  background: var(--bone);
  padding: 3px 8px;
  border-radius: 6px;
}}
.suggestion-placement {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--sage);
  margin: 4px 0 2px 24px;
  opacity: 0.8;
}}
.suggestion-why {{
  font-family: 'Manrope', sans-serif;
  color: var(--sage);
  font-size: 12px;
  margin-top: 6px;
  margin-left: 24px;
}}
.one-liner {{
  font-family: 'Manrope', sans-serif;
  color: var(--sage);
  font-size: 13px;
  font-style: italic;
}}
.how-to {{
  font-family: 'Manrope', sans-serif;
  color: var(--sage);
  font-size: 13px;
  font-style: italic;
}}

/* Cost */
.cost-total {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 40px;
  font-weight: 700;
  color: var(--ink);
  text-align: center;
  margin: 20px 0 28px;
}}
.cost-total span {{
  background: linear-gradient(to top, rgba(204,255,0,0.35) 40%, transparent 40%);
  padding: 0 6px;
}}
.token-stats {{
  padding: 8px 0;
}}
.token-stats p {{
  font-family: 'Manrope', sans-serif;
  font-size: 14px;
  color: var(--sage);
  margin-bottom: 6px;
}}
.token-stats strong {{
  font-family: 'JetBrains Mono', monospace;
  color: var(--ink);
}}

/* Timezone selector */
.tz-selector {{
  margin: 0 0 10px;
}}
.tz-selector select {{
  font-family: 'Manrope', sans-serif;
  font-size: 12px;
  background: var(--bone);
  color: var(--ink);
  border: 2px solid var(--ink);
  padding: 5px 10px;
  border-radius: 8px;
  cursor: pointer;
}}

@media (max-width: 600px) {{
  body {{ padding: 20px; }}
  h1 {{ font-size: 28px; }}
  .stat-box .value {{ font-size: 24px; }}
  .stats-row {{ gap: 8px; }}
  .cost-total {{ font-size: 32px; }}
}}
</style>
</head>
<body>

<!-- Header -->
<div class="section">
<h1>OpenCode Insights</h1>
<p class="header-stats">{total_sessions} sessions &middot; {total_messages} messages &middot; {total_hours}h</p>
<p class="date-range">{date_start} &mdash; {date_end}</p>
</div>

<!-- At a Glance -->
<div class="section">
<div class="glance-card">
<h2 class="section-title" style="margin:0 0 16px;">At a Glance</h2>
<h3><span class="marker">What's working</span></h3>
<p>{md_bold_to_html(at_a_glance.get('whats_working', ''))}</p>
<h3><span class="marker">What's hindering you</span></h3>
<p>{md_bold_to_html(at_a_glance.get('whats_hindering', ''))}</p>
<h3><span class="marker">Quick wins to try</span></h3>
<p>{md_bold_to_html(at_a_glance.get('quick_wins', ''))}</p>
<h3><span class="marker">Ambitious workflows</span></h3>
<p>{md_bold_to_html(at_a_glance.get('ambitious_workflows', ''))}</p>
</div>
</div>

<!-- Navigation -->
<div class="section">
<div class="nav-toc">
<a href="#section-work">What Keeps You Busy</a>
<a href="#section-models">Your Toolkit</a>
<a href="#section-usage">Your Working Style</a>
<a href="#section-wins">The Highlights Reel</a>
<a href="#section-friction">Room To Grow</a>
<a href="#section-cost">The Bottom Line</a>
<a href="#section-features">Worth Exploring</a>
<a href="#section-patterns">Try These Next</a>
<a href="#section-horizon">What's Coming</a>
</div>
</div>

<!-- Stats Row -->
<div class="section">
<div class="stats-row">
<div class="stat-box"><div class="value">{total_messages_fmt}</div><div class="label">Messages</div></div>
<div class="stat-box"><div class="value" style="font-size:22px;">+{lines_added}<br>&minus;{lines_removed}</div><div class="label">Lines Changed</div></div>
<div class="stat-box"><div class="value">{total_files}</div><div class="label">Files Modified</div></div>
<div class="stat-box"><div class="value">{git_commits}</div><div class="label">Commits</div></div>
<div class="stat-box"><div class="value">{agg.get('days_active', 0)}</div><div class="label">Days Active</div></div>
<div class="stat-box"><div class="value">{agg.get('messages_per_day', 0)}</div><div class="label">Msgs / Day</div></div>
</div>
</div>

<!-- What You Work On -->
<div class="section">
<h2 id="section-work" class="section-title">What Keeps You Busy</h2>
{_render_section_cards(project_areas.get('areas', []), 'rgb(204,255,0)', ('name', 'description'))}

<div class="charts-grid">
<div class="chart-section"><h3>What You Wanted</h3>
{chart_goals}</div>
<div class="chart-section"><h3>Top Tools Used</h3>
{chart_tools}</div>
</div>
<div class="charts-grid">
<div class="chart-section"><h3>Languages</h3>
{chart_langs}</div>
<div class="chart-section"><h3>Session Types</h3>
{chart_session_types}</div>
</div>
</div>

<!-- Model & Agent Usage -->
<div class="section">
<h2 id="section-models" class="section-title">Your Toolkit</h2>
<div class="charts-grid">
<div class="chart-section"><h3>Your Models</h3>
{chart_models}</div>
<div class="chart-section"><h3>Subagent Models</h3>
{chart_child_models}</div>
</div>
<div class="charts-grid" style="align-items:start;">
<div class="chart-section"><h3>Your Agents</h3>
{chart_agents}</div>
<div class="chart-section"><h3>Subagent Activity</h3>
{chart_child_agents}</div>
</div>
</div>

<!-- How You Use OpenCode -->
<div class="section">
<h2 id="section-usage" class="section-title">Your Working Style</h2>
<div class="sheet">{md_bold_to_html(interaction.get('narrative', ''))}</div>
<div class="key-pattern">{md_bold_to_html(interaction.get('key_pattern', ''))}</div>

<div class="charts-grid">
<div class="chart-section"><h3>Response Time Distribution</h3>
<p style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--sage);margin-bottom:10px;">Median: {agg.get('median_response_time', 0)}s &middot; Avg: {agg.get('avg_response_time', 0)}s</p>
{render_response_time_chart(agg.get('user_response_times', []), CHART_COLORS['response_times'])}</div>
<div class="chart-section"><h3>Parallel Sessions</h3>
<div class="parallel-stats">
<p>Overlap events: <strong>{ps_overlap}</strong></p>
<p>Sessions involved: <strong>{ps_sessions}</strong></p>
<p>Messages during overlap: <strong>{ps_messages}</strong></p>
</div></div>
</div>

<div class="charts-grid">
<div class="chart-section">
<h3>Activity by Time of Day</h3>
<div class="tz-selector">
<select id="tz-select" onchange="updateHourHistogram(this.value)">
<option value="0">UTC</option>
<option value="-12">UTC-12</option>
<option value="-11">UTC-11</option>
<option value="-10">HST (UTC-10)</option>
<option value="-9">AKST (UTC-9)</option>
<option value="-8">PT (UTC-8)</option>
<option value="-7">MT (UTC-7)</option>
<option value="-6">CT (UTC-6)</option>
<option value="-5">ET (UTC-5)</option>
<option value="-4">AST (UTC-4)</option>
<option value="-3">UTC-3</option>
<option value="-2">UTC-2</option>
<option value="-1">UTC-1</option>
<option value="1">CET (UTC+1)</option>
<option value="2">EET (UTC+2)</option>
<option value="3">UTC+3</option>
<option value="4">UTC+4</option>
<option value="5">IST (UTC+5)</option>
<option value="5.5">IST (UTC+5:30)</option>
<option value="6">UTC+6</option>
<option value="7">UTC+7</option>
<option value="8">CST (UTC+8)</option>
<option value="9">JST (UTC+9)</option>
<option value="10">AEST (UTC+10)</option>
<option value="11">UTC+11</option>
<option value="12">NZST (UTC+12)</option>
</select>
</div>
<div id="hour-chart">{render_time_of_day_chart(agg.get('message_hours', []), CHART_COLORS['time_of_day'])}</div>
</div>
<div class="chart-section"><h3>Tool Errors</h3>
{chart_errors}</div>
</div>
</div>

<!-- Impressive Things -->
<div class="section">
<h2 id="section-wins" class="section-title">The Highlights Reel</h2>
<p>{md_bold_to_html(what_works.get('intro', ''))}</p>
{_render_win_cards(what_works.get('impressive_workflows', []))}

<div class="charts-grid">
<div class="chart-section"><h3>What Helped Most</h3>
{chart_success}</div>
<div class="chart-section"><h3>Outcomes</h3>
{chart_outcomes}</div>
</div>
<div class="charts-grid">
<div class="chart-section"><h3>Helpfulness</h3>
{chart_helpfulness}</div>
</div>
</div>

<!-- Where Things Go Wrong -->
<div class="section">
<h2 id="section-friction" class="section-title">Room To Grow</h2>
<p>{md_bold_to_html(friction_analysis.get('intro', ''))}</p>
{_render_friction_cards(friction_analysis.get('categories', []))}

<div class="charts-grid">
<div class="chart-section"><h3>Friction Types</h3>
{chart_friction}</div>
<div class="chart-section"><h3>Inferred Satisfaction</h3>
{chart_satisfaction}</div>
</div>
</div>

<!-- Cost Breakdown -->
<div class="section">
<h2 id="section-cost" class="section-title">The Bottom Line</h2>
<div class="cost-total"><span>${agg.get('total_cost', 0):.2f}</span></div>
<div class="charts-grid">
<div class="chart-section"><h3>Cost by Model</h3>
{chart_cost_model}</div>
<div class="chart-section"><h3>Token Usage</h3>
<div class="token-stats">
<p>Input tokens: <strong>{agg.get('total_input_tokens', 0):,}</strong></p>
<p>Output tokens: <strong>{agg.get('total_output_tokens', 0):,}</strong></p>
<p>Reasoning tokens: <strong>{agg.get('total_reasoning_tokens', 0):,}</strong></p>
</div></div>
</div>
</div>

<!-- Features to Try -->
<div class="section">
<h2 id="section-features" class="section-title">Worth Exploring</h2>
{_render_suggestions_ui(suggestions)}
</div>

<!-- New Usage Patterns -->
<div class="section">
<h2 id="section-patterns" class="section-title">Try These Next</h2>
{_render_usage_patterns(suggestions.get('usage_patterns', []))}
</div>

<!-- On the Horizon -->
<div class="section">
<h2 id="section-horizon" class="section-title">What's Coming</h2>
<p>{md_bold_to_html(on_the_horizon.get('intro', ''))}</p>
{_render_horizon(on_the_horizon.get('opportunities', []))}
</div>

<!-- Fun Ending -->
<div class="section">
<div class="fun-card">
<div class="headline">"{escape(fun_ending.get('headline', ''))}"</div>
<div class="detail">{escape(fun_ending.get('detail', ''))}</div>
</div>
</div>

<script>
const rawHourCounts = {raw_hour_counts};

function _fallbackCopy(text) {{
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
}}

function copyText(btn) {{
  const block = btn.previousElementSibling || btn.parentElement;
  const code = block.querySelector('code') || block;
  navigator.clipboard.writeText(code.textContent).catch(() => {{
    const ta = document.createElement('textarea');
    ta.value = code.textContent;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }});
  btn.textContent = 'Copied!';
  setTimeout(() => btn.textContent = 'Copy', 1500);
}}

function copyCmdItem(idx) {{
  const el = document.querySelector(`[data-idx="${{idx}}"]`);
  if (el) {{
    const text = el.dataset.text;
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(text).catch(() => _fallbackCopy(text));
    }} else {{
      _fallbackCopy(text);
    }}
    const btn = el.closest('.suggestion-item').querySelector('.copy-btn-sm');
    if (btn) {{ btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = 'Copy', 1500); }}
  }}
}}

function copyAllChecked() {{
  const checked = document.querySelectorAll('.suggestion-item input[type=checkbox]:checked');
  const texts = Array.from(checked).map(cb => cb.dataset.text).filter(Boolean);
  const combined = texts.join('\\n\\n');
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(combined).catch(() => _fallbackCopy(combined));
  }} else {{
    _fallbackCopy(combined);
  }}
}}

function updateHourHistogram(offset) {{
  offset = parseFloat(offset);
  const shifted = {{}};
  for (let h = 0; h < 24; h++) {{
    const newH = ((h + Math.round(offset)) % 24 + 24) % 24;
    const label = String(newH).padStart(2, '0') + ':00';
    shifted[label] = (shifted[label] || 0) + (rawHourCounts[String(h)] || 0);
  }}
  const container = document.getElementById('hour-chart');
  const maxVal = Math.max(...Object.values(shifted), 1);
  let html = '';
  for (let h = 0; h < 24; h++) {{
    const label = String(h).padStart(2, '0') + ':00';
    const val = shifted[label] || 0;
    const pct = (val / maxVal) * 100;
    html += `<div class="bar-row"><span class="bar-label">${{label}}</span><div class="bar-track"><div class="bar-fill" style="width:${{pct.toFixed(1)}}%;background:#ccff00"></div></div><span class="bar-value">${{val}}</span></div>`;
  }}
  container.innerHTML = html;
}}

function toggleCollapsible(header) {{
  const content = header.nextElementSibling;
  content.style.display = content.style.display === 'none' ? 'block' : 'none';
}}

// Auto-detect user timezone
(function() {{
  try {{
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const now = new Date();
    const utcOffset = -now.getTimezoneOffset() / 60;
    const sel = document.getElementById('tz-select');
    if (sel) {{
      // Find the closest matching offset option
      let bestOption = null;
      let bestDiff = Infinity;
      for (const opt of sel.options) {{
        const diff = Math.abs(parseFloat(opt.value) - utcOffset);
        if (diff < bestDiff) {{
          bestDiff = diff;
          bestOption = opt;
        }}
      }}
      if (bestOption && bestDiff <= 0.5) {{
        sel.value = bestOption.value;
        updateHourHistogram(bestOption.value);
      }}
    }}
  }} catch(e) {{}}
}})();
</script>
</body>
</html>"""
