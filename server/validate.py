"""HAND-WRITTEN, NOT generated. See server/README.md.

Validation of the three value types the protocol constrains.
"""

from __future__ import annotations

import re

# REQ-NAME-001: 1-32 chars from [a-zA-Z0-9_-]. REQ-NAME-002/003: case-sensitive,
# no trimming or normalisation, so the pattern is anchored and total.
_NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,32}\Z")

# REQ-MSGID-001: UUIDv4 in canonical lowercase form. The version nibble must be 4 and
# the variant nibble one of 8/9/a/b.
_UUID4_RE = re.compile(
    r"\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)

TEXT_MIN = 1
TEXT_MAX = 4000


def is_valid_name(value: object) -> bool:
    """REQ-NAME-001."""
    return isinstance(value, str) and _NAME_RE.match(value) is not None


def is_valid_msg_id(value: object) -> bool:
    """REQ-MSGID-001."""
    return isinstance(value, str) and _UUID4_RE.match(value) is not None


def is_valid_text(value: object) -> bool:
    """REQ-TEXT-001 and REQ-TEXT-005.

    Length is counted in Unicode code points, which is what ``len`` measures in
    Python, so no conversion is needed. Lone surrogates can reach us through JSON
    ``\\udXXX`` escapes and are rejected.
    """
    if not isinstance(value, str):
        return False
    if not (TEXT_MIN <= len(value) <= TEXT_MAX):
        return False
    return not any(0xD800 <= ord(ch) <= 0xDFFF for ch in value)
