# Power BI Model Guide

Connect Power BI Desktop to PostgreSQL on `localhost:5432` using database `riverbend`, then select the six tables from the `analytics` schema.

## Recommended model

Use `fact_sales` as the center of the sales model and `fact_web_events` as the center of the digital-marketing model. The dimensions filter the fact tables; fact tables should not filter each other.

## Initial dashboard pages

1. Executive overview: revenue, orders, units, average order value, monthly trend.
2. Product and inventory: revenue and units by product/category.
3. Customer and loyalty: members versus non-members, repeat customers, customer revenue.
4. Store operations: revenue, orders, fulfillment method, and store comparison.
5. Marketing funnel: page views, product views, add-to-cart, checkout, and purchase events.

The next project phase will create the measures and visual specifications for these pages.
