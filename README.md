# IEEE 802.11 Standard MCP Server

An AI-readable extraction pipeline and MCP (Model Context Protocol) server for querying the IEEE 802.11 wireless LAN standard and its amendments.

Extracts the full text, tables, figures, definitions, and cross-references from IEEE 802.11 PDFs into a structured SQLite database, then exposes them through 10 MCP tools for AI assistants to navigate and query.

## Supported Standards

| PDF File | Standard Version | Description |
|----------|-----------------|-------------|
| `80211-2020.pdf` | 802.11-2020 | Base standard (Wi-Fi 6 and earlier) |
| `80211ax-2021.pdf` | 802.11ax-2021 | Amendment 1: High Efficiency WLAN (Wi-Fi 6) |
| `80211be-2024.pdf` | 802.11be-2024 | Amendment 2: Extremely High Throughput (Wi-Fi 7) |

## Architecture

```
resources/                      projects/ieee80211-db/
├── 80211-2020.pdf              ├── extract.py          ← Extraction pipeline
├── 80211ax-2021.pdf    ───►    ├── mcp_server.py       ← MCP server (stdio)
└── 80211be-2024.pdf            ├── config.py           ← Paths & constants
                                ├── schema.sql          ← DB schema
                                ├── extractors/         ← Module per content type
                                │   ├── sections.py
                                │   ├── tables.py
                                │   ├── figures.py
                                │   ├── definitions.py
                                │   └── crossrefs.py
                                └── output/
                                    ├── ieee80211.db     ← SQLite database
                                    └── figures/         ← Extracted PNGs
```

## Quick Start

### 1. Prerequisites

- Python 3.10+
- IEEE 802.11 PDF files placed in `resources/`

### 2. Install Dependencies

```bash
cd projects/ieee80211-db
pip install -r requirements.txt
```

**Dependencies:**
| Package | Purpose |
|---------|---------|
| `PyMuPDF` (>=1.24.0) | PDF parsing, text/table/image extraction |
| `pymupdf4llm` (>=0.0.20) | Markdown conversion (fallback) |
| `pdfplumber` (>=0.10.0) | Additional table detection |
| `pandas` (>=2.0.0) | Table structuring |
| `mcp` (>=1.0.0) | Model Context Protocol server framework |

### 3. Run Extraction

Extract all three standards into the database:

```bash
cd projects/ieee80211-db

# Extract base standard (takes ~10-15 minutes)
python extract.py --pdf ../../resources/80211-2020.pdf --standard-version "802.11-2020"

# Extract 802.11ax amendment (~2-3 minutes)
python extract.py --pdf ../../resources/80211ax-2021.pdf --standard-version "802.11ax-2021"

# Extract 802.11be amendment (~3-5 minutes)
python extract.py --pdf ../../resources/80211be-2024.pdf --standard-version "802.11be-2024"
```

### 4. Run MCP Server

```bash
cd projects/ieee80211-db
python mcp_server.py
```

The server communicates over **stdio** (stdin/stdout JSON-RPC) as per the MCP specification.

---

## Extraction Pipeline Details

### What `extract.py` Does

The pipeline runs 7 steps sequentially for each PDF:

| Step | What it does | Output |
|------|-------------|--------|
| 1 | Opens PDF with PyMuPDF | Document object |
| 2 | Creates/connects to SQLite DB, clears existing data for target version | Empty tables |
| 3 | **Sections** — Parses TOC, builds hierarchy, extracts full text per section | `sections` table |
| 4 | **Tables** — Finds tables per page, converts to markdown + structured JSON | `tables` table |
| 5 | **Figures** — Extracts raster images + renders vector diagrams to PNG | `figures` table + PNG files |
| 6 | **Definitions** — Parses Clause 3 terms and acronyms | `definitions` table |
| 7 | **Cross-references** — Scans text for section/table/figure/annex mentions | `cross_references` table |

### CLI Options

```
python extract.py [OPTIONS]

Options:
  --pdf PATH              Path to IEEE 802.11 PDF file
                          (default: resources/80211-2020.pdf)
  --output PATH           Output directory for database
                          (default: projects/ieee80211-db/output)
  --figures-dir PATH      Output directory for figure PNGs
                          (default: output/figures)
  --standard-version VER  Version identifier stored in DB
                          (default: "802.11-2020")
  --skip-figures          Skip figure extraction (faster)
  --pages START:END       Only process specific page range (e.g., "100:200")
  --batch-size N          DB commit batch size (default: 100)
```

### Database Schema

All tables include a `standard_version` column for multi-standard support:

- **`sections`** — Section number, title, level, parent, page range, full markdown content
- **`tables`** — Table number, caption, section, markdown rendering, structured JSON data
- **`figures`** — Figure number, caption, type classification, image file path, page
- **`definitions`** — Term, definition text, section reference
- **`cross_references`** — Source section → target (section/table/figure/annex), with context

FTS5 virtual tables (`sections_fts`, `tables_fts`, `definitions_fts`) enable full-text search with automatic sync triggers.

### Configuration (`config.py`)

```python
PDF_PATH = "resources/80211-2020.pdf"       # Default PDF
PDF_AX_PATH = "resources/80211ax-2021.pdf"  # 802.11ax
PDF_BE_PATH = "resources/80211be-2024.pdf"  # 802.11be

DB_PATH = "projects/ieee80211-db/output/ieee80211.db"
FIGURES_DIR = "projects/ieee80211-db/output/figures"
FIGURE_DPI = 200
FIGURE_FORMAT = "png"

PDF_VERSION_MAP = {
    "80211-2020.pdf": "802.11-2020",
    "80211ax-2021.pdf": "802.11ax-2021",
    "80211be-2024.pdf": "802.11be-2024",
}
```

---

## MCP Server

### Available Tools

| Tool | Description |
|------|-------------|
| `list_standards` | List loaded standard versions with section/table/figure counts |
| `get_section` | Get section by number — title, hierarchy, full content |
| `search_standard` | FTS5 full-text search across sections, tables, definitions |
| `get_table` | Get table by number — markdown + structured data (merges multi-page tables) |
| `get_figure` | Get figure metadata and image path |
| `get_definition` | Look up Clause 3 term or acronym |
| `get_related_sections` | Find incoming/outgoing cross-references for a section |
| `find_frame_format` | Search for frame format information by frame type name |
| `get_section_children` | List child subsections of a given section |
| `list_tables_in_section` | List all tables within a section |

All tools accept an optional `standard_version` parameter to filter results (e.g., `"802.11ax-2021"`). Omit to search across all loaded standards.

### Running Standalone

```bash
cd projects/ieee80211-db
python mcp_server.py --db output/ieee80211.db
```

---

## MCP Integration

### Cursor IDE

Add to your Cursor MCP settings (`.cursor/mcp.json` in your project, or global settings):

```json
{
  "mcpServers": {
    "ieee80211-standard": {
      "command": "python",
      "args": [
        "/absolute/path/to/wifi-standard-mcp/projects/ieee80211-db/mcp_server.py",
        "--db",
        "/absolute/path/to/wifi-standard-mcp/projects/ieee80211-db/output/ieee80211.db"
      ]
    }
  }
}
```

Replace `/absolute/path/to/` with your actual path. After adding, restart Cursor or reload MCP servers.

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ieee80211-standard": {
      "command": "python",
      "args": [
        "/absolute/path/to/wifi-standard-mcp/projects/ieee80211-db/mcp_server.py"
      ]
    }
  }
}
```

### Any MCP Client (Generic)

The server uses **stdio transport** — launch it as a subprocess and communicate via stdin/stdout using JSON-RPC 2.0 messages per the MCP specification.

```bash
python projects/ieee80211-db/mcp_server.py --db projects/ieee80211-db/output/ieee80211.db
```

---

## Documentation

Analysis documents generated from the extracted data:

| Document | Description |
|----------|-------------|
| `docs/TWT_Complete_Reference.md` | Complete TWT implementation reference (802.11ax + 802.11be) |
| `docs/EHT_TWT_Changes.md` | TWT changes and enhancements in 802.11be |
| `docs/MLO_TTLM.md` | Multi-Link Operation TID-to-Link Mapping analysis |
| `docs/STA_Power_Save_Techniques.md` | Comprehensive STA-side power save techniques |

---

## Project Structure

```
wifi-standard-mcp/
├── README.md                   ← This file
├── LICENSE.md                  ← Private/Personal license
├── CODE_OF_CONDUCT.md
├── resources/                  ← Source PDFs
│   ├── 80211-2020.pdf
│   ├── 80211ax-2021.pdf
│   └── 80211be-2024.pdf
├── projects/
│   └── ieee80211-db/           ← Main project
│       ├── extract.py          ← Extraction pipeline
│       ├── mcp_server.py       ← MCP server
│       ├── config.py           ← Configuration
│       ├── schema.sql          ← Database schema
│       ├── requirements.txt    ← Python dependencies
│       ├── extractors/         ← Extraction modules
│       └── output/             ← Generated artifacts
│           ├── ieee80211.db    ← SQLite database (~44 MB)
│           └── figures/        ← Extracted PNGs (~4400 files)
└── docs/                       ← Analysis documents
```

---

## Database Stats (Current)

| Content Type | 802.11-2020 | 802.11ax-2021 | 802.11be-2024 | Total |
|-------------|-------------|---------------|---------------|-------|
| Sections | 6,482 | 765 | 1,091 | 8,338 |
| Tables | 2,445 | 500 | 642 | 3,587 |
| Figures | 3,420 | 834 | 1,003 | 5,257 |
| Definitions | 178 | 4 | 13 | 195 |
| Cross-refs | 16,029 | 2,655 | 3,182 | 21,866 |
