import streamlit as st
import dateparser
from dateparser.search import search_dates
import pandas as pd
import os
from datetime import datetime, timedelta

# [NEW] AI 支持
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ================= 配置区 =================
MEMORY_FILE = 'memory.csv'

# ================= 核心功能函数 =================

def init_memory():
    """初始化存储文件"""
    need_reset = False
    if os.path.exists(MEMORY_FILE):
        df = pd.read_csv(MEMORY_FILE)
        if "状态" not in df.columns:
            need_reset = True
    else:
        need_reset = True

    if need_reset:
        df = pd.DataFrame(columns=["记录时间", "分类", "内容", "目标时间", "状态", "关联花销"])
        df.to_csv(MEMORY_FILE, index=False)

def load_memory():
    """读取记忆"""
    if os.path.exists(MEMORY_FILE):
        return pd.read_csv(MEMORY_FILE)
    return pd.DataFrame()

def save_record(category, content, target_time=None, status="Pending", cost=0.0):
    """保存记录到 CSV"""
    new_record = {
        "记录时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "分类": category,
        "内容": content,
        "目标时间": target_time.strftime("%Y-%m-%d %H:%M:%S") if target_time else "",
        "状态": status,
        "关联花销": cost
    }
    df = pd.DataFrame([new_record])
    df.to_csv(MEMORY_FILE, mode='a', header=not os.path.exists(MEMORY_FILE), index=False)
    return new_record

def update_status(index, new_status, expense_list=None):
    """更新某条记录的状态"""
    if expense_list is None:
        expense_list = []
        
    df = pd.read_csv(MEMORY_FILE)
    
    # 1. 更新状态
    total_cost = sum(item['cost'] for item in expense_list)
    df.at[index, "状态"] = new_status
    df.at[index, "关联花销"] = total_cost
    
    # 2. 待办完成后，自动转为 "日程"
    if df.at[index, "分类"] == "待办" and new_status == "Done":
            df.at[index, "分类"] = "日程"
            
    df.to_csv(MEMORY_FILE, index=False)
    
    # 3. 记录多笔花销
    original_content = df.at[index, "内容"]
    for item in expense_list:
        cost = item['cost']
        cat = item['category']
        if cost > 0:
            save_record(cat, f"{original_content} (来自待办)", status="Done", cost=cost)

def process_input(text):
    """理解用户输入"""
    dates = search_dates(text, languages=['zh'], settings={'PREFER_DATES_FROM': 'future'})
    parsed_date = None
    if dates:
        date_string, parsed_date = dates[0]
    
    now = datetime.now()
    category = "想法"
    # 关键词定义
    finance_keywords = ["买", "花", "元", "块", "钱", "支付", "花费", "预算"]
    schedule_keywords = ["开会", "去", "见面", "预约", "参加", "高铁", "飞机", "请", "约"]
    todo_keywords = ["记得", "需要", "办", "做", "带"]
    idea_keywords = ["我想", "主意", "灵感", "觉得", "可能", "不错", "建议"]

    is_future = False
    if parsed_date and parsed_date > now:
        is_future = True

    # === 分类逻辑 ===
    if is_future:
        category = "待办"
    else:
        if any(k in text for k in finance_keywords):
            category = "财务" 
        elif parsed_date or any(k in text for k in schedule_keywords):
            category = "日程"
        elif any(k in text for k in idea_keywords):
            category = "创意"
        elif any(k in text for k in todo_keywords):
            category = "待办"
        else:
            category = "创意"

    status = "Done" if category in ["财务", "日程"] else "Pending"
    
    save_record(category, text, parsed_date, status=status)
    return category, parsed_date

def get_report_data(period="month"):
    """获取用于生成报告的数据"""
    df = load_memory()
    if df.empty:
        return None
        
    df["记录时间"] = pd.to_datetime(df["记录时间"])
    now = datetime.now()
    
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
         start_date = now - timedelta(days=30)
    elif period == "year":
         start_date = now - timedelta(days=365)
    else:
        start_date = now - timedelta(days=30)

    # 筛选时间范围内的记录
    mask = df["记录时间"] > start_date
    filtered_df = df[mask]
    
    if filtered_df.empty:
        return "该时间段无记录。"

    finance = filtered_df[ (filtered_df["分类"]=="财务") | (filtered_df["关联花销"] > 0) ]
    total_cost = pd.to_numeric(finance["关联花销"]).sum() if not finance.empty else 0
    
    schedules = filtered_df[filtered_df["分类"] == "日程"]["内容"].tolist()
    ideas = filtered_df[filtered_df["分类"] == "创意"]["内容"].tolist()
    
    summary = f"""
    【时间范围】: 近 {period}
    【财务总支】: {total_cost} 元
    【主要日程/成就】: {', '.join(schedules[:10])}...
    【冒出的想法】: {', '.join(ideas[:5])}...
    """
    return summary

def call_ai_report(api_key, base_url, model_name, data_context, period):
    """调用 AI 生成报告"""
    if not OpenAI:
        return "请先安装 openai 库 (pip install openai)"
        
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    prompt = f"""
    你是一个贴心的生活助手。请根据以下用户的近期生活数据，写一份生动、温暖且有洞察力的【{period}生活周报/月报】。
    
    要求：
    1. 😃 语气轻松幽默，像老朋友一样。
    2. 💰 分析财务状况。
    3. 📅 总结成就和忙碌的时刻。
    4. 💡 点评用户的创意想法，给予鼓励。
    
    数据如下：
    {data_context}
    """
    
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful life assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI 调用失败: {str(e)}"

# ================= 页面 UI =================

st.set_page_config(page_title="时间胶囊", page_icon="💊", layout="wide")

st.markdown("""
<style>
    .stApp { font-family: "PingFang SC", "Microsoft YaHei", sans-serif; }
    h1 { color: #4F8BF9; font-weight: bold; text-align: center; }
    section[data-testid="stSidebar"] { background-color: #f7f9fc; }
    .stChatMessage { border-radius: 10px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

def render_msg(role, content):
    """渲染微信风格的消息"""
    if role == "user":
        st.markdown(f"""
        <div style="display: flex; justify-content: flex-end; align-items: flex-start; margin-bottom: 20px;">
            <div style="background-color: #95ec69; color: black; padding: 10px 15px; border-radius: 8px; margin-right: 10px; max-width: 70%; text-align: left; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                {content}
            </div>
            <div style="font-size: 28px; line-height: 1;">🧑‍💻</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="display: flex; justify-content: flex-start; align-items: flex-start; margin-bottom: 20px;">
            <div style="font-size: 28px; margin-right: 10px; line-height: 1;">💊</div>
            <div style="background-color: #ffffff; border: 1px solid #f0f0f0; color: black; padding: 10px 15px; border-radius: 8px; max-width: 70%; text-align: left; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                {content}
            </div>
        </div>
        """, unsafe_allow_html=True)

# 初始化
init_memory()
if "messages" not in st.session_state:
    st.session_state.messages = []
    
    # 尝试加载最近 3 天的历史记录
    try:
        df_history = load_memory()
        if not df_history.empty:
            df_history["记录时间"] = pd.to_datetime(df_history["记录时间"])
            three_days_ago = datetime.now() - timedelta(days=3)
            # 筛选最近3天的数据
            recent_history = df_history[df_history["记录时间"] > three_days_ago].sort_values("记录时间")
            
            for _, row in recent_history.iterrows():
                # 恢复用户输入
                st.session_state.messages.append({"role": "user", "content": row["内容"]})
                
                # 恢复助手回复 (模拟)
                time_str = ""
                if pd.notna(row['目标时间']) and row['目标时间']:
                     time_str = f" (时间: {row['目标时间']})"
                
                response = f"✅ 已记录到 **[{row['分类']}]**{time_str}"
                st.session_state.messages.append({"role": "assistant", "content": response})
                
    except Exception as e:
        print(f"History load error: {e}")

    if not st.session_state.messages:
        st.session_state.messages.append({"role": "assistant", "content": "你好！我是你的时间胶囊。把你的想法、安排和记忆交给我吧。💊"})

# === 侧边栏：分类管理 & 设置 ===
with st.sidebar:
    st.header("🗂️ 分类管理")
    df = load_memory()
    
    if not df.empty:
        # --- 1. 待办 (Pending) ---
        todos = df[ (df["状态"] == "Pending") & (df["分类"] == "待办") ]
        with st.expander(f"📝 待办 ({len(todos)})", expanded=True):
            if not todos.empty:
                for index, row in todos.iterrows():
                    with st.expander(f"{row['内容'][:10]}..."):
                        st.write(f"**{row['内容']}**")
                        st.caption(f"📅 目标: {row['目标时间']}")
                        
                        count_key = f"expense_count_{index}"
                        if count_key not in st.session_state:
                            st.session_state[count_key] = 1
                            
                        expenses_data = [] 
                        
                        for i in range(st.session_state[count_key]):
                            col1, col2 = st.columns([1, 1.5]) 
                            with col1:
                                c = st.number_input(f"金额{i+1}", min_value=0.0, step=10.0, key=f"cost_{index}_{i}")
                            with col2:
                                t = st.selectbox(f"类型{i+1}", ["餐饮", "交通", "购物", "娱乐", "居家", "其它"], key=f"type_{index}_{i}")
                            expenses_data.append({"cost": c, "category": t})

                        b_col1, b_col2 = st.columns([1, 1])
                        with b_col1:
                            if st.button("➕ 加一项", key=f"add_btn_{index}"):
                                st.session_state[count_key] += 1
                                st.rerun()
                        with b_col2:
                            if st.button("✅ 完成归档", key=f"done_btn_{index}"):
                                valid_expenses = [e for e in expenses_data if e['cost'] > 0]
                                update_status(index, "Done", expense_list=valid_expenses)
                                del st.session_state[count_key]
                                st.rerun()
            else:
                st.caption("暂无待办")

        # --- 2. 创意 (Pending) ---
        ideas = df[ (df["状态"] == "Pending") & (df["分类"] == "创意") ]
        with st.expander(f"💡 创意 ({len(ideas)})", expanded=True):
            if not ideas.empty:
                 for index, row in ideas.iterrows():
                    st.write(f"**{row['内容']}**")
                    if st.button("✨ 落地", key=f"finish_idea_{index}"):
                        update_status(index, "Done")
                        st.rerun()
            else:
                st.caption("暂无创意")

        # --- 3. 近期日程 (History) ---
        schedules = df[ df["分类"] == "日程" ].sort_values("记录时间", ascending=False).head(5)
        with st.expander("📅 近期日程", expanded=False):
            if not schedules.empty:
                for _, row in schedules.iterrows():
                    date_str = str(row['目标时间']) if pd.notna(row['目标时间']) and row['目标时间'] != "" else str(row['记录时间'])
                    st.text(f"• {date_str[:10]}: {row['内容']}")
            else:
                st.caption("暂无日程")

        # --- 4. 近期财务 (History) ---
        finances = df[ (df["分类"] == "财务") | (df["关联花销"] > 0) ].sort_values("记录时间", ascending=False).head(5)
        with st.expander("💰 近期财务", expanded=False):
            if not finances.empty:
                for _, row in finances.iterrows():
                    cost = row['关联花销']
                    st.text(f"• -{cost}元: {row['内容']}")
            else:
                st.caption("暂无消费")
    
    st.divider()
    with st.expander("⚙️ AI 设置"):
        st.caption("如果要生成AI报告，请配置：")
        api_key = st.text_input("API Key", value="sk-slmttbyivskikjlkqccrozdlywchgksvprulgajqjsaaiknn", type="password", help="OpenAI / DeepSeek / SiliconFlow Key")
        base_url = st.text_input("Base URL", value="https://api.siliconflow.cn/v1", help="例如 https://api.siliconflow.cn/v1")
        model_name = st.text_input("Model Name", value="deepseek-ai/DeepSeek-V3", help="LLM 模型名, 如 deepseek-ai/DeepSeek-V3")
        asr_model_name = st.text_input("ASR Model Name", value="FunAudioLLM/SenseVoiceSmall", help="语音转文字模型, 如 FunAudioLLM/SenseVoiceSmall")

    st.divider()
    # [NEW] 数据维护：去重
    if st.button("🧹 清理重复记录"):
        df_clean = load_memory()
        if not df_clean.empty:
            original_count = len(df_clean)
            
            # 逻辑：即使内容相同，如果是正常录入，时间点应该不同。
            # 机器循环导致的重复通常是短时间内（比如1分钟内）产生了多条相同内容。
            
            # 1. 转换时间类型
            df_clean["记录时间_dt"] = pd.to_datetime(df_clean["记录时间"], errors='coerce')
            
            # 2. 排序
            df_clean = df_clean.sort_values("记录时间_dt")
            
            # 3. 计算与上一条记录的时间差 (秒)
            # grouped by content etc to only compare similar items? 
            # 简单策略：如果 内容+分类+目标时间 相同，且时间间隔 < 60秒，视为重复
            
            df_clean["prev_content"] = df_clean["内容"].shift(1)
            df_clean["prev_category"] = df_clean["分类"].shift(1)
            df_clean["prev_time"] = df_clean["记录时间_dt"].shift(1)
            
            def is_duplicate(row):
                if pd.isna(row["prev_time"]):
                    return False
                time_diff = (row["记录时间_dt"] - row["prev_time"]).total_seconds()
                if (row["内容"] == row["prev_content"] and 
                    row["分类"] == row["prev_category"] and 
                    time_diff < 60): # 60秒内的重复内容
                    return True
                return False

            df_clean["is_dup"] = df_clean.apply(is_duplicate, axis=1)
            
            # 筛选非重复
            df_dedup = df_clean[~df_clean["is_dup"]].copy()
            new_count = len(df_dedup)
            
            # 保存 (去掉临时列)
            final_columns = ["记录时间", "分类", "内容", "目标时间", "状态", "关联花销"]
            df_dedup = df_dedup[final_columns]
            df_dedup.to_csv(MEMORY_FILE, index=False)
            
            removed_count = original_count - new_count
            if removed_count > 0:
                st.success(f"成功清理了 {removed_count} 条重复记录！")
                st.rerun()
            else:
                st.info("没有发现短时间内的重复记录。")

# === 主界面 ===

st.title("💊 时间胶囊 (Time Capsule)")

tab1, tab2 = st.tabs(["💬 对话", "📊 报表"])

# --- 标签页 1: 聊天 ---
with tab1:
    # 渲染历史消息
    for message in st.session_state.messages:
        render_msg(message["role"], message["content"])

    # === WeChat-Style 输入栏 ===
    # 初始化输入模式
    if "input_mode" not in st.session_state:
        st.session_state.input_mode = "text"  # "text" or "voice" or "file"
    
    # 创建三列布局: [模式切换] [输入区] [文件上传]
    col_left, col_center, col_right = st.columns([0.1, 0.8, 0.1])
    
    with col_left:
        # 左侧: 键盘/语音切换按钮
        if st.session_state.input_mode == "text":
            if st.button("🎤", key="switch_to_voice", help="切换到语音输入"):
                st.session_state.input_mode = "voice"
                st.rerun()
        else:
            if st.button("⌨️", key="switch_to_text", help="切换到文字输入"):
                st.session_state.input_mode = "text"
                st.rerun()
    
    with col_right:
        # 右侧: 文件上传按钮
        if st.button("➕", key="open_file_upload", help="上传文件到第二大脑"):
            st.session_state.input_mode = "file"
            st.rerun()
    
    # 中间输入区: 根据模式显示不同组件
    if st.session_state.input_mode == "text":
        # 文字输入模式
        prompt = st.chat_input("输入你的想法...")
        if prompt:
            # 用户输入 (渲染)
            render_msg("user", prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})

            category, target_time = process_input(prompt)
            time_str = f" (时间: {target_time.strftime('%Y-%m-%d %H:%M')})" if target_time else ""
            response = f"✅ 已记录到 **[{category}]**{time_str}"
            
            # 机器回复 (渲染)
            render_msg("assistant", response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    elif st.session_state.input_mode == "voice":
        # 语音输入模式
        audio_value = st.audio_input("🎤 点击录音...")

        if audio_value:
            # Prevent infinite reprocessing
            import hashlib
            audio_bytes = audio_value.getvalue()
            file_hash = hashlib.md5(audio_bytes).hexdigest()
            
            if "processed_audio_hashes" not in st.session_state:
                st.session_state.processed_audio_hashes = set()
                
            if file_hash not in st.session_state.processed_audio_hashes:
                if not api_key:
                     st.warning("⚠️ 请先在侧边栏配置 API Key。")
                else:
                     with st.spinner("🎧 正在听写..."):
                        try:
                            client = OpenAI(api_key=api_key, base_url=base_url)
                            transcription = client.audio.transcriptions.create(
                                model=asr_model_name, 
                                file=audio_value
                            )
                            transcript_text = transcription.text
                            
                            if transcript_text:
                                render_msg("user", transcript_text)
                                st.session_state.messages.append({"role": "user", "content": transcript_text})

                                category, target_time = process_input(transcript_text)
                                time_str = f" (时间: {target_time.strftime('%Y-%m-%d %H:%M')})" if target_time else ""
                                response = f"✅ 已记录到 **[{category}]**{time_str}"
                                
                                render_msg("assistant", response)
                                st.session_state.messages.append({"role": "assistant", "content": response})
                                st.session_state.processed_audio_hashes.add(file_hash)
                                st.rerun() 
                        except Exception as e:
                            st.error(f"语音识别失败: {e}")
    
    elif st.session_state.input_mode == "file":
        # 文件上传模式
        uploaded_file = st.file_uploader(
            "📎 上传文件到你的第二大脑", 
            type=["jpg", "jpeg", "png", "pdf", "txt", "md"],
            help="支持图片、PDF、文本文件"
        )
        
        if uploaded_file:
            with st.spinner("📖 正在读取文件内容..."):
                try:
                    file_content = ""
                    file_type = uploaded_file.type
                    
                    # 处理不同文件类型
                    if file_type.startswith("image/"):
                        # 图片 OCR (使用 API)
                        if not api_key:
                            st.warning("⚠️ 图片识别需要配置 API Key。")
                        else:
                            # 使用 OpenAI Vision API 或类似接口
                            # 注意: SiliconFlow 可能支持 vision 模型
                            st.info("💡 图片 OCR 功能开发中，暂时将图片路径记录到记忆。")
                            file_content = f"[图片上传] {uploaded_file.name}"
                    
                    elif file_type == "application/pdf":
                        # PDF 文本提取
                        try:
                            import PyPDF2
                            pdf_reader = PyPDF2.PdfReader(uploaded_file)
                            for page in pdf_reader.pages:
                                file_content += page.extract_text()
                        except ImportError:
                            st.warning("PDF 解析需要安装 PyPDF2 库")
                            file_content = f"[PDF上传] {uploaded_file.name}"
                    
                    elif file_type.startswith("text/"):
                        # 文本文件
                        file_content = uploaded_file.read().decode("utf-8")
                    
                    # 存入记忆
                    if file_content:
                        save_record("创意", f"📄 文件内容: {file_content[:500]}...", status="Done")
                        render_msg("assistant", f"✅ 已将文件内容存入你的第二大脑！\n摘要: {file_content[:100]}...")
                        st.session_state.input_mode = "text"  # 恢复文字模式
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"文件处理失败: {e}")

# --- 标签页 2: 报表 ---
with tab2:
    if not df.empty:
        # 1. 全局搜索
        st.subheader("🔍 记忆搜索")
        search_term = st.text_input("搜索关键词 (例如: '超市', '会议')", placeholder="输入关键词...")
        if search_term:
            search_result = df[df["内容"].str.contains(search_term, case=False, na=False)]
            if not search_result.empty:
                st.dataframe(search_result, use_container_width=True)
            else:
                st.info("没找到相关记录。")
        st.divider()

        # 2. 财务报表
        st.subheader("💰 财务报表")
        finance_df = df[ (df["分类"]=="财务") | (df["关联花销"] > 0) ].copy()
        
        if not finance_df.empty:
            finance_df["关联花销"] = pd.to_numeric(finance_df["关联花销"])
            total_cost = finance_df["关联花销"].sum()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="总支出", value=f"¥ {total_cost:,.2f}")
                # [NEW] 饼图分析
                st.write("###### 消费占比")
                if "category" in finance_df.columns:
                     # 如果有详细分类（目前是 save_record 存的 text，需要提取）
                     # 简单起见，目前因为 expenses 存在 Memory 里通常是"内容 (来自待办)", 分类是"财务"。
                     # 待办的多笔花销存的是: 分类=cat, 内容=...
                     st.bar_chart(finance_df["分类"].value_counts())
                else:
                     # 按'分类'列聚合 (财务, 餐饮, 交通等)
                     # 注意：save_record 时，如果来自待办，分类是具体的（餐饮/交通）。如果是直接记账，分类是“财务”。
                     # 这是一个混合数据。我们按“分类”画饼图。
                     chart_data = finance_df.groupby("分类")["关联花销"].sum().reset_index()
                     import altair as alt
                     base = alt.Chart(chart_data).encode(theta=alt.Theta("关联花销", stack=True))
                     pie = base.mark_arc(outerRadius=120).encode(
                        color=alt.Color("分类"),
                        order=alt.Order("关联花销", sort="descending"),
                        tooltip=["分类", "关联花销"]
                     )
                     text = base.mark_text(radius=140).encode(
                        text=alt.Text("关联花销", format=".1f"),
                        order=alt.Order("关联花销", sort="descending"),
                        color=alt.value("black") 
                     )
                     st.altair_chart(pie + text, use_container_width=True)

            with col2:
                st.bar_chart(finance_df, x="记录时间", y="关联花销")
                
            with st.expander("查看详细账单"):
                st.dataframe(finance_df[["记录时间", "分类", "内容", "关联花销"]].sort_values("记录时间", ascending=False))
                # [NEW] 下载数据
                csv = finance_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 下载账单 CSV",
                    data=csv,
                    file_name='finance_report.csv',
                    mime='text/csv',
                )
        else:
            st.caption("暂无财务记录")
            
        st.divider()
        
        st.subheader("📅 历史日程 (已完成/过去)")
        schedule_df = df[ df["分类"] == "日程" ].copy()
        
        if not schedule_df.empty:
            st.dataframe(
                schedule_df[["目标时间", "内容", "记录时间"]].sort_values("目标时间", ascending=False),
                use_container_width=True
            )
        else:
            st.info("暂无历史日程记录")

        st.divider()
        st.subheader("🧠 AI 生活总结")
        
        col_p, col_b = st.columns([2, 1])
        with col_p:
            report_period = st.selectbox("选择周期", ["week", "month", "year"], format_func=lambda x: {"week":"本周", "month":"本月", "year":"今年"}[x])
        with col_b:
            st.write("") 
            st.write("") 
            gen_btn = st.button("✨ 生成 AI 报告")
            
        if gen_btn:
            data_summary = get_report_data(report_period)
            if not data_summary:
                st.warning("这就尴尬了，这个时间段好像没有数据...")
            elif not api_key:
                st.info("💡 请先在左侧侧边栏【⚙️ AI 设置】中输入 API Key。")
                with st.expander("或者复制以下数据发给 ChatGPT"):
                    st.code(f"请帮我写一份{report_period}总结，数据如下：\n{data_summary}")
            else:
                with st.spinner("AI 正在疯狂回忆中..."):
                    report_content = call_ai_report(api_key, base_url, model_name, data_summary, report_period)
                    st.markdown(report_content)

    else:
        st.info("数据库为空。")
