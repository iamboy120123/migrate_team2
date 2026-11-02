"""Deliberately restricted demo dialect; never presents SQLite as Oracle/Spark."""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing

from .storage import WorkspaceError

IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,29}$")


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise WorkspaceError(f"Unsafe SQL identifier: {value!r}")
    return value.upper()


def convert(sql):
    """Only the explicit sample grammar is supported; unknown functions fail closed."""
    if not isinstance(sql, str) or not re.match(r"^\s*SELECT\b", sql, re.I):
        raise WorkspaceError("Simulation supports one SELECT per task")
    # Strings are removed for structural inspection; quotes must be balanced.
    literals = re.findall(r"'(?:[^']|'')*'", sql)
    scrubbed = re.sub(r"'(?:[^']|'')*'", "''", sql)
    if scrubbed.count("'") != 2 * len(literals):
        raise WorkspaceError("Unbalanced SQL quotes")
    if any(x in scrubbed for x in (";", "--", "/*", "*/")):
        raise WorkspaceError("SQL comments and multi-statement inputs are outside the demo grammar")
    if re.search(r"\b(INSERT|DELETE|UPDATE|MERGE|DROP|ALTER|CREATE|TRUNCATE|ATTACH|PRAGMA|UNION|WITH|JOIN|OVER|LIMIT)\b", scrubbed, re.I):
        raise WorkspaceError("SQL construct outside the supported demo subset")
    functions = re.findall(r"\b([A-Za-z_]\w*)\s*\(", scrubbed)
    if set(x.upper() for x in functions) - {"UPPER", "LOWER", "IFNULL", "COALESCE", "CAST"}:
        raise WorkspaceError("Unsupported function: a real dialect review is required")
    if len(re.findall(r"\bFROM\b", scrubbed, re.I)) != 1:
        raise WorkspaceError("Exactly one source table is supported")
    if re.search(r"SELECT\s+\*", scrubbed, re.I):
        raise WorkspaceError("Explicit column list required")
    # Convert outside string literals so a literal such as 'IFNULL(x)' is preserved.
    chunks = re.split(r"('(?:[^']|'')*')", sql.strip())
    for index in range(0, len(chunks), 2):
        part = re.sub(r"`([A-Za-z][A-Za-z0-9_]*)`", r"\1", chunks[index])
        part = re.sub(r"\bIFNULL\s*\(", "COALESCE(", part, flags=re.I)
        part = re.sub(r"\bAS\s+STRING\b", "AS VARCHAR2(100)", part, flags=re.I)
        chunks[index] = part
    return "".join(chunks)


def make_dml(task, sql):
    table = identifier(task["target_table"])
    columns = [identifier(x) for x in task["target_columns"]]
    if not columns or len(columns) != len(set(columns)):
        raise WorkspaceError("Target columns must be nonempty and unique")
    strategy = task["strategy"]
    if strategy == "append":
        return [f"INSERT INTO {table} ({', '.join(columns)})\n{sql}"]
    if strategy == "overwrite":
        # Explicit configured decision; no automatic choice of destructive strategy.
        if task.get("overwrite_decision") != "truncate_all" or task.get("partitions"):
            raise WorkspaceError("Overwrite requires an explicit full-table decision and empty partitions")
        return [f"TRUNCATE TABLE {table}", f"INSERT INTO {table} ({', '.join(columns)})\n{sql}"]
    if strategy != "upsert":
        raise WorkspaceError(f"Unsupported strategy: {strategy}")
    keys = [identifier(x) for x in task.get("merge_keys", [])]
    if not keys or not set(keys) <= set(columns):
        raise WorkspaceError("Upsert needs merge keys present in target columns")
    updates = [x for x in columns if x not in keys]
    result = f"MERGE INTO {table} t\nUSING ({sql}) s\nON ({' AND '.join(f't.{k} = s.{k}' for k in keys)})"
    if updates:
        result += "\nWHEN MATCHED THEN UPDATE SET " + ", ".join(f"t.{x} = s.{x}" for x in updates)
    result += f"\nWHEN NOT MATCHED THEN INSERT ({', '.join(columns)})\nVALUES ({', '.join('s.' + x for x in columns)})"
    return [result]


def evaluate(sql, tables):
    """Evaluate a portable projection in an isolated in-memory SQLite fixture."""
    with closing(sqlite3.connect(":memory:")) as connection:
        for name, source in tables.items():
            name = identifier(name)
            columns = [identifier(x) for x in source["columns"]]
            connection.execute(f"CREATE TABLE {name} ({', '.join(columns)})")
            connection.executemany(f"INSERT INTO {name} VALUES ({','.join('?' for _ in columns)})", source["rows"])
        # Independent execution of the generated query, with the one demo type adapted.
        query = re.sub(r"VARCHAR2\(100\)", "TEXT", sql, flags=re.I)
        connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_OK if action in
                                  {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
                                  else sqlite3.SQLITE_DENY)
        cursor = connection.execute(query)
        return [x[0].upper() for x in cursor.description], [list(x) for x in cursor.fetchall()]


def compare_rows(actual, expected):
    """Order-independent, duplicate-sensitive comparison of JSON-safe fixture rows."""
    import json
    from collections import Counter
    encode = lambda rows: Counter(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in rows)
    return encode(actual) == encode(expected)
