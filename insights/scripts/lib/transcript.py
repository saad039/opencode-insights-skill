"""Serialize OpenCode session messages into text transcripts."""


def serialize_transcript(
    messages: list[dict],
    parts_by_message: dict[str, list[dict]],
) -> str:
    """Convert session messages + parts into a human-readable transcript.

    Format:
        [USER] <text>
        [ASSISTANT] <text>
        [TOOL: bash] <command> → <output summary>
    """
    lines: list[str] = []

    for msg in messages:
        data = msg.get("data", {})
        role = data.get("role", "")
        parts = parts_by_message.get(msg["id"], [])

        for p in parts:
            pd = p.get("data", {})
            ptype = pd.get("type")

            if ptype == "text":
                text = pd.get("text", "").strip()
                if text:
                    tag = "USER" if role == "user" else "ASSISTANT"
                    lines.append(f"[{tag}] {text}")

            elif ptype == "tool":
                tool_name = pd.get("tool", "unknown")
                state = pd.get("state", {})
                inp = state.get("input", {})
                output = state.get("output", "")

                # Build input summary
                input_summary = ""
                if isinstance(inp, dict):
                    if tool_name == "bash":
                        input_summary = inp.get("command", "")
                    elif tool_name in ("edit", "write"):
                        input_summary = inp.get("file_path", "") or inp.get("path", "")
                    elif tool_name == "read":
                        input_summary = inp.get("file_path", "") or inp.get("path", "")
                    elif tool_name in ("grep", "glob"):
                        input_summary = inp.get("pattern", "")
                    else:
                        # Generic: show title or first key
                        input_summary = state.get("title", "")
                elif isinstance(inp, str):
                    input_summary = inp[:200]

                # Truncate output
                output_str = ""
                if isinstance(output, str):
                    output_str = output[:300].replace("\n", " ").strip()
                elif isinstance(output, dict):
                    output_str = str(output)[:300]

                status = state.get("status", "")
                status_marker = " [ERROR]" if status in ("error", "failed") else ""

                if input_summary and output_str:
                    lines.append(
                        f"[TOOL: {tool_name}]{status_marker} {input_summary} → {output_str}"
                    )
                elif input_summary:
                    lines.append(f"[TOOL: {tool_name}]{status_marker} {input_summary}")
                elif output_str:
                    lines.append(f"[TOOL: {tool_name}]{status_marker} → {output_str}")

    return "\n\n".join(lines)


def chunk_transcript(transcript: str, max_chars: int = 25000) -> list[str]:
    """Split a transcript into chunks of approximately max_chars.

    Splits at paragraph boundaries (double newline) to avoid cutting
    mid-message.
    """
    if len(transcript) <= max_chars:
        return [transcript]

    chunks: list[str] = []
    paragraphs = transcript.split("\n\n")
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para) + 2  # +2 for the \n\n separator
        if current_len + para_len > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks
