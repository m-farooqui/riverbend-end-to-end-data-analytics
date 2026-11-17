# Online Store Raw Extraction

This pipeline creates an immutable, timestamped snapshot of the Riverbend online-store operational database.

## Source tables

- `products`
- `customers`
- `orders`
- `order_items`
- `store_events`

## Output

Each execution creates a folder under `raw` named like `run_20261028_143000_utc`.
Every run contains five CSV files, `manifest.json`, and `_SUCCESS`. The manifest records row counts, file sizes, and SHA-256 checksums.

## Run the pipeline

Open CMD in the Online Beverage Store folder and rebuild the backend once:

```cmd
docker compose up --build -d
docker compose exec backend python -m app.export_raw_data
```

The completed files appear in:

```text
04_Data_Pipelines_and_Architecture\01_Online_Store_Extraction\raw
```
