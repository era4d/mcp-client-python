import asyncio
import json
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters

from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.websocket import websocket_client

from core.llm_service import get_llm_response
from core.logger import logger
from core.context_manager import ContextManager
from typing import Dict, List, Any

def convert_tool_to_openai_format(tool: Any) -> Dict[str, Any]:
    """将 MCP 工具结构转换为 OpenAI 格式的工具定义"""
    try:
        # 确保inputSchema是有效的JSON对象
        if not tool.inputSchema or not isinstance(tool.inputSchema, dict):
            logger.warning(f"工具 {tool.name} 的inputSchema无效")
            return None
            
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "No description provided.",
                "parameters": tool.inputSchema  # 直接使用 JSON Schema 结构
            }
        }
    except Exception as e:
        logger.warning(f"工具 {tool.name} 转换失败: {e}")
        return None

class MCPClient:
    def __init__(self, server_configs: list[dict]):
        self.server_configs = server_configs
        self.sessions: dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        
        # 初始化上下文管理器
        self.context_manager = ContextManager(
            context_file="logs/context_history.json",
            max_history=50
        )

    async def initialize_all(self):
        """连接所有 MCP Server 并初始化会话"""
        for server in self.server_configs:
            name = server.get("name")
            
            # 检查是否启用了服务器
            if server.get("enabled", True) is False:
                logger.warning(f"服务器 {name} 已禁用，跳过连接")
                continue
                
            try:
                if server["transport"] == "stdio":
                    transport = await self._connect_stdio(server)
                elif server["transport"] == "sse":
                    transport = await self._connect_sse(server)
                elif server["transport"] == "streamable_http":
                    transport = await self._connect_streamable_http(server)
                elif server["transport"] == "websocket":
                    transport = await self._connect_websocket(server)
                else:
                    logger.warning(f"未知 transport 类型: {server['transport']}")
                    continue

                # 检查transport是否是有效的元组
                if transport is None:
                    logger.error(f"连接服务器 {name} 失败: transport为空")
                    continue
                    
                if not isinstance(transport, (tuple, list)):
                    logger.error(f"连接服务器 {name} 失败: transport格式无效 {type(transport)}")
                    continue
                    
                if len(transport) != 2:
                    logger.error(f"连接服务器 {name} 失败: transport长度无效 {len(transport)}")
                    continue

                session = await self.exit_stack.enter_async_context(
                    ClientSession(transport[0], transport[1])
                )
                await session.initialize()
                self.sessions[name] = session

                try:
                    tools_resp = await session.list_tools()
                    logger.info(f"已连接: {name}, 工具数: {len(tools_resp.tools)}")
                except Exception as e:
                    logger.error(f"获取服务器 {name} 工具列表失败: {e}")
                    # 即使获取工具列表失败，也保持连接
                    logger.info(f"已连接: {name}, 但无法获取工具列表")
                    
            except Exception as e:
                logger.error(f"连接 {name} 失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # 继续处理其他服务器，不中断整个初始化过程

    async def _connect_stdio(self, server: dict):
        """连接 stdio 模式 Server"""
        try:
            params = StdioServerParameters(
                command=server.get("command", "python"),
                args=[server["path"]],
                env=None
            )
            logger.info(f"正在连接stdio服务器: {server.get('name')}")
            # 添加超时机制，避免无限等待
            return await asyncio.wait_for(
                self.exit_stack.enter_async_context(stdio_client(params)),
                timeout=10.0  # 10秒超时
            )
        except asyncio.TimeoutError:
            logger.error(f"连接stdio服务器超时: {server.get('name')}")
            raise
        except Exception as e:
            logger.error(f"连接stdio服务器失败: {server.get('name')}, 错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def _connect_sse(self, server: dict):
        """连接 SSE 模式 Server"""
        url = server.get("url")
        if not url:
            raise ValueError(f"SSE服务器 {server.get('name')} 未提供URL")
        
        logger.info(f"正在连接SSE服务器: {url}")
        try:
            return await self.exit_stack.enter_async_context(sse_client(url))
        except Exception as e:
            logger.error(f"连接SSE服务器失败: {url}, 错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
        
    async def _connect_streamable_http(self, server: dict):
        """连接 StreamableHTTP 模式 Server"""
        url = server.get("url")
        if not url:
            raise ValueError(f"StreamableHTTP服务器 {server.get('name')} 未提供URL")
        
        headers = server.get("headers", {})
        logger.info(f"正在连接StreamableHTTP服务器: {url}")
        try:
            result = await self.exit_stack.enter_async_context(streamablehttp_client(url, headers=headers))
            logger.debug(f"StreamableHTTP连接结果: {result}, 类型: {type(result)}, 长度: {len(result) if hasattr(result, '__len__') else 'N/A'}")
            # streamablehttp_client返回(read_stream, write_stream, get_session_id_callback)
            # 但ClientSession只需要前两个参数
            if isinstance(result, tuple) and len(result) >= 2:
                return (result[0], result[1])  # 只返回read_stream和write_stream
            else:
                raise ValueError(f"StreamableHTTP客户端返回了意外的结果格式: {type(result)}")
        except Exception as e:
            logger.error(f"连接StreamableHTTP服务器失败: {url}, 错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
            
    async def _connect_websocket(self, server: dict):
        """连接 WebSocket 模式 Server"""
            
        url = server.get("url")
        if not url:
            raise ValueError(f"WebSocket服务器 {server.get('name')} 未提供URL")
        
        logger.info(f"正在连接WebSocket服务器: {url}")
        try:
            return await self.exit_stack.enter_async_context(websocket_client(url))
        except Exception as e:
            logger.error(f"连接WebSocket服务器失败: {url}, 错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def chat_loop(self):
        """交互式聊天循环"""
        print("\n🤖 MCP Client 启动成功，输入你的问题，输入 'exit' 退出：")
        print("💡 特殊命令:")
        print("   - /history: 查看最近的对话历史")
        print("   - /stats: 查看工具使用统计")
        print("   - /clear: 清除当前会话记录")
        print("   - /export: 导出历史记录")
        
        while True:
            query = input("\n🧑 你: ").strip()
            
            # 处理特殊命令
            if query.lower() in ("exit", "quit"):
                break
            elif query.startswith("/history"):
                self._show_history()
                continue
            elif query.startswith("/stats"):
                self._show_stats()
                continue
            elif query.startswith("/clear"):
                self.context_manager.clear_current_session()
                print("\n🤖 AI: 已清除当前会话的上下文记录")
                continue
            elif query.startswith("/export"):
                self._export_history()
                continue
            
            try:
                response = await self.process_query(query)
                print("\n🤖 AI:", response)
                
                # 记录对话到上下文管理器
                self.context_manager.add_conversation_turn(
                    user_input=query,
                    ai_response=response
                )
                
            except Exception as e:
                logger.error(f"处理查询失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                error_msg = "抱歉，处理您的请求时出现了问题。详细错误信息已记录到日志中。"
                print(f"\n🤖 AI: {error_msg}")
                print(f"错误信息: {str(e)}")
                
                # 即使出错也记录对话
                self.context_manager.add_conversation_turn(
                    user_input=query,
                    ai_response=f"{error_msg} 错误: {str(e)}"
                )
                # 继续循环，不退出程序
    
    def _show_history(self):
        """显示最近的对话历史"""
        recent_conversations = self.context_manager.get_recent_conversations(5)
        if not recent_conversations:
            print("\n📝 暂无对话历史")
            return
        
        print("\n📝 最近的对话历史:")
        for i, turn in enumerate(recent_conversations, 1):
            print(f"\n--- 第 {i} 轮对话 ({turn.timestamp[:19]}) ---")
            print(f"🧑 用户: {turn.user_input[:100]}{'...' if len(turn.user_input) > 100 else ''}")
            print(f"🤖 AI: {turn.ai_response[:100]}{'...' if len(turn.ai_response) > 100 else ''}")
            if turn.tool_calls:
                print(f"🔧 工具调用: {len(turn.tool_calls)} 次")
    
    def _show_stats(self):
        """显示工具使用统计"""
        stats = self.context_manager.get_tool_usage_stats()
        print(f"\n📊 工具使用统计:")
        print(f"总调用次数: {stats['total_calls']}")
        print(f"成功率: {stats['success_rate']:.1%}")
        
        if stats['tool_stats']:
            print("\n各工具详细统计:")
            for tool_name, tool_stats in stats['tool_stats'].items():
                print(f"  🔧 {tool_name}:")
                print(f"     调用次数: {tool_stats['total']}")
                print(f"     成功率: {tool_stats['success_rate']:.1%}")
                print(f"     最后使用: {tool_stats['last_used'][:19]}")
        else:
            print("暂无工具调用记录")
    
    def _export_history(self):
        """导出历史记录"""
        from datetime import datetime
        export_file = f"logs/history_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        if self.context_manager.export_history(export_file):
            print(f"\n💾 历史记录已导出到: {export_file}")
        else:
            print("\n❌ 导出历史记录失败，请查看日志")

    async def process_query(self, query: str) -> str:
        """处理用户输入，调用工具，汇总结果"""
        # 第一步：获取所有已连接 Server 的工具信息
        tools = []
        tool_map = {}
        for name, session in self.sessions.items():
            try:
                resp = await session.list_tools()
                for tool in resp.tools:
                    openai_tool = convert_tool_to_openai_format(tool)
                    if openai_tool:  # 排除转换失败的工具
                        tools.append(openai_tool)
                        tool_map[tool.name] = (session, tool)
            except Exception as e:
                logger.error(f"获取服务器 {name} 的工具列表失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # 继续处理其他服务器，不中断整个流程
        
        # 确保有可用的工具
        if not tools:
            return "⚠️ 没有可用的工具，请检查服务器连接状态。"

        logger.debug(f"Tools passed to LLM: {tools}")

        try:
            # 第二步：获取相关上下文
            context = self.context_manager.get_relevant_context(query, max_turns=3)
            
            # 构建包含上下文的消息
            messages = []
            if context:
                messages.append({
                    "role": "system", 
                    "content": f"以下是相关的对话历史上下文，可以帮助你更好地理解用户的问题：\n\n{context}"
                })
            
            messages.append({"role": "user", "content": query})
            
            # 第三步：调用 LLM 生成回应（可能包含 tool_use）
            llm_response = await get_llm_response(None, tools, messages)

            # 第四步：执行工具调用 + 补全对话
            messages = llm_response["messages"]
            output_chunks = []
            tool_calls_in_turn = []  # 记录本轮对话中的工具调用

            for msg in llm_response["response"]:
                if msg["type"] == "text":
                    output_chunks.append(msg["text"])
                elif msg["type"] == "tool_use":
                    tool_name = msg["name"]
                    input_data = msg["input"]
                    session, _ = tool_map.get(tool_name, (None, None))
                    if not session:
                        error_msg = f"⚠️ 工具 {tool_name} 不存在"
                        output_chunks.append(error_msg)
                        
                        # 记录失败的工具调用
                        self.context_manager.add_tool_call_record(
                            tool_name=tool_name,
                            input_params=input_data,
                            output_result=error_msg,
                            success=False,
                            error_message="工具不存在"
                        )
                        continue

                    try:
                        result = await session.call_tool(tool_name, input_data)
                        
                        # 处理工具调用结果，确保是字符串格式
                        result_content = result.content
                        if hasattr(result_content, '__str__'):
                            result_content_str = str(result_content)
                        elif isinstance(result_content, list) and all(hasattr(item, '__str__') for item in result_content):
                            result_content_str = ', '.join(str(item) for item in result_content)
                        else:
                            result_content_str = "无法显示结果内容"
                            
                        output_chunks.append(f"🔧 调用 {tool_name}: {result_content_str}")
                        
                        # 记录成功的工具调用
                        self.context_manager.add_tool_call_record(
                            tool_name=tool_name,
                            input_params=input_data,
                            output_result=result_content_str,
                            success=True
                        )
                        
                        # 记录工具调用信息用于对话记录
                        tool_calls_in_turn.append({
                            "name": tool_name,
                            "input": input_data,
                            "output": result_content_str,
                            "success": True
                        })

                        # 插入工具调用和结果回 LLM，继续生成回复
                        # 使用标准文本格式描述工具调用
                        tool_call_text = f"我将使用 {tool_name} 工具"
                        messages.append({"role": "assistant", "content": tool_call_text})
                        
                        # 使用标准文本格式描述工具结果
                        messages.append({
                            "role": "user",
                            "content": f"工具 {tool_name} 的结果: {result_content_str}"
                        })

                        try:
                            # 再次请求 LLM 继续生成
                            llm_response = await get_llm_response(None, tools, messages)
                            for submsg in llm_response["response"]:
                                if submsg["type"] == "text":
                                    output_chunks.append(submsg["text"])
                        except Exception as e:
                            logger.error(f"工具调用后请求LLM失败: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                            output_chunks.append(f"⚠️ 处理工具 {tool_name} 的结果时出错: {str(e)}")
                    except Exception as e:
                        logger.error(f"调用工具 {tool_name} 失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        error_msg = f"⚠️ 调用工具 {tool_name} 失败: {str(e)}"
                        output_chunks.append(error_msg)
                        
                        # 记录失败的工具调用
                        self.context_manager.add_tool_call_record(
                            tool_name=tool_name,
                            input_params=input_data,
                            output_result=error_msg,
                            success=False,
                            error_message=str(e)
                        )
                        
                        # 记录工具调用信息用于对话记录
                        tool_calls_in_turn.append({
                            "name": tool_name,
                            "input": input_data,
                            "output": error_msg,
                            "success": False,
                            "error": str(e)
                        })
                        # 继续处理其他消息，不中断整个流程
        except Exception as e:
            logger.error(f"处理查询失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            error_response = f"⚠️ 处理查询时出错: {str(e)}"
            
            # 即使出错也记录对话
            self.context_manager.add_conversation_turn(
                user_input=query,
                ai_response=error_response
            )
            
            return error_response

        if not output_chunks:
            error_response = "⚠️ 处理完成，但没有生成任何输出。请检查日志获取详细信息。"
            
            # 记录对话到上下文管理器
            self.context_manager.add_conversation_turn(
                user_input=query,
                ai_response=error_response
            )
            
            return error_response
        
        # 记录对话到上下文管理器
        ai_response = "\n".join(output_chunks)
        self.context_manager.add_conversation_turn(
            user_input=query,
            ai_response=ai_response,
            tool_calls=tool_calls_in_turn if tool_calls_in_turn else None
        )
        
        return ai_response

    async def cleanup(self):
        """关闭连接，释放资源"""
        try:
            logger.info("正在清理资源...")
            if self.exit_stack:
                await self.exit_stack.aclose()
            logger.info("资源清理完成")
        except Exception as e:
            logger.error(f"清理资源时发生异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 即使清理失败也不抛出异常，避免影响程序退出
