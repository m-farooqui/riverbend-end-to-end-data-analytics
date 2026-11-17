# Riverbend Beverage Company Online Store

This project is the first operational source system for the November SQL presentation. It demonstrates how customer interactions become database records that can later feed data pipelines, analytics models, and Power BI dashboards.

## Services

- Frontend: HTML, CSS, and JavaScript served by Nginx
- Backend: FastAPI and SQLAlchemy
- Database: PostgreSQL

## Start the project on Windows

Open PowerShell in the project folder and run:

```powershell
docker compose up --build -d
```

Open:

- Storefront: http://localhost:8080
- FastAPI documentation: http://localhost:8000/docs
- FastAPI health check: http://localhost:8000/health

The promotion code for the demonstration is `SUMMER10`.

## Check the containers

```powershell
docker compose ps
```

## View backend logs

```powershell
docker compose logs -f backend
```

Press `Ctrl+C` to stop following the logs.

## Query the generated data

Open a PostgreSQL prompt inside the container:

```powershell
docker exec -it riverbend-postgres psql -U riverbend -d riverbend
```

Run these queries:

```sql
SELECT * FROM products ORDER BY id;

SELECT event_type, COUNT(*) AS event_count
FROM store_events
GROUP BY event_type
ORDER BY event_count DESC;

SELECT id, customer_id, order_total, promotion_code, ordered_at
FROM orders
ORDER BY ordered_at DESC;
```

Exit PostgreSQL:

```text
\q
```

## Stop the project

```powershell
docker compose down
```

The PostgreSQL volume preserves the generated records. To remove the stored demonstration records as well, run:

```powershell
docker compose down -v
```

Only use the `-v` command when you intentionally want to delete the demonstration database.

## Data generated

The storefront records:

- Browser sessions
- Age-gate responses
- Product views and searches
- Cart additions and quantity changes
- Promotion attempts
- Checkout starts
- Age confirmation
- Customers and loyalty enrollment
- Orders and order items

The hosted static storefront keeps a browser-local fallback. The Docker version sends the same activity to FastAPI and PostgreSQL.
