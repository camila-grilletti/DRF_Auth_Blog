import bleach
import re


ALLOWED_TAGS = [
    "p", "h1", "h2", "ul", "ol", "li", "sub", "sup", "blockquote",
    "pre", "a", "img", "video", "span", "strong", "em", "u", "s", "br"
]

ALLOWED_ATTRIBUTES = {'a': ['href', 'title']}

ALLOWED_SCHEMAS = ['http', 'https']

def sanitize_string(string):
    if string is None:
        return ""

    cleaned_string = bleach.clean(string, tags=[], strip=True)

    pattern = re.compile(r"[^a-zA-Z0-9\s',.:?-ÁÉÍÓÚáéíóúÑñÜü]")

    sanitize_string = pattern.sub("", cleaned_string)
    
    return sanitize_string


def sanitize_html(content):
    if content is None:
        return ""
    
    return bleach.clean(
        content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True, protocols=ALLOWED_SCHEMAS
    )