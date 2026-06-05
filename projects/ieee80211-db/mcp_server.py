"""MCP Server for IEEE 802.11 Standard Database.

Provides structured access to the 802.11 standard including sections,
tables, figures, definitions, and cross-references. Supports multiple
standard versions in a single database.

Usage:
    python mcp_server.py [--db PATH]
"""

import json
import sqlite3
import argparse
from pathlib import Path
from contextlib import contextmanager

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

DEFAULT_DB_PATH = Path(__file__).parent / "output" / "ieee80211.db"

VERSION_PARAM = {
    "type": "string",
    "description": (
        "Filter by standard version (e.g., '802.11-2020', '802.11ax-2021'). "
        "Omit to search across all versions."
    ),
}


@contextmanager
def get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_server(db_path: str) -> Server:
    server = Server("ieee80211-standard")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="list_standards",
                description="List all IEEE 802.11 standard versions loaded in the database.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "random_string": {
                            "type": "string",
                            "description": "Unused placeholder parameter",
                        }
                    },
                    "required": [],
                },
            ),
            Tool(
                name="get_section",
                description=(
                    "Get a specific section from the IEEE 802.11 standard by its number. "
                    "Returns the section title, hierarchy level, and full markdown content."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "section_number": {
                            "type": "string",
                            "description": "Section number (e.g., '9.4.2.1', '4.3.21', '1.1')",
                        },
                        "standard_version": VERSION_PARAM,
                    },
                    "required": ["section_number"],
                },
            ),
            Tool(
                name="search_standard",
                description=(
                    "Full-text search across the IEEE 802.11 standard. "
                    "Searches section titles, content, table captions, and definitions. "
                    "Returns matching sections with snippets."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (supports FTS5 syntax: AND, OR, NOT, phrases in quotes)",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 10)",
                            "default": 10,
                        },
                        "standard_version": VERSION_PARAM,
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_table",
                description=(
                    "Get a specific table from the IEEE 802.11 standard. "
                    "Returns the table in both markdown and structured JSON formats."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_number": {
                            "type": "string",
                            "description": "Table identifier (e.g., 'Table 9-92', 'Table 8-1')",
                        },
                        "standard_version": VERSION_PARAM,
                    },
                    "required": ["table_number"],
                },
            ),
            Tool(
                name="get_figure",
                description=(
                    "Get a figure/diagram from the IEEE 802.11 standard. "
                    "Returns the figure caption, type, and image path."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "figure_number": {
                            "type": "string",
                            "description": "Figure identifier (e.g., 'Figure 10-5', 'Figure 4-25')",
                        },
                        "standard_version": VERSION_PARAM,
                    },
                    "required": ["figure_number"],
                },
            ),
            Tool(
                name="get_definition",
                description=(
                    "Look up a term definition or acronym from the IEEE 802.11 standard (Clause 3). "
                    "Supports partial matching."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "Term or acronym to look up (e.g., 'BSS', 'access point', 'OFDM')",
                        },
                        "standard_version": VERSION_PARAM,
                    },
                    "required": ["term"],
                },
            ),
            Tool(
                name="get_related_sections",
                description=(
                    "Get sections related to a given section via cross-references. "
                    "Shows which sections reference this one and which it references."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "section_number": {
                            "type": "string",
                            "description": "Section number to find relations for",
                        },
                        "standard_version": VERSION_PARAM,
                    },
                    "required": ["section_number"],
                },
            ),
            Tool(
                name="find_frame_format",
                description=(
                    "Search for frame format information in the IEEE 802.11 standard. "
                    "Finds tables and sections related to specific frame types."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "frame_type": {
                            "type": "string",
                            "description": "Frame type to search for (e.g., 'beacon', 'probe request', 'authentication', 'data')",
                        },
                        "standard_version": VERSION_PARAM,
                    },
                    "required": ["frame_type"],
                },
            ),
            Tool(
                name="get_section_children",
                description=(
                    "Get all child subsections of a given section. "
                    "Useful for navigating the standard hierarchy."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "section_number": {
                            "type": "string",
                            "description": "Parent section number",
                        },
                        "standard_version": VERSION_PARAM,
                    },
                    "required": ["section_number"],
                },
            ),
            Tool(
                name="list_tables_in_section",
                description=(
                    "List all tables contained within a specific section of the standard."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "section_number": {
                            "type": "string",
                            "description": "Section number to list tables for",
                        },
                        "standard_version": VERSION_PARAM,
                    },
                    "required": ["section_number"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
        version = arguments.get("standard_version")
        with get_db(db_path) as conn:
            if name == "list_standards":
                return _list_standards(conn)
            elif name == "get_section":
                return _get_section(conn, arguments["section_number"], version)
            elif name == "search_standard":
                return _search_standard(
                    conn, arguments["query"], arguments.get("max_results", 10), version
                )
            elif name == "get_table":
                return _get_table(conn, arguments["table_number"], version)
            elif name == "get_figure":
                return _get_figure(conn, arguments["figure_number"], version)
            elif name == "get_definition":
                return _get_definition(conn, arguments["term"], version)
            elif name == "get_related_sections":
                return _get_related_sections(conn, arguments["section_number"], version)
            elif name == "find_frame_format":
                return _find_frame_format(conn, arguments["frame_type"], version)
            elif name == "get_section_children":
                return _get_section_children(conn, arguments["section_number"], version)
            elif name == "list_tables_in_section":
                return _list_tables_in_section(conn, arguments["section_number"], version)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


def _version_filter(version: str | None, col: str = "standard_version") -> tuple[str, tuple]:
    """Build a WHERE clause fragment for version filtering."""
    if version:
        return f" AND {col} = ?", (version,)
    return "", ()


def _list_standards(conn: sqlite3.Connection) -> list[TextContent]:
    rows = conn.execute(
        "SELECT DISTINCT standard_version FROM sections ORDER BY standard_version"
    ).fetchall()

    standards = []
    for row in rows:
        ver = row["standard_version"]
        sec_count = conn.execute(
            "SELECT COUNT(*) FROM sections WHERE standard_version = ?", (ver,)
        ).fetchone()[0]
        tbl_count = conn.execute(
            "SELECT COUNT(*) FROM tables WHERE standard_version = ?", (ver,)
        ).fetchone()[0]
        standards.append({
            "standard_version": ver,
            "sections": sec_count,
            "tables": tbl_count,
        })

    return [TextContent(type="text", text=json.dumps(standards, indent=2))]


def _get_section(conn: sqlite3.Connection, section_number: str, version: str | None = None) -> list[TextContent]:
    vf, vp = _version_filter(version)
    row = conn.execute(
        f"SELECT * FROM sections WHERE section_number = ?{vf}",
        (section_number,) + vp
    ).fetchone()

    if not row:
        return [TextContent(type="text", text=f"Section {section_number} not found.")]

    result = {
        "standard_version": row["standard_version"],
        "section_number": row["section_number"],
        "title": row["title"],
        "level": row["level"],
        "parent_section": row["parent_section"],
        "page_start": row["page_start"],
        "page_end": row["page_end"],
        "content": row["content_markdown"],
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _search_standard(conn: sqlite3.Connection, query: str, max_results: int, version: str | None = None) -> list[TextContent]:
    results = []

    # Search sections
    if version:
        rows = conn.execute(
            """SELECT standard_version, section_number, title,
                      snippet(sections_fts, 3, '<mark>', '</mark>', '...', 40) as snippet
               FROM sections_fts
               WHERE sections_fts MATCH ? AND standard_version = ?
               ORDER BY rank
               LIMIT ?""",
            (query, version, max_results),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT standard_version, section_number, title,
                      snippet(sections_fts, 3, '<mark>', '</mark>', '...', 40) as snippet
               FROM sections_fts
               WHERE sections_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, max_results),
        ).fetchall()

    for row in rows:
        results.append({
            "type": "section",
            "standard_version": row["standard_version"],
            "section_number": row["section_number"],
            "title": row["title"],
            "snippet": row["snippet"],
        })

    # Search tables
    if version:
        table_rows = conn.execute(
            """SELECT standard_version, table_number, caption,
                      snippet(tables_fts, 3, '<mark>', '</mark>', '...', 40) as snippet
               FROM tables_fts
               WHERE tables_fts MATCH ? AND standard_version = ?
               ORDER BY rank
               LIMIT ?""",
            (query, version, max_results // 2),
        ).fetchall()
    else:
        table_rows = conn.execute(
            """SELECT standard_version, table_number, caption,
                      snippet(tables_fts, 3, '<mark>', '</mark>', '...', 40) as snippet
               FROM tables_fts
               WHERE tables_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, max_results // 2),
        ).fetchall()

    for row in table_rows:
        results.append({
            "type": "table",
            "standard_version": row["standard_version"],
            "table_number": row["table_number"],
            "caption": row["caption"],
            "snippet": row["snippet"],
        })

    # Search definitions
    if version:
        def_rows = conn.execute(
            """SELECT standard_version, term, definition
               FROM definitions_fts
               WHERE definitions_fts MATCH ? AND standard_version = ?
               LIMIT ?""",
            (query, version, max_results // 2),
        ).fetchall()
    else:
        def_rows = conn.execute(
            """SELECT standard_version, term, definition
               FROM definitions_fts
               WHERE definitions_fts MATCH ?
               LIMIT ?""",
            (query, max_results // 2),
        ).fetchall()

    for row in def_rows:
        results.append({
            "type": "definition",
            "standard_version": row["standard_version"],
            "term": row["term"],
            "definition": row["definition"],
        })

    if not results:
        return [TextContent(type="text", text=f"No results found for: {query}")]

    return [TextContent(type="text", text=json.dumps(results, indent=2))]


def _get_table(conn: sqlite3.Connection, table_number: str, version: str | None = None) -> list[TextContent]:
    vf, vp = _version_filter(version)
    row = conn.execute(
        f"SELECT * FROM tables WHERE table_number = ?{vf}",
        (table_number,) + vp
    ).fetchone()

    if not row:
        rows = conn.execute(
            f"SELECT * FROM tables WHERE table_number LIKE ?{vf}",
            (f"%{table_number}%",) + vp
        ).fetchall()
        if rows:
            row = rows[0]
        else:
            return [TextContent(type="text", text=f"Table '{table_number}' not found.")]

    result = {
        "standard_version": row["standard_version"],
        "table_number": row["table_number"],
        "caption": row["caption"],
        "section_number": row["section_number"],
        "page_number": row["page_number"],
        "markdown": row["markdown"],
        "structured_data": json.loads(row["structured_json"]) if row["structured_json"] else None,
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _get_figure(conn: sqlite3.Connection, figure_number: str, version: str | None = None) -> list[TextContent]:
    vf, vp = _version_filter(version)
    row = conn.execute(
        f"SELECT * FROM figures WHERE figure_number = ?{vf}",
        (figure_number,) + vp
    ).fetchone()

    if not row:
        rows = conn.execute(
            f"SELECT * FROM figures WHERE figure_number LIKE ?{vf}",
            (f"%{figure_number}%",) + vp
        ).fetchall()
        if rows:
            row = rows[0]
        else:
            return [TextContent(type="text", text=f"Figure '{figure_number}' not found.")]

    result = {
        "standard_version": row["standard_version"],
        "figure_number": row["figure_number"],
        "caption": row["caption"],
        "section_number": row["section_number"],
        "figure_type": row["figure_type"],
        "page_number": row["page_number"],
        "image_path": row["image_path"],
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _get_definition(conn: sqlite3.Connection, term: str, version: str | None = None) -> list[TextContent]:
    vf, vp = _version_filter(version)

    # Exact match first
    row = conn.execute(
        f"SELECT * FROM definitions WHERE LOWER(term) = LOWER(?){vf}",
        (term,) + vp
    ).fetchone()

    if row:
        results = [{"standard_version": row["standard_version"], "term": row["term"],
                    "definition": row["definition"], "section": row["section_number"]}]
    else:
        rows = conn.execute(
            f"SELECT * FROM definitions WHERE LOWER(term) LIKE LOWER(?){vf}",
            (f"%{term}%",) + vp
        ).fetchall()
        results = [
            {"standard_version": r["standard_version"], "term": r["term"],
             "definition": r["definition"], "section": r["section_number"]}
            for r in rows[:10]
        ]

    if not results:
        # Try FTS
        if version:
            rows = conn.execute(
                "SELECT standard_version, term, definition FROM definitions_fts WHERE definitions_fts MATCH ? AND standard_version = ? LIMIT 5",
                (term, version)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT standard_version, term, definition FROM definitions_fts WHERE definitions_fts MATCH ? LIMIT 5",
                (term,)
            ).fetchall()
        results = [{"standard_version": r["standard_version"], "term": r["term"], "definition": r["definition"]} for r in rows]

    if not results:
        return [TextContent(type="text", text=f"No definition found for: {term}")]

    return [TextContent(type="text", text=json.dumps(results, indent=2))]


def _get_related_sections(conn: sqlite3.Connection, section_number: str, version: str | None = None) -> list[TextContent]:
    vf, vp = _version_filter(version)

    outgoing = conn.execute(
        f"SELECT target_section, target_type, context, standard_version FROM cross_references WHERE source_section = ?{vf}",
        (section_number,) + vp
    ).fetchall()

    incoming = conn.execute(
        f"SELECT source_section, target_type, context, standard_version FROM cross_references WHERE target_section = ?{vf}",
        (section_number,) + vp
    ).fetchall()

    result = {
        "section_number": section_number,
        "references_to": [
            {"target": r["target_section"], "type": r["target_type"],
             "context": r["context"], "standard_version": r["standard_version"]}
            for r in outgoing
        ],
        "referenced_by": [
            {"source": r["source_section"], "type": r["target_type"],
             "context": r["context"], "standard_version": r["standard_version"]}
            for r in incoming
        ],
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _find_frame_format(conn: sqlite3.Connection, frame_type: str, version: str | None = None) -> list[TextContent]:
    results = []
    vf, vp = _version_filter(version)

    table_rows = conn.execute(
        f"""SELECT table_number, caption, markdown, section_number, standard_version
           FROM tables
           WHERE (LOWER(caption) LIKE LOWER(?) OR LOWER(markdown) LIKE LOWER(?)){vf}
           LIMIT 10""",
        (f"%{frame_type}%", f"%{frame_type}%") + vp
    ).fetchall()

    for row in table_rows:
        results.append({
            "type": "table",
            "standard_version": row["standard_version"],
            "table_number": row["table_number"],
            "caption": row["caption"],
            "section_number": row["section_number"],
            "content": row["markdown"],
        })

    section_rows = conn.execute(
        f"""SELECT section_number, title, content_markdown, standard_version
           FROM sections
           WHERE (LOWER(title) LIKE LOWER(?) OR LOWER(content_markdown) LIKE LOWER(?))
           AND (LOWER(title) LIKE '%frame%' OR LOWER(title) LIKE '%format%'){vf}
           LIMIT 5""",
        (f"%{frame_type}%", f"%{frame_type}%") + vp
    ).fetchall()

    for row in section_rows:
        results.append({
            "type": "section",
            "standard_version": row["standard_version"],
            "section_number": row["section_number"],
            "title": row["title"],
            "content_preview": (row["content_markdown"] or "")[:500],
        })

    if not results:
        return [TextContent(type="text", text=f"No frame format info found for: {frame_type}")]

    return [TextContent(type="text", text=json.dumps(results, indent=2))]


def _get_section_children(conn: sqlite3.Connection, section_number: str, version: str | None = None) -> list[TextContent]:
    vf, vp = _version_filter(version)
    rows = conn.execute(
        f"""SELECT section_number, title, level, standard_version
           FROM sections WHERE parent_section = ?{vf}
           ORDER BY section_number""",
        (section_number,) + vp
    ).fetchall()

    children = [
        {"section_number": r["section_number"], "title": r["title"],
         "level": r["level"], "standard_version": r["standard_version"]}
        for r in rows
    ]

    if not children:
        return [TextContent(type="text", text=f"No child sections found for: {section_number}")]

    return [TextContent(type="text", text=json.dumps(children, indent=2))]


def _list_tables_in_section(conn: sqlite3.Connection, section_number: str, version: str | None = None) -> list[TextContent]:
    vf, vp = _version_filter(version)
    rows = conn.execute(
        f"""SELECT table_number, caption, page_number, standard_version
           FROM tables
           WHERE (section_number = ? OR section_number LIKE ?){vf}
           ORDER BY page_number""",
        (section_number, f"{section_number}.%") + vp
    ).fetchall()

    tables = [
        {"table_number": r["table_number"], "caption": r["caption"],
         "page": r["page_number"], "standard_version": r["standard_version"]}
        for r in rows
    ]

    if not tables:
        return [TextContent(type="text", text=f"No tables found in section: {section_number}")]

    return [TextContent(type="text", text=json.dumps(tables, indent=2))]


async def main():
    parser = argparse.ArgumentParser(description="IEEE 802.11 Standard MCP Server")
    parser.add_argument(
        '--db', type=str, default=str(DEFAULT_DB_PATH),
        help='Path to the SQLite database'
    )
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Error: Database not found at {args.db}")
        print("Run extract.py first to build the database.")
        return

    server = create_server(args.db)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
