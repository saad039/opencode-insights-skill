"""Display label mappings for OpenCode Insights report."""

GOAL_CATEGORIES = {
    "debug_investigate": "Debug/Investigate",
    "implement_feature": "Implement Feature",
    "fix_bug": "Fix Bug",
    "write_script_tool": "Write Script/Tool",
    "refactor_code": "Refactor Code",
    "configure_system": "Configure System",
    "create_pr_commit": "Create PR/Commit",
    "analyze_data": "Analyze Data",
    "understand_codebase": "Understand Codebase",
    "write_tests": "Write Tests",
    "write_docs": "Write Docs",
    "deploy_infra": "Deploy/Infra",
    "code_review": "Code Review",
    "warmup_minimal": "Cache Warmup",
}

SUCCESS_TYPES = {
    "fast_accurate_search": "Fast/Accurate Search",
    "correct_code_edits": "Correct Code Edits",
    "good_explanations": "Good Explanations",
    "proactive_help": "Proactive Help",
    "multi_file_changes": "Multi-file Changes",
    "handled_complexity": "Multi-file Changes",
    "good_debugging": "Good Debugging",
}

FRICTION_TYPES = {
    "misunderstood_request": "Misunderstood Request",
    "wrong_approach": "Wrong Approach",
    "buggy_code": "Buggy Code",
    "user_rejected_action": "User Rejected Action",
    "got_blocked": "Got Blocked",
    "user_stopped_early": "User Stopped Early",
    "wrong_file_or_location": "Wrong File/Location",
    "excessive_changes": "Excessive Changes",
    "slow_or_verbose": "Slow/Verbose",
    "tool_failed": "Tool Failed",
    "user_unclear": "User Unclear",
    "external_issue": "External Issue",
}

SATISFACTION_LEVELS = {
    "frustrated": "Frustrated",
    "dissatisfied": "Dissatisfied",
    "likely_satisfied": "Likely Satisfied",
    "satisfied": "Satisfied",
    "happy": "Happy",
    "unsure": "Unsure",
    "neutral": "Neutral",
    "delighted": "Delighted",
}

SESSION_TYPES = {
    "single_task": "Single Task",
    "multi_task": "Multi Task",
    "iterative_refinement": "Iterative Refinement",
    "exploration": "Exploration",
    "quick_question": "Quick Question",
}

OUTCOMES = {
    "fully_achieved": "Fully Achieved",
    "mostly_achieved": "Mostly Achieved",
    "partially_achieved": "Partially Achieved",
    "not_achieved": "Not Achieved",
    "unclear_from_transcript": "Unclear",
}

HELPFULNESS = {
    "unhelpful": "Unhelpful",
    "slightly_helpful": "Slightly Helpful",
    "moderately_helpful": "Moderately Helpful",
    "very_helpful": "Very Helpful",
    "essential": "Essential",
}

EXTENSION_TO_LANGUAGE = {
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript",
    ".py": "Python", ".rb": "Ruby",
    ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".md": "Markdown",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
    ".sh": "Shell", ".css": "CSS", ".html": "HTML",
    ".c": "C", ".cpp": "C++", ".h": "C/C++ Header",
    ".cs": "C#", ".swift": "Swift", ".kt": "Kotlin",
    ".sql": "SQL", ".toml": "TOML", ".xml": "XML",
}

SATISFACTION_ORDER = [
    "frustrated", "dissatisfied", "likely_satisfied",
    "satisfied", "happy", "unsure",
]

OUTCOME_ORDER = [
    "not_achieved", "partially_achieved", "mostly_achieved",
    "fully_achieved", "unclear_from_transcript",
]

# Bar chart color scheme
CHART_COLORS = {
    "goals": "#ccff00",
    "tools": "#ccff00",
    "languages": "#ccff00",
    "session_types": "#ccff00",
    "response_times": "#ccff00",
    "parallel_sessions": "#ccff00",
    "time_of_day": "#ccff00",
    "tool_errors": "rgb(255, 209, 153)",
    "what_helped": "#ccff00",
    "outcomes": "#ccff00",
    "friction": "rgb(255, 209, 153)",
    "satisfaction": "rgba(204, 255, 0, 0.7)",
    "models": "#ccff00",
    "agents": "rgb(153, 238, 255)",
    "cost": "#ccff00",
}

TOOL_ERROR_PATTERNS = {
    "Command Failed": ["exit code"],
    "User Rejected": ["rejected permission to use", "doesn't want"],
    "Edit Failed": [
        "could not find oldstring",       # OpenCode wording
        "no changes",
    ],
    "File Changed": ["modified since it was last read", "modified since read"],
    "File Too Large": ["exceeds maximum", "too large"],
    "File Not Found": ["file not found", "does not exist"],
    "Offset Out of Range": ["out of range for this file"],
    "Tool Aborted": ["tool execution aborted"],
    "Invalid Arguments": ["called with invalid arguments"],
    "Permission Denied": ["rule which prevents you from using", "eacces", "permission denied"],
    "API Error": ["request failed with status code"],
    "Directory Error": ["eisdir", "illegal operation on a directory"],
}



def display_label(key: str, mapping: dict) -> str:
    """Get human-readable label for a key, with smart fallback."""
    if key in mapping:
        return mapping[key]
    # Smart title-casing: uppercase 2-3 letter words (likely acronyms)
    words = key.replace("_", " ").split()
    result = []
    for w in words:
        if len(w) <= 3 and w.isalpha():
            result.append(w.upper())
        else:
            result.append(w.capitalize())
    return " ".join(result)
