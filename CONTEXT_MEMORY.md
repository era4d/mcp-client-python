# Context Memory Feature

## Overview

This project has successfully integrated a context memory feature, which can record and manage conversation history, tool call records, and provide intelligent context retrieval capabilities.

## Core Features

### 1. Conversation History Recording
- Automatically records each user input and AI response
- Includes timestamps and session IDs
- Supports association of tool call information
- Persistent storage in JSON files

### 2. Tool Call Records
- Records detailed information of all tool calls
- Includes input parameters, output results, and success status
- Error messages are recorded for debugging
- Provides tool usage statistical analysis

### 3. Intelligent Context Retrieval
- Context retrieval based on keyword matching
- Supports limiting the number of returned conversation turns
- Automatically constructs messages containing historical context

### 4. Statistical Analysis
- Total tool call statistics
- Success rate calculation
- Detailed usage statistics for each tool
- Last usage time record

## New Interactive Commands

In the client, users can use the following special commands:

- `/history` - View recent conversation history
- `/stats` - View tool usage statistics
- `/clear` - Clear current session records
- `/export` - Export history records to a file

## Technical Implementation

### Core Module

#### ContextManager Class
Location: `core/context_manager.py`

Main methods:
- `add_conversation_turn()` - Add conversation record
- `add_tool_call_record()` - Add tool call record
- `get_relevant_context()` - Get relevant context
- `get_tool_usage_stats()` - Get statistics
- `export_history()` - Export history records
- `clear_session()` - Clear session records

#### Data Structures

**ConversationTurn** - Conversation turn record
```python
@dataclass
class ConversationTurn:
    timestamp: str
    user_input: str
    ai_response: str
    tool_calls: Optional[List[Dict]] = None
    session_id: str = ""
```

**ToolCallRecord** - Tool call record
```python
@dataclass
class ToolCallRecord:
    timestamp: str
    tool_name: str
    input_params: Dict
    output_result: str
    success: bool
    error_message: Optional[str] = None
```

### Integration Method

1. **MCPClient Initialization**
   - Create a ContextManager instance in the `__init__` method
   - Set the context file path and maximum history record count

2. **process_query Method Enhancement**
   - Retrieve relevant context and construct messages containing history
   - Record tool call information
   - Save records after the conversation ends

3. **chat_loop Method Enhancement**
   - Add special command handling
   - Ensure conversation is recorded even in case of exceptions

## Configuration Options

```python
context_manager = ContextManager(
    context_file="logs/context_history.json",  # History file path
    max_history=50  # Maximum number of history records
)
```

## File Structure

```
logs/
├── context_history.json          # Main context history file
├── history_export_*.json         # Exported history record files
└── mcp_client.log                # Application log
```

## Testing and Validation

The project includes two test files:

1. `test_context.py` - Full integration test
2. `test_context_simple.py` - Context manager unit test

Run tests:
```bash
python test_context_simple.py
```

## Example Output

### Tool Usage Statistics
```
📊 Tool Usage Statistics:
Total calls: 2
Success rate: 50.0%

Detailed statistics for each tool:
  web_search: 1 call, 100.0% success rate, last used: 2025-07-09 04:34:12
  file_read: 1 call, 0.0% success rate, last used: 2025-07-09 04:34:12
```

### Exported History Record
```json
{
  "export_time": "2025-07-09T04:34:12.118972",
  "session_id": "20250709_043412",
  "conversations": [
    {
      "timestamp": "2025-07-09T04:34:12.093201",
      "user_input": "Hello, please help me calculate 1+1",
      "ai_response": "Hello! 1+1 equals 2.",
      "tool_calls": []
    }
  ],
  "tool_calls": [
    {
      "timestamp": "2025-07-09T04:34:12.093820",
      "tool_name": "web_search",
      "input_params": {"query": "Python tutorial"},
      "output_result": "Found relevant Python tutorial links",
      "success": true
    }
  ],
  "stats": {
    "total_calls": 2,
    "success_rate": 0.5
  }
}
```