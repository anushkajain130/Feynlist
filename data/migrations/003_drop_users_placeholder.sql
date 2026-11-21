-- Feynlist migration 003: remove the unused placeholder `users` table
-- (subscription tiers and a hard-coded time zone; nothing read or wrote it).
DROP TABLE IF EXISTS users;

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (3, 'Drop unused users placeholder table');
