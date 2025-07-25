#!/usr/bin/env python3
"""
简单的上下文记忆功能测试，不依赖外部服务器
"""

import asyncio
import sys
from core.context_manager import ContextManager

async def test_context_manager():
    """测试上下文管理器的基本功能"""
    print("🧪 开始测试上下文管理器...\n")
    
    # 创建上下文管理器
    context_manager = ContextManager(
        context_file="logs/test_context.json",
        max_history=10
    )
    
    try:
        # 测试1：添加对话记录
        print("📝 测试1: 添加对话记录")
        context_manager.add_conversation_turn(
            user_input="你好，请帮我计算1+1",
            ai_response="你好！1+1等于2。"
        )
        
        context_manager.add_conversation_turn(
            user_input="那2+2呢？",
            ai_response="2+2等于4。",
            tool_calls=[
                {
                    "name": "calculator",
                    "input": {"expression": "2+2"},
                    "output": "4",
                    "success": True
                }
            ]
        )
        print("✅ 对话记录添加成功\n")
        
        # 测试2：获取相关上下文
        print("📝 测试2: 获取相关上下文")
        context = context_manager.get_relevant_context("刚才的计算结果是什么？", max_turns=2)
        print(f"相关上下文:\n{context}\n")
        
        # 测试3：添加工具调用记录
        print("📝 测试3: 添加工具调用记录")
        context_manager.add_tool_call_record(
            tool_name="web_search",
            input_params={"query": "Python教程"},
            output_result="找到了相关的Python教程链接",
            success=True
        )
        
        context_manager.add_tool_call_record(
            tool_name="file_read",
            input_params={"path": "/nonexistent/file.txt"},
            output_result="文件不存在",
            success=False,
            error_message="FileNotFoundError"
        )
        print("✅ 工具调用记录添加成功\n")
        
        # 测试4：获取统计信息
        print("📝 测试4: 获取统计信息")
        stats = context_manager.get_tool_usage_stats()
        print(f"工具使用统计: {stats}\n")
        
        # 测试5：导出历史记录
        print("📝 测试5: 导出历史记录")
        export_file = "logs/test_export.json"
        if context_manager.export_history(export_file):
            print(f"✅ 历史记录已导出到: {export_file}\n")
        else:
            print("❌ 导出失败\n")
        
        # 测试6：查看历史记录
        print("📝 测试6: 查看历史记录")
        history = context_manager.get_conversation_history(limit=5)
        print(f"最近5条对话记录:")
        for i, turn in enumerate(history, 1):
            print(f"  {i}. 用户: {turn.user_input}")
            print(f"     AI: {turn.ai_response}")
            if turn.tool_calls:
                print(f"     工具调用: {len(turn.tool_calls)}个")
            print()
        
        print("✅ 上下文管理器测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_context_manager())