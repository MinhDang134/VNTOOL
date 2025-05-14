# main.py
import logging
from crawlers.wipo import crawl_wipo_by_name, crawl_wipo_by_date_range # Đảm bảo đường dẫn import đúng
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
    # khi mà chạy cái brand to search = Ronaldo thì nó sẽ truyền cái tên vào craw_wipo_by_name truyền theo tên
    brand_to_search = "RONALDO"  # Bạn có thể thay đổi hoặc lấy từ input/argument
    # khai báo tên  để khi mà mà cho nó chạy
    logger.info(f"Starting WIPO crawl application for brand: '{brand_to_search}'") # thông báo logging ra thôi
    try:# trường hợp đúng nếu đúng thì chạy và đây
        # crawl_wipo_by_name(brand_to_search) # truyền name vào cho nó sử lý
        # logger.info(f"WIPO crawl application finished for brand: '{brand_to_search}'") # hiển thị ra finish thế thui

        # --- Test crawl_wipo_by_date_range ---
        start_date = "2024-03-01"  # Ví dụ: Ngày bắt đầu (YYYY-MM-DD)
        end_date = "2024-03-05"    # Ví dụ: Ngày kết thúc (YYYY-MM-DD)
        logger.info(f"Attempting to crawl WIPO data from {start_date} to {end_date}...")
        # Đặt force_refresh=True để bỏ qua cache cho lần kiểm thử đầu tiên nếu cần
        results = crawl_wipo_by_date_range(start_date, end_date, force_refresh=True)

        if results is not None:
            logger.info(f"Successfully crawled {len(results)} items for the date range {start_date} - {end_date}.")
            # Ví dụ: In ra một vài thông tin cơ bản của các mục đã lấy được
            # for i, item in enumerate(results[:3]): # In 3 mục đầu tiên
            #     logger.info(f"Item {i+1}: ID={item.get('id')}, Name='{item.get('name')}', Owner='{item.get('owner')}'")
        else:
            logger.warning(f"Crawling failed or no results found for the date range {start_date} - {end_date}.")
        # --- Kết thúc Test crawl_wipo_by_date_range ---

    except Exception as e:
        # Bắt các lỗi không mong muốn ở cấp độ cao nhất của ứng dụng
        logger.critical(f"An unhandled error occurred in main execution for '{brand_to_search}': {e}", exc_info=True)
    finally:# cuối cùng thế nào thì nó cũng hiển thị cái này
        logger.info("WIPO crawl application is shutting down.")