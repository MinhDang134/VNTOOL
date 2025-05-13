from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Date, DateTime  # Thêm Integer nếu id là số
from datetime import datetime

Base = declarative_base()


def get_brand_model(table_name: str):  # Thêm type hint cho rõ ràng
    # Sử dụng một cơ chế cache đơn giản để tránh định nghĩa lại class nếu không cần
    # Điều này hữu ích nếu hàm được gọi nhiều lần với cùng table_name
    class_name = f"Brand_{table_name.capitalize()}"  # Tạo tên class động

    # Kiểm tra xem class đã tồn tại trong module chưa
    # Cách này hơi phức tạp, dùng dict cache đơn giản hơn
    # if class_name in globals():
    # return globals()[class_name]

    # Tạo class động
    BrandClass = type(class_name, (Base,), {
        '__tablename__': table_name,
        # Thêm __table_args__ nếu bạn cần ghi đè bảng hiện có khi test hoặc thay đổi cấu trúc
        # '__table_args__': {'extend_existing': True},

        'id': Column(String, primary_key=True, index=True),  # Thêm index=True cho primary key
        'name': Column(String, index=True, nullable=True),  # Thêm index và nullable nếu phù hợp
        'product_group': Column(String, nullable=True),
        'status': Column(String, nullable=True),
        'registration_date': Column(Date, nullable=True),  # Date là đúng nếu chỉ lưu ngày
        'image_url': Column(String, nullable=True),
        'source': Column(String, nullable=True),
        'created_at': Column(DateTime, default=datetime.utcnow, nullable=False),
        # Thêm các cột khác nếu cần, ví dụ:
        'owner': Column(String, nullable=True),
        'original_number': Column(String, nullable=True)
    })
    return BrandClass