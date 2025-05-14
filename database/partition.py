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
            registration_date DATE,
            image_url TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_status_{month} ON {table}(status);")) # tạo index trên cột status để tăng tốc độ tìm kiếm theot trang thái
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_reg_date_{month} ON {table}(registration_date);")) # tạo index cột ngày đăng kí lấy thông tin theo số đăng ký