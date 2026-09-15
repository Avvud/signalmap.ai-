PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS research_runs (
    id              TEXT PRIMARY KEY,
    company_name    TEXT NOT NULL,
    website_url     TEXT,
    research_question TEXT,
    mode            TEXT NOT NULL DEFAULT 'full'
                    CHECK (mode IN ('full', 'content', 'developer', 'messaging')),
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN (
                        'queued', 'fetching_sources', 'normalizing',
                        'analyzing', 'synthesizing', 'completed', 'failed'
                    )),
    error_message   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evidence (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    source              TEXT NOT NULL CHECK (source IN ('website', 'youtube', 'reddit', 'github')),
    source_url          TEXT NOT NULL,
    title               TEXT NOT NULL,
    raw_content         TEXT NOT NULL,
    normalized_content  TEXT NOT NULL,
    metadata_json       TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS findings (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    claim               TEXT NOT NULL,
    claim_type          TEXT NOT NULL CHECK (claim_type IN ('observation', 'interpretation', 'hypothesis')),
    evidence_ids_json   TEXT NOT NULL,
    confidence          REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source_category     TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reports (
    id                      TEXT PRIMARY KEY,
    run_id                  TEXT UNIQUE NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    executive_summary       TEXT NOT NULL,
    source_breakdown_json   TEXT NOT NULL,
    cross_platform_findings TEXT NOT NULL,
    opportunity             TEXT NOT NULL,
    limitations_json        TEXT NOT NULL,
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_evidence_run_id  ON evidence(run_id);
CREATE INDEX IF NOT EXISTS idx_findings_run_id  ON findings(run_id);
