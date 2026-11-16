import json
import re


def hcl_str(value) -> str:
    """Render a value as a safe HCL string literal."""
    text = json.dumps(str(value))  # adds quotes, escapes quotes and backslashes
    # In HCL, ${ and %{ start template code, so neutralise them
    return text.replace("${", "$${").replace("%{", "%%{")


def safe_name(raw, fallback: str) -> str:
    """Turn any text into a valid, lowercase HCL resource name."""
    name = re.sub(r"[^a-z0-9_]+", "_", (raw or "").lower()).strip("_")
    if not name:
        name = fallback
    if name[0].isdigit():
        name = "r_" + name
    return name