CREATE SCHEMA IF NOT EXISTS operational;
CREATE SCHEMA IF NOT EXISTS analytics;

COMMENT ON SCHEMA operational IS 'Source-aligned operational tables for the Riverbend demonstration.';
COMMENT ON SCHEMA analytics IS 'Future reporting tables populated by the analytics pipeline.';
