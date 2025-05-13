# main.py
import logging
from crawlers.wipo import crawl_wipo_by_name  # Đảm bảo đường dẫn import đúng
from database.connection import engine  # Cần thiết nếu Base.metadata.create_all ở đây
from database.models import Base

# Cấu hình logging tập trung cho toàn bộ ứng dụng
# Nên đặt ở điểm bắt đầu của ứng dụng (ví dụ: main.py)
logging.basicConfig(
    level=logging.INFO,  # Mức log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler("wipo_crawl_app.log", mode='a'),  # Ghi log ra file, mode 'a' để append
        logging.StreamHandler()  # Hiển thị log trên console
    ]
)
# Đặt tên cho logger của module này
logger = logging.getLogger(__name__)


def setup_database_schema():
    """
    Creates all tables in the database defined by SQLAlchemy Base metadata.
    Should ideally be called once at application startup or during deployment.
    """
    try:
        logger.info("Setting up database schema (creating tables if they don't exist)...")
        # `checkfirst=True` sẽ kiểm tra sự tồn tại của bảng trước khi tạo
        Base.metadata.create_all(engine, checkfirst=True)
        logger.info("Database schema setup complete.")
    except Exception as e:
        logger.error(f"Error setting up database schema: {e}", exc_info=True)
        # Tùy thuộc vào mức độ nghiêm trọng, bạn có thể muốn thoát ứng dụng ở đây
        # raise # Hoặc xử lý theo cách khác


if __name__ == "__main__":
    # Gọi hàm thiết lập database một lần khi ứng dụng khởi chạy
    # setup_database_schema() # Bỏ comment nếu bạn muốn create_all được gọi từ main
    # Hoặc bạn có thể chạy nó như một script riêng biệt khi deploy.

    # Ví dụ tên thương hiệu để tìm kiếm
    brand_to_search = "RONALDO"  # Bạn có thể thay đổi hoặc lấy từ input/argument

    logger.info(f"Starting WIPO crawl application for brand: '{brand_to_search}'")
    try:
        crawl_wipo_by_name(brand_to_search)
        logger.info(f"WIPO crawl application finished for brand: '{brand_to_search}'")
    except Exception as e:
        # Bắt các lỗi không mong muốn ở cấp độ cao nhất của ứng dụng
        logger.critical(f"An unhandled error occurred in main execution for '{brand_to_search}': {e}", exc_info=True)
    finally:
        logger.info("WIPO crawl application is shutting down.")