-- Feynlist migration 002: neutral daily check-in
-- commitment_kept: NULL = no check-in yet, 1 = "I kept my commitment today", 0 = "Not today".
-- The older `relapsed` column is kept for compatibility and mirrors (commitment_kept = 0).
ALTER TABLE daily_analytics ADD COLUMN commitment_kept INTEGER;

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (2, 'Neutral consistency check-in (commitment_kept)');
