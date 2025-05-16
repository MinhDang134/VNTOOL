from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Date, DateTime, func
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
    # truyền class vào đây ví dụ là nó sẽ lấy tông tin của bảng gì ấy quên rồi
    # đây là cách tạo class động mới với những class có thể dùng chung thuộc tính nhưng khác tên bảng
    BrandClass = type(class_name, (Base,), {
        '__tablename__': table_name,
        '__table_args__': {'extend_existing': True}, # cho phep overwirte nếu class này từng được định nghĩa rồi
        'id': Column(String(255), primary_key=True, index=True),  # Explicit length for String
        'name': Column(String(255), index=True, nullable=True),
        'product_group': Column(String(255), nullable=True),
        'status': Column(String(255), nullable=True),
        'country': Column(String(255), nullable=True),  # Changed to lowercase to match DB schema
        'source': Column(String(255), nullable=True),
        'owner': Column(String(255), nullable=True),
        'number': Column(String(255), nullable=True),  # Changed to lowercase to match DB schema
        'ipr': Column(String(255), nullable=True),
        'created_at': Column(DateTime, server_default=func.now(), nullable=False),
        'last_updated': Column(DateTime, server_default=func.now(), nullable=False),
        'image_url': Column(String(1024), nullable=True)
    })
    return BrandClass