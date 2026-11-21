-- =============================================================================
-- Migration 001: Initial Schema
-- Feynlist V1 — replaces all CSV files with a single SQLite database
-- =============================================================================

-- Tasks: replaces FL_tasks_daily.csv and FL_task_master.csv
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    date        TEXT NOT NULL,           -- ISO date: YYYY-MM-DD
    task        TEXT NOT NULL,
    start_time  TEXT NOT NULL,           -- HH:MM (24-hr)
    end_time    TEXT NOT NULL,           -- HH:MM (24-hr)
    points      INTEGER NOT NULL DEFAULT 0,
    completed   INTEGER NOT NULL DEFAULT 0,  -- 0/1 boolean
    task_class  TEXT NOT NULL DEFAULT 'Unspecified',
    sub_class   TEXT,
    sub_class2  TEXT,
    start_and_sit   INTEGER DEFAULT 0,   -- 0/1
    complete_task   INTEGER DEFAULT 0,   -- 0/1
    be_attentive    INTEGER DEFAULT 0,   -- 0/1
    slider_val      INTEGER DEFAULT 0,
    ps_var          REAL DEFAULT 0.0,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(date);
CREATE INDEX IF NOT EXISTS idx_tasks_class ON tasks(task_class);

-- Daily analytics: replaces FL_analytics_master.csv
CREATE TABLE IF NOT EXISTS daily_analytics (
    date                TEXT PRIMARY KEY,  -- YYYY-MM-DD
    alertness           REAL DEFAULT 0.0,
    discipline          REAL DEFAULT 0.0,
    ps_hrs              REAL DEFAULT 0.0,
    aura                REAL DEFAULT 0.0,
    retention_streak    INTEGER DEFAULT 0,
    happiness           REAL DEFAULT 0.0,
    total_points        INTEGER DEFAULT 0,
    tasks_completed     INTEGER DEFAULT 0,
    tasks_total         INTEGER DEFAULT 0,
    computed_at         TEXT DEFAULT (datetime('now'))
);

-- Hourly points: replaces FL_hrmaster.csv (wide-format → long-format)
CREATE TABLE IF NOT EXISTS hourly_points (
    date    TEXT NOT NULL,           -- YYYY-MM-DD
    hour    INTEGER NOT NULL,        -- 0–23
    points  INTEGER DEFAULT 0,
    PRIMARY KEY (date, hour),
    CHECK (hour BETWEEN 0 AND 23)
);

-- Memory entries: replaces FLxCouncil_hist.txt + adds structure
CREATE TABLE IF NOT EXISTS memory_entries (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT,            -- NULL = shared across all agents
    memory_type     TEXT NOT NULL DEFAULT 'factual',
    content         TEXT NOT NULL,
    tags            TEXT DEFAULT '[]',       -- JSON array of strings
    importance      REAL DEFAULT 0.5,        -- 0.0–1.0
    created_at      TEXT DEFAULT (datetime('now')),
    last_accessed   TEXT DEFAULT (datetime('now')),
    access_count    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_memory_agent ON memory_entries(agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_entries(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_importance ON memory_entries(importance DESC);

-- Events: full audit log of everything that happened
CREATE TABLE IF NOT EXISTS events (
    id              TEXT PRIMARY KEY,
    event_type      TEXT NOT NULL,
    timestamp       TEXT DEFAULT (datetime('now')),
    payload         TEXT DEFAULT '{}',   -- JSON
    source          TEXT DEFAULT 'system',
    agent_response  TEXT                 -- agent_message.id if responded
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);

-- Agent messages: every LLM response stored for audit + history
CREATE TABLE IF NOT EXISTS agent_messages (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL,
    content         TEXT NOT NULL,
    triggered_by    TEXT,            -- event_type
    call_priority   TEXT DEFAULT 'standard',
    tokens_used     INTEGER DEFAULT 0,
    latency_ms      INTEGER DEFAULT 0,
    timestamp       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_agent ON agent_messages(agent_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON agent_messages(timestamp DESC);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT DEFAULT (datetime('now')),
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (1, 'Initial schema — replaces all CSV files');
