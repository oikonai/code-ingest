#!/usr/bin/env python3
"""
One-off script to test code-ingest-mcp (e.g. with Docker running).

Usage (from repo root):
  python scripts/test_mcp_client.py
  # or: cd mcp && uv run python ../scripts/test_mcp_client.py

Requires: Docker stack up with MCP on port 8001, and fastmcp in path.
"""
import asyncio
import json
import sys

MCP_URL = "http://localhost:8001/mcp"


async def main():
    try:
        from fastmcp import Client
    except ImportError:
        print("Install fastmcp first: pip install fastmcp  (or run 'make install' from repo root)")
        sys.exit(1)

    print(f"Connecting to {MCP_URL} ...")
    async with Client(MCP_URL) as client:
        # List tools
        tools = await client.list_tools()
        print("\n--- Tools ---")
        for t in tools:
            print(f"  {t.name}: {getattr(t, 'description', '')[:60]}...")

        def _tool_text(out):
            if not getattr(out, "content", None):
                return str(out)
            part = out.content[0]
            return getattr(part, "text", str(part))

        # List collections
        print("\n--- list_collections() ---")
        try:
            out = await client.call_tool("list_collections", {})
            text = _tool_text(out)
            try:
                data = json.loads(text)
                print(json.dumps(data, indent=2)[:2500])
            except json.JSONDecodeError:
                print(text[:2500])
        except Exception as e:
            print(f"  Error: {e}")

        # Semantic search about repository config / repositories.yaml
        print("\n--- semantic_search(query='repository configuration repos_base_dir repositories yaml') ---")
        try:
            out = await client.call_tool(
                "semantic_search",
                {
                    "query": "repository configuration repos_base_dir repositories yaml",
                    "limit": 5,
                    "score_threshold": 0.3,
                },
            )
            text = _tool_text(out)
            try:
                data = json.loads(text)
                print(json.dumps(data, indent=2)[:4000])
            except json.JSONDecodeError:
                print(text[:4000])
        except Exception as e:
            print(f"  Error: {e}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
