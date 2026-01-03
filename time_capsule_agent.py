#!/usr/bin/env python3
"""
时间胶囊智能代理 (Time Capsule Agent)

与 AI as Me 主系统的接口层，负责：
1. 自动同步数据到知识库
2. 调用 AI as Me 的认知工作流
3. 生成智能建议
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import subprocess

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 配置
MEMORY_FILE = Path(__file__).parent / "memory.csv"
EXPORT_SCRIPT = Path(__file__).parent / "export_to_kb.py"
LAST_SYNC_FILE = Path(__file__).parent / ".last_sync"


class TimeCapsuleAgent:
    """时间胶囊智能代理"""
    
    def __init__(self):
        self.last_sync_time = self._load_last_sync_time()
    
    def _load_last_sync_time(self):
        """加载上次同步时间"""
        if LAST_SYNC_FILE.exists():
            with open(LAST_SYNC_FILE, 'r') as f:
                timestamp_str = f.read().strip()
                try:
                    return datetime.fromisoformat(timestamp_str)
                except:
                    return None
        return None
    
    def _save_last_sync_time(self):
        """保存同步时间"""
        with open(LAST_SYNC_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
    
    def check_new_records(self):
        """检查是否有新记录需要同步"""
        if not MEMORY_FILE.exists():
            return False
        
        df = pd.read_csv(MEMORY_FILE)
        if df.empty:
            return False
        
        df["记录时间"] = pd.to_datetime(df["记录时间"], errors='coerce')
        
        if self.last_sync_time is None:
            return True  # 首次同步
        
        # 检查是否有新于上次同步时间的记录
        new_records = df[df["记录时间"] > self.last_sync_time]
        return len(new_records) > 0
    
    def auto_sync_to_kb(self, force=False):
        """
        自动同步到知识库
        
        Args:
            force: 是否强制同步（忽略时间检查）
        
        Returns:
            bool: 是否成功同步
        """
        if not force and not self.check_new_records():
            print("✓ 没有新记录，跳过同步")
            return False
        
        try:
            print("🔄 开始自动同步到 AI as Me 知识库...")
            
            # 调用 export_to_kb.py
            result = subprocess.run(
                [sys.executable, str(EXPORT_SCRIPT)],
                capture_output=True,
                text=True,
                cwd=EXPORT_SCRIPT.parent
            )
            
            if result.returncode == 0:
                print("✅ 同步成功！")
                print(result.stdout)
                self._save_last_sync_time()
                return True
            else:
                print(f"❌ 同步失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 同步异常: {e}")
            return False
    
    def trigger_workflow(self, workflow_name, context):
        """
        触发 AI as Me 工作流
        
        Args:
            workflow_name: 工作流名称 (deep_thinking, socratic_mode, etc.)
            context: 上下文数据
        
        Returns:
            工作流执行结果
        """
        # TODO: 实现工作流调用逻辑
        # 这里需要根据 AI as Me 的实际接口来实现
        print(f"🔧 触发工作流: {workflow_name}")
        print(f"📝 上下文: {context}")
        return {"status": "pending", "message": "工作流调用功能开发中"}
    
    def analyze_idea(self, idea_text):
        """
        深度分析创意
        
        调用 deep_thinking 工作流
        """
        return self.trigger_workflow("deep_thinking", {
            "type": "idea_analysis",
            "content": idea_text
        })
    
    def prioritize_todos(self, todos_list):
        """
        基于用户原则为待办排序
        """
        return self.trigger_workflow("deep_thinking", {
            "type": "todo_prioritization",
            "todos": todos_list
        })
    
    def generate_suggestions(self):
        """
        生成智能建议
        
        基于历史数据和用户画像，生成行动建议
        """
        # TODO: 实现建议生成逻辑
        return {
            "suggestions": [
                {
                    "type": "todo",
                    "content": "上周创意中提到的'做 app'，是否添加到待办？",
                    "priority": "medium"
                }
            ]
        }


def auto_sync_hook():
    """
    自动同步钩子函数
    供 brain.py 在 save_record 后调用
    """
    agent = TimeCapsuleAgent()
    agent.auto_sync_to_kb()


if __name__ == "__main__":
    # 测试
    agent = TimeCapsuleAgent()
    
    print("=== 时间胶囊智能代理测试 ===\n")
    
    # 测试同步
    agent.auto_sync_to_kb(force=True)
    
    print("\n=== 测试完成 ===")
