"""Data validation for OpenCode Insights."""

REQUIRED_FACET_FIELDS = {
    "underlying_goal": str,
    "outcome": str,
    "brief_summary": str,
    "goal_categories": dict,
    "user_satisfaction_counts": dict,
    "friction_counts": dict,
}


def validate_facets(data: dict) -> bool:
    """Check that a facet dict has all required fields with correct types."""
    for field, expected_type in REQUIRED_FACET_FIELDS.items():
        if field not in data:
            return False
        if not isinstance(data[field], expected_type):
            return False
    return True
