from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Lead:
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    source: Optional[str] = None
    category: Optional[str] = None
    raw: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
