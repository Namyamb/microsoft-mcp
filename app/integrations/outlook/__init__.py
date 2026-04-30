"""
Outlook (Microsoft Graph) integration.

Exports a small registry of "tools" (callables) that can be wired into an MCP server.
"""

from .registry import TOOL_REGISTRY, get_outlook_tools

__all__ = ["TOOL_REGISTRY", "get_outlook_tools"]

