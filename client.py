import asyncio
import yaml
import os
import sys
from dotenv import load_dotenv

from core.logger import init_logger
from core.mcp_client import MCPClient
from mcp import ClientSession

# 加载环境变量
load_dotenv()

# 从环境变量读取DEBUG_MODE设置
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'

def debug_print(*args, **kwargs):
    """根据DEBUG_MODE环境变量控制debug输出"""
    if DEBUG_MODE:
        print(*args, **kwargs)


async def main():
    debug_print("DEBUG: main() function started")
    
    # 加载 .env 文件，读取 OpenAI Key 和 Base URL
    debug_print("DEBUG: Loading .env file")
    debug_print("DEBUG: .env file loaded")

    # 初始化日志记录器
    debug_print("DEBUG: Initializing logger")
    logger = init_logger()
    logger.info("MCP Client 启动中...")
    debug_print("DEBUG: Logger initialized")

    # 加载服务器配置文件 servers.yaml
    debug_print(f"当前工作目录: {os.getcwd()}")
    debug_print("DEBUG: About to check servers.yaml")

    if not os.path.exists("servers.yaml"):
        logger.error("找不到 servers.yaml 配置文件")
        sys.exit(1)

    async def read_config():
        loop = asyncio.get_event_loop()
        with open("servers.yaml", "r", encoding="utf-8") as f:
            return await loop.run_in_executor(None, yaml.safe_load, f)
    config = await read_config()
    
    servers = config.get("servers", [])
    if not servers:
        logger.error("servers.yaml 未配置任何 MCP Server")
        sys.exit(1)

    # 初始化客户端（可并发连接多个服务器）
    client = MCPClient(servers)
    
    # 不再跳过初始化过程，直接使用initialize_all方法
    try:
        await client.initialize_all()
        logger.info("所有服务器初始化完成")
    except Exception as e:
        logger.error(f"初始化服务器失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # 如果初始化失败，尝试手动连接（兼容旧代码）
        logger.warning("尝试手动连接服务器...")
        client.sessions = {}
        
        # 尝试连接所有服务器（包括 stdio、sse、streamable_http 和 websocket）
        for server in servers:
            # 检查是否启用了MCP工具
            if server.get("enabled", True) is False:
                logger.warning(f"服务器 {server.get('name')} 已禁用，跳过连接")
                continue
                
            try:
                name = server.get("name")
                transport_type = server.get("transport")
                logger.info(f"尝试连接服务器: {name}, 类型: {transport_type}")
                transport = None
                if transport_type == "stdio":
                    transport = await client._connect_stdio(server)
                elif transport_type == "streamable_http":
                    transport = await client._connect_streamable_http(server)
                elif transport_type == "sse":
                    transport = await client._connect_sse(server)
                elif transport_type == "websocket":
                    transport = await client._connect_websocket(server)
                else:
                    logger.warning(f"暂不支持的服务器类型: {transport_type}")
                    continue
                
                if transport is None:
                    logger.error(f"连接服务器 {name} 失败: transport为空")
                    continue
                
                # 检查transport是否是有效的元组
                if not isinstance(transport, (tuple, list)):
                    logger.error(f"连接服务器 {name} 失败: transport格式无效 {type(transport)}")
                    continue
                    
                if len(transport) != 2:
                    logger.error(f"连接服务器 {name} 失败: transport长度无效 {len(transport)}")
                    continue
                    
                session = await client.exit_stack.enter_async_context(
                    ClientSession(transport[0], transport[1])
                )
                await session.initialize()
                client.sessions[name] = session
                logger.info(f"成功连接服务器: {name}")
                
                # 列出服务器提供的工具
                try:
                    tools_resp = await session.list_tools()
                    logger.info(f"服务器 {name} 提供的工具数量: {len(tools_resp.tools)}")
                    print(f"\n服务器 {name} 提供的工具:")
                    for tool in tools_resp.tools:
                        print(f"  - {tool.name}: {tool.description}")
                except Exception as e:
                    logger.error(f"获取服务器 {name} 工具列表失败: {e}")
            except Exception as e:
                logger.error(f"连接服务器失败: {e}")
                import traceback
                logger.error(traceback.format_exc())

    # 启动交互式聊天
    try:
        await client.chat_loop()
    except KeyboardInterrupt:
        logger.info("用户中断，正在退出...")
    except Exception as e:
        logger.error(f"聊天循环发生异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.info("尝试继续运行...")
    finally:
        try:
            await client.cleanup()
        except Exception as e:
            logger.error(f"清理资源时发生异常: {e}")
            import traceback
            logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
