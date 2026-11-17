# Analytics Star Schema

This layer converts validated staging data into a reporting model designed for Power BI.

## Tables

| Table | Business purpose | Grain |
|---|---|---|
| `analytics.dim_date` | Calendar filtering and time comparisons | One row per date |
| `analytics.dim_customer` | Customer and loyalty analysis | One row per customer |
| `analytics.dim_product` | Product, category, style, and price analysis | One row per product |
| `analytics.dim_store` | Store and location comparisons | One row per store |
| `analytics.fact_sales` | Revenue, units, orders, discounts, and fulfillment | One row per order item |
| `analytics.fact_web_events` | Page views, carts, checkout activity, and purchases | One row per website event |

## Run the build

From the Online Beverage Store folder:

```cmd
docker compose up --build -d --force-recreate
docker compose exec backend python -m app.build_star_schema
```

The build can be rerun safely. It reloads the analytics tables from the latest contents of the staging schema.

## Verification queries with explanations

### Confirm that all six tables contain data

**Business purpose:** This query confirms that the dimensional model loaded successfully. Each result represents the number of records available to Power BI in one dimension or fact table.

```sql
SELECT 'dim_date' AS table_name, COUNT(*) AS row_count FROM analytics.dim_date
UNION ALL SELECT 'dim_customer', COUNT(*) FROM analytics.dim_customer
UNION ALL SELECT 'dim_product', COUNT(*) FROM analytics.dim_product
UNION ALL SELECT 'dim_store', COUNT(*) FROM analytics.dim_store
UNION ALL SELECT 'fact_sales', COUNT(*) FROM analytics.fact_sales
UNION ALL SELECT 'fact_web_events', COUNT(*) FROM analytics.fact_web_events
ORDER BY table_name;
```

### Review monthly revenue

**Business purpose:** Management can use this query to identify growth, seasonality, and weak months. The view groups individual sales records by year and month, counts orders and units, and totals revenue and discounts.

```sql
SELECT
    year_month,
    total_orders,
    units_sold,
    net_revenue,
    discounts
FROM analytics.vw_monthly_sales
ORDER BY year_month;
```

### Compare product performance

**Business purpose:** This query helps merchandising and inventory teams identify the highest-selling products. It orders products by net revenue so the strongest products appear first.

```sql
SELECT
    product_name,
    category,
    units_sold,
    total_orders,
    net_revenue
FROM analytics.vw_product_performance
ORDER BY net_revenue DESC;
```

### Analyze website behavior

**Business purpose:** Marketing can use this query to compare page views, product views, cart additions, checkout starts, and purchases. The results help identify where customers leave the purchasing process.

```sql
SELECT
    year_month,
    event_type,
    event_count,
    unique_sessions
FROM analytics.vw_marketing_funnel
ORDER BY year_month, event_type;
```

## Power BI relationships

Create one-to-many, single-direction relationships:

- `dim_date[date_key]` → `fact_sales[date_key]`
- `dim_date[date_key]` → `fact_web_events[date_key]`
- `dim_customer[customer_key]` → `fact_sales[customer_key]`
- `dim_product[product_key]` → `fact_sales[product_key]`
- `dim_product[product_key]` → `fact_web_events[product_key]`
- `dim_store[store_key]` → `fact_sales[store_key]`

Hide surrogate keys from report users after relationships are created.
