# Staging and Data Quality

This pipeline reads the newest successful raw snapshot, verifies every file checksum and manifest row count, validates business rules, and loads typed PostgreSQL tables in the `staging` schema.

## Run

From the Online Beverage Store folder:

```cmd
docker compose up --build -d --force-recreate
docker compose exec backend python -m app.load_staging
```

## Database outputs

- `staging.products`
- `staging.customers`
- `staging.orders`
- `staging.order_items`
- `staging.store_events`
- `staging.data_quality_runs`
- `staging.data_quality_checks`
- `staging.rejected_records`

## File outputs

Reports are created under `reports\dq_<source-run>`:

- `data_quality_report.json`
- `rejected_records.csv`

The raw snapshot is never changed.

## Verify

```sql
SELECT * FROM staging.data_quality_runs ORDER BY completed_at DESC;
SELECT * FROM staging.data_quality_checks ORDER BY table_name, check_name;
SELECT COUNT(*) FROM staging.orders;
SELECT COUNT(*) FROM staging.rejected_records;
```
