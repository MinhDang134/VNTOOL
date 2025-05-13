import time
import random
import logging
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, List, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from bs4 import BeautifulSoup


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

CACHE_DIR = "cache/wipo"
CACHE_EXPIRY_DAYS = 7

def ensure_cache_dir():
    """Ensure cache directory exists."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def get_cache_path(brand_name: str) -> str:
    """Get cache file path for a brand name."""
    safe_name = "".join(c for c in brand_name if c.isalnum() or c in (' ', '-', '_')).strip()
    return os.path.join(CACHE_DIR, f"{safe_name}.json")

def is_cache_valid(cache_path: str) -> bool:
    """Check if cache file exists and is not expired."""
    if not os.path.exists(cache_path):
        return False
    
    file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
    return datetime.now() - file_time < timedelta(days=CACHE_EXPIRY_DAYS)

def save_to_cache(brand_name: str, data: List[Dict[str, Any]]):
    """Save data to cache file."""
    ensure_cache_dir()
    cache_path = get_cache_path(brand_name)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'data': data
        }, f, ensure_ascii=False, indent=2)

def load_from_cache(brand_name: str) -> Optional[List[Dict[str, Any]]]:
    """Load data from cache file if valid."""
    cache_path = get_cache_path(brand_name)
    if not is_cache_valid(cache_path):
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            return cache_data.get('data')
    except Exception as e:
        logging.error(f"Error loading cache for {brand_name}: {e}")
        return None

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
    skipped_count = 0
    error_count = 0

    if not items_to_save:
        logging.info(f"DB Save ({source_name}): No items to save.")
        return

    for item_detail in items_to_save:
        processed_count += 1
        item_id = item_detail.get("id")
        
        # Kiểm tra ID
        if not item_id:
            logging.error(f"DB Save ({source_name}): Item skipped due to missing ID: {item_detail.get('name', 'N/A')}")
            skipped_count += 1
            continue

        try:
            # Kiểm tra xem record đã tồn tại chưa
            existing_item = db_session.get(BrandModel, item_id)
            
            if existing_item:
                logging.info(f"DB Save ({source_name}): Updating existing record for ID: {item_id}")
                # Cập nhật các trường từ dữ liệu mới
                for key, value in item_detail.items():
                    if hasattr(existing_item, key) and value is not None:
                        setattr(existing_item, key, value)
                # Cập nhật source và last_updated
                existing_item.source = source_name
                existing_item.last_updated = datetime.utcnow()
            else:
                logging.info(f"DB Save ({source_name}): Adding new record for ID: {item_id}")
                # Tạo instance mới với dữ liệu từ parser
                brand_instance_data = {
                    "id": item_id,
                    "name": item_detail.get("name"),
                    "product_group": item_detail.get("product_group"),
                    "status": item_detail.get("status"),
                    "registration_date": item_detail.get("registration_date"),
                    "image_url": item_detail.get("image_url"),
                    "source": source_name,
                    "owner": item_detail.get("owner"),
                    "original_number": item_detail.get("original_number")
                }
                brand_instance = BrandModel(**brand_instance_data)
                db_session.add(brand_instance)

            # Commit sau mỗi item để tránh lỗi ảnh hưởng đến toàn bộ batch
            db_session.commit()
            saved_count += 1
            logging.info(f"DB Save ({source_name}): Successfully saved item {item_id}")

        except Exception as e:
            db_session.rollback()
            error_count += 1
            logging.error(f"DB Save ({source_name}): Error processing/merging item (ID: {item_id}, Name: {item_detail.get('name')}). Rolled back for this item. Error: {str(e)}")
            continue

    # Log tổng kết
    logging.info(f"DB Save ({source_name}): Processing complete. "
                f"Processed: {processed_count}, "
                f"Saved: {saved_count}, "
                f"Skipped: {skipped_count}, "
                f"Errors: {error_count}")

    return saved_count


def crawl_wipo(month: str):
    """Crawls WIPO for trademarks registered in a specific month."""
    logging.info(f"WIPO Crawler: Starting crawl for month: {month}")
    
    try:
        # Validate month format (YYYY-MM)
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        logging.error(f"Invalid month format: {month}. Expected format: YYYY-MM")
        return None

    db_session = None
    driver = None
    html_content_for_parsing = None

    try:
        db_session = Session()
        table_name_for_brand = "trademark"
        create_partition_table(table_name_for_brand, engine)
        ConcreteBrandModel = get_brand_model(table_name_for_brand)

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(60)

        # Navigate to WIPO advanced search
        wipo_search_url = "https://branddb.wipo.int/branddb/en/search/advanced"
        driver.get(wipo_search_url)
        logging.info(f"WIPO Crawler: Navigated to {wipo_search_url}")

        user_interaction_prompt = (
            f"[WIPO INTERACTION REQUIRED]\n"
            f"1. Trình duyệt Chrome đã mở tại trang WIPO Advanced Search.\n"
            f"2. Vui lòng GIẢI CAPTCHA (nếu có).\n"
            f"3. Trong phần 'Registration Date', chọn tháng: {month}\n"
            f"4. Nhấn nút 'Search' và đợi kết quả.\n"
            f"Sau đó, NHẤN ENTER ở đây để tiếp tục..."
        )
        input(user_interaction_prompt)

        # Check for no results
        if check_no_results(driver):
            logging.info(f"WIPO Crawler: No results found for month {month}")
            return None

        # Get dynamic timeout
        timeout = get_dynamic_timeout(driver)
        logging.info(f"WIPO Crawler: Using dynamic timeout of {timeout} seconds")

        results_css_selector = "li.result-viewed"
        WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, results_css_selector))
        )
        logging.info("WIPO Crawler: Search results page elements located.")

        html_content_for_parsing = driver.page_source

    except TimeoutException:
        logging.error(f"WIPO Crawler: Timeout waiting for search results for month {month}", exc_info=True)
        raise
    except WebDriverException as e:
        logging.error(f"WIPO Crawler: WebDriverException occurred: {e}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"WIPO Crawler: Unexpected error: {e}", exc_info=True)
        raise
    finally:
        if driver:
            driver.quit()
        if db_session:
            db_session.close()

    if not html_content_for_parsing:
        logging.warning(f"WIPO Crawler: No HTML content retrieved for month {month}")
        return None

    logging.info(f"WIPO Crawler: Parsing HTML for month {month}...")
    parsed_brand_items = parse_wipo_html(html_content_for_parsing)

    if not parsed_brand_items:
        logging.info(f"WIPO Crawler: No items parsed from HTML for month {month}")
        return None

    # Validate items before saving
    valid_items = [item for item in parsed_brand_items if validate_brand_data(item)]
    if len(valid_items) != len(parsed_brand_items):
        logging.warning(f"WIPO Crawler: Filtered out {len(parsed_brand_items) - len(valid_items)} invalid items")

    # Save to cache
    cache_key = f"month_{month}"
    save_to_cache(cache_key, valid_items)

    if db_session and ConcreteBrandModel and valid_items:
        _save_wipo_items_to_db(db_session, ConcreteBrandModel, valid_items,
                               source_name=f"WIPO_Month_{month}")
    else:
        logging.error(f"WIPO Crawler: Cannot save items for month {month}")

    return valid_items


def retry_on_failure(max_retries=3, delay=1, backoff=2):
    """Decorator for retrying functions on failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        logging.error(f"Function {func.__name__} failed after {max_retries} retries: {str(e)}")
                        raise
                    wait_time = delay * (backoff ** (retries - 1))
                    logging.warning(f"Function {func.__name__} failed, retrying in {wait_time} seconds... Error: {str(e)}")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator

def validate_brand_data(brand_data: Dict[str, Any]) -> bool:
    """Validate brand data before saving to database."""
    required_fields = ['id', 'name']
    return all(field in brand_data and brand_data[field] for field in required_fields)

def check_no_results(driver) -> bool:
    """Check if the search returned no results."""
    try:
        # Sử dụng các selector hợp lệ cho Selenium
        selectors = [
            ".no-results-message",
            ".search-results-empty",
            ".no-results",
            ".alert-info",
            ".search-results"
        ]
        
        # Kiểm tra từng selector
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        # Kiểm tra text content bằng JavaScript
                        text = driver.execute_script("return arguments[0].textContent", element)
                        if "no results" in text.lower() or "không tìm thấy" in text.lower():
                            logging.info(f"Found no results message: {text}")
                            return True
            except NoSuchElementException:
                continue
            except Exception as e:
                logging.warning(f"Error checking selector {selector}: {e}")
                continue
                
        # Kiểm tra thêm bằng JavaScript
        try:
            no_results = driver.execute_script("""
                return Array.from(document.querySelectorAll('*')).some(el => {
                    const text = el.textContent.toLowerCase();
                    return text.includes('no results') || 
                           text.includes('không tìm thấy') ||
                           text.includes('no trademarks found');
                });
            """)
            if no_results:
                logging.info("Found no results message using JavaScript")
                return True
        except Exception as e:
            logging.warning(f"Error checking no results with JavaScript: {e}")
            
        return False
    except Exception as e:
        logging.warning(f"Error checking no results: {e}")
        return False

def get_dynamic_timeout(driver) -> int:
    """Calculate dynamic timeout based on page load time."""
    try:
        load_time = driver.execute_script("return performance.timing.loadEventEnd - performance.timing.navigationStart")
        return min(max(int(load_time / 1000) * 3, 60), 180)  # Tăng thời gian chờ lên 60-180 giây
    except:
        return 120  # Tăng timeout mặc định lên 120 giây

@retry_on_failure(max_retries=3)
def crawl_wipo_by_name(brand_name_to_search: str, force_refresh: bool = False):
    """Crawls WIPO for a given brand name using Selenium and saves data."""
    logging.info(f"WIPO Crawler: Starting crawl for brand name: '{brand_name_to_search}'")
    
    # Check cache first
    if not force_refresh:
        cached_data = load_from_cache(brand_name_to_search)
        if cached_data:
            logging.info(f"WIPO Crawler: Using cached data for '{brand_name_to_search}'")
            return cached_data

    db_session = None
    driver = None
    html_content_for_parsing = None

    try:
        db_session = Session()
        table_name_for_brand = "trademark"
        create_partition_table(table_name_for_brand, engine)
        ConcreteBrandModel = get_brand_model(table_name_for_brand)

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(120)  # Tăng timeout lên 120 giây

        wipo_search_url = "https://branddb.wipo.int/branddb/en/"
        driver.get(wipo_search_url)
        logging.info(f"WIPO Crawler: Navigated to {wipo_search_url}")

        user_interaction_prompt = (
            f"[WIPO INTERACTION REQUIRED]\n"
            f"1. Trình duyệt Chrome đã mở tại trang WIPO.\n"
            f"2. Vui lòng GIẢI CAPTCHA (nếu có).\n"
            f"3. Thực hiện TÌM KIẾM thủ công cho tên thương hiệu: '{brand_name_to_search}'.\n"
            f"4. Đợi trang KẾT QUẢ TÌM KIẾM tải hoàn tất.\n"
            f"Sau đó, NHẤN ENTER ở đây để tiếp tục..."
        )
        input(user_interaction_prompt)
        
        # Đợi trang load xong
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except TimeoutException:
            logging.warning("Page load timeout, but continuing anyway...")

        # Kiểm tra URL để xác nhận đã chuyển sang trang kết quả
        current_url = driver.current_url
        if not any(keyword in current_url.lower() for keyword in ['results', 'search', 'similarname']):
            logging.warning(f"WIPO Crawler: Not on search results page. Current URL: {current_url}")
            return None

        # Check for no results
        if check_no_results(driver):
            logging.info(f"WIPO Crawler: No results found for '{brand_name_to_search}'")
            return None

        # Get dynamic timeout
        timeout = get_dynamic_timeout(driver)
        logging.info(f"WIPO Crawler: Using dynamic timeout of {timeout} seconds")

        # Thêm nhiều selector khác nhau để tìm kết quả
        results_selectors = [
            "li.result-viewed",
            ".search-results li",
            ".result-item",
            ".brand-result",
            "div[class*='result']",
            ".search-results-container",
            "#search-results",
            ".results-list",
            ".brand-list",
            "table.search-results",
            "div[class*='brand']",
            "div[class*='trademark']",
            ".similar-name-results",  # Thêm selector cho trang similarname
            ".similar-name-result",
            "div[class*='similar']"
        ]

        results_found = False
        for selector in results_selectors:
            try:
                # Đợi element xuất hiện với timeout ngắn hơn
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                
                # Kiểm tra xem có phải là kết quả tìm kiếm thật không
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # Kiểm tra nội dung của element đầu tiên
                    first_element = elements[0]
                    if first_element.is_displayed():
                        # Lấy text content bằng JavaScript
                        text = driver.execute_script("return arguments[0].textContent", first_element)
                        if text and len(text.strip()) > 0:
                            results_found = True
                            logging.info(f"WIPO Crawler: Found results using selector: {selector}")
                            logging.info(f"First result text: {text[:100]}...")  # Log 100 ký tự đầu
                            break
            except TimeoutException:
                continue
            except Exception as e:
                logging.warning(f"Error checking selector {selector}: {e}")
                continue

        if not results_found:
            # Thử kiểm tra bằng JavaScript
            try:
                has_results = driver.execute_script("""
                    return Array.from(document.querySelectorAll('*')).some(el => {
                        const text = el.textContent.toLowerCase();
                        return text.includes('search results') || 
                               text.includes('kết quả tìm kiếm') ||
                               text.includes('trademark') ||
                               text.includes('thương hiệu') ||
                               text.includes('brand') ||
                               text.includes('result') ||
                               text.includes('similar') ||
                               text.includes('tương tự');
                    });
                """)
                if has_results:
                    results_found = True
                    logging.info("WIPO Crawler: Found results using JavaScript text search")
            except Exception as e:
                logging.warning(f"Error checking results with JavaScript: {e}")

        if not results_found:
            logging.error(f"WIPO Crawler: No results found with any selector for '{brand_name_to_search}'")
            return None

        # Thêm delay nhỏ để đảm bảo trang đã load hoàn toàn
        time.sleep(5)
        html_content_for_parsing = driver.page_source

    except TimeoutException:
        logging.error(f"WIPO Crawler: Timeout waiting for search results for '{brand_name_to_search}'", exc_info=True)
        raise
    except WebDriverException as e:
        logging.error(f"WIPO Crawler: WebDriverException occurred: {e}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"WIPO Crawler: Unexpected error: {e}", exc_info=True)
        raise
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("WIPO Crawler: Chrome driver quit successfully.")
            except Exception as e:
                logging.error(f"WIPO Crawler: Error quitting Chrome driver: {e}", exc_info=True)

    if not html_content_for_parsing:
        logging.warning(f"WIPO Crawler: No HTML content retrieved for '{brand_name_to_search}'")
        if db_session:
            db_session.close()
        return None

    logging.info(f"WIPO Crawler: Parsing HTML for '{brand_name_to_search}'...")
    parsed_brand_items = parse_wipo_html(html_content_for_parsing)

    if not parsed_brand_items:
        logging.info(f"WIPO Crawler: No items parsed from HTML for '{brand_name_to_search}'")
        return None

    # Validate items before saving
    valid_items = [item for item in parsed_brand_items if validate_brand_data(item)]
    if len(valid_items) != len(parsed_brand_items):
        logging.warning(f"WIPO Crawler: Filtered out {len(parsed_brand_items) - len(valid_items)} invalid items")

    # Save to cache
    save_to_cache(brand_name_to_search, valid_items)

    if db_session and ConcreteBrandModel and valid_items:
        _save_wipo_items_to_db(db_session, ConcreteBrandModel, valid_items,
                               source_name=f"WIPO_Search_{brand_name_to_search}")
        logging.info(f"WIPO Crawler: Successfully saved {len(valid_items)} items to database")
    else:
        logging.error(f"WIPO Crawler: Cannot save items for '{brand_name_to_search}'")

    if db_session:
        db_session.close()
        logging.info("WIPO Crawler: Database session closed.")

    return valid_items


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