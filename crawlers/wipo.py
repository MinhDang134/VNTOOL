import time
import random
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


# Thêm vào cuối file /home/minhdangpy134/DuAnWipoVNmark/crawlers/wipo.py

# (Các import selenium, bs4, logging, TimeoutException, WebDriverException đã có hoặc cần thiết)
from bs4 import BeautifulSoup # Đảm bảo import nếu chưa có ở phạm vi global cho hàm này

logger_wipo_fetch = logging.getLogger(__name__ + ".fetch_status") #
# Đảm bảo đường dẫn import là chính xác dựa trên cấu trúc thư mục của bạn
from crawlers.parser import parse_wipo_html
from database.connection import Session, engine  # Giả định Session và engine được cấu hình đúng
from database.models import get_brand_model, Base  # Giả định các hàm này tồn tại
# from database.save import save_to_db # BỎ IMPORT NÀY, sử dụng hàm _save_wipo_items_to_db
from database.partition import create_partition_table  # Giả định hàm này tồn tại
from database.trademark import upsert_trademark_master  # Giả định hàm này tồn tại

# request_log nên được quản lý cẩn thận hơn nếu có nhiều instance crawler
request_log_wipo = []  # Đổi tên để tránh xung đột nếu có request_log khác


def throttle_wipo(min_delay=0.1, max_delay=0.2, max_req_per_min=500, sleep_on_exceed=15):
    """Throttles requests to avoid overwhelming the WIPO server."""
    global request_log_wipo
    now = time.time()
    request_log_wipo = [t for t in request_log_wipo if now - t <= 60]  # Giữ lại các request trong 60s qua

    if len(request_log_wipo) >= max_req_per_min:
        logging.warning(
            f"WIPO Crawler: Request limit ({max_req_per_min}/min) reached. Sleeping for {sleep_on_exceed} seconds.")
        time.sleep(sleep_on_exceed)
        request_log_wipo = [t for t in request_log_wipo if time.time() - t <= 60]  # Cập nhật lại sau khi sleep

    request_log_wipo.append(now)  # Log request hiện tại
    time.sleep(random.uniform(min_delay, max_delay))  # Chờ ngẫu nhiên


def _save_wipo_items_to_db(db_session, BrandModel, items_to_save, source_name="WIPO_Search"):
    """Saves a list of parsed WIPO items to the database."""
    saved_count = 0
    processed_count = 0

    if not items_to_save:
        logging.info(f"DB Save ({source_name}): No items to save.")
        return

    for item_detail in items_to_save:
        processed_count += 1
        # ID đã được tạo và kiểm tra trong parser, nhưng kiểm tra lại cho chắc
        if not item_detail.get("id"):
            logging.error(f"DB Save ({source_name}): Item skipped due to missing ID: {item_detail.get('name', 'N/A')}")
            continue
        try:
            # Đảm bảo các key trong item_detail khớp với các tham số của BrandModel
            brand_instance_data = {
                "id": item_detail["id"],
                "name": item_detail.get("name"),
                "product_group": item_detail.get("product_group"),
                "status": item_detail.get("status"),
                "registration_date": item_detail.get("registration_date"),
                "image_url": item_detail.get("image_url"),
                "source": source_name,
                # Thêm các trường khác của BrandModel nếu có, ví dụ:
                # "owner": item_detail.get("owner"),
                # "original_application_number": item_detail.get("original_number")
            }
            # Loại bỏ các key có giá trị None nếu constructor của BrandModel không chấp nhận
            # brand_instance_data = {k: v for k, v in brand_instance_data.items() if v is not None}

            brand_instance = BrandModel(**brand_instance_data)
            db_session.merge(brand_instance)  # Sử dụng merge để insert hoặc update

            # Gọi upsert_trademark_master nếu cần
            # Kiểm tra lại tham số: db_session.bind (engine) hay db_session (session object)?
            upsert_trademark_master(db_session.bind, item_detail, source_name)
            saved_count += 1
        except Exception as e:
            # Quan trọng: Rollback session để hủy các thay đổi cho item lỗi này
            # và để session có thể sử dụng cho các item tiếp theo.
            # Nếu không rollback, lỗi có thể ảnh hưởng đến toàn bộ batch.
            try:
                db_session.rollback()
                logging.error(
                    f"DB Save ({source_name}): Error processing/merging item (ID: {item_detail.get('id')}, Name: {item_detail.get('name', 'N/A')}). Rolled back for this item. Error: {e}",
                    exc_info=True)
            except Exception as rb_exc:
                logging.error(
                    f"DB Save ({source_name}): CRITICAL - Failed to rollback after item error. Session might be unstable. Rollback error: {rb_exc}",
                    exc_info=True)
                # Có thể cần phải hủy toàn bộ batch nếu rollback thất bại

    if saved_count > 0:
        try:
            db_session.commit()
            logging.info(
                f"DB Save ({source_name}): Successfully committed {saved_count} out of {processed_count} processed items to DB.")
        except Exception as e:
            logging.error(f"DB Save ({source_name}): Error committing batch to DB: {e}", exc_info=True)
            try:
                db_session.rollback()
                logging.info(f"DB Save ({source_name}): Rolled back changes after commit error.")
            except Exception as rb_exc:
                logging.error(
                    f"DB Save ({source_name}): CRITICAL - Failed to rollback after commit error. DB state might be inconsistent. Rollback error: {rb_exc}",
                    exc_info=True)
    elif processed_count > 0:
        logging.info(
            f"DB Save ({source_name}): No new items were successfully processed to commit out of {processed_count} items.")
    # else: (No items were passed to the function, logged earlier)


def crawl_wipo(month: str):  # Tham số month hiện chưa được sử dụng
    logging.info(f"WIPO Crawler: crawl_wipo(month={month}) currently not implemented for real URL.")
    # Hàm này cần được triển khai nếu bạn muốn crawl theo tháng.


def crawl_wipo_by_name(brand_name_to_search: str):
    """Crawls WIPO for a given brand name using Selenium and saves data."""
    logging.info(f"WIPO Crawler: Starting crawl for brand name: '{brand_name_to_search}'")
    db_session = None  # Khởi tạo session ở ngoài try-finally
    driver = None  # Khởi tạo driver ở ngoài try-finally
    html_content_for_parsing = None

    try:
        db_session = Session()  # Tạo session DB

        # Cân nhắc việc gọi create_all ở đâu đó khi khởi tạo ứng dụng, không phải mỗi lần crawl
        # Base.metadata.create_all(engine, checkfirst=True)

        table_name_for_brand = "brand_manual"  # Tên bảng (có thể động nếu cần)
        # create_partition_table nên an toàn để gọi nhiều lần hoặc có kiểm tra sự tồn tại
        create_partition_table(table_name_for_brand, engine)
        ConcreteBrandModel = get_brand_model(table_name_for_brand)

        logging.info(f"WIPO Crawler: Simulating user search for: {brand_name_to_search}")

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        # chrome_options.add_argument('--headless') # Chạy ẩn (CAPTCHA sẽ là vấn đề lớn)
        # Thêm User-Agent để giống trình duyệt thông thường hơn
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(60)  # Thời gian chờ tải trang (giây)

        # URL của WIPO Global Brand Database (kiểm tra lại nếu cần)
        wipo_search_url = "https://branddb.wipo.int/branddb/en/"
        driver.get(wipo_search_url)
        logging.info(f"WIPO Crawler: Navigated to {wipo_search_url}")

        # throttle_wipo() # Throttle sau mỗi request mạng quan trọng

        # Bước yêu cầu người dùng tương tác (Giải CAPTCHA và tìm kiếm)
        user_interaction_prompt = (
            f"[WIPO INTERACTION REQUIRED]\n"
            f"1. Trình duyệt Chrome đã mở tại trang WIPO.\n"
            f"2. Vui lòng GIẢI CAPTCHA (nếu có).\n"
            f"3. Thực hiện TÌM KIẾM thủ công cho tên thương hiệu: '{brand_name_to_search}'.\n"
            f"4. Đợi trang KẾT QUẢ TÌM KIẾM tải hoàn tất.\n"
            f"Sau đó, NHẤN ENTER ở đây để tiếp tục..."
        )
        input(user_interaction_prompt)
        logging.info("WIPO Crawler: User has indicated search is complete. Proceeding to fetch HTML.")
        time.sleep(15)
        # Chờ cho các phần tử kết quả xuất hiện (điều chỉnh selector và thời gian chờ nếu cần)
        # Selector `li.result-viewed` cần được xác minh
        results_css_selector = "li.result-viewed"
        wait_time_for_results = 120  # Giây
        logging.info(
            f"WIPO Crawler: Waiting up to {wait_time_for_results}s for search results (selector: '{results_css_selector}')...")
        WebDriverWait(driver, wait_time_for_results).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, results_css_selector))
        )
        logging.info("WIPO Crawler: Search results page elements located.")

        html_content_for_parsing = driver.page_source
        # Lưu HTML để debug (tùy chọn)
        # debug_html_filename = f"debug_wipo_result_{brand_name_to_search.replace(' ', '_')}.html"
        # with open(debug_html_filename, "w", encoding="utf-8") as f:
        #     f.write(html_content_for_parsing)
        # logging.info(f"WIPO Crawler: HTML content saved to {debug_html_filename}")

    except TimeoutException:
        logging.error(
            f"WIPO Crawler: Timeout waiting for search results for '{brand_name_to_search}'. The page might not have loaded correctly or no results found with the selector.",
            exc_info=True)
    except WebDriverException as e:  # Bắt các lỗi chung của Selenium
        logging.error(
            f"WIPO Crawler: WebDriverException occurred during Selenium interaction for '{brand_name_to_search}': {e}",
            exc_info=True)
    except Exception as e:  # Bắt các lỗi không mong muốn khác
        logging.error(
            f"WIPO Crawler: An unexpected error occurred during Selenium phase for '{brand_name_to_search}': {e}",
            exc_info=True)
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("WIPO Crawler: Chrome driver quit successfully.")
            except Exception as e:
                logging.error(f"WIPO Crawler: Error quitting Chrome driver: {e}", exc_info=True)

    if not html_content_for_parsing:
        logging.warning(
            f"WIPO Crawler: No HTML content was retrieved for '{brand_name_to_search}'. Aborting further processing for this name.")
        if db_session:  # Đảm bảo session được đóng nếu thoát sớm
            try:
                db_session.close()
            except Exception as e_close:
                logging.error(f"WIPO Crawler: Error closing DB session after no HTML content: {e_close}", exc_info=True)
        return  # Kết thúc nếu không có HTML để parse

    # throttle_wipo() # Có thể throttle trước khi parse nếu parse tốn nhiều tài nguyên server (ít khả năng)

    logging.info(f"WIPO Crawler: Parsing HTML for '{brand_name_to_search}'...")
    parsed_brand_items = parse_wipo_html(html_content_for_parsing)

    if not parsed_brand_items:
        logging.info(f"WIPO Crawler: No items parsed from HTML for '{brand_name_to_search}'.")
    else:
        logging.info(
            f"WIPO Crawler: Parsed {len(parsed_brand_items)} items for '{brand_name_to_search}'. Proceeding to save.")
        # Gọi hàm lưu trữ đã được định nghĩa ở trên
        if db_session and ConcreteBrandModel:  # Đảm bảo session và model đã được khởi tạo
            _save_wipo_items_to_db(db_session, ConcreteBrandModel, parsed_brand_items,
                                   source_name=f"WIPO_Search_{brand_name_to_search}")
        else:
            logging.error(
                f"WIPO Crawler: Cannot save items for '{brand_name_to_search}' due to missing DB session or BrandModel.")

    # Đóng session DB sau khi mọi thứ hoàn tất (kể cả khi không có item để lưu)
    if db_session:
        try:
            db_session.close()
            logging.info("WIPO Crawler: Database session closed.")
        except Exception as e:
            logging.error(f"WIPO Crawler: Error closing database session: {e}", exc_info=True)


def fetch_status_from_site(brand_id: str) -> str | None:
    """
    Lấy trạng thái hiện tại của một thương hiệu từ trang WIPO dựa trên brand_id.
    Hàm này cần được triển khai đầy đủ. Hiện tại chỉ là khung sườn.

    Args:
        brand_id: ID của thương hiệu (ví dụ: số đơn quốc tế, số đăng ký WIPO).

    Returns:
        Chuỗi trạng thái nếu tìm thấy, ngược lại là None.
    """
    logger_wipo_fetch.info(f"Attempting to fetch status for WIPO brand ID: {brand_id}")

    if not brand_id:
        logger_wipo_fetch.warning("Brand ID is missing, cannot fetch WIPO status.")
        return None

    # Bước 1: Xây dựng URL đến trang chi tiết hoặc trang tìm kiếm.
    # URL này phụ thuộc vào cách WIPO cấu trúc. Bạn cần nghiên cứu:
    # - Có URL trực tiếp đến trang chi tiết dựa trên brand_id không?
    # - Hay bạn cần vào trang tìm kiếm, nhập brand_id, rồi click vào kết quả?
    # Ví dụ (CẦN THAY THẾ BẰNG URL VÀ LOGIC ĐÚNG):
    # detail_page_url = f"https://branddb.wipo.int/branddb/en/detail/{brand_id}" # URL GIẢ ĐỊNH
    # Hoặc, bạn có thể cần tự động hóa việc tìm kiếm `brand_id` trên trang WIPO.

    driver = None
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--headless')  # Chạy ẩn để không làm phiền
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(45)  # Thời gian chờ tải trang

        # --- LOGIC LẤY TRANG VÀ PARSE HTML ---
        # Đây là phần phức tạp nhất và bạn cần tự tìm hiểu cấu trúc trang WIPO:
        # 1. Điều hướng đến URL phù hợp (trang tìm kiếm hoặc trang chi tiết nếu có).
        #    Ví dụ: driver.get(search_url_wipo)
        #
        # 2. Nếu là trang tìm kiếm:
        #    - Tìm ô input, nhập brand_id: driver.find_element(...).send_keys(brand_id)
        #    - Tìm nút submit, click: driver.find_element(...).click()
        #    - Chờ kết quả tìm kiếm (hoặc trang chi tiết) tải: WebDriverWait(...)
        #    - Nếu có nhiều kết quả, bạn có thể cần click vào đúng kết quả để đến trang chi tiết.
        #
        # 3. Khi đã ở trang chi tiết của thương hiệu:
        #    - Chờ cho phần tử chứa trạng thái xuất hiện:
        #      status_selector = "selector.cho.truong.status" # <<< THAY BẰNG SELECTOR THỰC TẾ
        #      WebDriverWait(driver, 30).until(
        #          EC.presence_of_element_located((By.CSS_SELECTOR, status_selector))
        #      )
        #    - Lấy HTML của trang: html_detail = driver.page_source
        #    - Parse HTML bằng BeautifulSoup: soup = BeautifulSoup(html_detail, "html.parser")
        #    - Trích xuất trạng thái:
        #      status_element = soup.select_one(status_selector)
        #      if status_element:
        #          current_status = status_element.text.strip()
        #          logger_wipo_fetch.info(f"Fetched status for WIPO ID {brand_id}: {current_status}")
        #          return current_status
        #      else:
        #          logger_wipo_fetch.warning(f"Could not find status element for WIPO ID {brand_id} using selector '{status_selector}'.")
        #          # Lưu HTML để debug nếu không tìm thấy
        #          with open(f"debug_wipo_status_notfound_{brand_id}.html", "w", encoding="utf-8") as f:
        #              f.write(html_detail)
        #          return None

        # VÌ LOGIC TRÊN CHƯA ĐƯỢC IMPLEMENT, TRẢ VỀ GIÁ TRỊ PLACEHOLDER HOẶC NONE
        logger_wipo_fetch.warning(
            f"fetch_status_from_site for WIPO ID {brand_id} is NOT YET FULLY IMPLEMENTED. Returning placeholder.")
        # return None # Hoặc một giá trị mặc định để test
        return "Đang xử lý (WIPO Placeholder)"  # Ví dụ placeholder

    except TimeoutException:
        logger_wipo_fetch.error(f"Timeout while trying to fetch status for WIPO ID {brand_id}.", exc_info=True)
        if driver:  # Lưu HTML nếu có lỗi timeout để debug
            try:
                with open(f"debug_wipo_status_timeout_{brand_id}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                logger_wipo_fetch.info(f"HTML on timeout for WIPO ID {brand_id} saved.")
            except:
                pass  # Bỏ qua nếu không lưu được
        return None
    except WebDriverException as e_wd:
        logger_wipo_fetch.error(f"WebDriverException for WIPO ID {brand_id}: {e_wd}", exc_info=True)
        return None
    except Exception as e:
        logger_wipo_fetch.error(f"Unexpected error fetching status for WIPO ID {brand_id}: {e}", exc_info=True)
        return None
    finally:
        if driver:
            driver.quit()