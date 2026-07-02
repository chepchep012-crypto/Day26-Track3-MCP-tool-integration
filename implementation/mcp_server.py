"""FastMCP server exposing a small SQLite database.

Tools: search, insert, aggregate
Resources: schema://database, schema://table/{table_name}
"""

import json

from fastmcp import FastMCP

from db import SQLiteAdapter, ValidationError
from init_db import create_database

mcp = FastMCP("SQLite Lab MCP Server")

# Make sure the database exists before the adapter is used.
create_database()
adapter = SQLiteAdapter()


@mcp.tool(
    name="search",
    description=(
        "Search rows in a table with optional column selection, filters, "
        "ordering, and pagination. filters is a list of "
        "{column, operator, value} objects. Supported operators: "
        "=, !=, >, >=, <, <=, like, in."
    ),
)
def search(table: str, filters: list = None, columns: list = None,
           limit: int = 20, offset: int = 0, order_by: str = None,
           descending: bool = False):
    try:
        return adapter.search(
            table=table,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool(
    name="insert",
    description="Insert a new row into a table. values is a dict of column -> value.",
)
def insert(table: str, values: dict):
    try:
        return adapter.insert(table=table, values=values)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool(
    name="aggregate",
    description=(
        "Compute an aggregate metric (count, avg, sum, min, max) over a table, "
        "with optional filters and group_by."
    ),
)
def aggregate(table: str, metric: str, column: str = None,
              filters: list = None, group_by: str = None):
    try:
        return adapter.aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


@mcp.resource("schema://database")
def database_schema():
    """Full schema snapshot for every table in the database."""
    return json.dumps(adapter.get_database_schema(), indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str):
    """Schema for a single table."""
    try:
        return json.dumps(adapter.get_table_schema(table_name), indent=2)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


if __name__ == "__main__":
    mcp.run()
