-- statement
-- Riverbend Beverage Company analytics star schema
CREATE SCHEMA IF NOT EXISTS analytics;

-- statement
CREATE TABLE IF NOT EXISTS analytics.dim_date (
    date_key integer PRIMARY KEY,
    full_date date UNIQUE NOT NULL,
    day_of_month smallint NOT NULL,
    day_name text NOT NULL,
    day_of_week smallint NOT NULL,
    week_of_year smallint NOT NULL,
    month_number smallint NOT NULL,
    month_name text NOT NULL,
    month_short_name text NOT NULL,
    quarter_number smallint NOT NULL,
    quarter_name text NOT NULL,
    year_number smallint NOT NULL,
    year_month text NOT NULL,
    is_weekend boolean NOT NULL
);

-- statement
CREATE TABLE IF NOT EXISTS analytics.dim_customer (
    customer_key bigserial PRIMARY KEY,
    customer_id integer UNIQUE NOT NULL,
    full_name text NOT NULL,
    email text NOT NULL,
    loyalty_member boolean NOT NULL,
    loyalty_status text NOT NULL,
    customer_since date NOT NULL
);

-- statement
CREATE TABLE IF NOT EXISTS analytics.dim_product (
    product_key bigserial PRIMARY KEY,
    product_id text UNIQUE NOT NULL,
    product_name text NOT NULL,
    category text NOT NULL,
    style text NOT NULL,
    package_size text NOT NULL,
    list_price numeric(10,2) NOT NULL,
    badge text,
    active boolean NOT NULL
);

-- statement
CREATE TABLE IF NOT EXISTS analytics.dim_store (
    store_key bigserial PRIMARY KEY,
    store_name text UNIQUE NOT NULL,
    city text NOT NULL,
    region text NOT NULL,
    store_type text NOT NULL
);

-- statement
CREATE TABLE IF NOT EXISTS analytics.fact_sales (
    sales_key bigserial PRIMARY KEY,
    order_id text NOT NULL,
    order_item_id integer UNIQUE NOT NULL,
    date_key integer NOT NULL REFERENCES analytics.dim_date(date_key),
    customer_key bigint NOT NULL REFERENCES analytics.dim_customer(customer_key),
    product_key bigint NOT NULL REFERENCES analytics.dim_product(product_key),
    store_key bigint NOT NULL REFERENCES analytics.dim_store(store_key),
    fulfillment_method text NOT NULL,
    promotion_code text,
    order_status text NOT NULL,
    quantity integer NOT NULL,
    unit_price numeric(10,2) NOT NULL,
    gross_sales numeric(12,2) NOT NULL,
    discount_amount numeric(12,2) NOT NULL,
    net_sales numeric(12,2) NOT NULL,
    ordered_at timestamptz NOT NULL
);

-- statement
CREATE TABLE IF NOT EXISTS analytics.fact_web_events (
    web_event_key bigserial PRIMARY KEY,
    event_id text UNIQUE NOT NULL,
    date_key integer NOT NULL REFERENCES analytics.dim_date(date_key),
    product_key bigint REFERENCES analytics.dim_product(product_key),
    session_id text,
    event_type text NOT NULL,
    channel text NOT NULL,
    device_type text,
    traffic_source text,
    event_timestamp timestamptz NOT NULL
);

-- statement
TRUNCATE TABLE
    analytics.fact_sales,
    analytics.fact_web_events,
    analytics.dim_customer,
    analytics.dim_product,
    analytics.dim_store,
    analytics.dim_date
RESTART IDENTITY CASCADE;

-- statement
INSERT INTO analytics.dim_date (
    date_key, full_date, day_of_month, day_name, day_of_week, week_of_year,
    month_number, month_name, month_short_name, quarter_number, quarter_name,
    year_number, year_month, is_weekend
)
SELECT
    TO_CHAR(calendar_date, 'YYYYMMDD')::integer,
    calendar_date,
    EXTRACT(DAY FROM calendar_date)::smallint,
    TRIM(TO_CHAR(calendar_date, 'Day')),
    EXTRACT(ISODOW FROM calendar_date)::smallint,
    EXTRACT(WEEK FROM calendar_date)::smallint,
    EXTRACT(MONTH FROM calendar_date)::smallint,
    TRIM(TO_CHAR(calendar_date, 'Month')),
    TO_CHAR(calendar_date, 'Mon'),
    EXTRACT(QUARTER FROM calendar_date)::smallint,
    'Q' || EXTRACT(QUARTER FROM calendar_date)::integer,
    EXTRACT(YEAR FROM calendar_date)::smallint,
    TO_CHAR(calendar_date, 'YYYY-MM'),
    EXTRACT(ISODOW FROM calendar_date) IN (6, 7)
FROM GENERATE_SERIES(
    LEAST(
        (SELECT MIN(ordered_at)::date FROM staging.orders),
        (SELECT MIN(event_timestamp)::date FROM staging.store_events)
    ),
    GREATEST(
        (SELECT MAX(ordered_at)::date FROM staging.orders),
        (SELECT MAX(event_timestamp)::date FROM staging.store_events)
    ),
    INTERVAL '1 day'
) AS dates(calendar_date);

-- statement
INSERT INTO analytics.dim_customer (
    customer_id, full_name, email, loyalty_member, loyalty_status, customer_since
)
SELECT
    id,
    full_name,
    email,
    loyalty_member,
    CASE WHEN loyalty_member THEN 'Loyalty member' ELSE 'Non-member' END,
    created_at::date
FROM staging.customers;

-- statement
INSERT INTO analytics.dim_product (
    product_id, product_name, category, style, package_size, list_price, badge, active
)
SELECT id, name, category, style, size, price, badge, active
FROM staging.products;

-- statement
INSERT INTO analytics.dim_store (store_name, city, region, store_type)
SELECT DISTINCT
    store,
    SPLIT_PART(store, ' ', 1),
    'Capital Region',
    CASE
        WHEN store ILIKE '%Hub%' THEN 'Pickup hub'
        WHEN store ILIKE '%Market%' THEN 'Market store'
        ELSE 'Flagship store'
    END
FROM staging.orders;

-- statement
WITH order_gross AS (
    SELECT
        order_id,
        SUM(quantity * unit_price) AS gross_order_value
    FROM staging.order_items
    GROUP BY order_id
),
allocated_sales AS (
    SELECT
        oi.id AS order_item_id,
        oi.order_id,
        oi.product_id,
        oi.quantity,
        oi.unit_price,
        o.customer_id,
        o.store,
        o.fulfillment_method,
        o.promotion_code,
        o.order_status,
        o.ordered_at,
        ROUND((oi.quantity * oi.unit_price)::numeric, 2) AS gross_sales,
        CASE
            WHEN o.order_status = 'cancelled' THEN 0::numeric
            ELSE ROUND(
                ((oi.quantity * oi.unit_price) / NULLIF(og.gross_order_value, 0) * o.order_total)::numeric,
                2
            )
        END AS allocated_net_sales
    FROM staging.order_items oi
    JOIN staging.orders o ON o.id = oi.order_id
    JOIN order_gross og ON og.order_id = oi.order_id
)
INSERT INTO analytics.fact_sales (
    order_id, order_item_id, date_key, customer_key, product_key, store_key,
    fulfillment_method, promotion_code, order_status, quantity, unit_price,
    gross_sales, discount_amount, net_sales, ordered_at
)
SELECT
    sales.order_id,
    sales.order_item_id,
    TO_CHAR(sales.ordered_at, 'YYYYMMDD')::integer,
    customer.customer_key,
    product.product_key,
    store.store_key,
    sales.fulfillment_method,
    sales.promotion_code,
    sales.order_status,
    sales.quantity,
    sales.unit_price,
    sales.gross_sales,
    GREATEST(sales.gross_sales - sales.allocated_net_sales, 0),
    sales.allocated_net_sales,
    sales.ordered_at
FROM allocated_sales sales
JOIN analytics.dim_customer customer ON customer.customer_id = sales.customer_id
JOIN analytics.dim_product product ON product.product_id = sales.product_id
JOIN analytics.dim_store store ON store.store_name = sales.store;

-- statement
INSERT INTO analytics.fact_web_events (
    event_id, date_key, product_key, session_id, event_type, channel,
    device_type, traffic_source, event_timestamp
)
SELECT
    events.event_id,
    TO_CHAR(events.event_timestamp, 'YYYYMMDD')::integer,
    product.product_key,
    events.session_id,
    events.event_type,
    events.channel,
    NULLIF(events.event_data ->> 'device', ''),
    NULLIF(events.event_data ->> 'source', ''),
    events.event_timestamp
FROM staging.store_events events
LEFT JOIN analytics.dim_product product
    ON product.product_id = events.event_data ->> 'product_id';

-- statement
CREATE INDEX IF NOT EXISTS ix_fact_sales_date ON analytics.fact_sales(date_key);

-- statement
CREATE INDEX IF NOT EXISTS ix_fact_sales_customer ON analytics.fact_sales(customer_key);

-- statement
CREATE INDEX IF NOT EXISTS ix_fact_sales_product ON analytics.fact_sales(product_key);

-- statement
CREATE INDEX IF NOT EXISTS ix_fact_sales_store ON analytics.fact_sales(store_key);

-- statement
CREATE INDEX IF NOT EXISTS ix_fact_web_events_date ON analytics.fact_web_events(date_key);

-- statement
CREATE INDEX IF NOT EXISTS ix_fact_web_events_product ON analytics.fact_web_events(product_key);

-- statement
CREATE OR REPLACE VIEW analytics.vw_monthly_sales AS
SELECT
    date.year_month,
    date.year_number,
    date.month_number,
    COUNT(DISTINCT sales.order_id) AS total_orders,
    SUM(sales.quantity) AS units_sold,
    ROUND(SUM(sales.net_sales), 2) AS net_revenue,
    ROUND(SUM(sales.discount_amount), 2) AS discounts
FROM analytics.fact_sales sales
JOIN analytics.dim_date date ON date.date_key = sales.date_key
GROUP BY date.year_month, date.year_number, date.month_number;

-- statement
CREATE OR REPLACE VIEW analytics.vw_product_performance AS
SELECT
    product.product_id,
    product.product_name,
    product.category,
    SUM(sales.quantity) AS units_sold,
    COUNT(DISTINCT sales.order_id) AS total_orders,
    ROUND(SUM(sales.net_sales), 2) AS net_revenue
FROM analytics.fact_sales sales
JOIN analytics.dim_product product ON product.product_key = sales.product_key
GROUP BY product.product_id, product.product_name, product.category;

-- statement
CREATE OR REPLACE VIEW analytics.vw_marketing_funnel AS
SELECT
    date.year_month,
    events.event_type,
    COUNT(*) AS event_count,
    COUNT(DISTINCT events.session_id) AS unique_sessions
FROM analytics.fact_web_events events
JOIN analytics.dim_date date ON date.date_key = events.date_key
GROUP BY date.year_month, events.event_type;
