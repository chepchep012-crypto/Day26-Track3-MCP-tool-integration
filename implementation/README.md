# SQLite Lab MCP Server

A [FastMCP](https://gofastmcp.com/) server that exposes a small SQLite database
(`students`, `courses`, `enrollments`) through three MCP tools (`search`,
`insert`, `aggregate`) and two MCP resources (full schema + per-table schema).

## Project Structure

```text
implementation/
  db.py               # SQLiteAdapter: validation + safe SQL execution
  init_db.py           # creates lab.db and seeds sample data
  mcp_server.py         # FastMCP server: tools + resources
  verify_server.py       # repeatable end-to-end verification script
  start_inspector.sh      # launches MCP Inspector against this server
  .mcp.json.example       # example Claude Code client config
  requirements.txt
  tests/
    test_server.py       # automated pytest suite (in-memory MCP client)
```

## Setup

```bash
cd implementation
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python init_db.py           # creates lab.db with seed data
```

Re-run `python init_db.py --reset` at any time to wipe and recreate the
database from scratch.

## Data Model

- `students(id, name, cohort, email)`
- `courses(id, title, credits)`
- `enrollments(id, student_id, course_id, score)`

## Tools

### `search`

`search(table, filters=None, columns=None, limit=20, offset=0, order_by=None, descending=False)`

- `filters`: list of `{"column": ..., "operator": ..., "value": ...}`
- Supported operators: `=`, `!=`, `>`, `>=`, `<`, `<=`, `like`, `in`
- Returns `{rows, count, total, limit, offset, columns}`

Example: search all students in cohort `A1`

```json
{"table": "students", "filters": [{"column": "cohort", "operator": "=", "value": "A1"}]}
```

### `insert`

`insert(table, values)`

- `values`: dict of column -> value, must be non-empty
- Returns `{inserted, id}`

Example: insert a new student

```json
{"table": "students", "values": {"name": "Kim Do", "cohort": "A2", "email": "kim@example.com"}}
```

### `aggregate`

`aggregate(table, metric, column=None, filters=None, group_by=None)`

- `metric`: one of `count`, `avg`, `sum`, `min`, `max`
- Returns `{metric, column, group_by, rows}`

Example: average score by course

```json
{"table": "enrollments", "metric": "avg", "column": "score", "group_by": "course_id"}
```

## Resources

- `schema://database` — full schema (every table and column) as JSON
- `schema://table/{table_name}` — schema for a single table, e.g. `schema://table/students`

## Validation and Error Handling

All identifiers (table/column names) are checked against the live schema
before any SQL is built; values are always passed as bound parameters,
never string-concatenated. Rejected requests:

- unknown table names
- unknown column names
- unsupported filter operators
- invalid aggregate metrics or missing required column
- empty inserts

Invalid calls raise a clear error message back to the MCP client instead of
executing unsafe SQL.

## Testing and Verification

### Automated tests

```bash
python -m pytest tests/ -v
```

14 tests cover tool discovery, resource discovery, valid calls for all
three tools, both schema resources, and every validation/error case.

### End-to-end verification script

```bash
python verify_server.py
```

Spins up an in-memory MCP client against the server and walks through the
full checklist: server starts, tools discoverable, resources discoverable,
valid calls succeed, invalid calls fail with clear errors.

### MCP Inspector

```bash
./start_inspector.sh
```

or directly:

```bash
npx -y @modelcontextprotocol/inspector python mcp_server.py
```

Checklist to confirm in the Inspector UI:

- [ ] `search`, `insert`, `aggregate` tools appear with schemas
- [ ] `schema://database` and `schema://table/{table_name}` resources appear
- [ ] a valid `search` call (e.g. cohort `A1`) returns rows
- [ ] an invalid call (e.g. `table: "not_a_table"`) returns a clear error

## Client Configuration

### Claude Code

Copy `.mcp.json.example` to `.mcp.json` at the repo root (or add to your
existing config) and replace the path:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"],
      "env": {}
    }
  }
}
```

Then reference the schema resource directly in chat with
`@sqlite-lab:schema://database`.

### Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.sqlite_lab]
command = "python"
args = ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"]
```

### Gemini CLI

```bash
gemini mcp add sqlite-lab /ABSOLUTE/PATH/TO/python /ABSOLUTE/PATH/TO/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
gemini --allowed-mcp-server-names sqlite-lab --yolo -p "Use the sqlite-lab MCP server and show me the top 2 students by score."
```

## Demo Script (~2 minutes)

1. `python init_db.py --reset` — show a fresh database being created.
2. `python -m pytest tests/ -v` — show all 14 automated tests passing.
3. `./start_inspector.sh` (or a connected client) —
   - list tools: `search`, `insert`, `aggregate`
   - read `schema://database` and `schema://table/students`
   - call `search` for cohort `A1`
   - call `insert` for a new student
   - call `aggregate` with `metric=avg`, `column=score`, `group_by=course_id`
   - call `search` on a non-existent table and show the clear error

## Bonus Ideas (not implemented)

- SSE/HTTP transport with authentication
- PostgreSQL adapter behind the same interface as `SQLiteAdapter`
- Pagination metadata already returned by `search` (`count`/`total`/`limit`/`offset`) can be extended with cursor-based paging
