from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    style: str
    price: Decimal
    size: str
    color: str
    badge: str
    description: str


class EventCreate(BaseModel):
    event_id: str
    session_id: str | None = None
    event_type: str
    event_timestamp: datetime
    channel: str = "online_store"
    model_config = ConfigDict(extra="allow")


class OrderItemCreate(BaseModel):
    product_id: str
    product_name: str
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class OrderCreate(BaseModel):
    order_id: str
    customer_name: str = Field(min_length=2, max_length=150)
    customer_email: EmailStr
    fulfillment_method: str
    store: str
    loyalty_enrollment: bool = False
    promotion_code: str | None = None
    order_total: Decimal = Field(ge=0)
    order_items: list[OrderItemCreate]


class OrderResponse(BaseModel):
    order_id: str
    status: str
    recorded_items: int


class EventResponse(BaseModel):
    event_id: str
    event_type: str
    event_timestamp: datetime
    event_data: dict[str, Any]
