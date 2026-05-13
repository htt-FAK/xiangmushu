"""
智能计划书生成器 — Streamlit 前端
多知识库隔离、模板缓存、流式生成、常驻下载；主区 Tabs 单页操作
"""
from __future__ import annotations

import os
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

STREAM_BOX_HEIGHT = 420
DATAFRAME_SOURCES_HEIGHT = 320
DATAFRAME_TEMPLATES_HEIGHT = 240


def _init_session():
    if SS_ACTIVE_KB not in st.session_state:
        reg = load_registry()
        st.session_state[SS_ACTIVE_KB] = reg[0]["slug"]


def _template_signature(path: str) -> str:
    try:
        return f"{os.path.basename(path)}:{os.path.getmtime(path)}"
    except OSError:
        return os.path.basename(path)


def _tasks_to_dicts(tasks: list) -> list:
    return [asdict(t) for t in tasks]


def _dicts_to_tasks(data: list) -> list[FillTask]:
    return [FillTask(**d) for d in data]


def _glass_theme():
    st.markdown(
        """
<style>
html, body, .stApp { font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; }
.stApp {
  background: radial-gradient(900px 520px at 12% -8%, rgba(99, 102, 241, 0.18), transparent 55%),
              radial-gradient(700px 420px at 92% 18%, rgba(56, 189, 248, 0.14), transparent 50%),
              linear-gradient(168deg, #e9eef8 0%, #dfe7f3 42%, #eef2fb 100%);
  background-attachment: fixed;
}
[data-testid="stAppViewContainer"] > .main {
  background: transparent;
}
.block-container {
  padding-top: 1.25rem;
  padding-bottom: 2rem;
  max-width: 920px;
  background: rgba(255, 255, 255, 0.38);
  backdrop-filter: blur(22px) saturate(140%);
  -webkit-backdrop-filter: blur(22px) saturate(140%);
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.55);
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.07);
}
section[data-testid="stSidebar"] {
  background: rgba(255, 255, 255, 0.32) !important;
  backdrop-filter: blur(18px) saturate(130%);
  -webkit-backdrop-filter: blur(18px) saturate(130%);
  border-right: 1px solid rgba(255, 255, 255, 0.45) !important;
}
section[data-testid="stSidebar"] .block-container {
  background: transparent;
  border: none;
  box-shadow: none;
  border-radius: 0;
  padding: 1rem 1.1rem;
}
header[data-testid="stHeader"] { background: rgba(255,255,255,0.2); backdrop-filter: blur(12px); }
[data-testid="stDecoration"] { display: none; }
[data-testid="stToolbar"] { opacity: 0.55; }
[data-baseweb="tab-list"] {
  gap: 0.25rem;
  background: rgba(255,255,255,0.35);
  border-radius: 14px;
  padding: 6px 8px;
  border: 1px solid rgba(255,255,255,0.5);
  backdrop-filter: blur(12px);
}
[data-baseweb="tab"] { border-radius: 10px !important; font-weight: 500; letter-spacing: 0.02em; }
[data-baseweb="tab-highlight"] { border-radius: 10px !important; }
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(255,255,255,0.28) !important;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(255,255,255,0.45) !important;
  border-radius: 16px !important;
}
.stButton button {
  border-radius: 12px !important;
  font-weight: 500 !important;
  border: 1px solid rgba(15, 23, 42, 0.08) !important;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
}
h1, h2, h3 { font-weight: 600 !important; letter-spacing: -0.02em; color: #0f172a !important; }
hr { border: none; border-top: 1px solid rgba(15,23,42,0.08); margin: 1.1rem 0; }
[data-testid="stMetricValue"] { font-weight: 600 !important; }
</style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="计划书", page_icon="◆", layout="wide")
_init_session()
_glass_theme()


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


def _sidebar_env():
    with st.sidebar.expander("连接与模型", expanded=False):
        eff = (config.OPENAI_COMPAT_API_KEY or "").strip()
        st.caption(
            f"Key：{'OK' if eff else '未配置'} · Tavily：{'OK' if (config.TAVILY_API_KEY or '').strip() else '—'}"
        )
        st.caption(
            f"分析 `{config.SMALL_LLM_MODEL}` · 生成 `{config.LARGE_LLM_MODEL}` · 联网弱 `{config.VISION_WEB_MODEL}`"
        )


def _sidebar_kb_line():
    slug = st.session_state.get(SS_ACTIVE_KB, "kb1")
    reg = {e["slug"]: e["label"] for e in load_registry()}
    label = reg.get(slug, slug)
    st.sidebar.caption(f"当前 · {label}")


def _invalidate_vector_cache():
    try:
        get_vector_store.clear()
    except Exception:
        try:
            st.cache_resource.clear()
        except Exception:
            pass


_sidebar_env()
_sidebar_kb_line()
st.sidebar.divider()

active_slug = st.session_state[SS_ACTIVE_KB]
vs = get_vector_store(active_slug)
chunker = get_chunker()
filler = get_filler()

tab_kb, tab_tpl, tab_gen = st.tabs(["知识库", "模板", "生成"])

with tab_kb:
    st.markdown("##### 知识库")

    reg = load_registry()
    labels = [f"{e['label']} (`{e['slug']}`)" for e in reg]
    slugs = [e["slug"] for e in reg]
    idx = slugs.index(active_slug) if active_slug in slugs else 0
    choice = st.selectbox(
        "切换库", range(len(reg)), format_func=lambda i: labels[i], index=idx
    )
    new_slug = slugs[choice]
    if new_slug != st.session_state[SS_ACTIVE_KB]:
        st.session_state[SS_ACTIVE_KB] = new_slug
        st.rerun()

    with st.expander("新建库", expanded=False):
        nb_label = st.text_input("名称", placeholder="如：项目甲资料", key="kb_nb_label")
        nb_slug = st.text_input("标识（可空）", placeholder="小写字母数字下划线", key="kb_nb_slug")
        if st.button("创建", key="kb_create_btn"):
            if not (nb_label or "").strip():
                st.error("请填写名称。")
            else:
                slug_in = (nb_slug or "").strip() or None
                try:
                    created = add_kb(nb_label.strip(), slug_in)
                    st.session_state[SS_ACTIVE_KB] = created
                    _invalidate_vector_cache()
                    st.success(f"已创建 `{created}`")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with st.expander("删除当前库（危险）", expanded=False):
        st.caption("删除后向量不可恢复。")
        confirm = st.text_input("输入 DELETE", key="kb_del_confirm")
        if st.button("删除此库", type="secondary", key="kb_rm_btn"):
            if confirm.strip().upper() != "DELETE":
                st.error("需输入 DELETE。")
            else:
                slug = st.session_state[SS_ACTIVE_KB]
                try:
                    remove_kb(slug)
                except ValueError as e:
                    st.error(str(e))
                    st.stop()
                VectorStore(kb_slug=slug).delete_entire_collection()
                _invalidate_vector_cache()
                st.session_state.pop(SS_TASKS, None)
                st.session_state.pop(SS_TASKS_SIG, None)
                reg2 = load_registry()
                st.session_state[SS_ACTIVE_KB] = reg2[0]["slug"] if reg2 else "kb1"
                st.success("已删除。")
                st.rerun()

    uploaded_files = st.file_uploader(
        "上传资料",
        type=["docx", "pdf", "pptx", "png", "jpg", "jpeg", "webp", "gif"],
        accept_multiple_files=True,
        help="docx / pdf / pptx / 图片；旧 .ppt 请先转 pptx",
    )

    if uploaded_files and st.button("入库", type="primary"):
        bar = st.progress(0.0)
        total = len(uploaded_files)
        for i, file in enumerate(uploaded_files):
            save_path = os.path.join(config.HISTORICAL_DIR, file.name)
            with open(save_path, "wb") as f:
                f.write(file.read())
            with st.spinner(f"正在解析 {file.name}..."):
                parsed_doc = path_to_parsed_document(save_path, original_name=file.name)
                chunks = chunker.chunk(parsed_doc)
                vs.add_documents(chunks)
            bar.progress((i + 1) / total)
        st.success(f"已入库 {total} 个。")
        st.rerun()

    sources = vs.list_sources()
    c3, c4 = st.columns(2)
    c3.metric("片段", vs.get_collection_count())
    c4.metric("来源", len(sources))

    if not sources:
        st.caption("库为空，请上传文件后点「入库」。")
    else:
        st.dataframe(
            [{"来源": s} for s in sources],
            use_container_width=True,
            hide_index=True,
            height=DATAFRAME_SOURCES_HEIGHT,
        )
        del_pick = st.selectbox("移除来源", sources, key="kb_del_source_pick")
        if st.button("移除", key="kb_del_source_btn"):
            vs.delete_by_source(del_pick)
            st.rerun()

with tab_tpl:
    st.markdown("##### 模板")

    with st.expander("锚点写法（可选）", expanded=False):
        st.markdown(
            "待填处插入 `{{ANCHOR_NAME}}`（双花括号 + 字母数字下划线）。"
            "有锚点则自动扫描；无锚点则模型推断。"
        )

    template_file = st.file_uploader("Word 模板", type=["docx"])

    col_a, col_b = st.columns(2)
    with col_a:
        analyze_clicked = st.button("分析", type="primary")
    with col_b:
        if st.button("清除缓存"):
            st.session_state.pop(SS_TASKS, None)
            st.session_state.pop(SS_TASKS_SIG, None)
            st.success("已清除。")

    if template_file and analyze_clicked:
        save_path = os.path.join(config.TEMPLATE_DIR, template_file.name)
        with open(save_path, "wb") as f:
            f.write(template_file.read())

        with st.spinner("正在分析模板结构..."):
            analyzer = get_analyzer()
            tasks = analyzer.analyze(save_path)

        if not tasks:
            st.warning("未识别到待填位置。")
        else:
            st.session_state[SS_TASKS] = _tasks_to_dicts(tasks)
            st.session_state[SS_TASKS_SIG] = _template_signature(save_path)
            mode = "锚点" if tasks[0].location_hint.get("anchor") else "推断"
            st.success(f"{len(tasks)} 处待填 · {mode} · 已缓存")

            rows = [
                {
                    "序号": i + 1,
                    "章节": t.target_chapter,
                    "类型": t.task_type,
                    "字数": t.word_limit,
                    "定位": str(t.location_hint.get("anchor") or t.location_hint)[:72],
                }
                for i, t in enumerate(tasks)
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True, height=min(360, 80 + 28 * len(rows)))

    st.caption("已上传")
    templates = (
        os.listdir(config.TEMPLATE_DIR) if os.path.exists(config.TEMPLATE_DIR) else []
    )
    templates = [t for t in templates if t.endswith(".docx")]
    if templates:
        rows2 = []
        for t in templates:
            p = os.path.join(config.TEMPLATE_DIR, t)
            try:
                mtime = os.path.getmtime(p)
            except OSError:
                mtime = 0
            rows2.append(
                {
                    "文件名": t,
                    "修改时间": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                }
            )
        st.dataframe(
            rows2,
            use_container_width=True,
            hide_index=True,
            height=DATAFRAME_TEMPLATES_HEIGHT,
        )
    else:
        st.caption("暂无模板。")

with tab_gen:
    st.markdown("##### 生成")

    templates = (
        os.listdir(config.TEMPLATE_DIR) if os.path.exists(config.TEMPLATE_DIR) else []
    )
    templates = [t for t in templates if t.endswith(".docx")]

    if not templates:
        st.warning("请先在「模板」上传。")
        st.stop()

    reg = load_registry()
    kb_label = next(
        (e["label"] for e in reg if e["slug"] == active_slug), active_slug
    )
    st.caption(f"检索 · {kb_label}")

    selected = st.selectbox("模板", templates)

    default_word = st.number_input("每段字数", value=300, min_value=50, max_value=2000)

    use_stream = st.checkbox("流式显示", value=True)

    with st.expander("检索与联网", expanded=False):
        top_k = st.slider("检索条数", 1, 8, 4)
        retrieval_max_distance = st.slider(
            "检索距离上限",
            min_value=0.3,
            max_value=2.5,
            value=float(config.RETRIEVAL_MAX_DISTANCE),
            step=0.05,
            help="过大则丢弃；全丢视为检索弱，可配合联网。",
        )
        enable_web = st.checkbox("联网补料（需 Tavily）", value=False)
        force_reanalyze = st.button("清除模板分析缓存", key="gen_force_reanalyze")

    run_generate = st.button("生成", type="primary", use_container_width=True)

    if force_reanalyze:
        st.session_state.pop(SS_TASKS, None)
        st.session_state.pop(SS_TASKS_SIG, None)
        st.caption("已清缓存，将重新分析。")

    last_p = st.session_state.get(SS_LAST_OUT_PATH)
    last_n = st.session_state.get(SS_LAST_OUT_NAME)
    if last_p and last_n and os.path.isfile(last_p):
        with st.expander("上次文件", expanded=False):
            st.caption(last_n)
            with open(last_p, "rb") as f:
                st.download_button(
                    "再次下载", data=f.read(), file_name=last_n, key="dl_last"
                )
            if st.button("清除记录", key="gen_clear_last_dl"):
                st.session_state.pop(SS_LAST_OUT_PATH, None)
                st.session_state.pop(SS_LAST_OUT_NAME, None)
                st.rerun()

    if not run_generate:
        st.stop()

    template_path = os.path.join(config.TEMPLATE_DIR, selected)
    sig = _template_signature(template_path)

    tasks = None
    if (
        not force_reanalyze
        and st.session_state.get(SS_TASKS)
        and st.session_state.get(SS_TASKS_SIG) == sig
    ):
        tasks = _dicts_to_tasks(st.session_state[SS_TASKS])
        st.success("已用缓存的分析结果。")
    else:
        with st.spinner("正在分析模板..."):
            analyzer = get_analyzer()
            tasks = analyzer.analyze(template_path)
        if tasks:
            st.session_state[SS_TASKS] = _tasks_to_dicts(tasks)
            st.session_state[SS_TASKS_SIG] = sig

    if not tasks:
        st.error("未找到待填位置。")
        st.stop()

    generator = ContentGenerator(vs)
    results: list[str] = []

    st.caption("进度")
    progress = st.progress(0.0)
    task_title_ph = st.empty()
    stream_area = st.container(height=STREAM_BOX_HEIGHT)
    with stream_area:
        stream_ph = st.empty()

    for i, task in enumerate(tasks):
        if task.word_limit <= 0:
            task.word_limit = default_word

        task_title_ph.markdown(
            f"**任务 {i + 1}/{len(tasks)}** · {task.target_chapter}"
        )

        try:
            if use_stream:
                acc: list[str] = []

                def _stream_gen():
                    for piece in generator.generate_stream(
                        task,
                        top_k=top_k,
                        enable_web=enable_web,
                        retrieval_max_distance=retrieval_max_distance,
                    ):
                        acc.append(piece)
                        yield piece

                stream_ph.write_stream(_stream_gen())
                content = "".join(acc).strip()
            else:
                stream_ph.markdown("*生成中…*")
                with st.spinner("生成中..."):
                    content = generator.generate(
                        task,
                        top_k=top_k,
                        enable_web=enable_web,
                        retrieval_max_distance=retrieval_max_distance,
                    )
                stream_ph.markdown(content)
        except Exception as e:
            st.error(f"本任务生成失败，已跳过：{e}")
            content = f"（生成失败：{e}）"
            stream_ph.markdown(content)

        results.append(content)
        progress.progress((i + 1) / len(tasks))

    preview_h = min(400, 120 + 50 * len(results))
    with st.expander("全文预览", expanded=False):
        st.text_area(
            "合并预览",
            value="\n\n---\n\n".join(results),
            height=preview_h,
            key="gen_full_preview",
        )

    output_name = selected.replace(".docx", "_已填写.docx")
    output_path = os.path.join(config.OUTPUT_DIR, output_name)

    with st.spinner("正在回填到 Word..."):
        filler.fill_template(template_path, tasks, results, output_path)

    st.session_state[SS_LAST_OUT_PATH] = output_path
    st.session_state[SS_LAST_OUT_NAME] = output_name

    st.success("完成")
    with open(output_path, "rb") as f:
        st.download_button(
            "下载 Word",
            data=f.read(),
            file_name=output_name,
            type="primary",
        )
