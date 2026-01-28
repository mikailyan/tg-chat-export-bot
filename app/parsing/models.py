from dataclasses import dataclass
from typing import Optional

@dataclass
class Participant:
    user_id: Optional[str]
    username: Optional[str]
    full_name: str
    bio: Optional[str] = None

@dataclass
class ParseResult:
    participants: list[Participant]
    mentions: list[str]
    total_messages: int
