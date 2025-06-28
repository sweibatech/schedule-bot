import re


def escape_markdown(text: str) -> str:
    if not text:
        return ""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    text = re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", str(text))
    text = re.sub(r'(?m)^-', r'\\-', text)
    return text