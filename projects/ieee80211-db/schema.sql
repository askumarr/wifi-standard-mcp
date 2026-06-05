-- IEEE 802.11 Standard AI-Readable Database Schema
-- Supports multiple standard versions in a single database

-- Core section hierarchy
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY,
    standard_version TEXT NOT NULL,
    section_number TEXT,
    title TEXT,
    level INTEGER,
    parent_section TEXT,
    content_markdown TEXT,
    page_start INTEGER,
    page_end INTEGER,
    UNIQUE(standard_version, section_number)
);

-- Tables extracted from the standard
CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY,
    standard_version TEXT NOT NULL,
    section_number TEXT,
    table_number TEXT,
    caption TEXT,
    markdown TEXT,
    structured_json TEXT,
    page_number INTEGER
);

-- Figures and diagrams
CREATE TABLE IF NOT EXISTS figures (
    id INTEGER PRIMARY KEY,
    standard_version TEXT NOT NULL,
    section_number TEXT,
    figure_number TEXT,
    caption TEXT,
    image_path TEXT,
    description TEXT,
    figure_type TEXT,
    page_number INTEGER
);

-- Definitions from Clause 3
CREATE TABLE IF NOT EXISTS definitions (
    id INTEGER PRIMARY KEY,
    standard_version TEXT NOT NULL,
    term TEXT,
    definition TEXT,
    section_number TEXT
);

-- Cross-references between sections
CREATE TABLE IF NOT EXISTS cross_references (
    id INTEGER PRIMARY KEY,
    standard_version TEXT NOT NULL,
    source_section TEXT,
    target_section TEXT,
    target_type TEXT,
    context TEXT
);

-- Full-text search indexes
CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
    standard_version,
    section_number,
    title,
    content_markdown,
    content='sections',
    content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS tables_fts USING fts5(
    standard_version,
    table_number,
    caption,
    markdown,
    content='tables',
    content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS definitions_fts USING fts5(
    standard_version,
    term,
    definition,
    content='definitions',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS sections_ai AFTER INSERT ON sections BEGIN
    INSERT INTO sections_fts(rowid, standard_version, section_number, title, content_markdown)
    VALUES (new.id, new.standard_version, new.section_number, new.title, new.content_markdown);
END;

CREATE TRIGGER IF NOT EXISTS tables_ai AFTER INSERT ON tables BEGIN
    INSERT INTO tables_fts(rowid, standard_version, table_number, caption, markdown)
    VALUES (new.id, new.standard_version, new.table_number, new.caption, new.markdown);
END;

CREATE TRIGGER IF NOT EXISTS definitions_ai AFTER INSERT ON definitions BEGIN
    INSERT INTO definitions_fts(rowid, standard_version, term, definition)
    VALUES (new.id, new.standard_version, new.term, new.definition);
END;

-- Indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_sections_version ON sections(standard_version);
CREATE INDEX IF NOT EXISTS idx_sections_parent ON sections(parent_section);
CREATE INDEX IF NOT EXISTS idx_sections_level ON sections(level);
CREATE INDEX IF NOT EXISTS idx_tables_version ON tables(standard_version);
CREATE INDEX IF NOT EXISTS idx_tables_section ON tables(section_number);
CREATE INDEX IF NOT EXISTS idx_tables_number ON tables(table_number);
CREATE INDEX IF NOT EXISTS idx_figures_version ON figures(standard_version);
CREATE INDEX IF NOT EXISTS idx_figures_section ON figures(section_number);
CREATE INDEX IF NOT EXISTS idx_figures_number ON figures(figure_number);
CREATE INDEX IF NOT EXISTS idx_definitions_version ON definitions(standard_version);
CREATE INDEX IF NOT EXISTS idx_definitions_term ON definitions(term);
CREATE INDEX IF NOT EXISTS idx_crossrefs_version ON cross_references(standard_version);
CREATE INDEX IF NOT EXISTS idx_crossrefs_source ON cross_references(source_section);
CREATE INDEX IF NOT EXISTS idx_crossrefs_target ON cross_references(target_section);
