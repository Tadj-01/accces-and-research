

-- Drop tables if re-running (clean reset)
DROP TABLE IF EXISTS links CASCADE;
DROP TABLE IF EXISTS files CASCADE;
DROP TABLE IF EXISTS pages CASCADE;

-- ------------------------------------------------------------
-- TABLE: pages
-- ------------------------------------------------------------
CREATE TABLE pages (
    id          SERIAL PRIMARY KEY,
    url         TEXT NOT NULL UNIQUE,        -- used by ON CONFLICT (url)
    title       TEXT,
    headers     TEXT,
    meta_data   TEXT,
    content     TEXT,
    depth       INT  NOT NULL DEFAULT 1,
    indexed_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- TABLE: links
-- ------------------------------------------------------------
CREATE TABLE links (
    from_page   INT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    to_page     INT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    PRIMARY KEY (from_page, to_page)         -- used by ON CONFLICT DO NOTHING
);

-- ------------------------------------------------------------
-- TABLE: files
-- ------------------------------------------------------------
CREATE TABLE files (
    id            SERIAL PRIMARY KEY,
    page_id       INT  NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    file_url      TEXT NOT NULL UNIQUE,      -- used by ON CONFLICT (file_url)
    file_type     TEXT NOT NULL,
    file_name     TEXT NOT NULL,
    file_content  BYTEA,
    downloaded_at TIMESTAMP NOT NULL DEFAULT NOW()
);