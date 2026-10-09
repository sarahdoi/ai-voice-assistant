-- Retention: when this user last started a call. Guests inactive for longer than
-- MEMORY_RETENTION_DAYS have their facts deleted by the agent (see retention.py).
ALTER TABLE memories ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS memories_last_seen_at_idx ON memories (last_seen_at);
