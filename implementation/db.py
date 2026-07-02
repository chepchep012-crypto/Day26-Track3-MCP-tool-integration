"""SQLite database adapter used by the MCP server.

Responsible for opening connections, inspecting schema, and running
validated search / insert / aggregate operations. All SQL is built with
bound parameters; identifiers (table/column names) are validated against
the live schema instead of being interpolated from raw user input.
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "lab.db"

SUPPORTED_OPERATORS = {
    "=": "=",
    "!=": "!=",
    ">": ">",
    ">=": ">=",
    "<": "<",
    "<=": "<=",
    "like": "LIKE",
    "in": "IN",
}

SUPPORTED_AGGREGATES = {"count", "avg", "sum", "min", "max"}


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


class SQLiteAdapter:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_tables(self):
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table):
        self._validate_table(table)
        with self.connect() as conn:
            rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        return [
            {
                "name": row["name"],
                "type": row["type"],
                "not_null": bool(row["notnull"]),
                "default": row["dflt_value"],
                "primary_key": bool(row["pk"]),
            }
            for row in rows
        ]

    def get_database_schema(self):
        return {table: self.get_table_schema(table) for table in self.list_tables()}

    # -- validation helpers -------------------------------------------------

    def _validate_table(self, table):
        if table not in self.list_tables():
            raise ValidationError(f"Unknown table: {table!r}")

    def _column_names(self, table):
        return [col["name"] for col in self.get_table_schema(table)]

    def _validate_columns(self, table, columns):
        valid = set(self._column_names(table))
        unknown = [c for c in columns if c not in valid]
        if unknown:
            raise ValidationError(f"Unknown column(s) for {table!r}: {unknown}")

    # -- operations -----------------------------------------------------

    def search(self, table, columns=None, filters=None, limit=20, offset=0,
               order_by=None, descending=False):
        self._validate_table(table)
        valid_columns = self._column_names(table)

        if columns:
            self._validate_columns(table, columns)
            select_clause = ", ".join(f'"{c}"' for c in columns)
        else:
            select_clause = "*"

        where_clause, params = self._build_where(table, filters)

        order_clause = ""
        if order_by is not None:
            self._validate_columns(table, [order_by])
            direction = "DESC" if descending else "ASC"
            order_clause = f' ORDER BY "{order_by}" {direction}'

        if not isinstance(limit, int) or limit < 0:
            raise ValidationError("limit must be a non-negative integer")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset must be a non-negative integer")

        sql = f'SELECT {select_clause} FROM "{table}"{where_clause}{order_clause} LIMIT ? OFFSET ?'
        params = params + [limit, offset]

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            total = conn.execute(
                f'SELECT COUNT(*) AS n FROM "{table}"{where_clause}', params[:-2]
            ).fetchone()["n"]

        return {
            "rows": [dict(row) for row in rows],
            "count": len(rows),
            "total": total,
            "limit": limit,
            "offset": offset,
            "columns": valid_columns,
        }

    def insert(self, table, values):
        self._validate_table(table)
        if not values:
            raise ValidationError("insert requires a non-empty values dict")
        self._validate_columns(table, list(values.keys()))

        columns = list(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        column_clause = ", ".join(f'"{c}"' for c in columns)
        sql = f'INSERT INTO "{table}" ({column_clause}) VALUES ({placeholders})'

        with self.connect() as conn:
            cursor = conn.execute(sql, [values[c] for c in columns])
            conn.commit()
            new_id = cursor.lastrowid
            row = conn.execute(f'SELECT * FROM "{table}" WHERE rowid = ?', (new_id,)).fetchone()

        return {"inserted": dict(row) if row else values, "id": new_id}

    def aggregate(self, table, metric, column=None, filters=None, group_by=None):
        self._validate_table(table)
        metric = (metric or "").lower()
        if metric not in SUPPORTED_AGGREGATES:
            raise ValidationError(
                f"Unsupported aggregate metric: {metric!r}. Supported: {sorted(SUPPORTED_AGGREGATES)}"
            )

        if metric == "count":
            expr = "COUNT(*)" if not column else f'COUNT("{self._validated_column(table, column)}")'
        else:
            if not column:
                raise ValidationError(f"metric {metric!r} requires a column")
            expr = f'{metric.upper()}("{self._validated_column(table, column)}")'

        group_clause = ""
        group_select = ""
        if group_by is not None:
            self._validate_columns(table, [group_by])
            group_select = f'"{group_by}" AS "{group_by}", '
            group_clause = f' GROUP BY "{group_by}"'

        where_clause, params = self._build_where(table, filters)

        sql = f'SELECT {group_select}{expr} AS value FROM "{table}"{where_clause}{group_clause}'

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return {"metric": metric, "column": column, "group_by": group_by,
                "rows": [dict(row) for row in rows]}

    def _validated_column(self, table, column):
        self._validate_columns(table, [column])
        return column

    def _build_where(self, table, filters):
        if not filters:
            return "", []

        clauses = []
        params = []
        for f in filters:
            column = f.get("column")
            operator = f.get("operator", "=")
            value = f.get("value")

            self._validate_columns(table, [column])
            op_key = str(operator).lower()
            if op_key not in SUPPORTED_OPERATORS:
                raise ValidationError(
                    f"Unsupported filter operator: {operator!r}. "
                    f"Supported: {sorted(SUPPORTED_OPERATORS)}"
                )
            sql_op = SUPPORTED_OPERATORS[op_key]

            if op_key == "in":
                if not isinstance(value, (list, tuple)) or not value:
                    raise ValidationError("'in' operator requires a non-empty list value")
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f'"{column}" IN ({placeholders})')
                params.extend(value)
            else:
                clauses.append(f'"{column}" {sql_op} ?')
                params.append(value)

        return " WHERE " + " AND ".join(clauses), params
