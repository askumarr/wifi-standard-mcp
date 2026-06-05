"""MCP Server for IEEE 802.11 Standard Database.

Provides structured access to the 802.11-2020 standard including sections,
tables, figures, definitions, and cross-references.

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

DEFAULT_DB_PATH = Path(__file__).parent / "output" / "ieee80211_2020.db"


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
                name="get_section",
                description=(
                    "Get a specific section from the IEEE 802.11-2020 standard by its number. "
                    "Returns the section title, hierarchy level, and full markdown content."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "section_number": {
                            "type": "string",
                            "description": "Section number (e.g., '9.4.2.1', '4.3.21', '1.1')",
                        }
                    },
                    "required": ["section_number"],
                },
            ),
            Tool(
                name="search_standard",
                description=(
                    "Full-text search across the IEEE 802.11-2020 standard. "
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
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_table",
                description=(
                    "Get a specific table from the IEEE 802.11-2020 standard. "
                    "Returns the table in both markdown and structured JSON formats."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_number": {
                            "type": "string",
                            "description": "Table identifier (e.g., 'Table 9-92', 'Table 8-1')",
                        },
                    },
                    "required": ["table_number"],
                },
            ),
            Tool(
                name="get_figure",
                description=(
                    "Get a figure/diagram from the IEEE 802.11-2020 standard. "
                    "Returns the figure caption, type, and image path."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "figure_number": {
                            "type": "string",
                            "description": "Figure identifier (e.g., 'Figure 10-5', 'Figure 4-25')",
                        },
                    },
                    "required": ["figure_number"],
                },
            ),
            Tool(
                name="get_definition",
                description=(
                    "Look up a term definition or acronym from the IEEE 802.11-2020 standard (Clause 3). "
                    "Supports partial matching."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "Term or acronym to look up (e.g., 'BSS', 'access point', 'OFDM')",
                        },
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
                    },
                    "required": ["section_number"],
                },
            ),
            Tool(
                name="find_frame_format",
                description=(
                    "Search for frame format information in the IEEE 802.11-2020 standard. "
                    "Finds tables and sections related to specific frame types."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "frame_type": {
                            "type": "string",
                            "description": "Frame type to search for (e.g., 'beacon', 'probe request', 'authentication', 'data')",
                        },
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
                    },
                    "required": ["section_number"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
        with get_db(db_path) as conn:
            if name == "get_section":
                return _get_section(conn, arguments["section_number"])
            elif name == "search_standard":
                return _search_standard(
                    conn, arguments["query"], arguments.get("max_results", 10)
                )
            elif name == "get_table":
                return _get_table(conn, arguments["table_number"])
            elif name == "get_figure":
                return _get_figure(conn, arguments["figure_number"])
            elif name == "get_definition":
                return _get_definition(conn, arguments["term"])
            elif name == "get_related_sections":
                return _get_related_sections(conn, arguments["section_number"])
            elif name == "find_frame_format":
                return _find_frame_format(conn, arguments["frame_type"])
            elif name == "get_section_children":
                return _get_section_children(conn, arguments["section_number"])
            elif name == "list_tables_in_section":
                return _list_tables_in_section(conn, arguments["section_number"])
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


def _get_section(conn: sqlite3.Connection, section_number: str) -> list[TextContent]:
    row = conn.execute(
        "SELECT * FROM sections WHERE section_number = ?", (section_number,)
    ).fetchone()

    if not row:
        return [TextContent(type="text", text=f"Section {section_number} not found.")]

    result = {
        "section_number": row["section_number"],
        "title": row["title"],
        "level": row["level"],
        "parent_section": row["parent_section"],
        "page_start": row["page_start"],
        "page_end": row["page_end"],
        "content": row["content_markdown"],
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _search_standard(conn: sqlite3.Connection, query: str, max_results: int) -> list[TextContent]:
    results = []

    # Search sections
    rows = conn.execute(
        """SELECT section_number, title, snippet(sections_fts, 2, '<mark>', '</mark>', '...', 40) as snippet
           FROM sections_fts
           WHERE sections_fts MATCH ?
           ORDER BY rank
           LIMIT ?""",
        (query, max_results),
    ).fetchall()

    for row in rows:
        results.append({
            "type": "section",
            "section_number": row["section_number"],
            "title": row["title"],
            "snippet": row["snippet"],
        })

    # Search tables
    table_rows = conn.execute(
        """SELECT table_number, caption, snippet(tables_fts, 2, '<mark>', '</mark>', '...', 40) as snippet
           FROM tables_fts
           WHERE tables_fts MATCH ?
           ORDER BY rank
           LIMIT ?""",
        (query, max_results // 2),
    ).fetchall()

    for row in table_rows:
        results.append({
            "type": "table",
            "table_number": row["table_number"],
            "caption": row["caption"],
            "snippet": row["snippet"],
        })

    # Search definitions
    def_rows = conn.execute(
        """SELECT term, definition
           FROM definitions_fts
           WHERE definitions_fts MATCH ?
           LIMIT ?""",
        (query, max_results // 2),
    ).fetchall()

    for row in def_rows:
        results.append({
            "type": "definition",
            "term": row["term"],
            "definition": row["definition"],
        })

    if not results:
        return [TextContent(type="text", text=f"No results found for: {query}")]

    return [TextContent(type="text", text=json.dumps(results, indent=2))]


def _get_table(conn: sqlite3.Connection, table_number: str) -> list[TextContent]:
    row = conn.execute(
        "SELECT * FROM tables WHERE table_number = ?", (table_number,)
    ).fetchone()

    if not row:
        # Try fuzzy match
        rows = conn.execute(
            "SELECT * FROM tables WHERE table_number LIKE ?",
            (f"%{table_number}%",)
        ).fetchall()
        if rows:
            row = rows[0]
        else:
            return [TextContent(type="text", text=f"Table '{table_number}' not found.")]

    result = {
        "table_number": row["table_number"],
        "caption": row["caption"],
        "section_number": row["section_number"],
        "page_number": row["page_number"],
        "markdown": row["markdown"],
        "structured_data": json.loads(row["structured_json"]) if row["structured_json"] else None,
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _get_figure(conn: sqlite3.Connection, figure_number: str) -> list[TextContent]:
    row = conn.execute(
        "SELECT * FROM figures WHERE figure_number = ?", (figure_number,)
    ).fetchone()

    if not row:
        rows = conn.execute(
            "SELECT * FROM figures WHERE figure_number LIKE ?",
            (f"%{figure_number}%",)
        ).fetchall()
        if rows:
            row = rows[0]
        else:
            return [TextContent(type="text", text=f"Figure '{figure_number}' not found.")]

    result = {
        "figure_number": row["figure_number"],
        "caption": row["caption"],
        "section_number": row["section_number"],
        "figure_type": row["figure_type"],
        "page_number": row["page_number"],
        "image_path": row["image_path"],
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _get_definition(conn: sqlite3.Connection, term: str) -> list[TextContent]:
    # Exact match first
    row = conn.execute(
        "SELECT * FROM definitions WHERE LOWER(term) = LOWER(?)", (term,)
    ).fetchone()

    if row:
        results = [{"term": row["term"], "definition": row["definition"], "section": row["section_number"]}]
    else:
        # Partial match
        rows = conn.execute(
            "SELECT * FROM definitions WHERE LOWER(term) LIKE LOWER(?)",
            (f"%{term}%",)
        ).fetchall()
        results = [
            {"term": r["term"], "definition": r["definition"], "section": r["section_number"]}
            for r in rows[:10]
        ]

    if not results:
        # Try FTS
        rows = conn.execute(
            "SELECT term, definition FROM definitions_fts WHERE definitions_fts MATCH ? LIMIT 5",
            (term,)
        ).fetchall()
        results = [{"term": r["term"], "definition": r["definition"]} for r in rows]

    if not results:
        return [TextContent(type="text", text=f"No definition found for: {term}")]

    return [TextContent(type="text", text=json.dumps(results, indent=2))]


def _get_related_sections(conn: sqlite3.Connection, section_number: str) -> list[TextContent]:
    # Outgoing references (this section references...)
    outgoing = conn.execute(
        """SELECT target_section, target_type, context
           FROM cross_references WHERE source_section = ?""",
        (section_number,)
    ).fetchall()

    # Incoming references (referenced by...)
    incoming = conn.execute(
        """SELECT source_section, target_type, context
           FROM cross_references WHERE target_section = ?""",
        (section_number,)
    ).fetchall()

    result = {
        "section_number": section_number,
        "references_to": [
            {"target": r["target_section"], "type": r["target_type"], "context": r["context"]}
            for r in outgoing
        ],
        "referenced_by": [
            {"source": r["source_section"], "type": r["target_type"], "context": r["context"]}
            for r in incoming
        ],
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _find_frame_format(conn: sqlite3.Connection, frame_type: str) -> list[TextContent]:
    results = []

    # Search tables for frame format info
    table_rows = conn.execute(
        """SELECT table_number, caption, markdown, section_number
           FROM tables
           WHERE LOWER(caption) LIKE LOWER(?) OR LOWER(markdown) LIKE LOWER(?)
           LIMIT 10""",
        (f"%{frame_type}%", f"%{frame_type}%")
    ).fetchall()

    for row in table_rows:
        results.append({
            "type": "table",
            "table_number": row["table_number"],
            "caption": row["caption"],
            "section_number": row["section_number"],
            "content": row["markdown"],
        })

    # Search sections for frame format descriptions
    section_rows = conn.execute(
        """SELECT section_number, title, content_markdown
           FROM sections
           WHERE (LOWER(title) LIKE LOWER(?) OR LOWER(content_markdown) LIKE LOWER(?))
           AND (LOWER(title) LIKE '%frame%' OR LOWER(title) LIKE '%format%')
           LIMIT 5""",
        (f"%{frame_type}%", f"%{frame_type}%")
    ).fetchall()

    for row in section_rows:
        results.append({
            "type": "section",
            "section_number": row["section_number"],
            "title": row["title"],
            "content_preview": (row["content_markdown"] or "")[:500],
        })

    if not results:
        return [TextContent(type="text", text=f"No frame format info found for: {frame_type}")]

    return [TextContent(type="text", text=json.dumps(results, indent=2))]


def _get_section_children(conn: sqlite3.Connection, section_number: str) -> list[TextContent]:
    rows = conn.execute(
        """SELECT section_number, title, level
           FROM sections WHERE parent_section = ?
           ORDER BY section_number""",
        (section_number,)
    ).fetchall()

    children = [
        {"section_number": r["section_number"], "title": r["title"], "level": r["level"]}
        for r in rows
    ]

    if not children:
        return [TextContent(type="text", text=f"No child sections found for: {section_number}")]

    return [TextContent(type="text", text=json.dumps(children, indent=2))]


def _list_tables_in_section(conn: sqlite3.Connection, section_number: str) -> list[TextContent]:
    # Match exact section or child sections
    rows = conn.execute(
        """SELECT table_number, caption, page_number
           FROM tables
           WHERE section_number = ? OR section_number LIKE ?
           ORDER BY page_number""",
        (section_number, f"{section_number}.%")
    ).fetchall()

    tables = [
        {"table_number": r["table_number"], "caption": r["caption"], "page": r["page_number"]}
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
