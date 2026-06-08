# Projects

## ieee80211-db

The main project — an IEEE 802.11 standard extraction pipeline and MCP server.

### Components

| File | Purpose |
|------|---------|
| `extract.py` | Main extraction pipeline (PDF → SQLite) |
| `mcp_server.py` | MCP server exposing 10 query tools over stdio |
| `config.py` | Paths, constants, version mapping |
| `schema.sql` | SQLite database schema (with FTS5) |
| `requirements.txt` | Python dependencies |
| `extractors/` | Modular extractors (sections, tables, figures, definitions, cross-refs) |
| `output/` | Generated database and figure images |

### Quick Commands

```bash
cd projects/ieee80211-db

# Install dependencies
pip install -r requirements.txt

# Extract a standard
python extract.py --pdf ../../resources/80211ax-2021.pdf --standard-version "802.11ax-2021"

# Extract without figures (faster)
python extract.py --pdf ../../resources/80211be-2024.pdf --standard-version "802.11be-2024" --skip-figures

# Extract specific pages only
python extract.py --pdf ../../resources/80211-2020.pdf --standard-version "802.11-2020" --pages 100:200

# Run MCP server
python mcp_server.py

# Run MCP server with custom DB path
python mcp_server.py --db /path/to/ieee80211.db
```

See the root [README.md](../README.md) for full documentation.
