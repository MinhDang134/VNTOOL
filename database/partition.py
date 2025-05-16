from sqlalchemy import text

def create_partition_table(month: str, engine):
    # nó truyền tên bảng vào mà sao lại chuyển thành tháng nhỉ chỗ này bị sai rồi
    table = f"brand_{month}" # table sẽ bằng là brand_month để mà chia partition
    with engine.connect() as conn: # connect với database
        # tạo một bảng nếu chưa tồn tại với thuộc tính sau
        conn.execute(text(f""" 
        CREATE TABLE IF NOT EXISTS {table} (
            id TEXT PRIMARY KEY,
            name TEXT,
            product_group TEXT,
            status TEXT,
            country TEXT,
            source TEXT,
            owner TEXT,
            number TEXT,
            ipr TEXT,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """))
