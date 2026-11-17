"""Export Riverbend operational tables as a timestamped raw CSV snapshot."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from .database import engine


EXPORT_ROOT = Path("/app/exports")

EXPORTS = {
    "products": """
        SELECT id, name, category, style, price, size, badge, description, active
        FROM products ORDER BY id
    """,
    "customers": """
        SELECT id, full_name, email, loyalty_member, created_at
        FROM customers ORDER BY id
    """,
    "orders": """
        SELECT id, customer_id, fulfillment_method, store, promotion_code,
               order_total, order_status, ordered_at
        FROM orders ORDER BY ordered_at, id
    """,
    "order_items": """
        SELECT id, order_id, product_id, product_name, quantity, unit_price
        FROM order_items ORDER BY id
    """,
    "store_events": """
        SELECT id, event_id, session_id, event_type, event_timestamp,
               channel, event_data, received_at
        FROM store_events ORDER BY event_timestamp, id
    """,
}


def serialize(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_table(connection, name: str, query: str, output_directory: Path) -> dict:
    result = connection.execute(text(query))
    output_path = output_directory / f"{name}.csv"
    row_count = 0
    with output_path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.writer(destination)
        writer.writerow(result.keys())
        while True:
            rows = result.fetchmany(5_000)
            if not rows:
                break
            for row in rows:
                writer.writerow(serialize(value) for value in row)
            row_count += len(rows)

    return {
        "table": name,
        "file": output_path.name,
        "rows": row_count,
        "bytes": output_path.stat().st_size,
        "sha256": sha256(output_path),
    }


def main() -> None:
    extracted_at = datetime.now(timezone.utc)
    run_id = extracted_at.strftime("run_%Y%m%d_%H%M%S_utc")
    output_directory = EXPORT_ROOT / run_id
    output_directory.mkdir(parents=True, exist_ok=False)

    manifest = {
        "pipeline": "online_store_operational_extract",
        "source": "riverbend_postgresql",
        "run_id": run_id,
        "extracted_at_utc": extracted_at.isoformat(),
        "status": "running",
        "files": [],
    }

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                for table_name, query in EXPORTS.items():
                    details = export_table(connection, table_name, query, output_directory)
                    manifest["files"].append(details)
                    print(f"Exported {table_name}: {details['rows']:,} rows")
            finally:
                transaction.rollback()

        manifest["status"] = "succeeded"
        manifest["total_rows"] = sum(item["rows"] for item in manifest["files"])
        manifest["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        (output_directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        (output_directory / "_SUCCESS").write_text("", encoding="utf-8")
        print(f"Raw snapshot completed: {output_directory}")
        print(f"Total rows exported: {manifest['total_rows']:,}")
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = str(error)
        (output_directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        raise


if __name__ == "__main__":
    main()
