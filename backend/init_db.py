"""Create tables and insert sample orders. Read DATABASE_URL from .env."""

from __future__ import annotations

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine, get_database_url
from app.models import Order, User


def ensure_database() -> None:
    url = make_url(get_database_url())
    database = url.database
    if not database:
        raise RuntimeError("DATABASE_URL must include a database name, e.g. .../ai_cs")

    admin_url = url.set(database=None)
    admin_engine = create_engine(admin_url, future=True)
    with admin_engine.connect() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
        conn.commit()
    admin_engine.dispose()


def seed_orders(db: Session) -> None:
    user = db.scalar(select(User).where(User.username == "demo"))
    if user is None:
        user = User(
            username="demo",
            password_hash="demo-hash-not-for-login",
            style_preference="concise",
        )
        db.add(user)
        db.flush()

    samples = [
        Order(
            order_id="O20261001001",
            user_id=user.id,
            status="shipped",
            logistics_company="顺丰速运",
            tracking_no="SF1000000001",
            items=[{"sku": "SKU-A1", "name": "无线耳机", "qty": 1, "price": 299.00}],
        ),
        Order(
            order_id="O20261001002",
            user_id=user.id,
            status="pending",
            logistics_company=None,
            tracking_no=None,
            items=[{"sku": "SKU-B2", "name": "机械键盘", "qty": 1, "price": 459.00}],
        ),
        Order(
            order_id="O20261001003",
            user_id=user.id,
            status="delivered",
            logistics_company="中通快递",
            tracking_no="ZTO1000000003",
            items=[
                {"sku": "SKU-C3", "name": "显示器支架", "qty": 1, "price": 189.00},
                {"sku": "SKU-C4", "name": "HDMI 线", "qty": 2, "price": 29.90},
            ],
        ),
    ]

    for order in samples:
        exists = db.get(Order, order.order_id)
        if exists is None:
            db.add(order)

    db.commit()


def main() -> None:
    ensure_database()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_orders(db)
    print("Database initialized. Sample orders: O20261001001, O20261001002, O20261001003")


if __name__ == "__main__":
    main()
