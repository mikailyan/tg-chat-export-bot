import re
from typing import Iterable

MENTION_RE = re.compile(r"@([A-Za-z0-9_]{5,32})")

DELETED_MARKERS = {
    "deleted account",
    "удалённый аккаунт",
    "удаленный аккаунт",
    "account deleted",
}

def extract_mentions(text: str) -> list[str]:
    if not text:
        return []
    return [m.group(1) for m in MENTION_RE.finditer(text)]

def is_deleted_name(name: str) -> bool:
    if not name:
        return True
    norm = name.strip().lower()
    return norm in DELETED_MARKERS

def uniq_preserve(items: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for x in items:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out
