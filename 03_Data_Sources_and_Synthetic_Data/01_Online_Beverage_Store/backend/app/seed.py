from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Product


PRODUCTS = [
    {"id": "RB-101", "name": "Hudson Valley Lager", "category": "Beer", "style": "Crisp lager", "price": 13.99, "size": "6 pack", "color": "#315b3b", "badge": "Local", "description": "Clean, bright, and brewed for relaxed afternoons."},
    {"id": "RB-102", "name": "North Country IPA", "category": "Beer", "style": "Hazy IPA", "price": 15.99, "size": "4 pack", "color": "#b95035", "badge": "Popular", "description": "Juicy citrus notes with a smooth, balanced finish."},
    {"id": "RB-201", "name": "Finger Lakes Riesling", "category": "Wine", "style": "Semi-dry white", "price": 18.50, "size": "750 ml", "color": "#d2a743", "badge": "Staff pick", "description": "Fresh stone fruit, bright acidity, and a clean finish."},
    {"id": "RB-202", "name": "Catskill Cabernet", "category": "Wine", "style": "Dry red", "price": 24.00, "size": "750 ml", "color": "#71343b", "badge": "New", "description": "Dark fruit, gentle oak, and a long dinner-friendly finish."},
    {"id": "RB-301", "name": "Albany Small Batch Gin", "category": "Spirits", "style": "Botanical gin", "price": 31.99, "size": "750 ml", "color": "#446d6c", "badge": "Small batch", "description": "Juniper, citrus peel, and a subtle herbal character."},
    {"id": "RB-401", "name": "Orchard Sparkler", "category": "Nonalcoholic", "style": "Sparkling apple", "price": 8.99, "size": "4 pack", "color": "#c4772f", "badge": "0.0%", "description": "A lively alcohol-free option with crisp orchard flavor."},
]


def seed_products(database: Session) -> None:
    existing = database.scalar(select(Product.id).limit(1))
    if existing:
        return
    database.add_all(Product(**product) for product in PRODUCTS)
    database.commit()
