-- Minimal compatible column for knowledge-base processing failures (MySQL).

ALTER TABLE knowledge_docs
    ADD COLUMN error_message VARCHAR(1000) NULL;
