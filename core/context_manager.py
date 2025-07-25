#!/usr/bin/env python3
"""
上下文记忆管理器

提供对话历史记录、工具调用记录和上下文检索功能
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from core.logger import logger


@dataclass
class ConversationTurn:
    """单轮对话记录"""
    timestamp: str
    user_input: str
    ai_response: str
    tool_calls: List[Dict[str, Any]]
    session_id: str


@dataclass
class ToolCallRecord:
    """工具调用记录"""
    timestamp: str
    tool_name: str
    input_params: Dict[str, Any]
    output_result: str
    success: bool
    error_message: Optional[str] = None


class ContextManager:
    """上下文记忆管理器"""
    
    def __init__(self, context_file: str = "context_history.json", max_history: int = 100):
        self.context_file = Path(context_file)
        self.max_history = max_history
        self.current_session_id = self._generate_session_id()
        self.conversation_history: List[ConversationTurn] = []
        self.tool_call_history: List[ToolCallRecord] = []
        
        # 确保上下文目录存在
        self.context_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载历史记录
        self._load_history()
        
        logger.info(f"上下文管理器初始化完成，会话ID: {self.current_session_id}")
    
    def _generate_session_id(self) -> str:
        """生成唯一的会话ID"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _load_history(self):
        """从文件加载历史记录"""
        if not self.context_file.exists():
            logger.info("上下文历史文件不存在，创建新的历史记录")
            return
        
        try:
            with open(self.context_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 加载对话历史
            for item in data.get('conversations', []):
                self.conversation_history.append(ConversationTurn(**item))
            
            # 加载工具调用历史
            for item in data.get('tool_calls', []):
                self.tool_call_history.append(ToolCallRecord(**item))
                
            # 限制历史记录数量
            self.conversation_history = self.conversation_history[-self.max_history:]
            self.tool_call_history = self.tool_call_history[-self.max_history * 5:]  # 工具调用记录保留更多
            
            logger.info(f"加载历史记录完成: {len(self.conversation_history)} 轮对话, {len(self.tool_call_history)} 次工具调用")
            
        except Exception as e:
            logger.error(f"加载上下文历史失败: {e}")
            # 如果加载失败，创建备份并重新开始
            if self.context_file.exists():
                backup_file = self.context_file.with_suffix('.backup.json')
                self.context_file.rename(backup_file)
                logger.info(f"已将损坏的历史文件备份到: {backup_file}")
    
    def _save_history(self):
        """保存历史记录到文件"""
        try:
            data = {
                'conversations': [asdict(turn) for turn in self.conversation_history],
                'tool_calls': [asdict(call) for call in self.tool_call_history],
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.context_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug("上下文历史已保存")
            
        except Exception as e:
            logger.error(f"保存上下文历史失败: {e}")
    
    def add_conversation_turn(self, user_input: str, ai_response: str, tool_calls: List[Dict[str, Any]] = None):
        """添加一轮对话记录"""
        if tool_calls is None:
            tool_calls = []
            
        turn = ConversationTurn(
            timestamp=datetime.now().isoformat(),
            user_input=user_input,
            ai_response=ai_response,
            tool_calls=tool_calls,
            session_id=self.current_session_id
        )
        
        self.conversation_history.append(turn)
        
        # 限制历史记录数量
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
        
        self._save_history()
        logger.debug(f"添加对话记录: 用户输入长度={len(user_input)}, AI响应长度={len(ai_response)}")
    
    def add_tool_call_record(self, tool_name: str, input_params: Dict[str, Any], 
                           output_result: str, success: bool, error_message: str = None):
        """添加工具调用记录"""
        record = ToolCallRecord(
            timestamp=datetime.now().isoformat(),
            tool_name=tool_name,
            input_params=input_params,
            output_result=output_result,
            success=success,
            error_message=error_message
        )
        
        self.tool_call_history.append(record)
        
        # 限制工具调用历史数量
        if len(self.tool_call_history) > self.max_history * 5:
            self.tool_call_history = self.tool_call_history[-self.max_history * 5:]
        
        self._save_history()
        logger.debug(f"添加工具调用记录: {tool_name} - 成功={success}")
    
    def get_recent_conversations(self, count: int = 5) -> List[ConversationTurn]:
        """获取最近的对话记录"""
        return self.conversation_history[-count:] if self.conversation_history else []
    
    def get_relevant_context(self, query: str, max_turns: int = 3) -> str:
        """根据查询获取相关的上下文信息"""
        if not self.conversation_history:
            return ""
        
        # 简单的关键词匹配策略
        query_lower = query.lower()
        relevant_turns = []
        
        # 首先获取最近的几轮对话
        recent_turns = self.get_recent_conversations(max_turns)
        relevant_turns.extend(recent_turns)
        
        # 然后查找包含相似关键词的历史对话
        query_keywords = set(query_lower.split())
        for turn in reversed(self.conversation_history[:-max_turns]):
            if len(relevant_turns) >= max_turns * 2:
                break
                
            turn_text = (turn.user_input + " " + turn.ai_response).lower()
            turn_keywords = set(turn_text.split())
            
            # 如果有共同关键词，则认为相关
            if query_keywords & turn_keywords:
                relevant_turns.insert(-max_turns, turn)  # 插入到最近对话之前
        
        # 构建上下文字符串
        context_parts = []
        for turn in relevant_turns[-max_turns * 2:]:  # 限制最终数量
            context_parts.append(f"用户: {turn.user_input}")
            context_parts.append(f"AI: {turn.ai_response}")
            if turn.tool_calls:
                for tool_call in turn.tool_calls:
                    context_parts.append(f"工具调用: {tool_call.get('name', 'unknown')}")
        
        return "\n".join(context_parts)
    
    def get_tool_usage_stats(self) -> Dict[str, Any]:
        """获取工具使用统计信息"""
        if not self.tool_call_history:
            return {"total_calls": 0, "success_rate": 0, "tool_stats": {}}
        
        total_calls = len(self.tool_call_history)
        successful_calls = sum(1 for call in self.tool_call_history if call.success)
        success_rate = successful_calls / total_calls if total_calls > 0 else 0
        
        # 按工具统计
        tool_stats = {}
        for call in self.tool_call_history:
            tool_name = call.tool_name
            if tool_name not in tool_stats:
                tool_stats[tool_name] = {"total": 0, "success": 0, "last_used": call.timestamp}
            
            tool_stats[tool_name]["total"] += 1
            if call.success:
                tool_stats[tool_name]["success"] += 1
            
            # 更新最后使用时间
            if call.timestamp > tool_stats[tool_name]["last_used"]:
                tool_stats[tool_name]["last_used"] = call.timestamp
        
        # 计算每个工具的成功率
        for tool_name, stats in tool_stats.items():
            stats["success_rate"] = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        
        return {
            "total_calls": total_calls,
            "success_rate": success_rate,
            "tool_stats": tool_stats
        }
    
    def clear_current_session(self):
        """清除当前会话的记录"""
        # 只清除当前会话的记录
        self.conversation_history = [
            turn for turn in self.conversation_history 
            if turn.session_id != self.current_session_id
        ]
        
        # 生成新的会话ID
        self.current_session_id = self._generate_session_id()
        self._save_history()
        
        logger.info(f"已清除当前会话记录，新会话ID: {self.current_session_id}")
    
    def clear_all_history(self):
        """清除所有历史记录"""
        self.conversation_history.clear()
        self.tool_call_history.clear()
        self.current_session_id = self._generate_session_id()
        self._save_history()
        
        logger.info("已清除所有历史记录")
    
    def export_history(self, export_file: str) -> bool:
        """导出历史记录到指定文件"""
        try:
            export_path = Path(export_file)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'export_time': datetime.now().isoformat(),
                'session_id': self.current_session_id,
                'conversations': [asdict(turn) for turn in self.conversation_history],
                'tool_calls': [asdict(call) for call in self.tool_call_history],
                'stats': self.get_tool_usage_stats()
            }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"历史记录已导出到: {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出历史记录失败: {e}")
            return False