import os
import json
from pyexpat import model
from typing import Optional, Dict, List, Any

try:
    from openai import AsyncOpenAI
    from dotenv import load_dotenv
    load_dotenv()
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("警告：openai或python-dotenv包未安装，将使用模拟响应")

# 如果openai不可用，使用模拟响应
if not OPENAI_AVAILABLE:
    class MockAsyncOpenAI:
        def __init__(self, **kwargs):
            self.chat = self.Chat()
            
        class Chat:
            def __init__(self):
                self.completions = self.Completions()
                
            class Completions:
                @staticmethod
                async def create(**kwargs):
                    class MockResponse:
                        class Choice:
                            class Message:
                                content = "这是一个模拟响应，因为openai包未安装。"
                                tool_calls = None
                                
                            message = Message()
                            
                        choices = [Choice()]
                        
                    return MockResponse()
    
    AsyncOpenAI = MockAsyncOpenAI


# 初始化OpenAI客户端
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)


async def get_llm_response(
    query: Optional[str],
    tools: list[dict],
    messages: Optional[list] = None,
    model: str = "qwen-max",
    max_tokens: int = 1000
) -> dict:
    """
    请求 OpenAI / Qwen 模型，获取响应（支持 tools）

    :param query: 用户输入内容（首次请求时使用）
    :param tools: MCP 工具列表，格式为 dict
    :param messages: 可选的上下文消息（用于 tool_result 反馈后续请求）
    :param model: 使用的模型名称
    :return: 返回 messages + parsed response 内容
    """
    if messages is None:
        messages = [{"role": "user", "content": query}]

    try:
        response = await client.chat.completions.create(
            model=os.getenv("LLM_MODEL") or model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=max_tokens,
        )
        
        parsed = []
        # 检查响应格式
        message = response.choices[0].message
        
        # 处理不同的响应格式
        if hasattr(message, 'content') and message.content:
            # 如果content是字符串，则作为文本处理
            if isinstance(message.content, str):
                parsed.append({"type": "text", "text": message.content})
            # 如果content是列表，则按类型处理每个项
            elif isinstance(message.content, list):
                for item in message.content:
                    if hasattr(item, 'type'):
                        if item.type == "text":
                            parsed.append({"type": "text", "text": item.text})
                        elif item.type == "tool_use":
                            parsed.append({
                                "type": "tool_use",
                                "name": item.name,
                                "input": item.input,
                                "id": item.id
                            })
        
        # 处理工具调用
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                try:
                    # 尝试解析工具调用参数
                    tool_input = json.loads(tool_call.function.arguments)
                    parsed.append({
                        "type": "tool_use",
                        "name": tool_call.function.name,
                        "input": tool_input,
                        "id": tool_call.id
                    })
                except Exception as e:
                    # 如果解析失败，记录错误并使用原始字符串
                    parsed.append({
                        "type": "text",
                        "text": f"工具调用参数解析失败: {str(e)}"
                    })
    except Exception as e:
        import traceback
        traceback.print_exc()
        # 出错时返回错误信息
        parsed = [{"type": "text", "text": f"调用AI服务时出错: {str(e)}"}]

    return {"messages": messages, "response": parsed}
