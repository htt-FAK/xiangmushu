from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class FillTask:
    task_id: str
    target_chapter: str
    task_type: str  # "paragraph" | "table_cell"
    description: str
    location_hint: Dict[str, Any]
    word_limit: int = 300
