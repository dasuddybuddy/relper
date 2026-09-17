from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Optional

@dataclass
class PaperRecord:
    id : int
    item_id : UUID
    item_handle : str
    bitstream_id : UUID
    content_url : str
    status : str
    attempts : int
    max_attempts : int
    claimed_by : Optional[str]
    claimed_at : Optional[datetime]
    error : Optional[str]
    updated_at : datetime

    @classmethod
    def from_row(cls, row: dict) -> "PaperRecord":
        return cls(**row)

    @property
    def can_retry(self) -> bool:
        return self.attempts < self.max_attempts
