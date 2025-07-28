# MCP Client Python

This is a Python implementation of an MCP (Model Context Protocol) client that can connect to multiple MCP servers and invoke their tools.

## Features

- Support multiple transport protocols (stdio, SSE, StreamableHTTP, WebSocket)
- Concurrent connection to multiple MCP servers
- Command-line interface
- OpenAI-compatible API calls
- Enable/disable MCP tools in the configuration file
- [Context Memory](CONTEXT_MEMORY.md)
- logging

## Installation

```bash
# Clone the repository
git clone https://github.com/era4d/mcp-client-python.git
cd mcp-client-python

# Install dependencies
uv venv
source .venv/bin/activate
uv sync
``` 

## Configuration

1. Create a `.env` file to configure the OpenAI API key and base URL:

```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1  # or other compatible API address
```

2. Configure MCP servers in `servers.yaml`:

```yaml
servers:
  # Local stdio server
  - name: weather
    transport: stdio
    command: python
    path: servers/weather.py
    enabled: true  # optional, default is true
  - name: calc
    transport: stdio
    command: python
    path: servers/calc.py
    enabled: true
    
  # SSE server
  - name: remote-weather
    transport: sse
    url: http://localhost:8000/mcp
    enabled: false  # Set to false to disable this server
    
  # StreamableHTTP server
  - name: remote-tools
    transport: streamable_http
    url: http://localhost:8080/api/mcp
    enabled: true
    headers:
      Authorization: Bearer your-api-key-here
      
  # WebSocket server
  - name: websocket-server
    transport: websocket
    url: ws://localhost:8765
    enabled: false  # Default is disabled, set to true when needed
```

## Quick Start

### Command-line

```bash
# Start Service
cd servers && python crawler.py
cd servers && python weather.py
cd servers && python wiki.py

# Start MCP Host
python client.py
```
### Example Output
```bash
2025-07-25 06:58:57,383 [INFO] MCP Client 启动中...
DEBUG: Logger initialized
当前工作目录: /home/u/workspace/mcp-client-python
DEBUG: About to check servers.yaml
2025-07-25 06:58:57,387 [INFO] 上下文历史文件不存在，创建新的历史记录
2025-07-25 06:58:57,387 [INFO] 上下文管理器初始化完成，会话ID: 20250725_065857
2025-07-25 06:58:57,387 [WARNING] 服务器 calc 已禁用，跳过连接
2025-07-25 06:58:57,387 [WARNING] 服务器 remote-wiki-sse 已禁用，跳过连接
2025-07-25 06:58:57,387 [INFO] 正在连接StreamableHTTP服务器: http://localhost:8000/mcp
2025-07-25 06:58:57,438 [INFO] Received session ID: 9704973cf2694354a4a58ec1a055336d
2025-07-25 06:58:57,439 [INFO] Negotiated protocol version: 2025-06-18
2025-07-25 06:58:57,452 [INFO] 已连接: weather-stream, 工具数: 2
2025-07-25 06:58:57,452 [WARNING] 服务器 websocket-server 已禁用，跳过连接
2025-07-25 06:58:57,452 [INFO] 所有服务器初始化完成

🤖 MCP Client 启动成功，输入你的问题，输入 'exit' 退出：
💡 特殊命令:
   - /history: 查看最近的对话历史
   - /stats: 查看工具使用统计
   - /clear: 清除当前会话记录
   - /export: 导出历史记录

🧑 你: 纽约天气

🤖 AI: 为了获取纽约的天气预报，我将使用get_forecast函数。首先，我需要纽约的纬度和经度坐标。纽约市的大致地理中心位于40.7128° N, 74.0060° W。我现在就用这些坐标来调用get_forecast函数。
🔧 调用 get_forecast: [TextContent(type='text', text='\nOvernight:\nTemperature: 77°F\nWind: 10 mph SW\nForecast: Mostly clear, with a low around 77. Southwest wind around 10 mph.\n\n---\n\nFriday:\nTemperature: 93°F\nWind: 10 mph W\nForecast: Showers and thunderstorms likely after 2pm. Mostly sunny. High near 93, with temperatures falling to around 91 in the afternoon. Heat index values as high as 101. West wind around 10 mph. Chance of precipitation is 60%. New rainfall amounts between a quarter and half of an inch possible.\n\n---\n\nFriday Night:\nTemperature: 77°F\nWind: 7 to 10 mph NW\nForecast: Showers and thunderstorms likely before 11pm. Partly cloudy. Low around 77, with temperatures rising to around 79 overnight. Heat index values as high as 96. Northwest wind 7 to 10 mph. Chance of precipitation is 60%. New rainfall amounts between a quarter and half of an inch possible.\n\n---\n\nSaturday:\nTemperature: 82°F\nWind: 10 mph E\nForecast: Partly sunny. High near 82, with temperatures falling to around 79 in the afternoon. East wind around 10 mph.\n\n---\n\nSaturday Night:\nTemperature: 74°F\nWind: 5 to 10 mph S\nForecast: A slight chance of showers and thunderstorms after 5am. Mostly cloudy. Low around 74, with temperatures rising to around 76 overnight. South wind 5 to 10 mph. Chance of precipitation is 20%.\n', annotations=None, meta=None)]
这是纽约接下来几天的天气预报：

- **今晚**:
  - 温度: 77°F
  - 风速: 西南风约10英里/小时
  - 预报: 大部分时间晴朗，最低温度在77°F左右。

- **周五**:
  - 温度: 93°F
  - 风速: 西风约10英里/小时
  - 预报: 下午2点后可能有阵雨和雷暴。大部分时间阳光明媚。最高温度接近93°F，体感温度可高达101°F。降雨概率为60%，新降水量可能在四分之一到半英寸之间。

- **周五晚上**:
  - 温度: 77°F
  - 风速: 西北风7至10英里/小时
  - 预报: 晚上11点前可能有阵雨和雷暴。部分多云。最低温度在77°F左右，夜间温度可能升至79°F，体感温度可高达96°F。降雨概率为60%。

- **周六**:
  - 温度: 82°F
  - 风速: 东风约10英里/小时
  - 预报: 部分多云，最高温度接近82°F，下午温度会降至79°F左右。

- **周六晚上**:
  - 温度: 74°F
  - 风速: 南风5至10英里/小时
  - 预报: 凌晨5点后有可能出现阵雨和雷暴。大部分时间多云，最低温度在74°F左右，夜间温度可能升至76°F。降雨概率为20%。

请注意这些预报可能会发生变化，并且准备好应对可能出现的降水。

🧑 你: 
```  

## License

MIT
