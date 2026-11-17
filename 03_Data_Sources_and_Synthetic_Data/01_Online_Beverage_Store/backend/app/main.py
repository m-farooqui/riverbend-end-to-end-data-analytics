import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .models import Customer, Order, OrderItem, Product, StoreEvent
from .schemas import EventCreate, EventResponse, OrderCreate, OrderResponse, ProductResponse
from .seed import seed_products


def initialize_database() -> None:
    for attempt in range(20):
        try:
            Base.metadata.create_all(bind=engine)
            with SessionLocal() as database:
                seed_products(database)
            return
        except OperationalError:
            if attempt == 19:
                raise
            time.sleep(2)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Riverbend Online Store API",
    description="Operational API for the fictional Riverbend Beverage Company analytics demonstration.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "riverbend-online-store-api"}


@app.get("/api/products", response_model=list[ProductResponse])
def list_products(database: Session = Depends(get_db)):
    return database.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.id)).all()


@app.post("/api/events", status_code=201)
def create_event(payload: EventCreate, database: Session = Depends(get_db)):
    standard_fields = {"event_id", "session_id", "event_type", "event_timestamp", "channel"}
    event_data = {key: value for key, value in payload.model_dump().items() if key not in standard_fields}
    database.add(
        StoreEvent(
            event_id=payload.event_id,
            session_id=payload.session_id,
            event_type=payload.event_type,
            event_timestamp=payload.event_timestamp,
            channel=payload.channel,
            event_data=event_data,
        )
    )
    try:
        database.commit()
    except IntegrityError:
        database.rollback()
        return {"status": "already_recorded", "event_id": payload.event_id}
    return {"status": "recorded", "event_id": payload.event_id}


@app.get("/api/events", response_model=list[EventResponse])
def list_events(
    limit: int = Query(default=100, ge=1, le=1000),
    database: Session = Depends(get_db),
):
    events = database.scalars(select(StoreEvent).order_by(desc(StoreEvent.event_timestamp)).limit(limit)).all()
    return [
        EventResponse(
            event_id=event.event_id,
            event_type=event.event_type,
            event_timestamp=event.event_timestamp,
            event_data=event.event_data,
        )
        for event in events
    ]


@app.post("/api/orders", response_model=OrderResponse, status_code=201)
def create_order(payload: OrderCreate, database: Session = Depends(get_db)):
    if database.get(Order, payload.order_id):
        return OrderResponse(order_id=payload.order_id, status="already_recorded", recorded_items=0)

    customer = database.scalar(select(Customer).where(Customer.email == str(payload.customer_email)))
    if customer is None:
        customer = Customer(
            full_name=payload.customer_name,
            email=str(payload.customer_email),
            loyalty_member=payload.loyalty_enrollment,
        )
        database.add(customer)
        database.flush()
    else:
        customer.full_name = payload.customer_name
        customer.loyalty_member = customer.loyalty_member or payload.loyalty_enrollment

    product_ids = {item.product_id for item in payload.order_items}
    known_products = set(database.scalars(select(Product.id).where(Product.id.in_(product_ids))).all())
    unknown_products = product_ids - known_products
    if unknown_products:
        raise HTTPException(status_code=400, detail=f"Unknown products: {sorted(unknown_products)}")

    order = Order(
        id=payload.order_id,
        customer_id=customer.id,
        fulfillment_method=payload.fulfillment_method,
        store=payload.store,
        promotion_code=payload.promotion_code,
        order_total=payload.order_total,
    )
    database.add(order)
    for item in payload.order_items:
        database.add(
            OrderItem(
                order_id=payload.order_id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
        )
    database.commit()
    return OrderResponse(order_id=payload.order_id, status="recorded", recorded_items=len(payload.order_items))
