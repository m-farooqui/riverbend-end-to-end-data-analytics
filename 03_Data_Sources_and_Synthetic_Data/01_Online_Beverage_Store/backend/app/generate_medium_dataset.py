"""Generate a repeatable medium-sized Riverbend online-store dataset.

Run inside the backend container:
    python -m app.generate_medium_dataset

Run again from a clean synthetic baseline:
    python -m app.generate_medium_dataset --replace
"""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import delete, func, insert, select, text

from .database import SessionLocal
from .models import Customer, Order, OrderItem, Product, StoreEvent


SEED = 202611
CUSTOMER_COUNT = 750
ORDER_COUNT = 5_000
EVENT_COUNT = 30_000
START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2026, 10, 20, 23, 59, 59, tzinfo=timezone.utc)

FIRST_NAMES = [
    "Aaliyah", "Aiden", "Amelia", "Andre", "Ava", "Carlos", "Chloe", "Daniel",
    "Elena", "Ethan", "Fatima", "Grace", "Henry", "Isabella", "Jackson", "Jamal",
    "Leah", "Liam", "Maya", "Mia", "Noah", "Olivia", "Priya", "Rafael",
    "Sofia", "Sophia", "Tariq", "William", "Yasmin", "Zoe",
]
LAST_NAMES = [
    "Adams", "Baker", "Brooks", "Carter", "Chen", "Davis", "Diaz", "Edwards",
    "Garcia", "Green", "Hall", "Hernandez", "Jackson", "Johnson", "Khan", "Kim",
    "Lee", "Lewis", "Martin", "Martinez", "Miller", "Nguyen", "Patel", "Rivera",
    "Robinson", "Rodriguez", "Smith", "Taylor", "Thomas", "Williams",
]
STORES = ["Albany Flagship", "Troy Market", "Schenectady Pickup Hub"]
PROMOTIONS = [None, None, None, None, "SUMMER10", "WELCOME10", "WEEKEND5"]
EVENT_TYPES = [
    "page_view", "page_view", "page_view", "product_view", "product_view",
    "search", "add_to_cart", "remove_from_cart", "checkout_started",
]
MONTH_MULTIPLIER = {
    1: 0.75, 2: 0.78, 3: 0.88, 4: 0.95, 5: 1.05, 6: 1.12,
    7: 1.18, 8: 1.10, 9: 0.98, 10: 1.02, 11: 1.28, 12: 1.55,
}


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def weighted_timestamp(rng: random.Random) -> datetime:
    total_seconds = int((END_DATE - START_DATE).total_seconds())
    while True:
        candidate = START_DATE + timedelta(seconds=rng.randint(0, total_seconds))
        weekday_multiplier = 1.18 if candidate.weekday() in (4, 5) else 0.95
        hour_multiplier = 1.25 if 16 <= candidate.hour <= 21 else 0.80
        acceptance = MONTH_MULTIPLIER[candidate.month] * weekday_multiplier * hour_multiplier
        if rng.random() < min(acceptance / 2.0, 1.0):
            return candidate


def remove_previous_synthetic_data(database) -> None:
    synthetic_order_ids = select(Order.id).where(Order.id.like("SYN-%"))
    database.execute(delete(OrderItem).where(OrderItem.order_id.in_(synthetic_order_ids)))
    database.execute(delete(Order).where(Order.id.like("SYN-%")))
    database.execute(delete(StoreEvent).where(StoreEvent.event_id.like("SYN-%")))
    database.execute(delete(Customer).where(Customer.email.like("demo_customer_%@example.com")))
    database.commit()


def main(replace: bool) -> None:
    rng = random.Random(SEED)

    with SessionLocal() as database:
        existing = database.scalar(
            select(func.count()).select_from(Order).where(Order.id.like("SYN-%"))
        )
        if existing and not replace:
            print(
                f"Synthetic data already exists ({existing:,} orders). "
                "Use --replace to regenerate it."
            )
            return
        if replace:
            remove_previous_synthetic_data(database)

        products = list(database.scalars(select(Product).order_by(Product.id)).all())
        if not products:
            raise RuntimeError("No products found. Start the API once so products are seeded.")

        next_customer_id = (database.scalar(select(func.max(Customer.id))) or 0) + 1
        customer_rows = []
        customer_ids = []
        for number in range(1, CUSTOMER_COUNT + 1):
            customer_id = next_customer_id + number - 1
            customer_ids.append(customer_id)
            created_at = weighted_timestamp(rng)
            customer_rows.append(
                {
                    "id": customer_id,
                    "full_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                    "email": f"demo_customer_{number:04d}@example.com",
                    "loyalty_member": rng.random() < 0.42,
                    "created_at": created_at,
                }
            )
        database.execute(insert(Customer), customer_rows)

        product_weights = [24, 21, 17, 12, 10, 16]
        order_rows = []
        item_rows = []
        purchase_events = []
        next_item_id = (database.scalar(select(func.max(OrderItem.id))) or 0) + 1

        for order_number in range(1, ORDER_COUNT + 1):
            order_id = f"SYN-{order_number:06d}"
            ordered_at = weighted_timestamp(rng)
            customer_id = rng.choice(customer_ids)
            item_count = rng.choices([1, 2, 3, 4], weights=[38, 37, 19, 6], k=1)[0]
            chosen_products = rng.choices(products, weights=product_weights, k=item_count)
            quantities: dict[str, int] = {}
            for product in chosen_products:
                quantities[product.id] = quantities.get(product.id, 0) + rng.choices(
                    [1, 2, 3], weights=[78, 18, 4], k=1
                )[0]

            subtotal = Decimal("0.00")
            for product_id, quantity in quantities.items():
                product = next(product for product in products if product.id == product_id)
                subtotal += Decimal(product.price) * quantity
                item_rows.append(
                    {
                        "id": next_item_id,
                        "order_id": order_id,
                        "product_id": product.id,
                        "product_name": product.name,
                        "quantity": quantity,
                        "unit_price": money(Decimal(product.price)),
                    }
                )
                next_item_id += 1

            promotion = rng.choice(PROMOTIONS)
            discount_rate = Decimal("0.10") if promotion in ("SUMMER10", "WELCOME10") else Decimal("0.05") if promotion else Decimal("0.00")
            order_total = money(subtotal * (Decimal("1.00") - discount_rate))
            fulfillment = rng.choices(["store_pickup", "delivery"], weights=[64, 36], k=1)[0]
            store = rng.choices(STORES, weights=[50, 30, 20], k=1)[0]

            order_rows.append(
                {
                    "id": order_id,
                    "customer_id": customer_id,
                    "fulfillment_method": fulfillment,
                    "store": store,
                    "promotion_code": promotion,
                    "order_total": order_total,
                    "order_status": rng.choices(
                        ["completed", "confirmed", "cancelled"], weights=[86, 11, 3], k=1
                    )[0],
                    "ordered_at": ordered_at,
                }
            )

            session_id = f"session-{uuid.UUID(int=rng.getrandbits(128))}"
            purchase_events.extend(
                [
                    {
                        "event_id": f"SYN-CHECKOUT-{order_number:06d}",
                        "session_id": session_id,
                        "event_type": "checkout_started",
                        "event_timestamp": ordered_at - timedelta(minutes=rng.randint(2, 15)),
                        "channel": "online_store",
                        "event_data": {"order_id": order_id, "store": store},
                        "received_at": ordered_at,
                    },
                    {
                        "event_id": f"SYN-PURCHASE-{order_number:06d}",
                        "session_id": session_id,
                        "event_type": "purchase",
                        "event_timestamp": ordered_at,
                        "channel": "online_store",
                        "event_data": {"order_id": order_id, "order_total": str(order_total)},
                        "received_at": ordered_at,
                    },
                ]
            )

        database.execute(insert(Order), order_rows)
        database.execute(insert(OrderItem), item_rows)

        # Keep PostgreSQL identity sequences aligned after assigning explicit IDs.
        database.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('customers', 'id'), "
                "(SELECT MAX(id) FROM customers), true)"
            )
        )
        database.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('order_items', 'id'), "
                "(SELECT MAX(id) FROM order_items), true)"
            )
        )

        browsing_events = []
        remaining_events = EVENT_COUNT - len(purchase_events)
        for event_number in range(1, remaining_events + 1):
            timestamp = weighted_timestamp(rng)
            product = rng.choice(products)
            event_type = rng.choice(EVENT_TYPES)
            browsing_events.append(
                {
                    "event_id": f"SYN-EVENT-{event_number:07d}",
                    "session_id": f"session-{rng.randint(1, 9000):05d}",
                    "event_type": event_type,
                    "event_timestamp": timestamp,
                    "channel": "online_store",
                    "event_data": {
                        "product_id": product.id,
                        "product_name": product.name,
                        "category": product.category,
                        "source": rng.choice(["direct", "search", "email", "social", "referral"]),
                        "device": rng.choice(["mobile", "mobile", "desktop", "tablet"]),
                    },
                    "received_at": timestamp,
                }
            )

        for rows in (purchase_events, browsing_events):
            for start in range(0, len(rows), 5_000):
                database.execute(insert(StoreEvent), rows[start : start + 5_000])

        database.commit()

        print("Riverbend medium dataset created successfully")
        print(f"Customers:     {len(customer_rows):,}")
        print(f"Orders:        {len(order_rows):,}")
        print(f"Order items:   {len(item_rows):,}")
        print(f"Store events:  {len(purchase_events) + len(browsing_events):,}")
        print(f"Date range:    {START_DATE.date()} through {END_DATE.date()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Remove the previously generated SYN records and regenerate them.",
    )
    arguments = parser.parse_args()
    main(replace=arguments.replace)
