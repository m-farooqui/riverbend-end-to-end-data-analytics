"""Validate the latest raw snapshot and load PostgreSQL staging tables."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import text

from .database import engine


RAW_ROOT = Path("/app/exports")
OUTPUT_ROOT = Path("/app/staging_output")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.products (
    id text PRIMARY KEY, name text NOT NULL, category text NOT NULL,
    style text NOT NULL, price numeric(10,2) NOT NULL, size text NOT NULL,
    badge text, description text, active boolean NOT NULL, source_run_id text NOT NULL
);
CREATE TABLE IF NOT EXISTS staging.customers (
    id integer PRIMARY KEY, full_name text NOT NULL, email text NOT NULL,
    loyalty_member boolean NOT NULL, created_at timestamptz NOT NULL,
    source_run_id text NOT NULL
);
CREATE TABLE IF NOT EXISTS staging.orders (
    id text PRIMARY KEY, customer_id integer NOT NULL, fulfillment_method text NOT NULL,
    store text NOT NULL, promotion_code text, order_total numeric(10,2) NOT NULL,
    order_status text NOT NULL, ordered_at timestamptz NOT NULL, source_run_id text NOT NULL
);
CREATE TABLE IF NOT EXISTS staging.order_items (
    id integer PRIMARY KEY, order_id text NOT NULL, product_id text NOT NULL,
    product_name text NOT NULL, quantity integer NOT NULL,
    unit_price numeric(10,2) NOT NULL, source_run_id text NOT NULL
);
CREATE TABLE IF NOT EXISTS staging.store_events (
    id integer PRIMARY KEY, event_id text NOT NULL, session_id text,
    event_type text NOT NULL, event_timestamp timestamptz NOT NULL,
    channel text NOT NULL, event_data jsonb NOT NULL,
    received_at timestamptz NOT NULL, source_run_id text NOT NULL
);
CREATE TABLE IF NOT EXISTS staging.data_quality_runs (
    run_id text PRIMARY KEY, source_run_id text NOT NULL, started_at timestamptz NOT NULL,
    completed_at timestamptz, status text NOT NULL, accepted_records integer NOT NULL,
    rejected_records integer NOT NULL, report_path text
);
CREATE TABLE IF NOT EXISTS staging.data_quality_checks (
    id bigserial PRIMARY KEY, run_id text NOT NULL, table_name text NOT NULL,
    check_name text NOT NULL, passed boolean NOT NULL, failed_rows integer NOT NULL,
    details text
);
CREATE TABLE IF NOT EXISTS staging.rejected_records (
    id bigserial PRIMARY KEY, run_id text NOT NULL, table_name text NOT NULL,
    row_number integer NOT NULL, reason text NOT NULL, raw_record jsonb NOT NULL
);
"""

INSERT_SQL = {
    "products": """INSERT INTO staging.products
        (id,name,category,style,price,size,badge,description,active,source_run_id)
        VALUES (:id,:name,:category,:style,:price,:size,:badge,:description,:active,:source_run_id)""",
    "customers": """INSERT INTO staging.customers
        (id,full_name,email,loyalty_member,created_at,source_run_id)
        VALUES (:id,:full_name,:email,:loyalty_member,:created_at,:source_run_id)""",
    "orders": """INSERT INTO staging.orders
        (id,customer_id,fulfillment_method,store,promotion_code,order_total,order_status,ordered_at,source_run_id)
        VALUES (:id,:customer_id,:fulfillment_method,:store,:promotion_code,:order_total,:order_status,:ordered_at,:source_run_id)""",
    "order_items": """INSERT INTO staging.order_items
        (id,order_id,product_id,product_name,quantity,unit_price,source_run_id)
        VALUES (:id,:order_id,:product_id,:product_name,:quantity,:unit_price,:source_run_id)""",
    "store_events": """INSERT INTO staging.store_events
        (id,event_id,session_id,event_type,event_timestamp,channel,event_data,received_at,source_run_id)
        VALUES (:id,:event_id,:session_id,:event_type,:event_timestamp,:channel,CAST(:event_data AS jsonb),:received_at,:source_run_id)""",
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def latest_snapshot() -> Path:
    candidates = [
        folder for folder in RAW_ROOT.glob("run_*_utc")
        if (folder / "_SUCCESS").exists() and (folder / "manifest.json").exists()
    ]
    if not candidates:
        raise RuntimeError("No successful raw snapshot found. Run export_raw_data first.")
    return max(candidates, key=lambda folder: folder.name)


def required(row: dict, fields: list[str]) -> None:
    missing = [field for field in fields if not str(row.get(field, "")).strip()]
    if missing:
        raise ValueError(f"missing required values: {', '.join(missing)}")


def integer(value: str, field: str, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} is not an integer") from error
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return parsed


def decimal_value(value: str, field: str, minimum: Decimal | None = None) -> Decimal:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError) as error:
        raise ValueError(f"{field} is not numeric") from error
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return parsed


def boolean(value: str, field: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "t"}:
        return True
    if normalized in {"false", "0", "no", "f"}:
        return False
    raise ValueError(f"{field} is not boolean")


def timestamp(value: str, field: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} is not a valid timestamp") from error
    return value


def transform(table: str, row: dict, keys: dict[str, set]) -> dict:
    if table == "products":
        required(row, ["id", "name", "category", "style", "price", "size", "active"])
        row["price"] = decimal_value(row["price"], "price", Decimal("0"))
        row["active"] = boolean(row["active"], "active")
    elif table == "customers":
        required(row, ["id", "full_name", "email", "loyalty_member", "created_at"])
        row["id"] = integer(row["id"], "id", 1)
        if not EMAIL_PATTERN.match(row["email"]):
            raise ValueError("email has an invalid format")
        row["loyalty_member"] = boolean(row["loyalty_member"], "loyalty_member")
        row["created_at"] = timestamp(row["created_at"], "created_at")
    elif table == "orders":
        required(row, ["id", "customer_id", "fulfillment_method", "store", "order_total", "order_status", "ordered_at"])
        row["customer_id"] = integer(row["customer_id"], "customer_id", 1)
        if row["customer_id"] not in keys["customers"]:
            raise ValueError("customer_id does not exist in accepted customers")
        row["order_total"] = decimal_value(row["order_total"], "order_total", Decimal("0"))
        if row["order_status"] not in {"confirmed", "completed", "cancelled"}:
            raise ValueError("order_status is not recognized")
        row["ordered_at"] = timestamp(row["ordered_at"], "ordered_at")
        row["promotion_code"] = row.get("promotion_code") or None
    elif table == "order_items":
        required(row, ["id", "order_id", "product_id", "product_name", "quantity", "unit_price"])
        row["id"] = integer(row["id"], "id", 1)
        row["quantity"] = integer(row["quantity"], "quantity", 1)
        row["unit_price"] = decimal_value(row["unit_price"], "unit_price", Decimal("0"))
        if row["order_id"] not in keys["orders"]:
            raise ValueError("order_id does not exist in accepted orders")
        if row["product_id"] not in keys["products"]:
            raise ValueError("product_id does not exist in accepted products")
    elif table == "store_events":
        required(row, ["id", "event_id", "event_type", "event_timestamp", "channel", "event_data", "received_at"])
        row["id"] = integer(row["id"], "id", 1)
        row["event_timestamp"] = timestamp(row["event_timestamp"], "event_timestamp")
        row["received_at"] = timestamp(row["received_at"], "received_at")
        try:
            json.loads(row["event_data"])
        except json.JSONDecodeError as error:
            raise ValueError("event_data is not valid JSON") from error
        row["session_id"] = row.get("session_id") or None
    return row


def main() -> None:
    started_at = datetime.now(timezone.utc)
    snapshot = latest_snapshot()
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    source_run_id = manifest["run_id"]
    run_id = f"dq_{source_run_id.removeprefix('run_')}"
    report_dir = OUTPUT_ROOT / "reports" / run_id
    report_dir.mkdir(parents=True, exist_ok=True)

    accepted: dict[str, list[dict]] = {}
    rejected: list[dict] = []
    checks: list[dict] = []
    keys = {"products": set(), "customers": set(), "orders": set()}
    primary_fields = {
        "products": "id", "customers": "id", "orders": "id",
        "order_items": "id", "store_events": "id",
    }

    for file_info in manifest["files"]:
        table = file_info["table"]
        csv_path = snapshot / file_info["file"]
        checksum_ok = file_hash(csv_path) == file_info["sha256"]
        checks.append({"table_name": table, "check_name": "sha256_checksum", "passed": checksum_ok, "failed_rows": 0 if checksum_ok else 1, "details": "Raw file matches manifest" if checksum_ok else "Checksum mismatch"})
        if not checksum_ok:
            raise RuntimeError(f"Checksum mismatch for {csv_path.name}")

        accepted[table] = []
        seen = set()
        with csv_path.open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            source_rows = 0
            for row_number, raw_row in enumerate(reader, start=2):
                source_rows += 1
                try:
                    row = transform(table, dict(raw_row), keys)
                    primary_value = row[primary_fields[table]]
                    if primary_value in seen:
                        raise ValueError(f"duplicate {primary_fields[table]}")
                    seen.add(primary_value)
                    row["source_run_id"] = source_run_id
                    accepted[table].append(row)
                    if table in keys:
                        keys[table].add(primary_value)
                except ValueError as error:
                    rejected.append({"table_name": table, "row_number": row_number, "reason": str(error), "raw_record": raw_row})

        count_ok = source_rows == file_info["rows"]
        checks.append({"table_name": table, "check_name": "manifest_row_count", "passed": count_ok, "failed_rows": abs(source_rows - file_info["rows"]), "details": f"Manifest={file_info['rows']}; CSV={source_rows}"})
        checks.append({"table_name": table, "check_name": "validation_rejections", "passed": not any(item["table_name"] == table for item in rejected), "failed_rows": sum(item["table_name"] == table for item in rejected), "details": f"Accepted={len(accepted[table])}"})

    with engine.begin() as connection:
        for statement in [item.strip() for item in SCHEMA_SQL.split(";") if item.strip()]:
            connection.execute(text(statement))
        connection.execute(text("TRUNCATE staging.order_items, staging.orders, staging.store_events, staging.customers, staging.products"))
        connection.execute(text("DELETE FROM staging.data_quality_checks WHERE run_id=:run_id"), {"run_id": run_id})
        connection.execute(text("DELETE FROM staging.rejected_records WHERE run_id=:run_id"), {"run_id": run_id})
        connection.execute(text("DELETE FROM staging.data_quality_runs WHERE run_id=:run_id"), {"run_id": run_id})

        for table in ["products", "customers", "orders", "order_items", "store_events"]:
            rows = accepted[table]
            for start in range(0, len(rows), 2_000):
                connection.execute(text(INSERT_SQL[table]), rows[start:start + 2_000])

        for check in checks:
            connection.execute(text("""INSERT INTO staging.data_quality_checks
                (run_id,table_name,check_name,passed,failed_rows,details)
                VALUES (:run_id,:table_name,:check_name,:passed,:failed_rows,:details)"""), {"run_id": run_id, **check})
        for item in rejected:
            connection.execute(text("""INSERT INTO staging.rejected_records
                (run_id,table_name,row_number,reason,raw_record)
                VALUES (:run_id,:table_name,:row_number,:reason,CAST(:raw_record AS jsonb))"""), {**item, "run_id": run_id, "raw_record": json.dumps(item["raw_record"])})

        completed_at = datetime.now(timezone.utc)
        total_accepted = sum(len(rows) for rows in accepted.values())
        connection.execute(text("""INSERT INTO staging.data_quality_runs
            (run_id,source_run_id,started_at,completed_at,status,accepted_records,rejected_records,report_path)
            VALUES (:run_id,:source_run_id,:started_at,:completed_at,:status,:accepted_records,:rejected_records,:report_path)"""), {
                "run_id": run_id, "source_run_id": source_run_id,
                "started_at": started_at, "completed_at": completed_at,
                "status": "succeeded" if all(check["passed"] for check in checks) else "completed_with_warnings",
                "accepted_records": total_accepted, "rejected_records": len(rejected),
                "report_path": str(report_dir / "data_quality_report.json"),
            })

    report = {
        "run_id": run_id, "source_run_id": source_run_id,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "accepted_by_table": {table: len(rows) for table, rows in accepted.items()},
        "accepted_records": sum(len(rows) for rows in accepted.values()),
        "rejected_records": len(rejected), "checks": checks,
    }
    (report_dir / "data_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (report_dir / "rejected_records.csv").open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=["table_name", "row_number", "reason", "raw_record"])
        writer.writeheader()
        for item in rejected:
            writer.writerow({**item, "raw_record": json.dumps(item["raw_record"], sort_keys=True)})

    print(f"Loaded staging from: {source_run_id}")
    for table, rows in accepted.items():
        print(f"Accepted {table}: {len(rows):,}")
    print(f"Rejected records: {len(rejected):,}")
    print(f"Quality report: {report_dir / 'data_quality_report.json'}")


if __name__ == "__main__":
    main()
