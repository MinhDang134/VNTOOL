from sqlalchemy import text

def create_partition_table(month: str, engine):
    table = f"brand_{month}"
    with engine.connect() as conn:
        conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id TEXT PRIMARY KEY,
            name TEXT,
            product_group TEXT,
            status TEXT,
            registration_date DATE,
            image_url TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_status_{month} ON {table}(status);"))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_reg_date_{month} ON {table}(registration_date);"))