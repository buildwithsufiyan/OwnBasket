import re

from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe


def highlight_matches(text, query):
    """Escape ``text`` and wrap every case-insensitive ``query`` match in a <mark>."""
    if not text or not query:
        return text

    pattern = re.compile(re.escape(str(query)), re.IGNORECASE)
    source = str(text)
    result = []
    last_index = 0

    for match in pattern.finditer(source):
        result.append(conditional_escape(source[last_index:match.start()]))
        result.append(
            f"<mark class=\"search-highlight\">{conditional_escape(match.group(0))}</mark>"
        )
        last_index = match.end()

    result.append(conditional_escape(source[last_index:]))
    return mark_safe(''.join(result))
