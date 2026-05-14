"""任务分组：将同章节或同表格行的 FillTask 聚合，为后续分组检索做准备。

TaskGroup 是检索复用的基本单元：同组任务共享一次向量检索结果。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from core.fill_task import FillTask


@dataclass
class TaskGroup:
    group_id: str
    tasks: List[FillTask] = field(default_factory=list)
    shared_query: str = ""
    table_index: int = -1

    @property
    def is_table_group(self) -> bool:
        return self.table_index >= 0

    @property
    def task_type(self) -> str:
        if not self.tasks:
            return "paragraph"
        return self.tasks[0].task_type


def group_tasks(tasks: List[FillTask]) -> List[TaskGroup]:
    """将任务列表分组：

    - table_cell：按 (table_index, row) 归组，共享同行检索。
    - paragraph：按 target_chapter 归组（同章节连续任务共用一次检索）。
    """
    groups: List[TaskGroup] = []
    _table_groups: dict[tuple, TaskGroup] = {}
    _para_groups: dict[str, TaskGroup] = {}

    for task in tasks:
        if task.task_type == "table_cell":
            loc = task.location_hint or {}
            tbl_idx = int(loc.get("table_index", 0))
            row = int(loc.get("row", 0))
            key = (tbl_idx, row)
            if key not in _table_groups:
                gid = f"table_{tbl_idx}_row_{row}"
                grp = TaskGroup(
                    group_id=gid,
                    table_index=tbl_idx,
                    shared_query=f"{task.target_chapter} {task.description}",
                )
                _table_groups[key] = grp
                groups.append(grp)
            _table_groups[key].tasks.append(task)
        else:
            chapter = task.target_chapter or "__misc__"
            if chapter not in _para_groups:
                grp = TaskGroup(
                    group_id=f"para_{chapter}",
                    shared_query=f"{task.target_chapter} {task.description}",
                )
                _para_groups[chapter] = grp
                groups.append(grp)
            else:
                existing = _para_groups[chapter]
                existing.shared_query = (
                    existing.shared_query + " " + task.description
                )[:256]
            _para_groups[chapter].tasks.append(task)

    return groups
