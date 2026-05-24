"""
智能计划书生成器 — Streamlit 单页：侧栏配置 + 主区标签页（知识库 / 模板 / 生成预览）
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime

import streamlit as st

import config
from core.chunker import Chunker
from core.fill_task import FillTask
from core.content_auditor import (
    ContentAuditor,
    should_apply_revision,
    rule_audit,
    need_model_audit,
)
from core.batch_generator import batch_generate_table_row
from core.evidence_planner import Evidence, retrieve_for_group, format_evidence
from core.generator import ContentGenerator, GenerationBundle
from core.task_grouper import group_tasks
from core.table_context import build_table_cell_context
from core.filler import WordFiller
from core.kb_registry import add_kb, load_registry, remove_kb
from core.kb_extract import path_to_parsed_document
from core.template_analyzer import TemplateAnalyzer
from core.template_vision import get_or_build_template_vision_profile
from core.vector_store import VectorStore


def _configure_console_logging_from_env() -> None:
    """联调时在终端输出 INFO/DEBUG。默认关闭：Streamlit 不会像 smoke 脚本那样主动 print。"""
    raw = (os.getenv("APP_CONSOLE_LOG") or "").strip().lower()
    if raw not in ("1", "true", "yes", "on", "info", "debug"):
        return
    level = logging.DEBUG if raw == "debug" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    for noisy in (
        "httpx",
        "httpcore",
        "openai",
        "chromadb",
        "streamlit",
        "watchdog",
        "urllib3",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_configure_console_logging_from_env()

SS_ACTIVE_KB = "active_kb_slug"
SS_TASKS = "tpl_tasks_dicts"
SS_TASKS_SIG = "tpl_tasks_signature"
SS_LAST_OUT_PATH = "last_output_path"
SS_LAST_OUT_NAME = "last_output_name"

SS_GENERATION_MODE = "generation_mode"
SS_SELECTED_TEMPLATE = "selected_template"
SS_PENDING_MODE_APPLY = "_pending_generation_mode_apply"

MODE_ORDER = ["快速", "普通", "增强"]
MODE_DEFAULTS = {
    "快速": {
        "top_k": 3,
        "retrieval_max_distance": 0.7,
        "use_tavily": False,
        "default_word_limit": 500,
        "stream": False,
        "web_writing_mode": "calm",
    },
    "普通": {
        "top_k": 5,
        "retrieval_max_distance": 0.8,
        "use_tavily": False,
        "default_word_limit": 800,
        "stream": True,
        "web_writing_mode": "calm",
    },
    "增强": {
        "top_k": 10,
        "retrieval_max_distance": 0.9,
        "use_tavily": True,
        "default_word_limit": 1200,
        "stream": True,
        "web_writing_mode": "calm",
    },
}


def _template_signature(path: str) -> str:
    try:
        return f"{os.path.basename(path)}:{os.path.getmtime(path)}"
    except OSError:
        return os.path.basename(path)


def _tasks_to_dicts(tasks: list) -> list:
    return [asdict(t) for t in tasks]


def _dicts_to_tasks(data: list) -> list[FillTask]:
    return [FillTask(**d) for d in data]


def _apply_mode_defaults_to_session(mode: str) -> None:
    d = MODE_DEFAULTS.get(mode, MODE_DEFAULTS["普通"])
    st.session_state["adv_top_k"] = int(d["top_k"])
    st.session_state["adv_retrieval_max_distance"] = float(d["retrieval_max_distance"])
    st.session_state["adv_use_tavily"] = bool(d["use_tavily"])
    st.session_state["adv_default_word_limit"] = int(d["default_word_limit"])
    st.session_state["adv_use_stream"] = bool(d["stream"])
    wm = str(d.get("web_writing_mode") or getattr(config, "WEB_SEARCH_WRITING_MODE", "calm")).lower()
    st.session_state["adv_web_writing_mode"] = "creative" if wm == "creative" else "calm"


def _ensure_adv_params() -> None:
    if "adv_top_k" not in st.session_state:
        _apply_mode_defaults_to_session(st.session_state.get(SS_GENERATION_MODE, "普通"))
    if "adv_web_writing_mode" not in st.session_state:
        wm = getattr(config, "WEB_SEARCH_WRITING_MODE", "calm")
        st.session_state["adv_web_writing_mode"] = (
            "creative" if str(wm).lower() == "creative" else "calm"
        )


def _flush_pending_mode_defaults() -> None:
    pending = st.session_state.pop(SS_PENDING_MODE_APPLY, None)
    if pending in MODE_DEFAULTS:
        _apply_mode_defaults_to_session(str(pending))


def _init_session() -> None:
    if SS_ACTIVE_KB not in st.session_state:
        reg = load_registry()
        st.session_state[SS_ACTIVE_KB] = reg[0]["slug"] if reg else "kb1"
    if SS_GENERATION_MODE not in st.session_state:
        st.session_state[SS_GENERATION_MODE] = "普通"
    _ensure_adv_params()
    if SS_SELECTED_TEMPLATE not in st.session_state:
        st.session_state[SS_SELECTED_TEMPLATE] = None


def _glass_theme() -> None:
    st.markdown(
        """
<style>
html, body, .stApp, [data-testid="stAppViewContainer"] {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
    "Helvetica Neue", Arial, sans-serif;
}
.stApp {
  background: linear-gradient(165deg, #f5f5f7 0%, #ebebf0 45%, #f5f5f7 100%);
  background-attachment: fixed;
}
[data-testid="stAppViewContainer"] > .main {
  background: transparent;
  display: flex;
  flex-direction: column;
  justify-content: center;
  /* 顶栏占位 + 可视区垂直居中；内容过长时由页面滚动 */
  min-height: calc(100vh - 5.5rem);
  padding-top: 3.25rem;
  box-sizing: border-box;
}
.app-title-bar {
  position: relative;
  z-index: 0;
  padding: 0.15rem 0 0.75rem 0;
  margin: 0.35rem 0 0.75rem 0;
  background: linear-gradient(180deg, rgba(245,245,247,0.98) 70%, rgba(245,245,247,0));
  border-bottom: 1px solid rgba(0,0,0,0.06);
}
.block-container {
  margin-top: 10px;
  padding-top: 0.5rem;
  padding-bottom: 2rem;
  max-width: 1100px;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
}
section[data-testid="stSidebar"] {
  background: rgba(245, 245, 247, 0.85) !important;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-right: 1px solid rgba(0, 0, 0, 0.06) !important;
}
section[data-testid="stSidebar"] .block-container {
  background: transparent;
  border: none;
  box-shadow: none;
  border-radius: 0;
  max-width: none;
  padding: 1rem 1.1rem;
}
header[data-testid="stHeader"] {
  background: rgba(255, 255, 255, 0.35);
  backdrop-filter: blur(12px);
}
[data-testid="stDecoration"] { display: none; }
[data-testid="stToolbar"] { opacity: 0.55; }
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(255, 255, 255, 0.7) !important;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(0, 0, 0, 0.06) !important;
  border-radius: 12px !important;
  padding: 20px !important;
}
.stButton > button {
  border-radius: 8px !important;
  font-weight: 500 !important;
}
[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input {
  border-radius: 8px !important;
}
[data-testid="stExpander"] {
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(0, 0, 0, 0.05);
  border-radius: 8px;
  margin-bottom: 8px;
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] details > summary {
  font-weight: 600;
}
button[kind="secondary"] {
  opacity: 0.92;
}
h1, h2, h3 { font-weight: 600 !important; letter-spacing: -0.02em; color: #1d1d1f !important; }
[data-testid="stMetricValue"] { font-weight: 600 !important; }
</style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_vector_store(kb_slug: str):
    return VectorStore(kb_slug=kb_slug)


@st.cache_resource
def get_chunker():
    return Chunker()


@st.cache_resource
def get_analyzer():
    return TemplateAnalyzer()


_LOG = logging.getLogger(__name__)


def _run_template_vision_and_analyze(docx_path: str):
    """
    分步展示进度；成功返回 (vision_profile, vis_msg, tasks)，失败返回 None（已展示错误）。
    """
    with st.status("模板视觉理解 + 结构分析…", expanded=True) as status:
        status.write(
            "① **模板视觉**：docx→PDF（LibreOffice）→ 页图 → 多模态模型 "
            f"`{getattr(config, 'TEMPLATE_VISION_MODEL', '') or config.VISION_WEB_MODEL}`。"
            " 若勾选「跳过模板视觉」则本步只做文本抽取，通常数秒内完成。"
        )
        try:
            skip_v = bool(st.session_state.get("adv_skip_template_vision", False))
            vis_prof, vis_msg = get_or_build_template_vision_profile(
                docx_path, skip_vision=skip_v
            )
        except Exception as e:
            _LOG.exception("get_or_build_template_vision_profile")
            status.update(label="模板视觉阶段失败", state="error")
            st.error(f"模板视觉阶段异常：`{type(e).__name__}: {e}`")
            return None
        status.write(vis_msg or "（视觉阶段无额外说明）")
        analyze_model = config.TEMPLATE_ANALYZE_MODEL
        analyze_timeout = float(getattr(config, "TEMPLATE_ANALYZE_TIMEOUT", 90))
        status.write(
            "② **结构分析**：识别填空位（纯文本，模型 "
            f"`{analyze_model}`）。若模板无 `{{锚点}}`，此步必调用 LLM；"
            f"本步超时 {analyze_timeout:.0f}s（`TEMPLATE_ANALYZE_TIMEOUT`）；"
            "有百炼 Key 时结构分析走百炼以避开网关卡顿。"
            "终端 `APP_CONSOLE_LOG=1` 可见 `template_analyze` 日志。"
        )
        status.write("⏳ 正在请求结构分析 API…（大模板可能需 30～90 秒）")
        try:
            from core.slot_scanner import scan_deterministic_fill_tasks
            from core.task_reconcile import reconcile_fill_tasks

            tasks: list[FillTask] = get_analyzer().analyze(
                docx_path, vision_profile=vis_prof
            )
            tasks = reconcile_fill_tasks(
                tasks, scan_deterministic_fill_tasks(docx_path)
            )
        except Exception as e:
            _LOG.exception("TemplateAnalyzer.analyze")
            status.update(label="结构分析失败", state="error")
            st.error(f"结构分析异常：`{type(e).__name__}: {e}`")
            return None
        status.update(label="模板分析完成", state="complete")
    return vis_prof, vis_msg, tasks


@st.cache_resource
def get_filler():
    return WordFiller()


def _invalidate_vector_cache() -> None:
    try:
        get_vector_store.clear()
    except Exception:
        try:
            st.cache_resource.clear()
        except Exception:
            pass


def _list_docx_templates() -> list[str]:
    if not os.path.exists(config.TEMPLATE_DIR):
        return []
    return sorted(t for t in os.listdir(config.TEMPLATE_DIR) if t.endswith(".docx"))


def _maybe_autoselect_template() -> None:
    tpls = _list_docx_templates()
    if len(tpls) == 1 and not st.session_state.get(SS_SELECTED_TEMPLATE):
        st.session_state[SS_SELECTED_TEMPLATE] = tpls[0]


def _open_project_root() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    if os.name == "nt":
        os.startfile(root)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", root])
    else:
        subprocess.Popen(["xdg-open", root])


def _render_kb_selectbox(label: str, key: str) -> None:
    reg = load_registry()
    if not reg:
        st.warning("知识库注册表为空。")
        return
    labels = [f"{e['label']} · `{e['slug']}`" for e in reg]
    slugs = [e["slug"] for e in reg]
    active = st.session_state[SS_ACTIVE_KB]
    idx = slugs.index(active) if active in slugs else 0
    choice = st.selectbox(label, range(len(reg)), format_func=lambda j: labels[j], index=idx, key=key)
    new_slug = slugs[int(choice)]
    if new_slug != st.session_state[SS_ACTIVE_KB]:
        st.session_state[SS_ACTIVE_KB] = new_slug
        _invalidate_vector_cache()
        st.rerun()


def _render_intensity_select_slider() -> None:
    cur = st.session_state.get(SS_GENERATION_MODE, "普通")
    if cur not in MODE_ORDER:
        cur = "普通"
    picked = st.select_slider(
        "生成强度",
        options=MODE_ORDER,
        value=cur,
        help="快速：少检索、无联网、较短、非流式。普通：平衡。增强：多检索并尝试联网补料。",
    )
    if picked != st.session_state.get(SS_GENERATION_MODE):
        st.session_state[SS_GENERATION_MODE] = picked
        st.session_state[SS_PENDING_MODE_APPLY] = picked
        st.rerun()


def _stream_three_line_window(
    generator: ContentGenerator,
    task: FillTask,
    top_k: int,
    enable_web: bool,
    retrieval_max_distance: float,
    route_slot,
    table_context: str | None = None,
    correction_hint: str | None = None,
    web_writing_mode: str | None = None,
) -> tuple[str, GenerationBundle]:
    def _route_hook(meta: dict) -> None:
        if meta.get("native_web_search"):
            reason = (
                "弱库/无命中"
                if meta.get("weak_kb")
                else (
                    "最佳估算相似度过低"
                    if meta.get("low_similarity")
                    else "联网"
                )
            )
            route_slot.success(
                "联网：已请求百炼 enable_search（"
                + reason
                + "）· 模型 "
                + str(meta.get("model", ""))
                + f" · 知识库命中 {meta.get('kb_hits', 0)} 条 · weak_kb={meta.get('weak_kb')} "
                + f"· low_sim={meta.get('low_similarity')} · est_sim≈{meta.get('best_similarity_est')} "
                + "（终端可见 core.generator 的 INFO 日志）"
            )
        else:
            route_slot.info(
                "路由：未启用联网 · 模型 "
                + str(meta.get("model", ""))
                + f" · tier={meta.get('generation_tier')}"
                + f" · 知识库命中 {meta.get('kb_hits', 0)} 条 · 侧栏联网="
                + ("开" if meta.get("enable_web_requested") else "关")
                + f" · weak_kb={meta.get('weak_kb')} · low_sim={meta.get('low_similarity')}"
                + f" · est_sim≈{meta.get('best_similarity_est')} / 阈值 {meta.get('retrieval_web_similarity_threshold')}"
            )

    bundle = generator.prepare_generation_bundle(
        task,
        top_k=top_k,
        enable_web=enable_web,
        retrieval_max_distance=retrieval_max_distance,
        table_context=table_context,
        correction_hint=correction_hint,
        web_writing_mode=web_writing_mode,
    )
    hist_exp = st.expander("已生成历史内容（较早段落）", expanded=False)
    with hist_exp:
        hist_ph = st.empty()
    live_ph = st.empty()
    full = ""
    n_update = 0
    for piece in generator.stream_from_bundle(bundle, route_hook=_route_hook):
        full += piece
        n_update += 1
        lines = full.split("\n")
        if len(lines) <= 3:
            live_ph.markdown("\n".join(lines) or " ")
            hist_ph.markdown(" ")
        else:
            hist_body = "\n".join(lines[:-3])
            hist_ph.markdown(hist_body or " ")
            live_ph.markdown("\n".join(lines[-3:]))
        if n_update % 4 == 0:
            time.sleep(0)
    return full.strip(), bundle


def _render_persistent_download() -> None:
    last_p = st.session_state.get(SS_LAST_OUT_PATH)
    last_n = st.session_state.get(SS_LAST_OUT_NAME)
    if last_p and last_n and os.path.isfile(last_p):
        st.caption(f"上次输出：{last_n}")
        c1, c2 = st.columns([3, 1])
        with c1:
            with open(last_p, "rb") as f:
                st.download_button(
                    "下载上次生成的文档",
                    data=f.read(),
                    file_name=last_n,
                    use_container_width=True,
                    type="primary",
                    key="dl_persistent_main",
                )
        with c2:
            if st.button("清除记录", key="clr_dl_rec", type="secondary"):
                st.session_state.pop(SS_LAST_OUT_PATH, None)
                st.session_state.pop(SS_LAST_OUT_NAME, None)
                st.rerun()


def _render_hello_tab(active_slug: str) -> None:
    """首页：产品说明、推荐步骤、环境与配置只读摘要。"""
    st.markdown("#### 欢迎使用项目计划书生成器")
    st.markdown(
        "基于知识库 RAG 与 Word 模板填空，面向申报类、计划类文档的半自动撰写。"
        "侧栏管理知识库与生成参数；下方标签页完成入库、模板分析与生成下载。"
    )
    st.markdown("##### 推荐使用顺序")
    st.markdown(
        "1. **侧栏**：确认或新建知识库，设置生成强度与联网/审核等开关。  \n"
        "2. **知识库管理**：上传 PDF/Word 等资料并入库。  \n"
        "3. **模板配置**：上传 `.docx` 模板并分析填空位。  \n"
        "4. **生成预览**：一键生成并下载已填写文档。"
    )
    st.markdown("##### 当前环境")
    embed_ok = config.embedding_llm_configured()
    chat_ok = config.chat_llm_configured()
    c1, c2, c3 = st.columns(3)
    c1.metric("嵌入 / 入库", "就绪" if embed_ok else "未配置")
    c2.metric("聊天 / 生成", "就绪" if chat_ok else "未配置")
    c3.metric("生成强度", st.session_state.get(SS_GENERATION_MODE, "普通"))
    if not embed_ok:
        st.warning(
            "入库与检索需百炼兼容 Key：在 `.env` 配置 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY`。"
        )
    if not chat_ok:
        st.warning(
            "生成需聊天通道：配置 `FOSUN_AIGW_API_KEY`（复星网关）或上述百炼 Key。"
        )
    reg = load_registry()
    label = next((e["label"] for e in reg if e["slug"] == active_slug), active_slug)
    st.caption(f"当前知识库：**{label}** · `{active_slug}`")
    st.caption(
        "模型：小 `"
        + config.SMALL_LLM_MODEL
        + "` · 大 `"
        + config.LARGE_LLM_MODEL
        + "` · 联网 `"
        + config.VISION_WEB_MODEL
        + "` · 审核 `"
        + config.AUDIT_LLM_MODEL
        + "`"
    )


st.set_page_config(page_title="计划书生成器", page_icon="◆", layout="wide")
_init_session()
_flush_pending_mode_defaults()
_glass_theme()

_maybe_autoselect_template()

active_slug = st.session_state[SS_ACTIVE_KB]
vs = get_vector_store(active_slug)
chunker = get_chunker()
filler = get_filler()

st.markdown(
    '<div class="app-title-bar"><h2 style="margin:0;">项目计划书生成器</h2>'
    "<p style='margin:0.25rem 0 0 0;color:#6e6e73;font-size:0.9rem;'>"
    "侧栏管理知识库与生成强度；主区用标签页完成入库、模板与生成。</p></div>",
    unsafe_allow_html=True,
)

# ----- Sidebar -----
with st.sidebar:
    st.markdown("##### 配置区")

    with st.expander("知识库管理", expanded=True):
        embed_ok = config.embedding_llm_configured()
        chat_ok = config.chat_llm_configured()
        st.caption(f"嵌入（入库）：{'Key 可用' if embed_ok else '未配置百炼 Key'}")
        st.caption(f"聊天/生成：{'可用' if chat_ok else '未配置'}")
        if not embed_ok:
            st.warning(
                "入库与检索依赖百炼兼容接口：请在 `.env` 中配置 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY`。"
            )
        if not chat_ok:
            st.warning(
                "生成依赖聊天通道：请配置 `FOSUN_AIGW_API_KEY`（网关）或上述百炼 Key。"
            )
        st.caption(
            "弱知识库联网档：`"
            + config.VISION_WEB_MODEL
            + "`（须支持 `enable_search`；默认 qwen3.5-plus，失败回落百炼）。"
        )
        if st.button("打开项目目录", key="open_root", type="secondary"):
            try:
                _open_project_root()
                st.success("已尝试打开项目文件夹。")
            except Exception as e:
                st.error(str(e))

        _render_kb_selectbox("当前知识库", "sidebar_kb_sel")
        reg = load_registry()
        slug = st.session_state[SS_ACTIVE_KB]
        label = next((e["label"] for e in reg if e["slug"] == slug), slug)
        st.markdown(f"**{label}** · `{slug}`")

        c_new, c_del = st.columns(2)
        with c_new:
            with st.popover("新建库"):
                nb_label = st.text_input("名称", key="sb_nb_label")
                nb_slug = st.text_input("slug（可空）", key="sb_nb_slug")
                if st.button("创建", key="sb_kb_create"):
                    if not (nb_label or "").strip():
                        st.error("请填写名称。")
                    else:
                        try:
                            created = add_kb(nb_label.strip(), (nb_slug or "").strip() or None)
                            st.session_state[SS_ACTIVE_KB] = created
                            _invalidate_vector_cache()
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
        with c_del:
            with st.popover("删除库"):
                st.caption("向量不可恢复。输入 DELETE 后删除。")
                confirm = st.text_input("确认", key="sb_del_confirm")
                if st.button("删除当前库", type="secondary", key="sb_kb_rm"):
                    if confirm.strip().upper() != "DELETE":
                        st.error("需输入 DELETE。")
                    else:
                        slug_del = st.session_state[SS_ACTIVE_KB]
                        try:
                            remove_kb(slug_del)
                        except ValueError as e:
                            st.error(str(e))
                        else:
                            VectorStore(kb_slug=slug_del).delete_entire_collection()
                            _invalidate_vector_cache()
                            st.session_state.pop(SS_TASKS, None)
                            st.session_state.pop(SS_TASKS_SIG, None)
                            reg2 = load_registry()
                            st.session_state[SS_ACTIVE_KB] = reg2[0]["slug"] if reg2 else "kb1"
                            st.rerun()

    with st.expander("生成设置", expanded=True):
        _render_intensity_select_slider()
        st.caption(
            "模型：`"
            + config.SMALL_LLM_MODEL
            + "` / `"
            + config.LARGE_LLM_MODEL
            + "` · 审核：`"
            + config.AUDIT_LLM_MODEL
            + "`"
        )
        st.caption(
            "视觉：`"
            + config.VISION_EXTRACT_MODEL
            + "`（图入库）· `"
            + config.TEMPLATE_VISION_MODEL
            + "`（模板页）· `"
            + config.TABLE_CELL_VISION_MODEL
            + "`（表格切图）"
        )
        st.checkbox(
            "流式显示",
            key="adv_use_stream",
            help="开启后像打字一样实时刷新生成过程（仅影响展示方式）。",
        )
        st.checkbox(
            "联网补料（百炼内置搜索）",
            key="adv_use_tavily",
            help="在「知识库为空或检索无命中」或「最佳命中估算相似度低于阈值（默认 0.3，sim≈1−distance）」时，对该段改用 VISION_WEB_MODEL 并开启 enable_search（网关须支持该字段）。阈值见环境变量 RETRIEVAL_WEB_SIMILARITY_THRESHOLD。",
        )
        st.radio(
            "联网写作模式（仅本段实际走联网档 enable_search 时切换提示词）",
            ("calm", "creative"),
            format_func=lambda m: (
                "冷静：缺口标「资料未载明」，与当前默认一致"
                if m == "calm"
                else "创意：写满正文，少用「资料未载明」；合规数字仍勿编造"
            ),
            horizontal=True,
            key="adv_web_writing_mode",
            disabled=not bool(st.session_state.get("adv_use_tavily", False)),
            help="未勾选联网补料时本项无效。创意模式依赖模型与联网概括，申报类文稿请人工复核。",
        )
        st.checkbox(
            "启用审核 Agent",
            key="adv_use_audit_agent",
            help="每段生成后使用 "
            + config.AUDIT_LLM_MODEL
            + " 对照检索片段与表格上下文质检；minor_fix 时可自动采用修订稿。",
        )
        st.checkbox(
            "审核 major 时自动重试生成 1 次",
            key="adv_audit_regenerate",
            help="仅当启用审核且审核 verdict 为 major_issue 时，将审核意见注入后重新生成一段（仍消耗 API）。",
        )
        st.checkbox(
            "快速生成（表格不联网、不传截图；已关深度思考）",
            value=True,
            key="adv_fast_gen",
            help="表格批量与逐格填写均不走 enable_search/页图多模态，改用 "
            + getattr(config, "BATCH_TABLE_FAST_MODEL", "qwen3.5-plus")
            + " 纯文本；正文段在开启本项时也不走联网档。显著加快，弱库时可能更多「资料未载明」。",
        )
        st.checkbox(
            "表格行批量生成（降低 API 调用次数）",
            value=True,
            key="adv_use_batch_table",
            help="将同一表格行的单元格合并为一次 LLM 调用输出 JSON；解析失败自动降级为逐格生成。",
        )

    with st.expander("高级参数", expanded=False):
        st.number_input(
            "每段默认字数",
            min_value=50,
            max_value=2000,
            key="adv_default_word_limit",
            help="控制每段生成的大致长度；300 字约半页 Word（视字号而定）。",
        )
        st.slider(
            "检索条数 top_k",
            1,
            15,
            key="adv_top_k",
            help="从知识库取几条最相关的片段参与写作；例如 3 表示最多 3 条。",
        )
        st.slider(
            "最大检索距离",
            min_value=0.3,
            max_value=2.5,
            key="adv_retrieval_max_distance",
            help="向量距离上限：越小越严格，只保留更相似的片段；过大可能混入较弱相关文本。",
        )
        st.checkbox(
            "下次生成前强制重新分析模板",
            key="adv_force_clear_analysis",
            value=False,
            help="清除已缓存的模板结构分析，用当前文件重新识别填空位。",
        )
        st.checkbox(
            "启用视觉审核",
            key="adv_visual_audit_enabled",
            value=getattr(config, "VISUAL_AUDIT_ENABLED", True),
            help="生成后对文档进行视觉质量审核（需要 VLM 支持）。",
        )
        st.checkbox(
            "使用 MiMo 模型",
            key="adv_use_mimo",
            value=False,
            help="使用 MiMo-V2.5-Pro 进行内容生成（支持联网搜索）。",
        )

tab_home, tab_kb, tab_tpl, tab_gen = st.tabs(
    ["首页", "知识库管理", "模板配置", "生成预览"]
)

with tab_home:
    _render_hello_tab(active_slug)

with tab_kb:
    st.markdown("#### 知识库管理")
    st.caption("在侧栏切换知识库；此处查看片段与来源，并上传资料入库。")
    counts = vs.source_chunk_counts()
    sources = sorted(counts.keys())
    c1, c2 = st.columns(2)
    c1.metric("片段数量", vs.get_collection_count())
    c2.metric("来源数量", len(sources))

    st.markdown("##### 来源列表")
    if not sources:
        st.warning("当前库尚无资料，请使用下方上传器添加后点击「入库」。")
    else:
        for src in sources:
            cc1, cc2 = st.columns([4, 1])
            cc1.markdown(f"**{src}** · {counts.get(src, 0)} 条片段")
            safe_key = "rm_" + str(abs(hash(src)))[-12:]
            if cc2.button("移除", key=safe_key, type="secondary"):
                vs.delete_by_source(src)
                _invalidate_vector_cache()
                st.rerun()

    st.markdown("##### 上传并入库")
    st.caption("支持 Word / PDF / PPT / 图片；旧 .ppt 请先另存为 pptx。")
    uploaded = st.file_uploader(
        "拖拽或选择文件",
        type=["docx", "pdf", "pptx", "png", "jpg", "jpeg", "webp", "gif"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded:
        st.caption(f"已选择 {len(uploaded)} 个文件")
    if uploaded and st.button("入库", type="primary", key="tab_kb_ingest"):
        bar = st.progress(0.0)
        total = len(uploaded)
        for i, file in enumerate(uploaded):
            save_path = os.path.join(config.HISTORICAL_DIR, file.name)
            with open(save_path, "wb") as f:
                f.write(file.read())
            with st.spinner(f"正在解析 {file.name}…"):
                parsed_doc = path_to_parsed_document(save_path, original_name=file.name)
                chunks = chunker.chunk(parsed_doc)
                vs.add_documents(chunks)
            bar.progress((i + 1) / total)
        st.success(f"已入库 {total} 个文件。")
        st.rerun()

with tab_tpl:
    st.markdown("#### 模板配置")
    st.caption(
        "上传 `.docx`；可用 `{{ANCHOR_NAME}}` 标注待填空位，无锚点时由模型推断待填区域。"
    )
    left, right = st.columns([2, 1])

    with left:
        st.checkbox(
            "跳过模板视觉（不跑 PDF/多模态，仅用 Word 内文本摘要；更快，版式提示弱）",
            key="adv_skip_template_vision",
            help="卡在步骤①或网关视觉慢时勾选。全局关闭可设环境变量 TEMPLATE_VISION_ENABLED=0。",
        )
        tpl_up = st.file_uploader(
            "拖拽或选择 Word 模板",
            type=["docx"],
            key="tab_tpl_up",
            label_visibility="visible",
        )
        if st.button("分析模板", type="primary", key="tab_tpl_analyze"):
            if not tpl_up:
                st.warning("请先选择 .docx 文件。")
            else:
                save_path = os.path.join(config.TEMPLATE_DIR, tpl_up.name)
                with open(save_path, "wb") as f:
                    f.write(tpl_up.getbuffer())
                out = _run_template_vision_and_analyze(save_path)
                if out is None:
                    st.stop()
                vis_prof, vis_msg, tasks = out
                st.caption(vis_msg)
                if not tasks:
                    st.warning("未识别到待填位置，请检查文档或锚点写法。")
                else:
                    st.session_state[SS_TASKS] = _tasks_to_dicts(tasks)
                    st.session_state[SS_TASKS_SIG] = _template_signature(save_path)
                    st.session_state[SS_SELECTED_TEMPLATE] = tpl_up.name
                    st.success(f"已识别 {len(tasks)} 处待填。")
                    rows = [
                        {
                            "章节": t.target_chapter,
                            "类型": t.task_type,
                            "描述": (t.description or "")[:120],
                            "字数建议": t.word_limit,
                        }
                        for t in tasks
                    ]
                    st.dataframe(rows, use_container_width=True, hide_index=True)

    with right:
        st.markdown("##### 已上传模板")
        templates = _list_docx_templates()
        if not templates:
            st.caption("暂无模板。")
        else:
            for tname in templates:
                p = os.path.join(config.TEMPLATE_DIR, tname)
                try:
                    mt = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")
                except OSError:
                    mt = "—"
                sel = st.session_state.get(SS_SELECTED_TEMPLATE) == tname
                if st.button(
                    f"{'✓ ' if sel else ''}{tname}",
                    key=f"pick_tpl_{tname}",
                    use_container_width=True,
                    type="primary" if sel else "secondary",
                ):
                    st.session_state[SS_SELECTED_TEMPLATE] = tname
                    st.rerun()
                st.caption(mt)
        if st.button("清除模板分析缓存", key="tab_tpl_clear", type="secondary"):
            st.session_state.pop(SS_TASKS, None)
            st.session_state.pop(SS_TASKS_SIG, None)
            st.success("已清除。")

with tab_gen:
    st.markdown("#### 生成预览")
    templates = _list_docx_templates()
    selected = st.session_state.get(SS_SELECTED_TEMPLATE)
    if selected and selected not in templates:
        selected = templates[0] if templates else None
        st.session_state[SS_SELECTED_TEMPLATE] = selected
    if templates and not selected:
        st.session_state[SS_SELECTED_TEMPLATE] = templates[0]
        selected = templates[0]

    reg = load_registry()
    kb_label = next((e["label"] for e in reg if e["slug"] == active_slug), active_slug)
    counts = vs.source_chunk_counts()
    st.caption(
        f"知识库：{kb_label} · 片段 {vs.get_collection_count()} · 来源 {len(counts)}"
        + (f" · 模板：{selected}" if selected else " · 未选模板")
    )

    _render_persistent_download()

    top_k = int(st.session_state.get("adv_top_k", 5))
    retrieval_max_distance = float(st.session_state.get("adv_retrieval_max_distance", 0.8))
    enable_web = bool(st.session_state.get("adv_use_tavily", False))
    fast_gen = bool(st.session_state.get("adv_fast_gen", True))
    web_writing_mode = str(st.session_state.get("adv_web_writing_mode", "calm")).strip().lower()
    if web_writing_mode != "creative":
        web_writing_mode = "calm"
    default_word = int(st.session_state.get("adv_default_word_limit", 500))
    use_stream = bool(st.session_state.get("adv_use_stream", True))

    n_frag = vs.get_collection_count()
    gen_disabled = (
        not templates
        or not selected
        or not config.chat_llm_configured()
    )
    if not n_frag:
        st.warning("知识库为空，生成可能缺少依据。")

    st.markdown("---")
    run_generate = st.button(
        "开始生成",
        type="primary",
        use_container_width=True,
        disabled=gen_disabled,
        key="tab_gen_run",
    )

    if run_generate:
        if st.session_state.get("adv_force_clear_analysis", False):
            st.session_state.pop(SS_TASKS, None)
            st.session_state.pop(SS_TASKS_SIG, None)

        if not templates or not selected:
            st.error("请先上传并在「模板配置」中选择模板。")
        else:
            template_path = os.path.join(config.TEMPLATE_DIR, selected)
            sig = _template_signature(template_path)

            tasks = None
            if st.session_state.get(SS_TASKS) and st.session_state.get(SS_TASKS_SIG) == sig:
                tasks = _dicts_to_tasks(st.session_state[SS_TASKS])
                st.info("使用已缓存的模板分析。")
            else:
                out = _run_template_vision_and_analyze(template_path)
                if out is None:
                    st.stop()
                vis_prof, vis_msg, tasks = out
                st.caption(vis_msg)
                if tasks:
                    st.session_state[SS_TASKS] = _tasks_to_dicts(tasks)
                    st.session_state[SS_TASKS_SIG] = sig

            if not tasks:
                st.warning("没有可用的填空任务，请先在「模板配置」中分析模板。")
            else:
                generator = ContentGenerator(vs)
                from core.template_vision import ensure_template_page_pngs

                ensure_template_page_pngs(template_path)
                results: list[str] = []
                total_chars = 0

                # 预检索：按分组做一次向量检索，后续任务复用
                task_groups = group_tasks(tasks)
                with st.spinner(f"预检索中（{len(task_groups)} 个任务组）…"):
                    evidence_map: dict[str, Evidence] = {}
                    for grp in task_groups:
                        ev = retrieve_for_group(
                            vs, grp,
                            top_k=top_k,
                            max_distance=retrieval_max_distance,
                        )
                        evidence_map[grp.group_id] = ev
                        for t in grp.tasks:
                            t._evidence_group_id = grp.group_id  # type: ignore[attr-defined]

                # 批量生成（表格行）：提前尝试，失败则逐格降级
                use_batch = bool(st.session_state.get("adv_use_batch_table", True))
                batch_cache: dict[str, str] = {}  # task_id -> content
                if use_batch:
                    table_groups = [g for g in task_groups if g.is_table_group]
                    batch_n = len(table_groups)
                    with st.spinner(
                        f"批量生成表格行（{'快速' if fast_gen else '标准'}，共 {batch_n} 组）…"
                    ):
                        batch_prog = st.progress(0.0) if batch_n else None
                        batch_status = st.empty()
                        for bi, grp in enumerate(table_groups):
                            if batch_status is not None:
                                batch_status.caption(
                                    f"表格批量 {bi + 1}/{batch_n} · {grp.tasks[0].target_chapter}"
                                )
                            if batch_prog is not None and batch_n:
                                batch_prog.progress((bi + 1) / batch_n)
                            ev = evidence_map.get(grp.group_id)
                            if ev is None:
                                continue
                            loc0 = grp.tasks[0].location_hint or {}
                            tbl_ctx = None
                            row_pngs = None
                            try:
                                from core.table_context import build_table_cell_context

                                tbl_ctx = build_table_cell_context(
                                    template_path,
                                    int(loc0.get("table_index", 0)),
                                    int(loc0.get("row", 0)),
                                    int(loc0.get("col", 0)),
                                )
                            except Exception:
                                tbl_ctx = None
                            if not fast_gen:
                                try:
                                    from core.template_vision import (
                                        load_table_cell_vision_pngs,
                                    )

                                    row_pngs = load_table_cell_vision_pngs(
                                        template_path, int(loc0.get("table_index", 0))
                                    )
                                    row_pngs = row_pngs or None
                                except Exception:
                                    row_pngs = None
                            batch_result = batch_generate_table_row(
                                generator._client,
                                grp.tasks,
                                ev,
                                table_context=tbl_ctx,
                                enable_web=enable_web,
                                template_path=template_path,
                                web_writing_mode=web_writing_mode,
                                table_cell_vision_pngs=row_pngs,
                                fast_mode=fast_gen,
                            )
                            if batch_result is not None:
                                for cell_idx, cell_content in batch_result.items():
                                    if 0 <= cell_idx < len(grp.tasks):
                                        batch_cache[grp.tasks[cell_idx].task_id] = cell_content

                with st.status("正在生成…", expanded=True) as status:
                    prog = st.progress(0.0)
                    n_tasks = len(tasks)
                    for i, task in enumerate(tasks):
                        if task.word_limit <= 0:
                            task.word_limit = default_word
                        if task.task_type == "paragraph" and WordFiller._is_abstract_chapter(
                            task.target_chapter or ""
                        ):
                            task.word_limit = max(
                                int(task.word_limit),
                                int(getattr(config, "ABSTRACT_WORD_LIMIT", 650)),
                            )
                        st.markdown(
                            f"**正在生成** · {task.target_chapter} · {i + 1}/{n_tasks} · "
                            f"累计约 {total_chars} 字"
                        )
                        route_slot = st.empty()
                        audit_slot = st.empty()
                        use_audit = bool(
                            st.session_state.get("adv_use_audit_agent", False)
                        )
                        audit_regen = bool(
                            st.session_state.get("adv_audit_regenerate", False)
                        )

                        table_ctx: str | None = None
                        tbl_pngs_for_cell: list[bytes] | None = None
                        if task.task_type == "table_cell":
                            loc = task.location_hint or {}
                            table_ctx = build_table_cell_context(
                                template_path,
                                int(loc.get("table_index", 0)),
                                int(loc.get("row", 0)),
                                int(loc.get("col", 0)),
                            )
                            if not fast_gen:
                                from core.template_vision import load_table_cell_vision_pngs

                                _p = load_table_cell_vision_pngs(
                                    template_path, int(loc.get("table_index", 0))
                                )
                                tbl_pngs_for_cell = _p if _p else None

                        gen_bundle: GenerationBundle | None = None
                        content = ""

                        # 尝试从批量缓存取结果
                        if task.task_id in batch_cache:
                            content = batch_cache[task.task_id]
                            _ev_gid = getattr(task, "_evidence_group_id", "") or ""
                            _ev_obj = evidence_map.get(_ev_gid)
                            _kb_n = _ev_obj.kb_hits if _ev_obj is not None else 0
                            route_slot.info(f"批量生成（表格行）· kb={_kb_n}")
                            wc = len(content)
                            total_chars += wc
                            st.text_area(
                                label=f"完成(批量) · {task.target_chapter}（约 {wc} 字）",
                                value=content,
                                height=min(260, max(100, wc // 2 + 40)),
                                disabled=True,
                                key=f"gen_done_batch_{i}_{task.task_id}",
                            )
                            results.append(content)
                            prog.progress((i + 1) / n_tasks)
                            continue

                        _ev_group_id: str = getattr(task, "_evidence_group_id", "")
                        _shared_ev: Evidence | None = evidence_map.get(_ev_group_id)

                        def _make_bundle(
                            _correction_hint: str | None = None,
                        ) -> GenerationBundle:
                            if _shared_ev is not None:
                                return generator.prepare_bundle_from_evidence(
                                    task,
                                    _shared_ev,
                                    enable_web=enable_web,
                                    table_context=table_ctx,
                                    correction_hint=_correction_hint,
                                    web_writing_mode=web_writing_mode,
                                    table_cell_vision_pngs=tbl_pngs_for_cell,
                                    fast_mode=fast_gen,
                                )
                            return generator.prepare_generation_bundle(
                                task,
                                top_k=top_k,
                                enable_web=enable_web,
                                retrieval_max_distance=retrieval_max_distance,
                                table_context=table_ctx,
                                correction_hint=_correction_hint,
                                web_writing_mode=web_writing_mode,
                                table_cell_vision_pngs=tbl_pngs_for_cell,
                                fast_mode=fast_gen,
                            )

                        try:
                            if use_stream:
                                gen_bundle = _make_bundle()

                                def _route_hook_stream(meta: dict) -> None:
                                    if meta.get("native_web_search"):
                                        rs = (
                                            "弱库/无命中" if meta.get("weak_kb")
                                            else ("相似度过低" if meta.get("low_similarity") else "联网")
                                        )
                                        route_slot.success(
                                            f"联网 · {rs} · 模型 {meta.get('model','')} · "
                                            f"kb={meta.get('kb_hits',0)} · sim≈{meta.get('best_similarity_est')}"
                                        )
                                    else:
                                        tier = meta.get("generation_tier", "large")
                                        route_slot.info(
                                            f"路由：{tier} · 模型 {meta.get('model','')} · "
                                            f"kb={meta.get('kb_hits',0)} · sim≈{meta.get('best_similarity_est')}"
                                        )

                                content_parts: list[str] = []
                                _route_hook_stream(gen_bundle.route_meta)
                                for piece in generator.stream_from_bundle(gen_bundle, route_hook=None):
                                    content_parts.append(piece)
                                content = "".join(content_parts).strip()
                            else:
                                st.caption("非流式，请稍候…")

                                def _route_hook_ns(meta: dict) -> None:
                                    if meta.get("native_web_search"):
                                        rs = (
                                            "弱库/无命中"
                                            if meta.get("weak_kb")
                                            else (
                                                "最佳估算相似度过低"
                                                if meta.get("low_similarity")
                                                else "联网"
                                            )
                                        )
                                        route_slot.success(
                                            "联网：已请求百炼 enable_search（"
                                            + rs
                                            + "）· 模型 "
                                            + str(meta.get("model", ""))
                                            + f" · kb_hits={meta.get('kb_hits', 0)} · est_sim≈{meta.get('best_similarity_est')}"
                                        )
                                    else:
                                        route_slot.info(
                                            "路由：未启用联网 · 模型 "
                                            + str(meta.get("model", ""))
                                            + f" · kb_hits={meta.get('kb_hits', 0)} · low_sim={meta.get('low_similarity')} · est_sim≈{meta.get('best_similarity_est')}"
                                        )

                                gen_bundle = _make_bundle()
                                _route_hook_ns(gen_bundle.route_meta)
                                content = generator.generate_from_bundle(
                                    gen_bundle, route_hook=None
                                )

                            if (
                                use_audit
                                and gen_bundle is not None
                                and not str(content).startswith("（生成失败")
                            ):
                                r_issues = rule_audit(task, content, gen_bundle.route_meta)
                                do_model_audit = need_model_audit(
                                    task, gen_bundle.route_meta, r_issues
                                )

                                applied_revision = False
                                last_ar = None
                                audit_lines: list[str] = []

                                if r_issues and not do_model_audit:
                                    audit_lines.append("规则审核：问题 · " + "；".join(r_issues))
                                    audit_slot.warning("\n".join(audit_lines))
                                elif do_model_audit:
                                    auditor = ContentAuditor()
                                    ar = auditor.audit(
                                        task,
                                        content,
                                        gen_bundle.ref_texts,
                                        table_ctx,
                                        gen_bundle.route_meta,
                                    )
                                    last_ar = ar
                                    if r_issues:
                                        audit_lines.append("规则：" + "；".join(r_issues))
                                    audit_lines += [
                                        f"模型审核：{ar.verdict}",
                                        (ar.one_line_summary or "").strip() or "（无摘要）",
                                    ]
                                    if ar.issues:
                                        audit_lines.append(
                                            "问题：" + "；".join(ar.issues[:5])
                                        )
                                    if should_apply_revision(task, ar):
                                        content = ar.revised_content
                                        applied_revision = True
                                    elif (
                                        ar.verdict == "major_issue"
                                        and audit_regen
                                        and ar.issues
                                    ):
                                        hint = "\n".join(ar.issues[:10])
                                        gen_bundle2 = _make_bundle(hint)
                                        if use_stream:
                                            content = "".join(
                                                generator.stream_from_bundle(
                                                    gen_bundle2, route_hook=None
                                                )
                                            ).strip()
                                        else:
                                            content = generator.generate_from_bundle(
                                                gen_bundle2, route_hook=None
                                            )
                                        ar2 = auditor.audit(
                                            task,
                                            content,
                                            gen_bundle2.ref_texts,
                                            table_ctx,
                                            gen_bundle2.route_meta,
                                        )
                                        last_ar = ar2
                                        audit_lines.append(
                                            "重试后：" + ar2.verdict + " · "
                                            + ((ar2.one_line_summary or "").strip() or "（无摘要）")
                                        )
                                        if ar2.issues:
                                            audit_lines.append(
                                                "问题：" + "；".join(ar2.issues[:4])
                                            )
                                        if should_apply_revision(task, ar2):
                                            content = ar2.revised_content
                                            applied_revision = True

                                    msg = "\n".join(audit_lines)
                                    if applied_revision:
                                        audit_slot.success(msg + "\n（已采用审核修订稿）")
                                    elif last_ar and last_ar.verdict == "major_issue":
                                        audit_slot.warning(msg)
                                    elif last_ar and last_ar.verdict == "minor_fix":
                                        audit_slot.info(msg)
                                    else:
                                        audit_slot.success(msg)
                                else:
                                    audit_slot.success("规则审核通过（跳过模型审核）")
                        except Exception as e:
                            st.error(f"本段失败：{e}")
                            content = f"（生成失败：{e}）"

                        wc = len(content)
                        total_chars += wc
                        st.text_area(
                            label=f"完成 · {task.target_chapter}（约 {wc} 字）",
                            value=content,
                            height=min(260, max(100, wc // 2 + 40)),
                            disabled=True,
                            key=f"gen_done_{i}_{task.task_id}",
                        )

                        results.append(content)
                        prog.progress((i + 1) / n_tasks)

                    status.update(label="生成结束", state="complete")

                st.metric("本次生成总字数（约）", total_chars)

                output_name = selected.replace(".docx", "_已填写.docx")
                output_path = os.path.join(config.OUTPUT_DIR, output_name)
                with st.spinner("正在写入 Word…"):
                    filler.fill_template(template_path, tasks, results, output_path)

                # 视觉审核（如果启用）
                if getattr(config, "VISUAL_AUDIT_ENABLED", True):
                    try:
                        from core.visual_auditor import audit_document_visual, should_optimize
                        from core.document_optimizer import optimize_document, format_optimization_report

                        with st.spinner("正在进行视觉审核…"):
                            visual_result = audit_document_visual(output_path)

                        if visual_result.parse_ok:
                            st.info(f"视觉审核完成：总分 {visual_result.score}/100")

                            # 显示详细评分
                            cols = st.columns(5)
                            cols[0].metric("水印", f"{visual_result.watermark_score}/20")
                            cols[1].metric("格式", f"{visual_result.format_score}/20")
                            cols[2].metric("内容", f"{visual_result.content_score}/20")
                            cols[3].metric("表格", f"{visual_result.table_score}/20")
                            cols[4].metric("排版", f"{visual_result.layout_score}/20")

                            # 显示保护元素检测
                            if visual_result.protected_elements:
                                with st.expander("检测到的保护元素"):
                                    for elem in visual_result.protected_elements:
                                        st.write(f"- {elem}")

                            # 封面修改警告
                            if visual_result.cover_modified:
                                st.error("⚠️ 封面被意外修改！请检查封面内容是否被填充或修改。")

                            # 评分表修改警告
                            if visual_result.rating_table_modified:
                                st.error("⚠️ 评分表/评价表被意外修改！请检查评分区域是否被填充。")

                            # 如果需要优化
                            if should_optimize(visual_result):
                                st.warning(f"文档质量未达标（{visual_result.score} < {config.VISUAL_AUDIT_PASS_SCORE}），启动二轮优化…")

                                # 简化版优化：记录问题并提示用户
                                if visual_result.issues:
                                    with st.expander("发现的问题"):
                                        for issue in visual_result.issues:
                                            st.write(f"- {issue}")
                                if visual_result.suggestions:
                                    with st.expander("改进建议"):
                                        for suggestion in visual_result.suggestions:
                                            st.write(f"- {suggestion}")
                            else:
                                st.success("文档质量审核通过！")
                        else:
                            st.warning("视觉审核失败，跳过优化检查")
                    except Exception as e:
                        _LOG.warning("视觉审核流程异常: %s", e)
                        st.warning(f"视觉审核异常: {e}")

                st.session_state[SS_LAST_OUT_PATH] = output_path
                st.session_state[SS_LAST_OUT_NAME] = output_name

                st.success("生成完成。")
                with st.expander("预览全部段落", expanded=False):
                    for j, (t, txt) in enumerate(zip(tasks, results), start=1):
                        st.markdown(f"**{j}. {t.target_chapter}**")
                        st.text(txt)
                        st.divider()

                with open(output_path, "rb") as f:
                    st.download_button(
                        "下载已填写文档",
                        data=f.read(),
                        file_name=output_name,
                        type="primary",
                        use_container_width=True,
                        key="dl_filled_after_gen",
                    )
