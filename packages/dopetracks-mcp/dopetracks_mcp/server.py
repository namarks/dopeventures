"""
Dopetracks MCP Server

A Model Context Protocol server for creating Spotify playlists from iMessage chats.

Usage:
    python -m dopetracks_mcp.server

Or add to ~/.claude/mcp_servers.json:
{
    "dopetracks": {
        "command": "python",
        "args": ["-m", "dopetracks_mcp.server"],
        "cwd": "/path/to/packages/dopetracks-mcp"
    }
}
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

from .tools import chat_tools, spotify_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create the MCP server
server = Server("dopetracks")


def _json_result(data: Dict[str, Any]) -> CallToolResult:
    """Convert a dict to a CallToolResult with JSON text content."""
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(data, indent=2, default=str))]
    )


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List all available tools."""
    return [
        # Chat tools
        Tool(
            name="search_chats",
            description=(
                "Search for iMessage chats by name, or find chats containing Spotify links. "
                "Use this to find the chat_id needed for other tools."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term for chat name or participant. Leave empty to list all chats.",
                    },
                    "with_spotify_links": {
                        "type": "boolean",
                        "description": "If true, only return chats that contain Spotify links",
                        "default": False,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="get_messages",
            description=(
                "Get messages from a specific chat. Supports date filtering and text search."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "integer",
                        "description": "The chat ID from search_chats results",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum messages to return",
                        "default": 50,
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start of date range (ISO format, e.g., '2024-01-01')",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End of date range (ISO format, e.g., '2024-12-31')",
                    },
                    "search": {
                        "type": "string",
                        "description": "Filter messages containing this text",
                    },
                },
                "required": ["chat_id"],
            },
        ),
        Tool(
            name="extract_spotify_links",
            description=(
                "Extract all Spotify URLs from a chat within a date range. "
                "Returns a list of Spotify track/album/playlist URLs found in messages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "integer",
                        "description": "The chat ID from search_chats results",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start of date range (ISO format). Defaults to 30 days ago.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End of date range (ISO format). Defaults to now.",
                    },
                },
                "required": ["chat_id"],
            },
        ),
        Tool(
            name="get_chat_stats",
            description=(
                "Get statistics about Spotify link sharing in a chat. "
                "Shows who shared the most songs, unique track count, etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "integer",
                        "description": "The chat ID from search_chats results",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start of date range (ISO format). Defaults to 30 days ago.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End of date range (ISO format). Defaults to now.",
                    },
                },
                "required": ["chat_id"],
            },
        ),
        # Spotify tools
        Tool(
            name="spotify_auth_status",
            description=(
                "Check if the user is authenticated with Spotify. "
                "Returns authentication status and user info if logged in."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="spotify_login",
            description=(
                "Initiate Spotify OAuth authentication. Opens a browser for the user to log in. "
                "Must be called before creating playlists if not already authenticated."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="create_playlist",
            description=(
                "Create a Spotify playlist from a list of track URLs. "
                "If a playlist with the same name exists, new tracks are added (duplicates skipped)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the playlist",
                    },
                    "track_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of Spotify track URLs",
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Whether the playlist should be public",
                        "default": True,
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description for the playlist",
                    },
                },
                "required": ["name", "track_urls"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle tool calls."""
    logger.info(f"Tool call: {name} with args: {arguments}")

    try:
        # Chat tools
        if name == "search_chats":
            result = chat_tools.search_chats(
                query=arguments.get("query"),
                with_spotify_links=arguments.get("with_spotify_links", False),
                limit=arguments.get("limit", 20),
            )
            return _json_result(result)

        elif name == "get_messages":
            result = chat_tools.get_messages(
                chat_id=arguments["chat_id"],
                limit=arguments.get("limit", 50),
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
                search=arguments.get("search"),
            )
            return _json_result(result)

        elif name == "extract_spotify_links":
            result = chat_tools.extract_spotify_links(
                chat_id=arguments["chat_id"],
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
            )
            return _json_result(result)

        elif name == "get_chat_stats":
            result = chat_tools.get_chat_stats(
                chat_id=arguments["chat_id"],
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
            )
            return _json_result(result)

        # Spotify tools
        elif name == "spotify_auth_status":
            result = spotify_tools.spotify_auth_status()
            return _json_result(result)

        elif name == "spotify_login":
            result = spotify_tools.spotify_login()
            return _json_result(result)

        elif name == "create_playlist":
            result = spotify_tools.create_playlist(
                name=arguments["name"],
                track_urls=arguments["track_urls"],
                public=arguments.get("public", True),
                description=arguments.get("description"),
            )
            return _json_result(result)

        else:
            return _json_result({"error": f"Unknown tool: {name}"})

    except Exception as e:
        logger.exception(f"Error in tool {name}")
        return _json_result({"error": str(e)})


async def run_server():
    """Run the MCP server."""
    logger.info("Starting Dopetracks MCP server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for the server."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
