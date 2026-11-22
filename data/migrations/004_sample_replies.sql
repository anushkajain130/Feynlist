-- Feynlist migration 004: mark pre-written sample replies (free-tier sample mode)
ALTER TABLE agent_messages ADD COLUMN is_sample INTEGER DEFAULT 0;
ALTER TABLE agent_messages ADD COLUMN sample_reason TEXT;

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (4, 'Sample replies flag on agent_messages');
