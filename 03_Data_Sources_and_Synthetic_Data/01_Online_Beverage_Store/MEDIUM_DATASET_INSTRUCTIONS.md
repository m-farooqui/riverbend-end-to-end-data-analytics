# Riverbend Medium Dataset

This generator adds a repeatable demonstration dataset to the existing PostgreSQL database:

- 750 synthetic customers
- 5,000 synthetic online orders
- Approximately 10,000 order-item rows
- 30,000 website events
- Dates from January 1, 2025 through October 20, 2026

All generated order IDs begin with `SYN-`, all generated event IDs begin with `SYN-`, and all generated customer emails use the `example.com` domain.

## Installation

Extract `Riverbend-Medium-Dataset-Generator.zip` into the root of the existing `01_Online_Beverage_Store` folder. It adds one file:

```text
backend\app\generate_medium_dataset.py
```

## Generate the dataset

From the `01_Online_Beverage_Store` folder, run:

```cmd
docker compose up --build -d
docker compose exec backend python -m app.generate_medium_dataset
```

The generator uses a fixed random seed, so it creates consistent results for demonstrations. If the dataset already exists, it stops safely instead of duplicating the records.

To remove and regenerate only the synthetic records:

```cmd
docker compose exec backend python -m app.generate_medium_dataset --replace
```

## Verify the row counts

```cmd
docker exec -it riverbend-postgres psql -U riverbend -d riverbend
```

```sql
SELECT COUNT(*) FROM customers;
SELECT COUNT(*) FROM orders;
SELECT COUNT(*) FROM order_items;
SELECT COUNT(*) FROM store_events;
```

Exit PostgreSQL with `\q`.
