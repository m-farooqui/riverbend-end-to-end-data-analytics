"""Rebuild Riverbend web events as coherent customer journeys.

Run inside the backend container:
    python -m app.rebuild_coherent_web_events

This replaces only synthetic SYN-* store events. Orders, customers, products,
and sales data remain unchanged.
"""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import delete, insert, select

from .database import SessionLocal
from .models import Order, OrderItem, Product, StoreEvent


SEED = 202611
SESSION_COUNT = 13_000
PRODUCT_VIEW_COUNT = 9_000
ADD_TO_CART_COUNT = 7_000
CHECKOUT_COUNT = 6_500
PURCHASE_COUNT = 5_000

SOURCES = ["direct", "search", "email", "social", "referral"]
DEVICES = ["mobile", "mobile", "desktop", "tablet"]


def event_row(
    *,
    event_id: str,
    session_id: str,
    event_type: str,
    timestamp,
    source: str,
    device: str,
    product: Product | None = None,
    order: Order | None = None,
) -> dict:
    data = {"source": source, "device": device}
    if product is not None:
        data.update(
            {
                "product_id": product.id,
                "product_name": product.name,
                "category": product.category,
            }
        )
    if order is not None:
        data.update(
            {
                "order_id": order.id,
                "store": order.store,
                "order_total": str(order.order_total),
            }
        )

    return {
        "event_id": event_id,
        "session_id": session_id,
        "event_type": event_type,
        "event_timestamp": timestamp,
        "channel": "online_store",
        "event_data": data,
        "received_at": timestamp,
    }


def main() -> None:
    rng = random.Random(SEED)

    with SessionLocal() as database:
        products = list(database.scalars(select(Product).order_by(Product.id)).all())
        orders = list(
            database.scalars(
                select(Order)
                .where(Order.id.like("SYN-%"))
                .order_by(Order.ordered_at, Order.id)
            ).all()
        )

        if not products:
            raise RuntimeError("No products were found.")
        if len(orders) != PURCHASE_COUNT:
            raise RuntimeError(
                f"Expected {PURCHASE_COUNT:,} synthetic orders, found {len(orders):,}. "
                "Run the medium dataset generator first."
            )

        order_product_ids = dict(
            database.execute(
                select(OrderItem.order_id, OrderItem.product_id)
                .where(OrderItem.order_id.like("SYN-%"))
                .distinct(OrderItem.order_id)
                .order_by(OrderItem.order_id, OrderItem.product_id)
            ).all()
        )
        product_by_id = {product.id: product for product in products}

        # A deterministic shuffle prevents the non-purchase sessions from being
        # concentrated in only one date range.
        orders_for_sessions = orders.copy()
        rng.shuffle(orders_for_sessions)

        rows: list[dict] = []
        stage_counts = {
            "page_view": 0,
            "product_view": 0,
            "add_to_cart": 0,
            "checkout_started": 0,
            "purchase": 0,
        }

        for index in range(SESSION_COUNT):
            session_number = index + 1
            session_id = f"journey-{session_number:06d}"
            source = rng.choice(SOURCES)
            device = rng.choice(DEVICES)

            if index < PURCHASE_COUNT:
                order = orders_for_sessions[index]
                product = product_by_id.get(order_product_ids.get(order.id)) or rng.choice(products)
                purchase_time = order.ordered_at
                page_time = purchase_time - timedelta(minutes=rng.randint(18, 45))
            else:
                order = None
                product = rng.choice(products)
                anchor_order = orders_for_sessions[index % PURCHASE_COUNT]
                page_time = anchor_order.ordered_at + timedelta(
                    minutes=rng.randint(-720, 720)
                )
                purchase_time = None

            rows.append(
                event_row(
                    event_id=f"SYN-JOURNEY-{session_number:06d}-01-PAGE",
                    session_id=session_id,
                    event_type="page_view",
                    timestamp=page_time,
                    source=source,
                    device=device,
                )
            )
            stage_counts["page_view"] += 1

            if index < PRODUCT_VIEW_COUNT:
                product_time = (
                    purchase_time - timedelta(minutes=rng.randint(12, 17))
                    if purchase_time
                    else page_time + timedelta(minutes=rng.randint(1, 5))
                )
                rows.append(
                    event_row(
                        event_id=f"SYN-JOURNEY-{session_number:06d}-02-PRODUCT",
                        session_id=session_id,
                        event_type="product_view",
                        timestamp=product_time,
                        source=source,
                        device=device,
                        product=product,
                    )
                )
                stage_counts["product_view"] += 1

            if index < ADD_TO_CART_COUNT:
                cart_time = (
                    purchase_time - timedelta(minutes=rng.randint(7, 11))
                    if purchase_time
                    else page_time + timedelta(minutes=rng.randint(6, 12))
                )
                rows.append(
                    event_row(
                        event_id=f"SYN-JOURNEY-{session_number:06d}-03-CART",
                        session_id=session_id,
                        event_type="add_to_cart",
                        timestamp=cart_time,
                        source=source,
                        device=device,
                        product=product,
                    )
                )
                stage_counts["add_to_cart"] += 1

            if index < CHECKOUT_COUNT:
                checkout_time = (
                    purchase_time - timedelta(minutes=rng.randint(2, 6))
                    if purchase_time
                    else page_time + timedelta(minutes=rng.randint(13, 18))
                )
                rows.append(
                    event_row(
                        event_id=f"SYN-JOURNEY-{session_number:06d}-04-CHECKOUT",
                        session_id=session_id,
                        event_type="checkout_started",
                        timestamp=checkout_time,
                        source=source,
                        device=device,
                        product=product,
                        order=order,
                    )
                )
                stage_counts["checkout_started"] += 1

            if index < PURCHASE_COUNT:
                rows.append(
                    event_row(
                        event_id=f"SYN-JOURNEY-{session_number:06d}-05-PURCHASE",
                        session_id=session_id,
                        event_type="purchase",
                        timestamp=purchase_time,
                        source=source,
                        device=device,
                        product=product,
                        order=order,
                    )
                )
                stage_counts["purchase"] += 1

        # The transaction commits only after every new event has been inserted.
        database.execute(delete(StoreEvent).where(StoreEvent.event_id.like("SYN-%")))
        for start in range(0, len(rows), 5_000):
            database.execute(insert(StoreEvent), rows[start : start + 5_000])
        database.commit()

        print("Coherent Riverbend web journeys created successfully")
        print(f"Total sessions:    {SESSION_COUNT:,}")
        print(f"Total events:      {len(rows):,}")
        for stage, count in stage_counts.items():
            print(f"{stage:20s} {count:>7,} distinct sessions")
        print(f"Website conversion:      {PURCHASE_COUNT / SESSION_COUNT:.2%}")
        print(f"Cart-to-purchase rate:    {PURCHASE_COUNT / ADD_TO_CART_COUNT:.2%}")


if __name__ == "__main__":
    main()
