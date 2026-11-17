"""Build and validate the Riverbend analytics star schema."""

from pathlib import Path

from sqlalchemy import text

from .database import engine


SQL_PATH = Path("/app/analytics_sql/create_star_schema.sql")
STATEMENT_MARKER = "-- statement"


def main() -> None:
    if not SQL_PATH.exists():
        raise FileNotFoundError(f"Star-schema SQL was not mounted: {SQL_PATH}")

    sql_text = SQL_PATH.read_text(encoding="utf-8")
    statements = [part.strip() for part in sql_text.split(STATEMENT_MARKER) if part.strip()]

    with engine.begin() as connection:
        staging_exists = connection.scalar(text("SELECT to_regclass('staging.orders') IS NOT NULL"))
        if not staging_exists:
            raise RuntimeError("Staging tables were not found. Run python -m app.load_staging first.")

        for number, statement in enumerate(statements, start=1):
            connection.execute(text(statement))
            print(f"Completed SQL statement {number} of {len(statements)}")

        counts = connection.execute(text("""
            SELECT 'dim_date' AS table_name, COUNT(*) AS row_count FROM analytics.dim_date
            UNION ALL SELECT 'dim_customer', COUNT(*) FROM analytics.dim_customer
            UNION ALL SELECT 'dim_product', COUNT(*) FROM analytics.dim_product
            UNION ALL SELECT 'dim_store', COUNT(*) FROM analytics.dim_store
            UNION ALL SELECT 'fact_sales', COUNT(*) FROM analytics.fact_sales
            UNION ALL SELECT 'fact_web_events', COUNT(*) FROM analytics.fact_web_events
            ORDER BY table_name
        """)).all()

    print("Riverbend analytics star schema completed")
    for table_name, row_count in counts:
        print(f"{table_name}: {row_count:,} rows")


if __name__ == "__main__":
    main()

