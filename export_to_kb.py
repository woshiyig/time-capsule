#!/usr/bin/env python3
"""
时间胶囊 → AI as Me 知识库导出工具 (增强版)

将 memory.csv 中的数据转换为 AI as Me 知识库文档
包含规则统计 + AI 深度分析
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI
import os

# 配置路径
MEMORY_FILE = "memory.csv"
KB_BASE = Path("../memory/knowledge_base")
LIFE_KB = KB_BASE / "life"
FINANCE_KB = KB_BASE / "finance"

# AI 配置（从环境变量读取，或使用默认值）
API_KEY = os.getenv("SILICONFLOW_API_KEY", "sk-slmttbyivskikjlkqccrozdlywchgksvprulgajqjsaaiknn")
BASE_URL = os.getenv("API_BASE_URL", "https://api.siliconflow.cn/v1")
MODEL_NAME = "deepseek-ai/DeepSeek-V3"

def ensure_kb_dirs():
    """确保知识库目录存在"""
    LIFE_KB.mkdir(parents=True, exist_ok=True)
    FINANCE_KB.mkdir(parents=True, exist_ok=True)

def load_memory():
    """加载记忆数据"""
    try:
        df = pd.read_csv(MEMORY_FILE)
        df["记录时间"] = pd.to_datetime(df["记录时间"], errors='coerce')
        df["目标时间"] = pd.to_datetime(df["目标时间"], errors='coerce')
        return df
    except FileNotFoundError:
        print(f"❌ {MEMORY_FILE} 不存在")
        return pd.DataFrame()

def analyze_patterns(df, period="week"):
    """规则分析：提取行为模式"""
    now = datetime.now()
    
    if period == "week":
        cutoff = now - timedelta(days=7)
    else:  # month
        cutoff = now.replace(day=1)
    
    data = df[df["记录时间"] >= cutoff].copy()
    
    if data.empty:
        return {}
    
    # 添加辅助列
    data["weekday"] = data["记录时间"].dt.dayofweek  # 0=Monday
    data["hour"] = data["记录时间"].dt.hour
    data["is_weekend"] = data["weekday"] >= 5
    
    patterns = {}
    
    # 1. 财务维度
    finance_data = data[data["关联花销"] > 0]
    if not finance_data.empty:
        weekend_spending = finance_data[finance_data["is_weekend"]]["关联花销"].sum()
        weekday_spending = finance_data[~finance_data["is_weekend"]]["关联花销"].sum()
        total = finance_data["关联花销"].sum()
        
        patterns["finance"] = {
            "total": total,
            "weekend_pct": (weekend_spending / total * 100) if total > 0 else 0,
            "avg_per_day": total / 7 if period == "week" else total / now.day,
            "top_category": finance_data["分类"].value_counts().index[0] if len(finance_data) > 0 else "N/A"
        }
    
    # 2. 时间维度
    todos = data[data["分类"] == "待办"]
    done_todos = data[(data["分类"] == "日程") & (data["状态"] == "Done")]
    if len(todos) > 0:
        completion_rate = len(done_todos) / len(todos) * 100
    else:
        completion_rate = 0
    
    patterns["productivity"] = {
        "completion_rate": completion_rate,
        "total_todos": len(todos),
        "completed": len(done_todos)
    }
    
    # 3. 行为模式
    ideas = data[data["分类"] == "创意"]
    if not ideas.empty:
        peak_hour = ideas["hour"].mode()[0] if len(ideas) > 0 else "N/A"
        peak_day = ideas["weekday"].value_counts().index[0] if len(ideas) > 0 else "N/A"
        day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        patterns["creativity"] = {
            "count": len(ideas),
            "peak_hour": peak_hour,
            "peak_day": day_names[peak_day] if isinstance(peak_day, int) else "N/A"
        }
    
    return patterns

def call_ai_for_insights(raw_data, patterns, period="week"):
    """调用 AI 进行深度分析"""
    try:
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        
        prompt = f"""你是一个专业的生活分析师。基于以下用户的{period}数据，请提供深度洞察和建议。

**统计数据**:
{patterns}

**原始记录样本** (最近10条):
{raw_data.tail(10)[['记录时间', '分类', '内容', '关联花销']].to_string()}

请从以下维度分析：
1. **财务健康**: 消费模式、异常支出、省钱建议
2. **时间管理**: 待办完成率、时间分配
3. **行为习惯**: 创意高峰期、生活规律性
4. **对比趋势**: 与历史对比（如果有明显变化）
5. **行动建议**: 3条具体可执行的改进建议（⚠️ 重点：这些建议需要非常具体，可以直接转化为下周的待办事项）

**输出格式要求**：
- 分为两部分：【深度洞察】和【下周行动建议】
- 洞察部分控制在200字以内
- 行动建议以清单形式给出，每条建议应该是可执行的动作
- 语气友好、鼓励性，基于数据而非臆测
"""
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"⚠️ AI 分析暂时不可用: {e}\n\n请查看上方的统计数据。"

def generate_weekly_summary(df):
    """生成周报（含 AI 洞察）"""
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    week_data = df[df["记录时间"] >= week_ago]
    
    if week_data.empty:
        return None
    
    # 规则分析
    patterns = analyze_patterns(df, "week")
    
    # AI 深度分析
    ai_insights = call_ai_for_insights(week_data, patterns, "周")
    
    # 基础统计
    stats = {
        "总记录数": len(week_data),
        "待办": len(week_data[week_data["分类"] == "待办"]),
        "日程": len(week_data[week_data["分类"] == "日程"]),
        "创意": len(week_data[week_data["分类"] == "创意"]),
        "财务": len(week_data[week_data["分类"] == "财务"]),
        "总支出": week_data["关联花销"].sum()
    }
    
    week_num = now.isocalendar()[1]
    filename = LIFE_KB / f"week_{now.year}_{week_num:02d}.md"
    
    # 提取 tags
    tags = []
    if stats['创意'] > 3:
        tags.append('high_creativity')
    if stats['总支出'] > 1000:
        tags.append('high_spending')
    if len(week_data) > 15:
        tags.append('active_user')
    
    content = f"""---
type: weekly_summary
date: {now.strftime('%Y-%m-%d')}
week: {week_num}
source: time_capsule
tags: [{', '.join(tags)}]
record_count: {stats['总记录数']}
total_spending: {stats['总支出']:.2f}
---

# 📅 {now.year}年第{week_num}周生活总结

## 🧠 AI 深度洞察

{ai_insights}

---

## 📊 数据统计

- **记录总数**: {stats['总记录数']} 条
- **待办事项**: {stats['待办']} 项
- **完成日程**: {stats['日程']} 个
- **创意想法**: {stats['创意']} 个
- **财务记录**: {stats['财务']} 笔
- **本周支出**: ¥{stats['总支出']:.2f}

"""
    
    # 行为模式
    if patterns:
        content += "## 🔍 行为模式\n\n"
        if "finance" in patterns:
            f = patterns["finance"]
            content += f"- **消费习惯**: 周末消费占比 {f['weekend_pct']:.1f}%，日均 ¥{f['avg_per_day']:.2f}\n"
        if "productivity" in patterns:
            p = patterns["productivity"]
            content += f"- **执行力**: 待办完成率 {p['completion_rate']:.1f}% ({p['completed']}/{p['total_todos']})\n"
        if "creativity" in patterns:
            c = patterns["creativity"]
            content += f"- **创意高峰**: {c['peak_day']} {c['peak_hour']}点 (共 {c['count']} 条)\n"
        content += "\n"
    
    # 创意记录
    ideas = week_data[week_data["分类"] == "创意"]
    if not ideas.empty:
        content += "## 💡 创意记录\n\n"
        for _, row in ideas.iterrows():
            content += f"- {row['内容'][:100]}\n"
        content += "\n"
    
    # 主要支出
    expenses = week_data[week_data["关联花销"] > 0].sort_values("关联花销", ascending=False).head(5)
    if not expenses.empty:
        content += "## 💰 主要支出\n\n"
        for _, row in expenses.iterrows():
            content += f"- ¥{row['关联花销']:.2f} - {row['内容'][:50]}\n"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return filename

def generate_monthly_finance_report(df):
    """生成月度财务报告（含 AI 洞察）"""
    now = datetime.now()
    month_start = now.replace(day=1)
    month_data = df[df["记录时间"] >= month_start]
    finance_data = month_data[month_data["关联花销"] > 0]
    
    if finance_data.empty:
        return None
    
    patterns = analyze_patterns(df, "month")
    ai_insights = call_ai_for_insights(month_data, patterns, "月")
    
    total = finance_data["关联花销"].sum()
    filename = FINANCE_KB / f"month_{now.year}_{now.month:02d}.md"
    
    # 提取财务 tags
    avg_daily = total / now.day
    finance_tags = ['finance']
    if total > 5000:
        finance_tags.append('high_spending_month')
    if avg_daily > 200:
        finance_tags.append('above_average_daily')
    
    content = f"""---
type: finance_report
date: {now.strftime('%Y-%m-%d')}
month: {now.month}
source: time_capsule
tags: [{', '.join(finance_tags)}]
total_spending: {total:.2f}
avg_daily_spending: {avg_daily:.2f}
---

# 💰 {now.year}年{now.month}月财务报告

## 🧠 AI 财务洞察

{ai_insights}

---

## 📊 总览

- **总支出**: ¥{total:.2f}
- **交易笔数**: {len(finance_data)}
- **日均消费**: ¥{(total / now.day):.2f}

## 📈 分类明细

"""
    
    by_category = finance_data.groupby("分类")["关联花销"].sum().sort_values(ascending=False)
    for cat, amount in by_category.items():
        percentage = (amount / total) * 100
        content += f"- **{cat}**: ¥{amount:.2f} ({percentage:.1f}%)\n"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return filename

if __name__ == "__main__":
    print("🚀 开始导出时间胶囊数据到AI as Me知识库...")
    print(f"🤖 使用 AI 模型: {MODEL_NAME}\n")
    
    ensure_kb_dirs()
    df = load_memory()
    
    if df.empty:
        print("⚠️ 没有数据可导出")
        exit(1)
    
    # 生成周报
    weekly_file = generate_weekly_summary(df)
    if weekly_file:
        print(f"✅ 周报已生成: {weekly_file}")
    
    # 生成月度财务报告
    finance_file = generate_monthly_finance_report(df)
    if finance_file:
        print(f"✅ 财务报告已生成: {finance_file}")
    
    print("\n🎉 导出完成！AI已为你生成深度洞察。")

