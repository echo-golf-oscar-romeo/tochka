"""GeoSQL chat — ad-hoc spatial analysis loop.

Two-shot LLM cycle per user question:

  1. Build SKILL.md + table schemas + history into a system prompt.
     Ask the LLM for ONE SELECT query wrapped in <sql>…</sql>.
  2. Validate (SELECT-only, no DDL/DML, no multiple statements). Reject
     unsafe queries with a clear message back to the user.
  3. Execute against the live DuckDB connection (with osm_pois already
     loaded and the user's network registered as _user_locations).
  4. Hand the rows back to the LLM and ask for a 2–3 sentence narrative
     interpretation referencing the actual numbers.

Returns the answer, the SQL it ran, the rows, and any error.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from app.clients.ddb import ensure_kontur_loaded, ensure_osm_loaded, get_duckdb, register_locations
from app.clients.llm import get_llm
from app.models.network import Network
from app.orchestrator.chat_tools import maybe_run_tool

log = logging.getLogger(__name__)

_SKILL_PATH = Path(__file__).resolve().parent / "SKILL_geosql.md"
_SKILL_TEXT: str | None = None


def _skill() -> str:
    global _SKILL_TEXT
    if _SKILL_TEXT is None:
        _SKILL_TEXT = _SKILL_PATH.read_text(encoding="utf-8")
    return _SKILL_TEXT


# Forbidden SQL keywords — case-insensitive whole-word match.
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|ATTACH|DETACH|COPY|EXPORT|"
    r"PRAGMA|INSTALL|LOAD|TRUNCATE|REPLACE|MERGE|GRANT|REVOKE|VACUUM)\b",
    re.IGNORECASE,
)
_SQL_TAG = re.compile(r"<sql>([\s\S]*?)</sql>", re.IGNORECASE)
_MAX_ROWS = 100
_TIMEOUT_MS = 10_000


class GeoSQLError(Exception):
    """Raised when the LLM-produced SQL is unsafe or fails to parse."""


def extract_sql(text: str) -> str:
    """Pull the first <sql>…</sql> block out of the LLM response."""
    m = _SQL_TAG.search(text)
    if not m:
        raise GeoSQLError("LLM did not return a <sql>…</sql> block.")
    return m.group(1).strip().rstrip(";").strip()


def validate_sql(sql: str) -> None:
    """Raise GeoSQLError if the SQL is unsafe."""
    if not sql:
        raise GeoSQLError("Empty SQL.")
    # Strip simple line comments before lexical scan.
    stripped = re.sub(r"--[^\n]*", "", sql)
    stripped = re.sub(r"/\*[\s\S]*?\*/", "", stripped)
    # Reject multiple statements (a stray ';' mid-query).
    if ";" in stripped.strip().rstrip(";"):
        raise GeoSQLError("Multiple statements are not allowed.")
    # Reject forbidden keywords.
    bad = _FORBIDDEN.search(stripped)
    if bad:
        raise GeoSQLError(f"Forbidden keyword: {bad.group(0).upper()}.")
    # First non-whitespace, non-WITH keyword must be SELECT or WITH-then-SELECT.
    head = re.match(r"\s*(WITH\b[\s\S]*?SELECT|SELECT)\b", stripped, re.IGNORECASE)
    if not head:
        raise GeoSQLError("Only SELECT (optionally preceded by WITH) is permitted.")


def execute_sql(sql: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Run the query with a row cap. Returns (column_names, rows_as_dicts)."""
    conn = get_duckdb()
    # DuckDB's statement_timeout pragma — best effort; some versions ignore it.
    try:
        conn.execute(f"SET statement_timeout = '{_TIMEOUT_MS}ms';")
    except Exception:
        pass
    rs = conn.execute(sql)
    cols = [d[0] for d in rs.description] if rs.description else []
    rows = rs.fetchmany(_MAX_ROWS)
    return cols, [dict(zip(cols, row, strict=False)) for row in rows]


SYSTEM_NARRATE = (
    "You are a friendly senior spatial analyst. Given a user question, the SQL we ran, "
    "and the result rows, write 2–3 sentences in plain English that answers the question "
    "referencing concrete numbers from the rows. Do not output SQL again. If the rows are "
    "empty or only contain a 'note' field, explain why the question couldn't be answered."
)


async def run_chat_turn(network: Network, history: list[dict], user_message: str,
                        storymap_summary: str | None = None) -> dict[str, Any]:
    """Run one chat turn and return:
       {answer, sql, rows, columns, error?, provider}
    """
    llm = get_llm()
    if not llm.has_key:
        return {
            "answer": "The LLM provider isn't configured (no API key). Set DEEPSEEK_API_KEY or DASHSCOPE_API_KEY and restart the backend.",
            "sql": None, "rows": [], "columns": [], "error": "no_api_key",
            "provider": llm.provider,
        }

    # Make sure the DuckDB tables are loaded with this network.
    try:
        conn = get_duckdb()
        ensure_osm_loaded(conn)
        ensure_kontur_loaded(conn)
        register_locations(conn, network.locations)
    except Exception as e:
        log.warning("Failed to prep DuckDB tables for chat: %s", e)

    # Route intent-detected prompts (OSM fetch, isochrone, H3 aggregation)
    # to deterministic tools BEFORE the SQL agent. The tools handle their
    # own narration + layer payload.
    try:
        tool_result = await maybe_run_tool(network=network, message=user_message)
    except Exception as e:
        log.warning("Chat tool failed for %r: %s", user_message, e)
        tool_result = None
    if tool_result is not None:
        tool_result.setdefault("provider", llm.provider)
        return tool_result

    # ---- Step 1: generate SQL ----
    system = _skill()
    if storymap_summary:
        system += f"\n\n## Storymap context\n{storymap_summary}\n"
    messages = (
        [{"role": "system", "content": system}]
        + history[-10:]  # keep last 5 turns
        + [{"role": "user", "content": user_message}]
    )
    raw = await llm.chat(messages=messages, temperature=0.1, max_tokens=500)
    if not raw:
        return {"answer": "The LLM didn't respond. Try again.",
                "sql": None, "rows": [], "columns": [], "error": "llm_no_response",
                "provider": llm.provider}

    try:
        sql = extract_sql(raw)
        validate_sql(sql)
    except GeoSQLError as e:
        return {"answer": f"Couldn't produce a safe SQL query: {e}",
                "sql": raw, "rows": [], "columns": [], "error": str(e),
                "provider": llm.provider}

    # ---- Step 2: execute ----
    try:
        columns, rows = execute_sql(sql)
    except Exception as e:
        log.warning("GeoSQL execution failed for SQL %r: %s", sql, e)
        return {
            "answer": f"The SQL didn't execute: {e}. Try rephrasing the question.",
            "sql": sql, "rows": [], "columns": [], "error": str(e),
            "provider": llm.provider,
        }

    # ---- Step 3: narrate ----
    rows_preview = rows[:20]  # keep prompt small
    narrate_messages = [
        {"role": "system", "content": SYSTEM_NARRATE},
        {"role": "user", "content": (
            f"Question:\n{user_message}\n\n"
            f"SQL:\n{sql}\n\n"
            f"Result columns: {columns}\n"
            f"Result rows ({len(rows)} of up to {_MAX_ROWS}):\n{rows_preview}"
        )},
    ]
    answer = await llm.chat(messages=narrate_messages, temperature=0.3, max_tokens=400)
    if not answer:
        answer = (
            f"Query returned {len(rows)} row(s). "
            "(LLM narration unavailable — see the raw results.)"
        )

    return {
        "answer": answer.strip(),
        "sql": sql,
        "rows": rows,
        "columns": columns,
        "provider": llm.provider,
    }
