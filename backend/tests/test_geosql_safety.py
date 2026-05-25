"""Unit tests for the GeoSQL safety gate.

No external services required. Validates that the SQL validator accepts
the documented-safe patterns and rejects forbidden keywords or multi-
statement payloads.
"""

from __future__ import annotations

import os

import pytest

# Settings are loaded once at import time; force a known empty env so the
# import doesn't try to hit anything.
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DASHSCOPE_API_KEY", "")
os.environ.setdefault("DEEPSEEK_API_KEY", "")

from app.orchestrator.geosql import (    # noqa: E402
    GeoSQLError,
    extract_sql,
    validate_sql,
)


# --- extract_sql ---

def test_extract_sql_simple():
    assert extract_sql("<sql>SELECT 1</sql>") == "SELECT 1"


def test_extract_sql_multiline_and_strips_trailing_semicolon():
    raw = "<sql>\n  SELECT name\n  FROM osm_pois\n  LIMIT 5;\n</sql>"
    assert extract_sql(raw) == "SELECT name\n  FROM osm_pois\n  LIMIT 5"


def test_extract_sql_falls_back_to_markdown_fence():
    # DeepSeek tends to wrap SQL in fenced code blocks instead of tags.
    raw = "Here you go:\n```sql\nSELECT name FROM osm_pois LIMIT 5\n```"
    assert extract_sql(raw) == "SELECT name FROM osm_pois LIMIT 5"


def test_extract_sql_falls_back_to_bare_select():
    # Last resort: pick up a bare SELECT … from prose. Still validated
    # downstream by validate_sql().
    raw = "Here is some SQL: SELECT 1"
    assert extract_sql(raw) == "SELECT 1"


def test_extract_sql_raises_when_no_sql_at_all():
    with pytest.raises(GeoSQLError):
        extract_sql("I cannot answer — out of scope, sorry.")


# --- validate_sql ---

def test_validate_select():
    validate_sql("SELECT 1")
    validate_sql("SELECT * FROM osm_pois WHERE type='bank' LIMIT 5")


def test_validate_with_cte():
    validate_sql("WITH x AS (SELECT id FROM osm_pois LIMIT 1) SELECT * FROM x")


def test_validate_rejects_insert():
    with pytest.raises(GeoSQLError):
        validate_sql("INSERT INTO osm_pois VALUES ('x', 'bank', 'n', 'b', 0, 0, 'd', false)")


def test_validate_rejects_drop():
    with pytest.raises(GeoSQLError):
        validate_sql("DROP TABLE osm_pois")


def test_validate_rejects_attach():
    with pytest.raises(GeoSQLError):
        validate_sql("ATTACH 'evil.db' AS x")


def test_validate_rejects_pragma():
    with pytest.raises(GeoSQLError):
        validate_sql("PRAGMA show_tables")


def test_validate_rejects_multi_statement():
    with pytest.raises(GeoSQLError):
        validate_sql("SELECT 1; SELECT 2")


def test_validate_strips_line_comments():
    # Line comment that "contains" DROP shouldn't trigger the keyword reject.
    validate_sql("-- DROP TABLE osm_pois\nSELECT 1")


def test_validate_strips_block_comments():
    validate_sql("/* DROP */ SELECT 1")


def test_validate_empty_raises():
    with pytest.raises(GeoSQLError):
        validate_sql("")


def test_validate_non_select_first_raises():
    with pytest.raises(GeoSQLError):
        validate_sql("EXPLAIN SELECT 1")
