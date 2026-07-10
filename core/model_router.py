from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import config
from core.provider_registry import (
    available_models_for_role as registry_available_models_for_role,
    resolve_role_choice,
)


MAIN_WRITER = "main_writer"
FAST_WRITER = "fast_writer"
VISION_LAYOUT = "vision_layout"
TEMPLATE_PLANNER = "template_planner"
AUDIT_TEXT = "audit_text"
EMBEDDING = "embedding"


LEGACY_MODULE_TO_ROLE: dict[str, str] = {
    "generation": MAIN_WRITER,
    "lightweight": FAST_WRITER,
    "vision": VISION_LAYOUT,
    "audit": AUDIT_TEXT,
}

ROLE_TO_LEGACY_MODULE: dict[str, str] = {
    MAIN_WRITER: "generation",
    FAST_WRITER: "lightweight",
    VISION_LAYOUT: "vision",
    TEMPLATE_PLANNER: "lightweight",
    AUDIT_TEXT: "audit",
}


@dataclass(frozen=True)
class ModelRoleProfile:
    role: str
    label: str
    description: str
    default_model: str
    fallback_models: tuple[str, ...] = ()
    temperature: float | None = None
    extra_body: Mapping[str, Any] = field(default_factory=dict)
    legacy_module: str = ""
    legacy_config_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelCallProfile:
    role: str
    model: str
    fallback_models: tuple[str, ...] = ()
    temperature: float | None = None
    extra_body: dict[str, Any] = field(default_factory=dict)
    routing_reason: str = ""
    legacy_module: str = ""
    source: str = "default"

    @property
    def model_chain(self) -> list[str]:
        seen: set[str] = set()
        chain: list[str] = []
        for item in (self.model, *self.fallback_models):
            model = str(item or "").strip()
            if not model or model in seen:
                continue
            seen.add(model)
            chain.append(model)
        return chain

    def trace(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "model": self.model,
            "fallback_models": list(self.fallback_models),
            "temperature": self.temperature,
            "extra_body_keys": sorted(self.extra_body.keys()),
            "routing_reason": self.routing_reason,
            "legacy_module": self.legacy_module,
            "source": self.source,
        }


def normalize_role(role_or_module: str) -> str:
    key = str(role_or_module or "").strip()
    return LEGACY_MODULE_TO_ROLE.get(key, key)


def model_roles() -> dict[str, ModelRoleProfile]:
    return {
        MAIN_WRITER: ModelRoleProfile(
            role=MAIN_WRITER,
            label="Main writing",
            description="Final paragraph and table-cell content writer.",
            default_model=(
                getattr(config, "MAIN_WRITER_MODEL", "")
                or getattr(config, "LARGE_LLM_MODEL", "")
                or "deepseek-v4-pro"
            ),
            fallback_models=(
                getattr(config, "MAIN_WRITER_FALLBACK_MODEL_1", ""),
                getattr(config, "MAIN_WRITER_FALLBACK_MODEL_2", ""),
                getattr(config, "FALLBACK_LLM_MODEL_1", ""),
                getattr(config, "FALLBACK_LLM_MODEL_2", ""),
                getattr(config, "FALLBACK_LLM_MODEL_3", ""),
            ),
            temperature=getattr(config, "TEMP_LARGE_LLM", None),
            legacy_module="generation",
            legacy_config_keys=("LARGE_LLM_MODEL",),
        ),
        FAST_WRITER: ModelRoleProfile(
            role=FAST_WRITER,
            label="Fast fill",
            description="Low-cost short content, strong-RAG paragraphs, and table fast fill.",
            default_model=getattr(config, "FAST_WRITER_MODEL", "")
            or getattr(config, "SMALL_LLM_MODEL", "")
            or "qwen3.6-flash",
            fallback_models=(
                getattr(config, "FAST_WRITER_FALLBACK_MODEL_1", ""),
                getattr(config, "SMALL_LLM_FALLBACK_MODEL", ""),
                getattr(config, "VISION_WEB_FALLBACK_MODEL", ""),
            ),
            temperature=getattr(config, "TEMP_SMALL_LLM", None),
            legacy_module="lightweight",
            legacy_config_keys=("SMALL_LLM_MODEL", "BATCH_TABLE_FAST_MODEL"),
        ),
        VISION_LAYOUT: ModelRoleProfile(
            role=VISION_LAYOUT,
            label="Template vision",
            description="Template image, screenshot, and layout understanding.",
            default_model=getattr(config, "VISION_LAYOUT_MODEL", "")
            or getattr(config, "TEMPLATE_VISION_MODEL", "")
            or "qwen3.7-plus",
            fallback_models=(
                getattr(config, "VISION_LAYOUT_FALLBACK_MODEL_1", ""),
                getattr(config, "TEMPLATE_VISION_FALLBACK_MODEL", ""),
                getattr(config, "VISION_WEB_FALLBACK_MODEL", ""),
            ),
            temperature=getattr(config, "TEMP_VISION", None),
            legacy_module="vision",
            legacy_config_keys=("TEMPLATE_VISION_MODEL", "TABLE_CELL_VISION_MODEL"),
        ),
        TEMPLATE_PLANNER: ModelRoleProfile(
            role=TEMPLATE_PLANNER,
            label="Template planning",
            description="Turn template structure, deterministic scan, and visual profile into FillTasks.",
            default_model=getattr(config, "TEMPLATE_PLANNER_MODEL", "")
            or getattr(config, "TEMPLATE_ANALYZE_MODEL", "")
            or "qwen3.7-plus",
            fallback_models=(
                getattr(config, "TEMPLATE_PLANNER_FALLBACK_MODEL_1", ""),
                getattr(config, "TEMPLATE_ANALYZE_FALLBACK_MODEL", ""),
                getattr(config, "SMALL_LLM_FALLBACK_MODEL", ""),
            ),
            temperature=getattr(config, "TEMP_TEMPLATE_ANALYZE", None),
            legacy_module="lightweight",
            legacy_config_keys=("TEMPLATE_ANALYZE_MODEL",),
        ),
        AUDIT_TEXT: ModelRoleProfile(
            role=AUDIT_TEXT,
            label="Content audit",
            description="Model-based review of generated text against task evidence.",
            default_model=getattr(config, "AUDIT_TEXT_MODEL", "")
            or getattr(config, "AUDIT_LLM_MODEL", "")
            or "qwen3.6-flash",
            fallback_models=(
                getattr(config, "AUDIT_TEXT_FALLBACK_MODEL_1", ""),
                getattr(config, "AUDIT_FALLBACK_1", ""),
                getattr(config, "AUDIT_FALLBACK_2", ""),
                getattr(config, "AUDIT_FALLBACK_3", ""),
            ),
            temperature=getattr(config, "TEMP_AUDIT", None),
            legacy_module="audit",
            legacy_config_keys=("AUDIT_LLM_MODEL",),
        ),
        EMBEDDING: ModelRoleProfile(
            role=EMBEDDING,
            label="Embedding",
            description="Knowledge-base embedding and vector retrieval.",
            default_model=getattr(config, "EMBEDDING_MODEL", "") or "text-embedding-v4",
            fallback_models=(),
            temperature=None,
            legacy_module="",
            legacy_config_keys=("EMBEDDING_MODEL",),
        ),
    }


def _model_choices_for_user(user_id: int | None) -> dict[str, str]:
    if user_id is None:
        return {}
    try:
        resolved = resolve_role_choice(MAIN_WRITER, user_id)
        if resolved.get("source", "").startswith("user:") or resolved.get("source", "").startswith("fallback:"):
            from core.provider_registry import load_user_model_choices

            registry_choices = load_user_model_choices(user_id)
            if registry_choices:
                return {str(k): str(v) for k, v in registry_choices.items() if str(v or "").strip()}
    except Exception:
        pass
    try:
        from core.auth import get_user_preferences

        raw = get_user_preferences(user_id).get("model_choices", {})
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items() if str(v or "").strip()}
    except Exception:
        return {}
    return {}


def selected_model_for_role(role_or_module: str, user_id: int | None = None) -> tuple[str, str]:
    role = normalize_role(role_or_module)
    profiles = model_roles()
    profile = profiles.get(role)
    if profile is None:
        return "", "unknown"

    try:
        resolved = resolve_role_choice(role, user_id)
        selected = str(resolved.get("model") or "").strip()
        source = str(resolved.get("source") or "")
        registry_models = registry_available_models_for_role(role)
        if selected and (source != "default" or registry_models):
            return selected, source or "default"
    except Exception:
        pass

    choices = _model_choices_for_user(user_id)
    for key in (role, profile.legacy_module):
        selected = str(choices.get(key) or "").strip()
        if selected:
            return selected, f"user:{key}"
    return profile.default_model, "default"


def resolve_model_profile(
    role_or_module: str,
    *,
    user_id: int | None = None,
    routing_reason: str = "",
    extra_body: Mapping[str, Any] | None = None,
    temperature: float | None = None,
) -> ModelCallProfile:
    role = normalize_role(role_or_module)
    profile = model_roles().get(role)
    if profile is None:
        return ModelCallProfile(
            role=role,
            model="",
            routing_reason=routing_reason,
            source="unknown",
        )

    model, source = selected_model_for_role(role, user_id)
    merged_extra = dict(profile.extra_body)
    merged_extra.update(dict(extra_body or {}))
    try:
        resolved = resolve_role_choice(role, user_id)
        merged_extra.update(dict(resolved.get("extra_body") or {}))
    except Exception:
        pass
    return ModelCallProfile(
        role=role,
        model=model,
        fallback_models=profile.fallback_models,
        temperature=profile.temperature if temperature is None else temperature,
        extra_body=merged_extra,
        routing_reason=routing_reason,
        legacy_module=profile.legacy_module,
        source=source,
    )


def available_models_for_role(role_or_module: str) -> list[str]:
    role = normalize_role(role_or_module)
    profile = model_roles().get(role)
    if profile is None:
        return []

    try:
        registry_models = registry_available_models_for_role(role)
        if registry_models:
            return [str(item["model"]) for item in registry_models if str(item.get("model") or "").strip()]
    except Exception:
        pass

    models: list[str] = []
    seen: set[str] = set()

    def add(model: str) -> None:
        item = str(model or "").strip()
        if item and item not in seen:
            seen.add(item)
            models.append(item)

    add(profile.default_model)
    for model in profile.fallback_models:
        add(model)

    legacy = getattr(config, "USER_MODEL_OPTIONS", {}).get(profile.legacy_module) or {}
    for tier_models in (legacy.get("tiers") or {}).values():
        for item in tier_models:
            add(str((item or {}).get("model") or ""))
    for item in legacy.get("options") or []:
        add(str((item or {}).get("model") or ""))

    return models
