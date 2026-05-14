"""
智能计划书生成器 — Streamlit 单页：侧栏配置 + 主区标签页（知识库 / 模板 / 生成预览）
"""
from __future__ import annotations

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
from core.generator import ContentGenerator
from core.filler import WordFiller
from core.kb_registry import add_kb, load_registry, remove_kb
from core.kb_extract import path_to_parsed_document
from core.template_analyzer import TemplateAnalyzer
from core.vector_store import VectorStore

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
        "default_word_limit": 300,
        "stream": False,
    },
    "普通": {
        "top_k": 5,
        "retrieval_max_distance": 0.8,
        "use_tavily": False,
        "default_word_limit": 500,
        "stream": True,
    },
    "增强": {
        "top_k": 10,
        "retrieval_max_distance": 0.9,
        "use_tavily": True,
        "default_word_limit": 800,
        "stream": True,
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


@st.cache_resource
def get_analyzer():
    return TemplateAnalyzer()


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
) -> str:
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
                + f" · 知识库命中 {meta.get('kb_hits', 0)} 条 · 侧栏联网="
                + ("开" if meta.get("enable_web_requested") else "关")
                + f" · weak_kb={meta.get('weak_kb')} · low_sim={meta.get('low_similarity')}"
                + f" · est_sim≈{meta.get('best_similarity_est')} / 阈值 {meta.get('retrieval_web_similarity_threshold')}"
            )

    hist_exp = st.expander("已生成历史内容（较早段落）", expanded=False)
    with hist_exp:
        hist_ph = st.empty()
    live_ph = st.empty()
    full = ""
    n_update = 0
    for piece in generator.generate_stream(
        task,
        top_k=top_k,
        enable_web=enable_web,
        retrieval_max_distance=retrieval_max_distance,
        route_hook=_route_hook,
    ):
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
    return full.strip()


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
        compat_ok = bool((config.OPENAI_COMPAT_API_KEY or "").strip())
        st.caption(
            f"Key：{'可用' if compat_ok else '未配置'}"
        )
        if not compat_ok:
            st.warning("请在项目根目录 `.env` 中配置 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY`。")
        st.caption(
            "弱知识库联网时使用模型：`" + config.VISION_WEB_MODEL + "`（须为百炼支持 `enable_search` 的 qwen-plus 系）。"
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
            with st.expander("新建库", expanded=False):
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
            with st.expander("删除库", expanded=False):
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
        st.caption("模型：`" + config.SMALL_LLM_MODEL + "` / `" + config.LARGE_LLM_MODEL + "`")
        st.checkbox(
            "流式显示",
            key="adv_use_stream",
            help="开启后像打字一样实时刷新生成过程（仅影响展示方式）。",
        )
        st.checkbox(
            "联网补料（百炼内置搜索）",
            key="adv_use_tavily",
            help="在「知识库为空或检索无命中」或「最佳命中估算相似度低于阈值（默认 0.3，sim≈1−distance）」时，对该段改用 VISION_WEB_MODEL 并开启 enable_search。阈值见环境变量 RETRIEVAL_WEB_SIMILARITY_THRESHOLD。",
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

st.info("推荐顺序：侧栏确认知识库 → **知识库管理** 入库 → **模板配置** 上传并分析 → **生成预览** 一键生成。")

tab_kb, tab_tpl, tab_gen = st.tabs(["知识库管理", "模板配置", "生成预览"])

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
                with st.spinner("正在分析模板结构…"):
                    tasks = get_analyzer().analyze(save_path)
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
    default_word = int(st.session_state.get("adv_default_word_limit", 500))
    use_stream = bool(st.session_state.get("adv_use_stream", True))

    n_frag = vs.get_collection_count()
    gen_disabled = (
        not templates
        or not selected
        or not (config.OPENAI_COMPAT_API_KEY or "").strip()
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
                with st.spinner("正在分析模板…"):
                    tasks = get_analyzer().analyze(template_path)
                if tasks:
                    st.session_state[SS_TASKS] = _tasks_to_dicts(tasks)
                    st.session_state[SS_TASKS_SIG] = sig

            if not tasks:
                st.warning("没有可用的填空任务，请先在「模板配置」中分析模板。")
            else:
                generator = ContentGenerator(vs)
                results: list[str] = []
                total_chars = 0

                with st.status("正在生成…", expanded=True) as status:
                    prog = st.progress(0.0)
                    n_tasks = len(tasks)
                    for i, task in enumerate(tasks):
                        if task.word_limit <= 0:
                            task.word_limit = default_word
                        st.markdown(
                            f"**正在生成** · {task.target_chapter} · {i + 1}/{n_tasks} · "
                            f"累计约 {total_chars} 字"
                        )
                        route_slot = st.empty()
                        try:
                            if use_stream:
                                content = _stream_three_line_window(
                                    generator,
                                    task,
                                    top_k=top_k,
                                    enable_web=enable_web,
                                    retrieval_max_distance=retrieval_max_distance,
                                    route_slot=route_slot,
                                )
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

                                content = generator.generate(
                                    task,
                                    top_k=top_k,
                                    enable_web=enable_web,
                                    retrieval_max_distance=retrieval_max_distance,
                                    route_hook=_route_hook_ns,
                                )
                        except Exception as e:
                            st.error(f"本段失败：{e}")
                            content = f"（生成失败：{e}）"

                        wc = len(content)
                        total_chars += wc
                        with st.expander(f"完成 · {task.target_chapter}（约 {wc} 字）", expanded=False):
                            st.text(content)

                        results.append(content)
                        prog.progress((i + 1) / n_tasks)

                    status.update(label="生成结束", state="complete")

                st.metric("本次生成总字数（约）", total_chars)

                output_name = selected.replace(".docx", "_已填写.docx")
                output_path = os.path.join(config.OUTPUT_DIR, output_name)
                with st.spinner("正在写入 Word…"):
                    filler.fill_template(template_path, tasks, results, output_path)

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
