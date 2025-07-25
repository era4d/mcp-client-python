#!/usr/bin/env python3
"""
MCP WebSocket Server Implementation

This server implements the standard MCP (Model Context Protocol) over WebSocket transport.
It provides web crawling functionality through the MCP protocol.
"""

import asyncio
import json
from typing import Any, Dict, List
import httpx
from fake_useragent import UserAgent
from selectolax.parser import HTMLParser
from playwright.async_api import async_playwright
from urllib.parse import urlparse

from mcp.server import Server
from mcp.server.websocket import websocket_server
from mcp.types import Tool, TextContent
import mcp.types as types

# Initialize MCP server
server = Server("websocket-crawler")

# --- 工具实现逻辑 ---

async def fetch_normal(url: str, retries=2, timeout=10) -> str:
    """使用httpx获取网页内容"""
    headers = {
        "User-Agent": UserAgent().random,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for _ in range(retries):
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200 and "text/html" in response.headers.get("content-type", ""):
                    return response.text
            except Exception:
                await asyncio.sleep(1)
    return ""

async def fetch_js(url: str, timeout=15) -> str:
    """使用Playwright获取JavaScript渲染后的网页内容"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=timeout * 1000)
            await asyncio.sleep(2)
            content = await page.content()
            await browser.close()
            return content
    except Exception:
        return ""

def extract_content(html: str) -> Dict[str, str]:
    """从HTML中提取标题和正文内容"""
    doc = HTMLParser(html)
    title = doc.css_first("title").text(strip=True) if doc.css_first("title") else ""
    body = " ".join([n.text(strip=True) for n in doc.css("p") if n.text(strip=True)])
    return {"title": title, "text": body[:1500]}

def is_valid_url(url: str) -> bool:
    """验证URL格式是否正确"""
    try:
        result = urlparse(url)
        return result.scheme in ["http", "https"] and result.netloc != ""
    except Exception:
        return False

# --- MCP 工具定义 ---

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """列出可用的工具"""
    return [
        Tool(
            name="web_crawler",
            description="抓取网页并提取标题与正文内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "目标网页URL"
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="validate_url",
            description="验证URL是否有效且可访问",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要验证的URL"
                    }
                },
                "required": ["url"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """处理工具调用"""
    if name == "web_crawler":
        url = arguments.get("url")
        if not url:
            return [TextContent(type="text", text="错误: 缺少URL参数")]
        
        result = await web_crawler_impl(url)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    
    elif name == "validate_url":
        url = arguments.get("url")
        if not url:
            return [TextContent(type="text", text="错误: 缺少URL参数")]
        
        result = await validate_url_impl(url)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    
    else:
        return [TextContent(type="text", text=f"错误: 未知工具 {name}")]

async def web_crawler_impl(url: str) -> Dict[str, Any]:
    """抓取网页并提取标题与正文内容"""
    if not is_valid_url(url):
        return {"error": "无效的URL格式"}
    
    # 首先尝试普通抓取
    html = await fetch_normal(url)
    
    # 如果内容太少，尝试JavaScript渲染
    if len(html) < 1000:
        html = await fetch_js(url)
    
    if not html:
        return {"error": "网页抓取失败"}
    
    result = extract_content(html)
    return {
        "url": url,
        "title": result["title"],
        "content": result["text"],
        "status": "success"
    }

async def validate_url_impl(url: str) -> Dict[str, Any]:
    """验证URL是否有效且可访问"""
    if not is_valid_url(url):
        return {"valid": False, "reason": "URL格式无效"}
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.head(url, follow_redirects=True)
            return {
                "valid": True,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", "unknown")
            }
    except Exception as e:
        return {"valid": False, "reason": str(e)}

async def main():
    """启动WebSocket服务器"""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import WebSocketRoute
    from mcp.server.websocket import websocket_server
    
    async def websocket_endpoint(websocket):
        """WebSocket端点处理函数"""
        try:
            async with websocket_server(websocket.scope, websocket.receive, websocket.send) as streams:
                read_stream, write_stream = streams
                await server.run(read_stream, write_stream, server.create_initialization_options())
        except Exception as e:
            print(f"WebSocket连接错误: {e}")
    
    # 创建Starlette应用
    app = Starlette(
        routes=[
            WebSocketRoute("/ws", websocket_endpoint),
        ]
    )
    
    print("WebSocket MCP服务器已启动: ws://localhost:8765/ws")
    
    # 启动服务器
    config = uvicorn.Config(app, host="0.0.0.0", port=8765, log_level="info")
    server_instance = uvicorn.Server(config)
    await server_instance.serve()

if __name__ == "__main__":
    asyncio.run(main())