import streamlit as st
import os
import config
from core.parser import DocumentParser
from core.chunker import Chunker
from core.vector_store import VectorStore
from core.template_analyzer import TemplateAnalyzer
from core.generator import ContentGenerator
from core.filler import WordFiller

st.set_page_config(page_title="智能计划书生成器", page_icon="📝", layout="wide")

# 初始化组件
@st.cache_resource
def get_vector_store():
    return VectorStore()


@st.cache_resource
def get_parser():
    return DocumentParser()


@st.cache_resource
def get_chunker():
    return Chunker()


@st.cache_resource
def get_analyzer(model=None):
    return TemplateAnalyzer(model=model)


@st.cache_resource
def get_filler():
    return WordFiller()


vs = get_vector_store()
parser = get_parser()
chunker = get_chunker()
filler = get_filler()

# 侧边栏导航
page = st.sidebar.radio("导航", ["知识库管理", "模板管理", "生成中心"])

# ============================================================
# 页面 1：知识库管理
# ============================================================
if page == "知识库管理":
    st.header("知识库管理")
    st.caption("上传历史计划书，系统会自动解析、切片并存入向量库。")

    uploaded_files = st.file_uploader(
        "上传历史计划书", type=["docx"], accept_multiple_files=True
    )

    if uploaded_files and st.button("入库", type="primary"):
        for file in uploaded_files:
            save_path = os.path.join(config.HISTORICAL_DIR, file.name)
            with open(save_path, "wb") as f:
                f.write(file.read())

            with st.spinner(f"正在解析 {file.name}..."):
                parsed_doc = parser.parse(save_path)
                chunks = chunker.chunk(parsed_doc)
                vs.add_documents(chunks)

            st.success(f"已入库：{file.name}（{len(chunks)} 个片段）")

    st.divider()
    st.subheader("已入库文件")

    sources = vs.list_sources()
    if not sources:
        st.info("暂无数据，请上传历史计划书。")
    else:
        st.write(f"共 {vs.get_collection_count()} 个片段，来自 {len(sources)} 个文件：")
        for src in sources:
            col1, col2 = st.columns([4, 1])
            col1.write(src)
            if col2.button("删除", key=f"del_{src}"):
                vs.delete_by_source(src)
                st.rerun()

# ============================================================
# 页面 2：模板管理
# ============================================================
elif page == "模板管理":
    st.header("模板管理")
    st.caption("上传计划书模板，系统会分析结构并识别待填写位置。")

    model = st.selectbox(
        "分析模型",
        ["gpt-4o", "deepseek-chat", "claude-3-5-sonnet"],
        key="template_model",
    )

    template_file = st.file_uploader("上传模板", type=["docx"])

    if template_file and st.button("分析模板", type="primary"):
        save_path = os.path.join(config.TEMPLATE_DIR, template_file.name)
        with open(save_path, "wb") as f:
            f.write(template_file.read())

        with st.spinner("正在分析模板结构..."):
            analyzer = get_analyzer(model=model)
            tasks = analyzer.analyze(save_path)

        if not tasks:
            st.warning("未检测到待填写位置，请检查模板内容。")
        else:
            st.success(f"检测到 {len(tasks)} 个待填写位置：")
            for i, task in enumerate(tasks):
                with st.expander(f"{i+1}. [{task.task_type}] {task.target_chapter}"):
                    st.write(f"**描述**: {task.description}")
                    st.write(f"**字数要求**: {task.word_limit} 字")
                    st.write(f"**定位**: {task.location_hint}")

    st.divider()
    st.subheader("已上传模板")
    templates = os.listdir(config.TEMPLATE_DIR) if os.path.exists(config.TEMPLATE_DIR) else []
    templates = [t for t in templates if t.endswith(".docx")]
    if templates:
        for t in templates:
            st.write(t)
    else:
        st.info("暂无模板，请上传。")

# ============================================================
# 页面 3：生成中心
# ============================================================
elif page == "生成中心":
    st.header("生成项目计划书")

    templates = (
        os.listdir(config.TEMPLATE_DIR) if os.path.exists(config.TEMPLATE_DIR) else []
    )
    templates = [t for t in templates if t.endswith(".docx")]

    if not templates:
        st.warning("请先在「模板管理」页面上传模板。")
        st.stop()

    selected = st.selectbox("选择模板", templates)

    col1, col2, col3 = st.columns(3)
    with col1:
        top_k = st.slider("检索参考数量", 1, 5, 3)
    with col2:
        default_word = st.number_input("默认每段字数", value=300, min_value=50, max_value=2000)
    with col3:
        model = st.selectbox("生成模型", ["gpt-4o", "deepseek-chat", "claude-3-5-sonnet"])

    if st.button("开始生成", type="primary"):
        template_path = os.path.join(config.TEMPLATE_DIR, selected)

        # 1. 分析模板
        with st.spinner("正在分析模板..."):
            analyzer = get_analyzer(model=model)
            tasks = analyzer.analyze(template_path)

        if not tasks:
            st.error("模板分析失败，未找到待填写位置。")
            st.stop()

        st.info(f"共 {len(tasks)} 个待填写任务，开始生成...")

        # 2. 逐个生成
        generator = ContentGenerator(vs, model=model)
        progress = st.progress(0)
        results = []

        for i, task in enumerate(tasks):
            # 如果没有指定字数，使用默认值
            if task.word_limit <= 0:
                task.word_limit = default_word

            with st.spinner(f"正在生成 [{task.target_chapter}]..."):
                content = generator.generate(task, top_k=top_k)
                results.append(content)

            progress.progress((i + 1) / len(tasks))

            with st.expander(f"✅ {task.target_chapter} - {task.description[:40]}"):
                st.markdown(content)

        # 3. 回填并下载
        output_name = selected.replace(".docx", "_已填写.docx")
        output_path = os.path.join(config.OUTPUT_DIR, output_name)

        with st.spinner("正在回填到模板..."):
            filler.fill_template(template_path, tasks, results, output_path)

        st.success("生成完成！")

        with open(output_path, "rb") as f:
            st.download_button(
                "下载生成的计划书",
                data=f,
                file_name=output_name,
                type="primary",
            )
