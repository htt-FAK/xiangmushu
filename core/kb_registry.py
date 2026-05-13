"""知识库注册表：slug 与显示名，持久化 JSON。"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

import config

REGISTRY_PATH = os.path.join(os.path.dirname(config.__file__), "data", "kb_registry.json")
COLLECTION_PREFIX = "plan_kb__"


def _ensure_data_dir():
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)


def default_registry() -> List[Dict[str, Any]]:
    return [
        {"slug": "kb1", "label": "知识库1"},
        {"slug": "kb2", "label": "知识库2"},
    ]


def load_registry() -> List[Dict[str, Any]]:
    _ensure_data_dir()
    if not os.path.isfile(REGISTRY_PATH):
        reg = default_registry()
        save_registry(reg)
        return reg
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or not data:
            reg = default_registry()
            save_registry(reg)
            return reg
        return data
    except (json.JSONDecodeError, OSError):
        reg = default_registry()
        save_registry(reg)
        return reg


def save_registry(entries: List[Dict[str, Any]]) -> None:
    _ensure_data_dir()
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def slugify(label: str) -> str:
    """仅小写字母数字下划线，便于 Chroma collection 名安全。"""
    s = (label or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_") or "kb"
    return s[:32]


def collection_name_for_slug(slug: str) -> str:
    safe = re.sub(r"[^a-z0-9_]", "", slug.lower())
    if not safe:
        safe = "default"
    return f"{COLLECTION_PREFIX}{safe}"


def add_kb(label: str, slug: str | None = None) -> str:
    reg = load_registry()
    base = (slug or slugify(label)).lower()
    base = re.sub(r"[^a-z0-9_]", "", base) or "kb"
    slug = base
    n = 2
    while any(e["slug"] == slug for e in reg):
        slug = f"{base}_{n}"
        n += 1
    reg.append({"slug": slug, "label": (label or slug).strip() or slug})
    save_registry(reg)
    return slug


def remove_kb(slug: str) -> None:
    reg = load_registry()
    if len(reg) <= 1:
        raise ValueError("至少保留一个知识库")
    new = [e for e in reg if e["slug"] != slug]
    if len(new) == len(reg):
        return
    save_registry(new)
