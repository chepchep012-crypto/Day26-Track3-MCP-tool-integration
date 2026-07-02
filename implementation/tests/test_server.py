"""Automated tests for the SQLite Lab MCP server.

Uses fastmcp's in-memory Client (no subprocess/transport needed) to
exercise tool discovery, resource discovery, valid calls, and error
handling. Each test gets a fresh temporary database.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import Client

import db as db_module
import mcp_server
from init_db import create_database


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_lab.db"
    create_database(db_path=db_path, reset=True)
    monkeypatch.setattr(mcp_server, "adapter", db_module.SQLiteAdapter(db_path))
    return Client(mcp_server.mcp)


@pytest.mark.asyncio
async def test_tools_are_discoverable(client):
    async with client as c:
        tools = await c.list_tools()
        names = sorted(t.name for t in tools)
        assert names == ["aggregate", "insert", "search"]


@pytest.mark.asyncio
async def test_resources_are_discoverable(client):
    async with client as c:
        resources = await c.list_resources()
        templates = await c.list_resource_templates()
        assert any(str(r.uri) == "schema://database" for r in resources)
        assert any(t.uriTemplate == "schema://table/{table_name}" for t in templates)


@pytest.mark.asyncio
async def test_search_filters_and_pagination(client):
    async with client as c:
        result = await c.call_tool(
            "search",
            {"table": "students", "filters": [{"column": "cohort", "operator": "=", "value": "A1"}], "limit": 2},
        )
        assert result.data["count"] <= 2
        assert all(row["cohort"] == "A1" for row in result.data["rows"])


@pytest.mark.asyncio
async def test_insert_returns_payload(client):
    async with client as c:
        result = await c.call_tool(
            "insert",
            {"table": "students", "values": {"name": "New Kid", "cohort": "A1", "email": "new.kid@example.com"}},
        )
        assert result.data["inserted"]["name"] == "New Kid"
        assert result.data["id"] is not None


@pytest.mark.asyncio
async def test_aggregate_count(client):
    async with client as c:
        result = await c.call_tool("aggregate", {"table": "students", "metric": "count"})
        assert result.data["rows"][0]["value"] == 5


@pytest.mark.asyncio
async def test_aggregate_avg_group_by(client):
    async with client as c:
        result = await c.call_tool(
            "aggregate",
            {"table": "enrollments", "metric": "avg", "column": "score", "group_by": "course_id"},
        )
        assert len(result.data["rows"]) == 3


@pytest.mark.asyncio
async def test_database_schema_resource(client):
    async with client as c:
        contents = await c.read_resource("schema://database")
        assert "students" in contents[0].text
        assert "courses" in contents[0].text


@pytest.mark.asyncio
async def test_table_schema_resource(client):
    async with client as c:
        contents = await c.read_resource("schema://table/students")
        assert "cohort" in contents[0].text


@pytest.mark.asyncio
async def test_search_unknown_table_rejected(client):
    async with client as c:
        with pytest.raises(Exception, match="Unknown table"):
            await c.call_tool("search", {"table": "not_a_table"})


@pytest.mark.asyncio
async def test_search_unknown_column_rejected(client):
    async with client as c:
        with pytest.raises(Exception, match="Unknown column"):
            await c.call_tool(
                "search", {"table": "students", "filters": [{"column": "nope", "operator": "=", "value": 1}]}
            )


@pytest.mark.asyncio
async def test_search_bad_operator_rejected(client):
    async with client as c:
        with pytest.raises(Exception, match="Unsupported filter operator"):
            await c.call_tool(
                "search", {"table": "students", "filters": [{"column": "cohort", "operator": "DROP", "value": 1}]}
            )


@pytest.mark.asyncio
async def test_insert_empty_values_rejected(client):
    async with client as c:
        with pytest.raises(Exception, match="non-empty"):
            await c.call_tool("insert", {"table": "students", "values": {}})


@pytest.mark.asyncio
async def test_aggregate_bad_metric_rejected(client):
    async with client as c:
        with pytest.raises(Exception, match="Unsupported aggregate metric"):
            await c.call_tool("aggregate", {"table": "students", "metric": "median"})


@pytest.mark.asyncio
async def test_table_schema_unknown_table_rejected(client):
    async with client as c:
        with pytest.raises(Exception, match="Unknown table"):
            await c.read_resource("schema://table/not_a_table")
