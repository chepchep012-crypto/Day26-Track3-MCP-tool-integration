"""Repeatable verification script for the SQLite Lab MCP server.

Connects an in-memory FastMCP client to mcp_server.py and walks through
the checklist from the lab README:
  1. server starts
  2. tools are discoverable
  3. schema resource is discoverable
  4. valid tool calls return useful results
  5. invalid tool calls return clear errors

Run with: python verify_server.py
"""

import asyncio
import json

from fastmcp import Client

from mcp_server import mcp


def _print_header(title):
    print(f"\n=== {title} ===")


async def main():
    async with Client(mcp) as client:
        _print_header("1. Tool discovery")
        tools = await client.list_tools()
        tool_names = sorted(t.name for t in tools)
        print("Discovered tools:", tool_names)
        assert tool_names == ["aggregate", "insert", "search"], tool_names

        _print_header("2. Resource discovery")
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        print("Resources:", [r.uri for r in resources])
        print("Resource templates:", [t.uriTemplate for t in templates])

        _print_header("3. Valid call: search students in cohort A1")
        result = await client.call_tool(
            "search",
            {"table": "students", "filters": [{"column": "cohort", "operator": "=", "value": "A1"}]},
        )
        print(json.dumps(result.data, indent=2))
        assert result.data["count"] > 0

        _print_header("4. Valid call: insert a new student")
        result = await client.call_tool(
            "insert",
            {
                "table": "students",
                "values": {"name": "Test Student", "cohort": "A1", "email": "test.student@example.com"},
            },
        )
        print(json.dumps(result.data, indent=2))
        assert result.data["id"] is not None

        _print_header("5. Valid call: count rows in students")
        result = await client.call_tool("aggregate", {"table": "students", "metric": "count"})
        print(json.dumps(result.data, indent=2))

        _print_header("6. Valid call: average score by cohort")
        result = await client.call_tool(
            "aggregate",
            {
                "table": "enrollments",
                "metric": "avg",
                "column": "score",
                "group_by": "course_id",
            },
        )
        print(json.dumps(result.data, indent=2))

        _print_header("7. Read schema://database")
        contents = await client.read_resource("schema://database")
        print(contents[0].text[:300], "...")

        _print_header("8. Read schema://table/students")
        contents = await client.read_resource("schema://table/students")
        print(contents[0].text)

        _print_header("9. Invalid call: unknown table")
        try:
            await client.call_tool("search", {"table": "not_a_table"})
            print("ERROR: expected failure, but call succeeded")
        except Exception as exc:
            print("Got expected error:", exc)

        _print_header("10. Invalid call: unknown column filter")
        try:
            await client.call_tool(
                "search", {"table": "students", "filters": [{"column": "nope", "operator": "=", "value": 1}]}
            )
            print("ERROR: expected failure, but call succeeded")
        except Exception as exc:
            print("Got expected error:", exc)

        _print_header("11. Invalid call: bad operator")
        try:
            await client.call_tool(
                "search", {"table": "students", "filters": [{"column": "cohort", "operator": "DROP", "value": 1}]}
            )
            print("ERROR: expected failure, but call succeeded")
        except Exception as exc:
            print("Got expected error:", exc)

        _print_header("12. Invalid call: empty insert")
        try:
            await client.call_tool("insert", {"table": "students", "values": {}})
            print("ERROR: expected failure, but call succeeded")
        except Exception as exc:
            print("Got expected error:", exc)

        _print_header("13. Invalid call: bad aggregate metric")
        try:
            await client.call_tool("aggregate", {"table": "students", "metric": "median"})
            print("ERROR: expected failure, but call succeeded")
        except Exception as exc:
            print("Got expected error:", exc)

        print("\nAll verification steps completed.")


if __name__ == "__main__":
    asyncio.run(main())
