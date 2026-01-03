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
    """更新某条记录的状态
    expense_list: [{"cost": 10.0, "category": "餐饮"}, ...]
    """
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

# 初始化
init_memory()
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "你好！我是你的时间胶囊。把你的想法、安排和记忆交给我吧。💊"})

# === 侧边栏：分类管理 ===
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
                        
                        # --- 动态添加花销逻辑 ---
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

# === 主界面：多页面切换 ===

st.title("💊 时间胶囊 (Time Capsule)")

tab1, tab2 = st.tabs(["💬 对话", "📊 报表"])

# --- 标签页 1: 聊天 ---
with tab1:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

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
        st.subheader("💰 财务报表")
        finance_df = df[ (df["分类"]=="财务") | (df["关联花销"] > 0) ].copy()
        
        if not finance_df.empty:
            finance_df["关联花销"] = pd.to_numeric(finance_df["关联花销"])
            total_cost = finance_df["关联花销"].sum()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="总支出", value=f"¥ {total_cost:,.2f}")
            with col2:
                st.bar_chart(finance_df, x="记录时间", y="关联花销")
                
            with st.expander("查看详细账单"):
                st.dataframe(finance_df[["记录时间", "内容", "关联花销"]].sort_values("记录时间", ascending=False))
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

    else:
        st.info("数据库为空。")
