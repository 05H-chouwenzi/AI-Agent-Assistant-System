-- Minimal compatible column for pgvector chunk metadata.
-- Apply only to the PostgreSQL database configured by PGVECTOR_DATABASE_URL.

ALTER TABLE knowledge_vectors
    ADD COLUMN metadata_json JSON NULL;
