-- Skylar IQ QA Tool — Postgres schema.
-- All statements use IF NOT EXISTS so this file can be replayed safely on every boot.

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    name            TEXT,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS test_files (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,           -- on-disk basename inside data/test_files/
    original_name   TEXT NOT NULL,
    question_count  INTEGER,
    size_bytes      BIGINT,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS test_files_user_id_idx ON test_files(user_id, uploaded_at DESC);

CREATE TABLE IF NOT EXISTS presets (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    login_url           TEXT,
    username            TEXT,
    machine_id          TEXT,
    sql_agent_path      TEXT,
    run_sql_timeout_ms  INTEGER,
    gen_viz_timeout_ms  INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS presets_user_id_idx ON presets(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    test_type       TEXT NOT NULL DEFAULT 'sql_agent'
                       CHECK (test_type IN ('sql_agent', 'site_search')),
    login_url       TEXT NOT NULL,            -- for sql_agent: the login page URL
                                              -- for site_search: the page URL with the search box
    username        TEXT,                     -- credential username for sql_agent (NULL for site_search)
    machine_id      TEXT,
    sql_agent_path  TEXT,
    search_input_selector TEXT,               -- site_search only — defaults to '#searchbox'
    question_count  INTEGER,
    test_file_id    TEXT REFERENCES test_files(id) ON DELETE SET NULL,
    test_file_name  TEXT,                     -- denormalised for stable history if test_files row deleted
    status          TEXT NOT NULL,
    summary         JSONB,
    error           TEXT,
    traceback       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ
);

-- Backfill column on already-existing tables (no-op when column already exists)
ALTER TABLE runs ADD COLUMN IF NOT EXISTS test_type TEXT NOT NULL DEFAULT 'sql_agent';
ALTER TABLE runs ADD COLUMN IF NOT EXISTS search_input_selector TEXT;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS site_search_config JSONB;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS bundle_id TEXT;
-- variant_groups: for "Variant Tests" runs, the group structure
-- (which qids are originals, which are their variants) used to build the
-- SQL-consistency report. NULL for ordinary runs.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS variant_groups JSONB;
ALTER TABLE presets ADD COLUMN IF NOT EXISTS site_search_config JSONB;

CREATE TABLE IF NOT EXISTS hosted_bundles (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    original_filename TEXT,
    file_count        INTEGER,
    size_bytes        BIGINT,
    main_js           TEXT,            -- relative path inside the bundle dir
    main_css          TEXT,            -- relative path or NULL
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS hosted_bundles_user_id_idx ON hosted_bundles(user_id, uploaded_at DESC);
CREATE INDEX IF NOT EXISTS runs_user_id_idx ON runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS runs_status_idx ON runs(status);

-- Per-query result lives as a JSONB blob — schema-flexible, query-friendly.
-- run_id + qid is the natural key.
CREATE TABLE IF NOT EXISTS query_results (
    run_id      TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    qid         INTEGER NOT NULL,
    status      TEXT,
    duration_ms INTEGER,
    nl_query    TEXT,
    record      JSONB NOT NULL,
    PRIMARY KEY (run_id, qid)
);
CREATE INDEX IF NOT EXISTS query_results_status_idx ON query_results(status);
