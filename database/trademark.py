from sqlalchemy import text
from datetime import datetime

def upsert_trademark_master(engine, item, source):
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS trademark (
            id TEXT PRIMARY KEY,
            name TEXT,
            product_group TEXT,
            status TEXT,
            registration_date DATE,
            image_url TEXT,
            source TEXT,
            last_updated TIMESTAMP DEFAULT NOW()
        );
        """))

        conn.execute(text("""
        INSERT INTO trademark (id, name, product_group, status, registration_date, image_url, source, last_updated)
        VALUES (:id, :name, :product_group, :status, :registration_date, :image_url, :source, :last_updated)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            product_group = EXCLUDED.product_group,
            status = EXCLUDED.status,
            registration_date = EXCLUDED.registration_date,
            image_url = EXCLUDED.image_url,
            source = EXCLUDED.source,
            last_updated = EXCLUDED.last_updated;
        """), {
            "id": item["id"],
            "name": item["name"],
            "product_group": item["product_group"],
            "status": item["status"],
            "registration_date": item["registration_date"],
            "image_url": item["image_url"],
            "source": source,
            "last_updated": datetime.utcnow()
        })