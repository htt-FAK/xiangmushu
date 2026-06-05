"""
智能计划书生成器 — Streamlit 单页：侧栏配置 + 主区标签页（知识库 / 模板 / 生成预览）
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime

import streamlit as st

import config
from core.chunker import Chunker
from core.content_auditor import (
    ContentAuditor,
    need_model_audit,
    rule_audit,
    should_apply_revision,
)
from core.fill_task import FillTask
from core.generator import ContentGenerator
from core.filler import WordFiller
from core.kb_registry import add_kb, load_registry, remove_kb
from core.kb_extract import path_to_parsed_document
from core.post_fill_verifier import verify_filled_document
from core.reporting import (
    build_generation_trace,
    build_quality_report,
    quality_report_summary,
    save_quality_report,
)
from core.slot_scanner import scan_anchor_tasks
from core.vector_store import VectorStore
from core.visual_auditor import audit_document_visual


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


def _ensure_adv_params() -> None:
    if "adv_top_k" not in st.session_state:
        _apply_mode_defaults_to_session(st.session_state.get(SS_GENERATION_MODE, "普通"))


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


_LOG = logging.getLogger(__name__)


def _run_template_vision_and_analyze(docx_path: str):
    """一期默认模板分析路径：仅支持锚点模板。"""
    with st.status("模板分析…", expanded=True) as status:
        status.write("① **锚点扫描**：识别 `{{ANCHOR_NAME}}` 形式的待填空位。")
        try:
            tasks = scan_anchor_tasks(docx_path)
        except Exception as e:
            _LOG.exception("scan_anchor_tasks")
            status.update(label="模板分析失败", state="error")
            st.error(f"模板分析异常：`{type(e).__name__}: {e}`")
            return None

        if not tasks:
            status.update(label="未识别到锚点", state="error")
            st.warning(
                "一期默认仅支持带锚点的模板。请在模板中添加 `{{ANCHOR_NAME}}` 占位符后重试。"
            )
            return None

        status.write(f"已识别 {len(tasks)} 处锚点待填。")
        status.update(label="模板分析完成", state="complete")
    return tasks


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
        "这是一个面向申报类、计划类文档的一期初稿生成工具。"
        "默认流程聚焦知识库入库、锚点模板分析、分段生成与 Word 导出。"
    )
    st.markdown("##### 推荐使用顺序")
    st.markdown(
        "1. **侧栏**：确认或新建知识库，设置生成强度、联网和基础检索参数。  \n"
        "2. **知识库管理**：上传 Word 或文本层 PDF 资料并入库。  \n"
        "3. **模板配置**：上传带 `{{ANCHOR_NAME}}` 的 `.docx` 模板并分析锚点。  \n"
        "4. **生成预览**：按任务逐段生成，导出可继续人工复核的 Word 初稿。"
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
            "知识库不足时可启用联网补充；正式交付前仍需人工复核。"
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
            + "`"
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
        st.checkbox(
            "全量召回（跳过向量检索）",
            key="adv_full_recall",
            value=config.FULL_RECALL_MODE,
            help="开启后将知识库所有文档直接拼入 prompt，不再做向量相似度检索。召回更全，但消耗更多 token。",
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
            "启用内容审核",
            key="adv_enable_content_audit",
            value=False,
            help="规则审核始终执行；开启后对高风险或低相似段落追加模型审核，并在可安全替换时采用修订稿。",
        )
        st.checkbox(
            "生成后输出质量报告",
            key="adv_enable_quality_report",
            value=True,
            help="生成 docx 后执行占位符残留、章节完整性和保护区检查，并输出同名 report.json。",
        )
        st.checkbox(
            "启用视觉审核",
            key="adv_enable_visual_audit",
            value=bool(config.VISUAL_AUDIT_ENABLED),
            help="在质量报告中追加结构化视觉审核得分；关闭后仍会保留基础回填校验。",
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
    st.caption("一期默认支持 Word 和文本层 PDF 入库；其他格式不作为默认交付范围。")
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
        "上传带 `{{ANCHOR_NAME}}` 锚点的 `.docx` 模板；一期默认仅支持锚点模板。"
    )
    left, right = st.columns([2, 1])

    with left:
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
                tasks = _run_template_vision_and_analyze(save_path)
                if tasks is None:
                    st.stop()
                if not tasks:
                    st.warning("未识别到锚点，请检查模板写法。")
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
    default_word = int(st.session_state.get("adv_default_word_limit", 500))
    use_stream = bool(st.session_state.get("adv_use_stream", True))
    enable_content_audit = bool(st.session_state.get("adv_enable_content_audit", False))
    enable_quality_report = bool(st.session_state.get("adv_enable_quality_report", True))
    enable_visual_audit = bool(st.session_state.get("adv_enable_visual_audit", config.VISUAL_AUDIT_ENABLED))
    # 全量召回开关：同步到 config，让 generator 读取
    config.FULL_RECALL_MODE = bool(st.session_state.get("adv_full_recall", config.FULL_RECALL_MODE))

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
                tasks = _run_template_vision_and_analyze(template_path)
                if tasks is None:
                    st.stop()
                if tasks:
                    st.session_state[SS_TASKS] = _tasks_to_dicts(tasks)
                    st.session_state[SS_TASKS_SIG] = sig

            if not tasks:
                st.warning("没有可用的填空任务，请先在「模板配置」中分析模板。")
            else:
                generator = ContentGenerator(vs)
                auditor = ContentAuditor() if enable_content_audit else None
                results: list[str] = []
                traces = []
                total_chars = 0

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
                        content = ""

                        try:
                            gen_bundle = generator.prepare_generation_bundle(
                                task,
                                top_k=top_k,
                                enable_web=enable_web,
                                retrieval_max_distance=retrieval_max_distance,
                            )
                            if use_stream:
                                def _route_hook_stream(meta: dict) -> None:
                                    if meta.get("full_recall_mode"):
                                        route_slot.success(
                                            f"全量召回 · 模型 {meta.get('model','')} · "
                                            f"kb_hits={meta.get('kb_hits',0)}"
                                        )
                                    elif meta.get("native_web_search"):
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
                                    refs = meta.get("evidence_refs") or []
                                    if refs:
                                        st.caption("证据：" + " ; ".join(refs[:3]))

                                content_parts: list[str] = []
                                _route_hook_stream(gen_bundle.route_meta)
                                for piece in generator.stream_from_bundle(gen_bundle, route_hook=None):
                                    content_parts.append(piece)
                                content = "".join(content_parts).strip()
                            else:
                                st.caption("非流式，请稍候…")

                                def _route_hook_ns(meta: dict) -> None:
                                    if meta.get("full_recall_mode"):
                                        route_slot.success(
                                            "全量召回：已将知识库全部文档拼入 prompt"
                                            + "· 模型 "
                                            + str(meta.get("model", ""))
                                            + f" · kb_hits={meta.get('kb_hits', 0)}"
                                        )
                                    elif meta.get("native_web_search"):
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
                                    refs = meta.get("evidence_refs") or []
                                    if refs:
                                        st.caption("证据：" + " ; ".join(refs[:3]))

                                _route_hook_ns(gen_bundle.route_meta)
                                content = generator.generate_from_bundle(
                                    gen_bundle, route_hook=None
                                )
                        except Exception as e:
                            st.error(f"本段失败：{e}")
                            content = f"（生成失败：{e}）"
                            traces.append(
                                build_generation_trace(
                                    task,
                                    {"model": "", "generation_tier": "error", "evidence_refs": []},
                                    content,
                                    audit_verdict="error",
                                    audit_issues=[str(e)],
                                )
                            )
                            results.append(content)
                            prog.progress((i + 1) / n_tasks)
                            continue

                        audit_issues = rule_audit(task, content, gen_bundle.route_meta)
                        audit_verdict = "pass" if not audit_issues else "rule_issue"
                        revised = False
                        if audit_issues:
                            st.warning("规则审核：" + "；".join(audit_issues[:3]))
                        if auditor is not None and need_model_audit(task, gen_bundle.route_meta, audit_issues):
                            ar = auditor.audit(
                                task,
                                content,
                                gen_bundle.ref_texts,
                                None,
                                gen_bundle.route_meta,
                            )
                            audit_verdict = ar.verdict
                            audit_issues = audit_issues + list(ar.issues)
                            if should_apply_revision(task, ar):
                                content = ar.revised_content.strip()
                                revised = True
                                st.info("已采用审核修订稿。")
                            elif ar.issues:
                                st.warning("模型审核：" + "；".join(ar.issues[:3]))

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
                        traces.append(
                            build_generation_trace(
                                task,
                                gen_bundle.route_meta,
                                content,
                                audit_verdict=audit_verdict,
                                audit_issues=audit_issues,
                                revised=revised,
                            )
                        )
                        prog.progress((i + 1) / n_tasks)

                    status.update(label="生成结束", state="complete")

                st.metric("本次生成总字数（约）", total_chars)

                output_name = selected.replace(".docx", "_已填写.docx")
                output_path = os.path.join(config.OUTPUT_DIR, output_name)
                with st.spinner("正在写入 Word…"):
                    filler.fill_template(template_path, tasks, results, output_path)

                report_path = ""
                report = None
                post_fill_checks = {}
                visual_payload = {}
                if enable_quality_report:
                    with st.spinner("正在执行回填校验…"):
                        post_fill_checks = verify_filled_document(template_path, output_path, tasks)
                    if enable_visual_audit and config.VISUAL_AUDIT_ENABLED:
                        with st.spinner("正在执行视觉审核…"):
                            visual_payload = asdict(audit_document_visual(output_path))
                    report = build_quality_report(
                        template_name=selected,
                        output_path=output_path,
                        traces=traces,
                        post_fill_checks=post_fill_checks,
                        visual_audit=visual_payload,
                    )
                    report_path = save_quality_report(output_path, report)

                st.session_state[SS_LAST_OUT_PATH] = output_path
                st.session_state[SS_LAST_OUT_NAME] = output_name

                st.success("初稿生成完成，可下载后继续人工复核。")
                if report is not None:
                    st.caption(quality_report_summary(report))
                    if post_fill_checks.get("leftover_placeholders"):
                        st.warning(
                            "残留占位：" + "；".join(post_fill_checks["leftover_placeholders"][:3])
                        )
                    if post_fill_checks.get("protected_issues"):
                        st.warning(
                            "保护区检查：" + "；".join(post_fill_checks["protected_issues"][:3])
                        )
                    if visual_payload:
                        st.info(
                            "视觉审核："
                            + str(visual_payload.get("score", 0))
                            + "/100"
                        )
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
                if report_path and os.path.isfile(report_path):
                    with open(report_path, "rb") as f:
                        st.download_button(
                            "下载质量报告 JSON",
                            data=f.read(),
                            file_name=os.path.basename(report_path),
                            use_container_width=True,
                            key="dl_quality_report",
                        )
