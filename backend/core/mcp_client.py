import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import os

class MCPClientManager:
    def __init__(self):
        self.sessions = {}
        self.exit_stacks = {}
        
    async def connect_to_server(self, server_name: str, command: str, args: list[str], env: dict = None):
        print(f"Connecting to MCP server '{server_name}' via {command} {' '.join(args)}...")
        exit_stack = AsyncExitStack()
        self.exit_stacks[server_name] = exit_stack
        
        # Merge environment variables if provided
        server_env = os.environ.copy()
        if env:
            server_env.update(env)
            
        server_params = StdioServerParameters(command=command, args=args, env=server_env)
        
        try:
            stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
            read, write = stdio_transport
            
            session = await exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[server_name] = session
            print(f"Successfully connected to MCP server '{server_name}'.")
        except Exception as e:
            print(f"Failed to connect to MCP server '{server_name}': {e}")
            await exit_stack.aclose()
            if server_name in self.exit_stacks:
                del self.exit_stacks[server_name]
        
    async def get_all_tools(self):
        all_tools = []
        for name, session in self.sessions.items():
            try:
                res = await session.list_tools()
                for t in res.tools:
                    all_tools.append({
                        "server": name,
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.inputSchema
                    })
            except Exception as e:
                print(f"Failed to get tools from {name}: {e}")
        return all_tools
        
    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        if server_name not in self.sessions:
            return f"Error: MCP Server '{server_name}' not found or not connected."
        
        session = self.sessions[server_name]
        try:
            res = await session.call_tool(tool_name, arguments)
            # res.content is a list of TextContent, ImageContent, etc.
            text_outputs = [c.text for c in res.content if hasattr(c, 'text')]
            return "\n".join(text_outputs) if text_outputs else "Tool executed successfully (no text output)."
        except Exception as e:
            return f"Error executing tool '{tool_name}' on '{server_name}': {e}"
            
    async def cleanup(self):
        for name, stack in self.exit_stacks.items():
            print(f"Closing connection to MCP server '{name}'...")
            await stack.aclose()
        self.exit_stacks.clear()
        self.sessions.clear()

# Global singleton
mcp_manager = MCPClientManager()
