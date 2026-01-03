import streamlit as st
import dateparser
from dateparser.search import search_dates
import pandas as pd
import os
from datetime import datetime

# ================= 配置区 =================
MEMORY_FILE = 'memory.csv'

# ================= 核心功能函数 =================

def init_memory():
    """初始化存储文件"""
    # 如果文件不存在，或者格式不对（比如少列了），都重置
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

def update_status(index, new_status, cost=0.0):
    """更新某条记录的状态"""
    df = pd.read_csv(MEMORY_FILE)
    
    # 1. 更新状态
    df.at[index, "状态"] = new_status
    df.at[index, "关联花销"] = cost
    
    # 2. 【核心逻辑变更】: 待办完成后，自动转为 "日程" (如果不涉及花销)
    if df.at[index, "分类"] == "待办" and new_status == "Done":
        if cost > 0:
            df.at[index, "分类"] = "日程"
        else:
            df.at[index, "分类"] = "日程"
            
    df.to_csv(MEMORY_FILE, index=False)
    
    # 3. 如果产生了花销，额外追加一条财务明细
    if cost > 0:
        original_content = df.at[index, "内容"]
        save_record("财务", f"完成任务: {original_content}", status="Done", cost=cost)

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

    # === 分类逻辑 (遵循用户定义) ===
    if is_future:
        # [规则] 所有未来的事 -> 待办
        category = "待办"
    else:
        # [规则] 过去/现在的事情
        if any(k in text for k in finance_keywords):
            category = "财务" 
        elif parsed_date or any(k in text for k in schedule_keywords):
            # 有时间或者有动词的过去事情 -> 日程
            category = "日程" 
        elif any(k in text for k in todo_keywords):
            # 明确的行动指令 -> 待办
            category = "待办"
        else:
            # 既不是日程，也不是财务，也没有待办关键词 -> 归为 [创意]
            category = "创意"

    # 默认状态
    status = "Done" if category in ["财务", "日程"] else "Pending"
    
    save_record(category, text, parsed_date, status=status)
    return category, parsed_date

# ================= 页面 UI =================

st.set_page_config(page_title="时间胶囊", page_icon="💊", layout="wide")

# (可选) 自定义 CSS 美化
st.markdown("""
<style>
    /* 全局字体优化 */
    .stApp {
        font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    /* 标题样式 */
    h1 {
        color: #4F8BF9;
        font-weight: bold;
        text-align: center;
    }
    /* 侧边栏美化 */
    section[data-testid="stSidebar"] {
        background-color: #f7f9fc;
    }
    /* 聊天框微调 */
    .stChatMessage {
        border-radius: 10px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 初始化
init_memory()
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "你好！我是你的时间胶囊。把你的想法、安排和记忆交给我吧。💊"})

# === 侧边栏：任务管理 ===
with st.sidebar:
    st.header("📅 待办与日程")
    st.caption("未完成的任务会留在这里，等待你完成。")
    df = load_memory()
    
    if not df.empty:
        # pending_tasks 逻辑保持不变...
        pending_tasks = df[ (df["状态"] == "Pending") & (df["分类"].isin(["日程", "待办"])) ]
        
        if pending_tasks.empty:
            st.info("目前没有待办事项 🎉")
        else:
            for index, row in pending_tasks.iterrows():
                with st.expander(f"{row['分类']}: {row['内容'][:10]}..."):
                    st.write(f"内容: {row['内容']}")
                    st.write(f"时间: {row['目标时间']}")
                    with st.form(key=f"finish_task_{index}"):
                        cost = st.number_input("实际花费 (元)", min_value=0.0, step=10.0)
                        submit = st.form_submit_button("✅ 完成并归档")
                        if submit:
                            update_status(index, "Done", cost)
                            st.success("已完成！(如有花销已自动记账)")
                            st.rerun()

# === 主界面：多页面切换 ===

st.title("💊 时间胶囊 (Time Capsule)")

# 创建两个标签页
tab1, tab2 = st.tabs(["💬 对话", "📊 报表"])

# --- 标签页 1: 聊天 ---
with tab1:
    # 显示历史
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # 处理输入
    prompt = st.chat_input("输入你的想法...")

    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        category, target_time = process_input(prompt)

        time_str = f" (时间: {target_time.strftime('%Y-%m-%d %H:%M')})" if target_time else ""
        response = f"✅ 已记录到 **[{category}]**{time_str}"
        
        with st.chat_message("assistant"):
            st.write(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

# --- 标签页 2: 报表 ---
with tab2:
    if not df.empty:
        # === A. 财务概览 ===
        st.subheader("💰 财务报表")
        finance_df = df[ (df["分类"]=="财务") | (df["关联花销"] > 0) ].copy()
        
        if not finance_df.empty:
            finance_df["关联花销"] = pd.to_numeric(finance_df["关联花销"])
            total_cost = finance_df["关联花销"].sum()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="总支出", value=f"¥ {total_cost:,.2f}")
            with col2:
                # 简单的柱状图
                st.bar_chart(finance_df, x="记录时间", y="关联花销")
                
            with st.expander("查看详细账单"):
                st.dataframe(finance_df[["记录时间", "内容", "关联花销"]].sort_values("记录时间", ascending=False))
        else:
            st.caption("暂无财务记录")
            
        st.divider() # 分割线
        
        # === B. 历史日程 ===
        st.subheader("📅 历史日程 (已完成/过去)")
        # 筛选出 "日程" 类的记录
        schedule_df = df[ df["分类"] == "日程" ].copy()
        
        if not schedule_df.empty:
            # 按目标时间倒序排列（最近的在上面）
            st.dataframe(
                schedule_df[["目标时间", "内容", "记录时间"]].sort_values("目标时间", ascending=False),
                use_container_width=True
            )
        else:
            st.info("暂无历史日程记录")

    else:
        st.info("数据库为空。")
