"""
Mem0 MCP Server - Model Context Protocol Server for Universal AI Access

This module implements an MCP server that exposes Mem0 memories to any 
MCP-compatible AI client (Claude Desktop, Cursor IDE, Continue.dev, etc.)

MCP is Anthropic's open standard for AI tool integration, functioning as
a "USB-C port for AI" - a universal interface for memory access.

Usage:
    # Run as standalone server
    python -m mem0.mcp_server
    
    # Or programmatically
    from mem0.mcp_server import Mem0MCPServer
    server = Mem0MCPServer()
    server.run()

Configuration for Claude Desktop (claude_desktop_config.json):
    {
        "mcpServers": {
            "mem0": {
                "command": "python",
                "args": ["-m", "mem0.mcp_server"]
            }
        }
    }
"""

import json
import sys
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

# MCP uses JSON-RPC 2.0 over stdio
class Mem0MCPServer:
    """
    MCP Server exposing Mem0 memory operations.
    
    Implements the Model Context Protocol to allow any MCP client
    (Claude, Cursor, Continue, etc.) to access user memories.
    
    Tools exposed:
    - memories_add: Add a new memory
    - memories_search: Search memories semantically
    - memories_get: Get a specific memory by ID
    - memories_list: List all memories for a user
    - memories_delete: Delete a memory
    - memories_time_travel: Get memories as they were at a past time
    """
    
    def __init__(self):
        self.name = "mem0"
        self.version = "1.0.0"
        self._memory = None
        self._temporal = None
    
    @property
    def memory(self):
        """Lazy load Memory to avoid import errors."""
        if self._memory is None:
            from mem0.memory.main import Memory
            self._memory = Memory()
        return self._memory
    
    @property
    def temporal(self):
        """Lazy load TemporalMemory."""
        if self._temporal is None:
            from mem0.temporal import TemporalMemory
            self._temporal = TemporalMemory()
        return self._temporal
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return the list of available MCP tools."""
        return [
            {
                "name": "memories_add",
                "description": "Add a new memory for a user. Use this to store facts, preferences, or important information about the user.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The memory content to store"
                        },
                        "user_id": {
                            "type": "string",
                            "description": "User identifier"
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Optional metadata (tags, categories, etc.)"
                        }
                    },
                    "required": ["content", "user_id"]
                }
            },
            {
                "name": "memories_search",
                "description": "Search memories semantically. Returns the most relevant memories for a query.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "user_id": {
                            "type": "string",
                            "description": "User identifier"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query", "user_id"]
                }
            },
            {
                "name": "memories_list",
                "description": "List all memories for a user.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "User identifier"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 20)",
                            "default": 20
                        }
                    },
                    "required": ["user_id"]
                }
            },
            {
                "name": "memories_get",
                "description": "Get a specific memory by its ID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "Memory UUID"
                        }
                    },
                    "required": ["memory_id"]
                }
            },
            {
                "name": "memories_delete",
                "description": "Delete a specific memory.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "Memory UUID to delete"
                        }
                    },
                    "required": ["memory_id"]
                }
            },
            {
                "name": "memories_time_travel",
                "description": "Get memories as they existed at a past point in time. Useful for questions like 'What did I know last week?'",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "User identifier"
                        },
                        "days_ago": {
                            "type": "integer",
                            "description": "How many days in the past to query"
                        }
                    },
                    "required": ["user_id", "days_ago"]
                }
            }
        ]
    
    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool and return the result."""
        try:
            if name == "memories_add":
                result = self.memory.add(
                    arguments["content"],
                    user_id=arguments["user_id"],
                    metadata=arguments.get("metadata", {})
                )
                return {"success": True, "result": result}
            
            elif name == "memories_search":
                results = self.memory.search(
                    arguments["query"],
                    user_id=arguments["user_id"],
                    limit=arguments.get("limit", 5)
                )
                return {"results": results}
            
            elif name == "memories_list":
                results = self.memory.get_all(
                    user_id=arguments["user_id"],
                    limit=arguments.get("limit", 20)
                )
                return {"memories": results}
            
            elif name == "memories_get":
                result = self.memory.get(arguments["memory_id"])
                return {"memory": result}
            
            elif name == "memories_delete":
                self.memory.delete(arguments["memory_id"])
                return {"success": True, "deleted": arguments["memory_id"]}
            
            elif name == "memories_time_travel":
                results = self.temporal.get_memories_at(
                    arguments["user_id"],
                    days_ago=arguments["days_ago"]
                )
                return {"memories": results, "as_of": f"{arguments['days_ago']} days ago"}
            
            else:
                return {"error": f"Unknown tool: {name}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming JSON-RPC request."""
        method = request.get("method", "")
        request_id = request.get("id")
        params = request.get("params", {})
        
        result = None
        error = None
        
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": self.name,
                        "version": self.version
                    }
                }
            
            elif method == "tools/list":
                result = {"tools": self.get_tools()}
            
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                tool_result = self.handle_tool_call(tool_name, tool_args)
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(tool_result, indent=2, default=str)
                        }
                    ]
                }
            
            elif method == "notifications/initialized":
                # Client is ready, no response needed
                return None
            
            else:
                error = {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
                
        except Exception as e:
            error = {
                "code": -32603,
                "message": str(e)
            }
        
        # Build response
        response = {"jsonrpc": "2.0", "id": request_id}
        if error:
            response["error"] = error
        else:
            response["result"] = result
        
        return response
    
    def run(self):
        """Run the MCP server, reading from stdin and writing to stdout."""
        print(f"[mem0-mcp] Starting Mem0 MCP Server v{self.version}", file=sys.stderr)
        
        while True:
            try:
                # Read a line from stdin
                line = sys.stdin.readline()
                if not line:
                    break
                
                # Parse JSON-RPC request
                request = json.loads(line.strip())
                
                # Handle the request
                response = self.handle_request(request)
                
                # Send response (if any)
                if response:
                    print(json.dumps(response), flush=True)
                    
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {e}"
                    }
                }
                print(json.dumps(error_response), flush=True)
            except Exception as e:
                print(f"[mem0-mcp] Error: {e}", file=sys.stderr)


def main():
    """Entry point for running as a module."""
    server = Mem0MCPServer()
    server.run()


if __name__ == "__main__":
    main()
