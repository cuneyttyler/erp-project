-- Runs once, on first container init, against the erp_platform database
-- created by POSTGRES_DB. Enables pgvector (technical.md §2/§8.7) so it's
-- available from the very first migration, in every environment.
CREATE EXTENSION IF NOT EXISTS vector;
